"""
Tests for forexfactory._refresh.run_refresh.

All tests use injected FakeSession / FakeResponse — no live HTTP requests.
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from forexfactory import _cache, _scrape
from forexfactory._refresh import run_refresh


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RefreshTests(unittest.TestCase):

    def _make_html(self, days):
        """Build minimal HTML with calendarComponentStates for FakeSession."""
        return (
            '<script>window.calendarComponentStates = '
            f'{{"month": {{"days": {json.dumps(days)}}}}};</script>'
        )

    def test_empty_scrape_writes_no_raw_file_and_no_manifest_entry(self):
        """QUAL-03: when scrape_month returns [], no raw file and no manifest entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            with patch.object(_scrape, "scrape_month", return_value=[]):
                result = run_refresh(
                    start="2026-05", end="2026-05",
                    cache_dir=cache_dir,
                    session=object(),
                    between_pages_delay=0.0,
                    retry_delay=0.0,
                )

            raw_file = _cache.raw_json_path(cache_dir, date(2026, 5, 1))
            self.assertFalse(raw_file.exists(),
                             "no raw file must be written for an empty scrape")

            manifest = _cache.read_manifest(cache_dir)
            self.assertNotIn("2026-05", manifest.get("months", {}),
                             "manifest must not record an entry for a failed scrape")

            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["skipped"], 0)

    def test_existing_nonempty_raw_month_is_skipped_without_network_call(self):
        """D-11: month with an existing non-empty raw JSON is not re-scraped."""
        days = [{"events": [{"currency": "USD", "impactName": "high",
                              "name": "CPI y/y", "dateline": 1772368200, "id": "cpi-1"}]}]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            _cache.ensure_dirs(cache_dir)

            # Pre-write non-empty raw file for 2026-05.
            raw_path = _cache.raw_json_path(cache_dir, date(2026, 5, 1))
            raw_path.write_text(json.dumps(days), encoding="utf-8")

            fake_session = FakeSession([])  # no responses — must not be called

            result = run_refresh(
                start="2026-05", end="2026-05",
                cache_dir=cache_dir,
                session=fake_session,
                between_pages_delay=0.0,
                retry_delay=0.0,
            )

            self.assertEqual(len(fake_session.calls), 0,
                             "session.get must not be called for an already-cached month")
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["failed"], 0)

    def test_fresh_month_scraped_staged_parquet_built_and_manifest_recorded(self):
        """Fresh month: scraped, raw JSON staged, parquet built, manifest updated."""
        days = [{"events": [{"currency": "USD", "impactName": "high",
                              "name": "CPI y/y", "dateline": 1772368200, "id": "cpi-1"}]}]
        html = self._make_html(days)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            fake_session = FakeSession([FakeResponse(html)])

            result = run_refresh(
                start="2026-05", end="2026-05",
                cache_dir=cache_dir,
                session=fake_session,
                currencies=["USD"],
                impacts=["high", "holiday"],
                between_pages_delay=0.0,
                retry_delay=0.0,
            )

            # Raw JSON staged under cache_dir/raw/
            raw_path = _cache.raw_json_path(cache_dir, date(2026, 5, 1))
            self.assertTrue(raw_path.exists(), "raw JSON must be written for a successful scrape")

            # Per-month parquet built under cache_dir/
            parquet_path = _cache.month_parquet_path(cache_dir, date(2026, 5, 1))
            self.assertTrue(parquet_path.exists(), "per-month parquet must be built")

            # Manifest records the month entry (D-02)
            manifest = _cache.read_manifest(cache_dir)
            self.assertIn("2026-05", manifest.get("months", {}),
                          "manifest must record the fetched month")

            self.assertEqual(result["fetched"], 1)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(result["failed"], 0)


class RefreshForceRefreshTests(unittest.TestCase):
    """CACHE-06 / D-02: force_refresh kwarg bypasses the skip-if-cached check."""

    def _make_html(self, days):
        return (
            '<script>window.calendarComponentStates = '
            f'{{"month": {{"days": {json.dumps(days)}}}}};</script>'
        )

    def test_force_refresh_true_rescrapes_cached_month(self):
        """force_refresh=True re-scrapes a month that already has non-empty raw JSON."""
        days = [{"events": [{"currency": "USD", "impactName": "high",
                              "name": "CPI y/y", "dateline": 1772368200, "id": "cpi-1"}]}]
        html = self._make_html(days)

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            _cache.ensure_dirs(cache_dir)

            # Pre-write non-empty raw file for 2026-05.
            raw_path = _cache.raw_json_path(cache_dir, date(2026, 5, 1))
            raw_path.write_text(json.dumps(days), encoding="utf-8")

            fake_session = FakeSession([FakeResponse(html)])

            result = run_refresh(
                start="2026-05", end="2026-05",
                cache_dir=cache_dir,
                session=fake_session,
                currencies=["USD"],
                impacts=["high", "holiday"],
                between_pages_delay=0.0,
                retry_delay=0.0,
                force_refresh=True,
            )

            self.assertEqual(
                len(fake_session.calls), 1,
                "session.get must be called once when force_refresh=True",
            )
            self.assertEqual(result["fetched"], 1)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(result["failed"], 0)

    def test_force_refresh_false_preserves_skip_behavior(self):
        """force_refresh=False (explicit) skips a month with non-empty raw JSON — regression guard."""
        days = [{"events": [{"currency": "USD", "impactName": "high",
                              "name": "CPI y/y", "dateline": 1772368200, "id": "cpi-1"}]}]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            _cache.ensure_dirs(cache_dir)

            raw_path = _cache.raw_json_path(cache_dir, date(2026, 5, 1))
            raw_path.write_text(json.dumps(days), encoding="utf-8")

            fake_session = FakeSession([])  # no responses — must not be called

            result = run_refresh(
                start="2026-05", end="2026-05",
                cache_dir=cache_dir,
                session=fake_session,
                between_pages_delay=0.0,
                retry_delay=0.0,
                force_refresh=False,
            )

            self.assertEqual(
                len(fake_session.calls), 0,
                "session.get must not be called when force_refresh=False",
            )
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(result["fetched"], 0)
            self.assertEqual(result["failed"], 0)


class RefreshCliRoutingTests(unittest.TestCase):

    def test_cli_refresh_dispatches_to_run_refresh_with_append_currencies(self):
        """refresh subcommand routes to _refresh.run_refresh with D-12 append args."""
        from forexfactory import _refresh
        from forexfactory.cli import main as cli_main

        captured = {}

        def fake_run_refresh(
            *,
            currencies=None,
            impacts=None,
            start=None,
            end=None,
            cache_dir=None,
            session=None,
            between_pages_delay=None,
            retry_delay=None,
            force_refresh=False,
        ):
            captured["currencies"] = currencies
            captured["impacts"] = impacts
            captured["start"] = start
            captured["end"] = end
            captured["between_pages_delay"] = between_pages_delay
            captured["retry_delay"] = retry_delay
            return {"fetched": 0, "skipped": 0, "failed": 0}

        with patch.object(_refresh, "run_refresh", side_effect=fake_run_refresh):
            exit_code = cli_main([
                "refresh",
                "--currency", "USD",
                "--currency", "EUR",
                "--impact", "high",
                "--start", "2026-04",
                "--end", "2026-05",
                "--between-pages-delay", "2.0",
                "--retry-delay", "1.5",
            ])

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["currencies"], ["USD", "EUR"],
                         "--currency should collect into a list (D-12 append action)")
        self.assertEqual(captured["impacts"], ["high"])
        self.assertEqual(captured["start"], "2026-04")
        self.assertEqual(captured["end"], "2026-05")
        self.assertEqual(captured["between_pages_delay"], 2.0)
        self.assertEqual(captured["retry_delay"], 1.5)


if __name__ == "__main__":
    unittest.main()
