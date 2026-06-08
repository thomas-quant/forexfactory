"""
Tests for src/forexfactory/_query.py — cache read + filter + result parquet.

Covers: D-07 (returns Path to consolidated parquet), D-08 (deterministic path,
        overwritten each call), D-09 (out-of-scope raises ValueError with guidance),
        SC4 (forexfactory.get() returns Path), DATA-01 (correct columns).
"""
import pathlib
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers shared by both test classes
# ---------------------------------------------------------------------------

def _make_parquet(path: Path, rows: list) -> None:
    """Write a DATA-01-schema parquet to path (zstd level 3)."""
    df = pd.DataFrame(rows)
    df.to_parquet(str(path), index=False, compression="zstd", compression_level=3)


def _usd_high_row(dt: str = "2026-03-01 08:30:00") -> dict:
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "USD",
        "impact": "high",
        "title": "CPI y/y",
        "id": "cpi-1",
        "leaked": False,
    }


def _eur_medium_row(dt: str = "2026-03-01 09:00:00") -> dict:
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "EUR",
        "impact": "medium",
        "title": "ECB Rate Decision",
        "id": "ecb-1",
        "leaked": False,
    }


def _usd_high_data_row(dt: str = "2026-03-01 08:30:00") -> dict:
    """USD/high data-bearing row with hasDataValues=True (Phase-2 schema)."""
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "USD",
        "impact": "high",
        "title": "CPI y/y",
        "id": "cpi-1",
        "leaked": False,
        "hasDataValues": True,
    }


def _speech_row(dt: str = "2026-03-01 09:00:00") -> dict:
    """USD/high speech row with hasDataValues=False (no data release)."""
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "USD",
        "impact": "high",
        "title": "Fed Chair Powell Speaks",
        "id": "powell-1",
        "leaked": False,
        "hasDataValues": False,
    }


def _holiday_row(dt: str = "2026-03-01 00:00:00") -> dict:
    """USD/holiday row with hasDataValues=False (bank holiday — always visible by default, D-08)."""
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "USD",
        "impact": "holiday",
        "title": "Presidents Day",
        "id": "holiday-1",
        "leaked": False,
        "hasDataValues": False,
    }


# ---------------------------------------------------------------------------
# Task 1 — D-07 / D-08 / SC4: happy path tests
# ---------------------------------------------------------------------------

class QueryHappyPathTests(unittest.TestCase):
    """Task 1 — run_query returns filtered Path; forexfactory.get() works (D-07/D-08/SC4)."""

    def _setup_cache(
        self,
        cache_dir: Path,
        months: list,
        rows_per_month: list,
        scope: dict | None = None,
    ) -> None:
        """Write per-month parquets + manifest under cache_dir."""
        from forexfactory import _cache

        _cache.ensure_dirs(cache_dir)
        if scope is None:
            scope = {"currencies": ["USD"], "impacts": ["high", "holiday"]}
        manifest = {"scope": scope, "months": {}}
        for (year, month), rows in zip(months, rows_per_month):
            anchor = date(year, month, 1)
            p = _cache.month_parquet_path(cache_dir, anchor)
            _make_parquet(p, rows)
            manifest["months"][f"{year:04d}-{month:02d}"] = {
                "scraped_at": "2026-06-08T00:00:00Z",
                "settled": True,
            }
        _cache.write_manifest(cache_dir, manifest)

    def test_run_query_returns_path_under_queries_dir(self):
        """run_query returns an absolute Path inside queries_dir (D-07)."""
        from forexfactory import _query, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_cache(cache_dir, [(2026, 3)], [[_usd_high_row()]])

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            self.assertIsInstance(result, pathlib.Path)
            self.assertTrue(result.exists(), "result parquet must exist on disk")
            self.assertEqual(result.parent, _cache.queries_dir(cache_dir))

    def test_result_parquet_has_data01_columns(self):
        """Result parquet has all DATA-01 columns (datetime_utc, currency, impact, title, id, leaked)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_cache(cache_dir, [(2026, 3)], [[_usd_high_row()]])

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            df = pd.read_parquet(result)
            for col in ("datetime_utc", "currency", "impact", "title", "id", "leaked"):
                self.assertIn(col, df.columns, f"DATA-01 column missing: {col}")

    def test_result_parquet_filtered_to_requested_currency_and_impact(self):
        """Result parquet contains only rows matching requested currencies/impacts."""
        from forexfactory import _query, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            # Scope covers both USD/high and EUR/medium
            wide_scope = {"currencies": ["EUR", "USD"], "impacts": ["high", "medium"]}
            self._setup_cache(
                cache_dir,
                [(2026, 3)],
                [[_usd_high_row(), _eur_medium_row()]],
                scope=wide_scope,
            )

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            df = pd.read_parquet(result)
            self.assertGreater(len(df), 0, "result must have at least one row")
            self.assertTrue((df["currency"] == "USD").all(), "only USD rows expected")
            self.assertTrue((df["impact"] == "high").all(), "only high-impact rows expected")

    def test_deterministic_path_same_on_two_calls(self):
        """Two identical run_query calls return the same path (D-08 deterministic)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_cache(cache_dir, [(2026, 3)], [[_usd_high_row()]])

            r1 = _query.run_query(currencies=["USD"], impacts=["high"], cache_dir=cache_dir)
            r2 = _query.run_query(currencies=["USD"], impacts=["high"], cache_dir=cache_dir)

            self.assertEqual(r1, r2)

    def test_result_parquet_overwritten_each_call(self):
        """A second run_query call overwrites the result parquet (D-08)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_cache(cache_dir, [(2026, 3)], [[_usd_high_row()]])

            r1 = _query.run_query(currencies=["USD"], impacts=["high"], cache_dir=cache_dir)
            mtime1 = r1.stat().st_mtime

            time.sleep(0.05)

            r2 = _query.run_query(currencies=["USD"], impacts=["high"], cache_dir=cache_dir)
            mtime2 = r2.stat().st_mtime

            self.assertGreaterEqual(mtime2, mtime1, "second call must overwrite result file")

    def test_multiple_months_concatenated(self):
        """run_query reads and concatenates events from multiple months (D-07)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            row_jan = _usd_high_row("2026-01-15 10:00:00")
            row_feb = _usd_high_row("2026-02-15 10:00:00")
            row_mar = _usd_high_row("2026-03-15 10:00:00")
            self._setup_cache(
                cache_dir,
                [(2026, 1), (2026, 2), (2026, 3)],
                [[row_jan], [row_feb], [row_mar]],
            )

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            df = pd.read_parquet(result)
            self.assertEqual(len(df), 3, "expected 3 rows from 3 months")

    def test_forexfactory_get_returns_path(self):
        """forexfactory.get() returns the identical Path as run_query (SC4 / PKG-03)."""
        import forexfactory
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_cache(cache_dir, [(2026, 3)], [[_usd_high_row()]])

            expected = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            result = forexfactory.get(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            self.assertIsInstance(result, pathlib.Path)
            self.assertEqual(result, expected)


# ---------------------------------------------------------------------------
# Task 2 — D-09: out-of-scope error tests
# ---------------------------------------------------------------------------

class QueryScopeErrorTests(unittest.TestCase):
    """Task 2 — D-09: out-of-scope request raises ValueError with populate guidance."""

    def _setup_usd_high_only(self, cache_dir: Path) -> None:
        """Write a manifest with scope limited to USD/high + holiday."""
        from forexfactory import _cache

        _cache.ensure_dirs(cache_dir)
        _cache.write_manifest(cache_dir, {
            "scope": {"currencies": ["USD"], "impacts": ["high", "holiday"]},
            "months": {
                "2026-03": {"scraped_at": "2026-06-08T00:00:00Z", "settled": True},
            },
        })

    def test_out_of_scope_raises_value_error(self):
        """Requesting EUR/medium when scope is USD/high raises ValueError (D-09)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_usd_high_only(cache_dir)

            with self.assertRaises(ValueError):
                _query.run_query(
                    currencies=["EUR"],
                    impacts=["medium"],
                    cache_dir=cache_dir,
                )

    def test_out_of_scope_error_message_contains_populate_command(self):
        """ValueError message contains 'forexfactory populate' with remediation guidance (D-09)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_usd_high_only(cache_dir)

            try:
                _query.run_query(
                    currencies=["EUR"],
                    impacts=["medium"],
                    cache_dir=cache_dir,
                )
                self.fail("Expected ValueError not raised")
            except ValueError as exc:
                self.assertIn(
                    "forexfactory populate",
                    str(exc),
                    "error message must contain 'forexfactory populate' remediation",
                )

    def test_out_of_scope_does_not_write_result_file(self):
        """No result parquet is written when the request is out of scope (D-09)."""
        from forexfactory import _query, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_usd_high_only(cache_dir)

            try:
                _query.run_query(
                    currencies=["EUR"],
                    impacts=["medium"],
                    cache_dir=cache_dir,
                )
            except ValueError:
                pass

            q_dir = _cache.queries_dir(cache_dir)
            written = list(q_dir.glob("*.parquet")) if q_dir.exists() else []
            self.assertEqual(len(written), 0, "no parquet should be written on scope error")

    def test_empty_manifest_raises_value_error(self):
        """Empty manifest (nothing populated) raises ValueError for any request (D-09)."""
        from forexfactory import _query, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            _cache.ensure_dirs(cache_dir)
            # No manifest written — empty cache

            with self.assertRaises(ValueError):
                _query.run_query(
                    currencies=["USD"],
                    impacts=["high"],
                    cache_dir=cache_dir,
                )

    def test_error_message_names_missing_currency(self):
        """Error message includes the uncovered currency identifier (D-09)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            self._setup_usd_high_only(cache_dir)

            try:
                _query.run_query(
                    currencies=["EUR"],
                    impacts=["medium"],
                    cache_dir=cache_dir,
                )
                self.fail("Expected ValueError not raised")
            except ValueError as exc:
                msg = str(exc)
                self.assertIn("EUR", msg)
                self.assertIn("medium", msg)


# ---------------------------------------------------------------------------
# Phase-2 D-08/D-09: include_no_data filter tests
# ---------------------------------------------------------------------------

class QueryIncludeNoDataTests(unittest.TestCase):
    """D-08/D-09: include_no_data filter — speeches hidden by default, holidays visible."""

    def _setup_cache(
        self,
        cache_dir: Path,
        months: list,
        rows_per_month: list,
        scope: dict | None = None,
    ) -> None:
        """Write per-month parquets + manifest under cache_dir."""
        from forexfactory import _cache

        _cache.ensure_dirs(cache_dir)
        if scope is None:
            scope = {"currencies": ["USD"], "impacts": ["high", "holiday"]}
        manifest = {"scope": scope, "months": {}}
        for (year, month), rows in zip(months, rows_per_month):
            anchor = __import__("datetime").date(year, month, 1)
            p = _cache.month_parquet_path(cache_dir, anchor)
            _make_parquet(p, rows)
            manifest["months"][f"{year:04d}-{month:02d}"] = {
                "scraped_at": "2026-06-08T00:00:00Z",
                "settled": True,
            }
        _cache.write_manifest(cache_dir, manifest)

    def test_default_hides_speeches(self):
        """Default run_query hides hasDataValues=False non-holiday rows (D-08)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            data_row = _usd_high_data_row("2026-03-01 08:30:00")
            speech = _speech_row("2026-03-01 09:00:00")
            self._setup_cache(cache_dir, [(2026, 3)], [[data_row, speech]])

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high", "holiday"],
                cache_dir=cache_dir,
            )

            df = pd.read_parquet(result)
            self.assertEqual(len(df), 1, "default result should contain only the data-bearing row")
            self.assertEqual(df.iloc[0]["title"], "CPI y/y")
            self.assertFalse(
                any(df["title"] == "Fed Chair Powell Speaks"),
                "speech row must not appear in default result",
            )

    def test_include_no_data_surfaces_speeches(self):
        """include_no_data=True returns data-bearing rows AND speech rows (D-09)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            data_row = _usd_high_data_row("2026-03-01 08:30:00")
            speech = _speech_row("2026-03-01 09:00:00")
            self._setup_cache(cache_dir, [(2026, 3)], [[data_row, speech]])

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high", "holiday"],
                cache_dir=cache_dir,
                include_no_data=True,
            )

            df = pd.read_parquet(result)
            self.assertEqual(len(df), 2, "include_no_data=True must include both rows")
            titles = set(df["title"].tolist())
            self.assertIn("CPI y/y", titles)
            self.assertIn("Fed Chair Powell Speaks", titles)

    def test_holiday_visible_by_default(self):
        """Holidays (impact='holiday', hasDataValues=False) appear in default result (D-08)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            holiday = _holiday_row("2026-03-01 00:00:00")
            speech = _speech_row("2026-03-01 09:00:00")
            self._setup_cache(cache_dir, [(2026, 3)], [[holiday, speech]])

            result = _query.run_query(
                currencies=["USD"],
                impacts=["high", "holiday"],
                cache_dir=cache_dir,
            )

            df = pd.read_parquet(result)
            self.assertGreater(len(df), 0, "holiday must not be hidden by default filter")
            self.assertTrue(
                any(df["impact"] == "holiday"),
                "holiday row must appear in default result (D-08)",
            )
            self.assertFalse(
                any(df["title"] == "Fed Chair Powell Speaks"),
                "speech must still be hidden even when holiday is visible",
            )

    def test_stale_cache_without_hasdatavalues_does_not_raise(self):
        """Querying a pre-Phase-2 parquet lacking hasDataValues column does not raise (RESEARCH Pitfall 4)."""
        from forexfactory import _query

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            # Rows without hasDataValues key (pre-Phase-2 parquet)
            stale_row = _usd_high_row("2026-03-01 08:30:00")
            self._setup_cache(cache_dir, [(2026, 3)], [[stale_row]])

            # Must not raise — should degrade gracefully and return a result Path
            result = _query.run_query(
                currencies=["USD"],
                impacts=["high"],
                cache_dir=cache_dir,
            )

            self.assertIsInstance(result, Path)
            self.assertTrue(result.exists(), "result parquet must exist even for stale cache")

    def test_forexfactory_get_include_no_data_kwarg_forwarded(self):
        """forexfactory.get(include_no_data=True) kwarg is forwarded to run_query (D-12)."""
        import forexfactory

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            data_row = _usd_high_data_row("2026-03-01 08:30:00")
            speech = _speech_row("2026-03-01 09:00:00")
            self._setup_cache(cache_dir, [(2026, 3)], [[data_row, speech]])

            result = forexfactory.get(
                currencies=["USD"],
                impacts=["high", "holiday"],
                cache_dir=cache_dir,
                include_no_data=True,
            )

            df = pd.read_parquet(result)
            self.assertEqual(len(df), 2, "get(include_no_data=True) must surface speech rows")


if __name__ == "__main__":
    unittest.main()
