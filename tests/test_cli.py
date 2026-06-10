"""
Tests for forexfactory.cli — routing, D-10/D-12/D-09, and walking-skeleton end-to-end.
"""

import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import forexfactory.cli as cli

# ─────────────────────────────────────────────────────────────────────────────
# Walking-skeleton end-to-end test (Phase 1 SC2 + SC3)
# ─────────────────────────────────────────────────────────────────────────────

_FIXTURE_DAYS = [
    {
        "events": [
            {
                "currency": "USD",
                "impactName": "High Impact Expected",
                "name": "Non-Farm Payrolls",
                "dateline": 1772323200,
                "id": "nfp-1",
                "leaked": False,
                "hasDataValues": True,
            }
        ]
    }
]


class SkeletonEndToEndTests(unittest.TestCase):
    def test_populate_then_query_returns_valid_parquet_path(self):
        """install→populate(on-disk JSON)→query→pd.read_parquet succeeds (SC2, SC3)."""
        with (
            tempfile.TemporaryDirectory() as raw_dir_str,
            tempfile.TemporaryDirectory() as cache_dir_str,
        ):
            raw_dir = pathlib.Path(raw_dir_str)
            cache_dir = pathlib.Path(cache_dir_str)

            # Write one real-shaped USD/high fixture month (zero HTTP, SC2)
            (raw_dir / "days_2026_03.json").write_text(json.dumps(_FIXTURE_DAYS), encoding="utf-8")

            # Populate from raw dir — must make zero network calls (SC2)
            cli.main(
                [
                    "populate",
                    "--raw-dir",
                    str(raw_dir),
                    "--cache-dir",
                    str(cache_dir),
                ]
            )

            # Query — capture stdout; D-10 demands path-only output
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--impact",
                        "high",
                        "--cache-dir",
                        str(cache_dir),
                    ]
                )

            output = buf.getvalue()
            non_empty_lines = [ln for ln in output.splitlines() if ln.strip()]

            # D-10: exactly one line on stdout
            self.assertEqual(
                len(non_empty_lines),
                1,
                f"Expected exactly one line on stdout (D-10), got: {output!r}",
            )

            path_str = non_empty_lines[0].strip()

            # Path must be absolute
            result_path = pathlib.Path(path_str)
            self.assertTrue(
                result_path.is_absolute(),
                f"Expected an absolute path, got: {path_str!r}",
            )

            # Path must exist on disk
            self.assertTrue(
                result_path.exists(),
                f"Parquet path does not exist: {path_str!r}",
            )

            # Must open with pd.read_parquet and have DATA-01 columns
            df = pd.read_parquet(str(result_path))
            expected_cols = {"datetime_utc", "currency", "impact", "title", "id", "leaked"}
            self.assertTrue(
                expected_cols.issubset(set(df.columns)),
                f"Missing DATA-01 columns. Got: {list(df.columns)}",
            )

            # Must contain at least one USD/high row (SC3)
            usd_high = df[(df["currency"] == "USD") & (df["impact"] == "high")]
            self.assertGreater(
                len(usd_high),
                0,
                "No USD/high rows found in query result parquet",
            )


# ─────────────────────────────────────────────────────────────────────────────
# CLI routing + contract tests (D-10, D-12, D-09, populate dispatch)
# ─────────────────────────────────────────────────────────────────────────────


class CliRoutingTests(unittest.TestCase):
    def test_query_repeatable_currency_flags_produce_list(self):
        """D-12: --currency USD --currency EUR yields currencies == ["USD", "EUR"]."""
        captured = {}

        def fake_run_query(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            captured["currencies"] = currencies
            captured["impacts"] = impacts
            return pathlib.Path("/tmp/fake.parquet")  # cli.main just prints it

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--currency",
                        "EUR",
                        "--impact",
                        "high",
                    ]
                )

        self.assertEqual(captured["currencies"], ["USD", "EUR"])

    def test_query_prints_only_path_to_stdout(self):
        """D-10: query subcommand writes exactly the parquet path to stdout, nothing else."""
        fake_path = pathlib.Path("/tmp/fake_result.parquet")

        def fake_run_query(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            return fake_path

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(["query", "--currency", "USD", "--impact", "high"])

        output = buf.getvalue()
        non_empty = [ln.strip() for ln in output.splitlines() if ln.strip()]
        self.assertEqual(
            len(non_empty),
            1,
            f"Expected exactly one line on stdout, got: {output!r}",
        )
        self.assertEqual(non_empty[0], str(fake_path))

    def test_query_out_of_scope_exits_code_1_with_stderr_guidance(self):
        """D-09: ValueError from run_query → sys.exit(1) with guidance message on stderr."""
        err_msg = (
            "EUR/medium not populated — run: forexfactory populate --currency EUR --impact medium"
        )

        def fake_raise(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            raise ValueError(err_msg)

        buf_err = io.StringIO()
        with (
            patch.object(cli._query, "run_query", side_effect=fake_raise),
            contextlib.redirect_stderr(buf_err),
            self.assertRaises(SystemExit) as cm,
        ):
            cli.main(["query", "--currency", "EUR", "--impact", "medium"])

        self.assertEqual(cm.exception.code, 1)
        stderr_text = buf_err.getvalue()
        self.assertIn("EUR", stderr_text)
        self.assertIn("forexfactory populate", stderr_text)

    def test_populate_routes_to_run_populate_with_forwarded_args(self):
        """populate subcommand routes to _populate.run_populate with correct args."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["currencies"] = currencies
            captured["raw_dir"] = raw_dir
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(
                [
                    "populate",
                    "--currency",
                    "USD",
                    "--impact",
                    "high",
                    "--raw-dir",
                    "out",
                ]
            )

        self.assertEqual(captured["currencies"], ["USD"])
        self.assertEqual(captured["raw_dir"], "out")

    def test_repeatable_impact_flags_produce_list(self):
        """D-12: --impact high --impact holiday yields impacts == ["high", "holiday"]."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["impacts"] = impacts
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(
                [
                    "populate",
                    "--impact",
                    "high",
                    "--impact",
                    "holiday",
                    "--raw-dir",
                    "out",
                ]
            )

        self.assertEqual(captured["impacts"], ["high", "holiday"])


class CliValidateMonthTests(unittest.TestCase):
    """WR-05: _validate_month must range-check the month integer to [1, 12]."""

    def test_month_99_exits_code_1(self):
        """'2024-99' must produce sys.exit(1) with an error message, not a traceback."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err), self.assertRaises(SystemExit) as cm:
            cli.main(["populate", "--start", "2024-99", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_month_00_exits_code_1(self):
        """'2024-00' must produce sys.exit(1) with an error message, not a traceback."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err), self.assertRaises(SystemExit) as cm:
            cli.main(["populate", "--end", "2024-00", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_month_13_exits_code_1(self):
        """'2024-13' must produce sys.exit(1) — 13 is out of the 1–12 range."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err), self.assertRaises(SystemExit) as cm:
            cli.main(["populate", "--start", "2024-13", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_valid_month_does_not_exit(self):
        """A valid month string '2024-03' passes validation without sys.exit."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["start"] = start
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--start", "2024-03", "--raw-dir", "out"])

        self.assertEqual(captured["start"], "2024-03")


# ─────────────────────────────────────────────────────────────────────────────
# Phase-2 D-09/D-12: --include-no-data and --force flag tests
# ─────────────────────────────────────────────────────────────────────────────

_SPEECH_EVENT = {
    "currency": "USD",
    "impactName": "High Impact Expected",
    "name": "Fed Chair Powell Speaks",
    "dateline": 1772323200,
    "id": "powell-1",
    "leaked": False,
    "hasDataValues": False,
}

_DATA_EVENT = {
    "currency": "USD",
    "impactName": "High Impact Expected",
    "name": "Non-Farm Payrolls",
    "dateline": 1772326800,
    "id": "nfp-1",
    "leaked": False,
    "hasDataValues": True,
}


class CliIncludeNoDataTests(unittest.TestCase):
    """D-09/D-12: --include-no-data flag hides speeches by default, surfaces them with flag."""

    def test_default_query_hides_speech_row(self):
        """Default query result excludes speech events (hasDataValues=False, non-holiday)."""
        with (
            tempfile.TemporaryDirectory() as raw_dir_str,
            tempfile.TemporaryDirectory() as cache_dir_str,
        ):
            raw_dir = pathlib.Path(raw_dir_str)
            cache_dir = pathlib.Path(cache_dir_str)

            fixture = [{"events": [_DATA_EVENT, _SPEECH_EVENT]}]
            (raw_dir / "days_2026_03.json").write_text(json.dumps(fixture), encoding="utf-8")

            cli.main(["populate", "--raw-dir", str(raw_dir), "--cache-dir", str(cache_dir)])

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--impact",
                        "high",
                        "--cache-dir",
                        str(cache_dir),
                    ]
                )

            path_str = buf.getvalue().strip()
            df = pd.read_parquet(path_str)
            self.assertFalse(
                any(df["title"] == "Fed Chair Powell Speaks"),
                "speech must be absent from default query result",
            )
            self.assertTrue(
                any(df["title"] == "Non-Farm Payrolls"),
                "data-bearing event must appear in default query result",
            )

    def test_include_no_data_flag_surfaces_speech_row(self):
        """--include-no-data makes speech events appear in the query result (D-09)."""
        with (
            tempfile.TemporaryDirectory() as raw_dir_str,
            tempfile.TemporaryDirectory() as cache_dir_str,
        ):
            raw_dir = pathlib.Path(raw_dir_str)
            cache_dir = pathlib.Path(cache_dir_str)

            fixture = [{"events": [_DATA_EVENT, _SPEECH_EVENT]}]
            (raw_dir / "days_2026_03.json").write_text(json.dumps(fixture), encoding="utf-8")

            cli.main(["populate", "--raw-dir", str(raw_dir), "--cache-dir", str(cache_dir)])

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--impact",
                        "high",
                        "--cache-dir",
                        str(cache_dir),
                        "--include-no-data",
                    ]
                )

            path_str = buf.getvalue().strip()
            df = pd.read_parquet(path_str)
            self.assertTrue(
                any(df["title"] == "Fed Chair Powell Speaks"),
                "--include-no-data must surface speech events",
            )
            self.assertEqual(len(df), 2, "--include-no-data result must contain both rows")


class CliForcePopulateTests(unittest.TestCase):
    """Phase-2: --force flag wired to run_populate(force=...) at dispatch."""

    def test_force_flag_forwarded_to_run_populate(self):
        """--force sets force=True in the run_populate call."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["force"] = force
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--force", "--raw-dir", "out"])

        self.assertTrue(captured["force"], "--force must set force=True in run_populate call")

    def test_no_force_flag_defaults_false(self):
        """Without --force, force=False is passed to run_populate."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["force"] = force
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--raw-dir", "out"])

        self.assertFalse(captured["force"], "force must default to False when --force not given")


class CliForceRefreshTests(unittest.TestCase):
    """CACHE-06 / D-01/D-02: --force-refresh wired through CLI on populate and refresh."""

    def test_populate_force_refresh_flag_forwarded_to_run_populate(self):
        """--force-refresh on populate sets force_refresh=True in run_populate call."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["force_refresh"] = force_refresh
            return {"fetched": 1, "skipped": 0, "failed": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            exit_code = cli.main(["populate", "--force-refresh", "--raw-dir", "out"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(
            captured["force_refresh"],
            "--force-refresh must set force_refresh=True in run_populate call",
        )

    def test_populate_without_force_refresh_defaults_false(self):
        """Without --force-refresh, force_refresh=False is passed to run_populate."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["force_refresh"] = force_refresh
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--raw-dir", "out"])

        self.assertFalse(
            captured["force_refresh"],
            "force_refresh must default to False when --force-refresh not given",
        )

    def test_refresh_force_refresh_flag_forwarded_to_run_refresh(self):
        """--force-refresh on refresh sets force_refresh=True in run_refresh call (D-02)."""
        from forexfactory import _refresh

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
            captured["force_refresh"] = force_refresh
            return {"fetched": 1, "skipped": 0, "failed": 0}

        with patch.object(_refresh, "run_refresh", side_effect=fake_run_refresh):
            exit_code = cli.main(
                [
                    "refresh",
                    "--force-refresh",
                    "--start",
                    "2026-04",
                    "--end",
                    "2026-05",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(
            captured["force_refresh"],
            "--force-refresh must set force_refresh=True in run_refresh call",
        )

    def test_refresh_without_force_refresh_defaults_false(self):
        """Without --force-refresh on refresh, force_refresh=False is passed to run_refresh."""
        from forexfactory import _refresh

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
            captured["force_refresh"] = force_refresh
            return {"fetched": 0, "skipped": 1, "failed": 0}

        with patch.object(_refresh, "run_refresh", side_effect=fake_run_refresh):
            cli.main(
                [
                    "refresh",
                    "--start",
                    "2026-04",
                    "--end",
                    "2026-05",
                ]
            )

        self.assertFalse(
            captured["force_refresh"], "force_refresh must default to False without --force-refresh"
        )


# ─────────────────────────────────────────────────────────────────────────────
# WR-02: --no-auto-fetch flag threads auto_fetch=False to run_populate / run_query
# ─────────────────────────────────────────────────────────────────────────────


class CliNoAutoFetchTests(unittest.TestCase):
    """WR-02: --no-auto-fetch flag on populate and query subparsers forwards auto_fetch=False."""

    def test_populate_no_auto_fetch_flag_forwards_false(self):
        """--no-auto-fetch on populate passes auto_fetch=False to run_populate."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["auto_fetch"] = auto_fetch
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            exit_code = cli.main(["populate", "--no-auto-fetch", "--raw-dir", "out"])

        self.assertEqual(exit_code, 0)
        self.assertFalse(
            captured["auto_fetch"],
            "--no-auto-fetch must pass auto_fetch=False to run_populate",
        )

    def test_populate_without_no_auto_fetch_defaults_true(self):
        """Without --no-auto-fetch, auto_fetch=True is passed to run_populate (default on)."""
        captured = {}

        def fake_run_populate(
            *,
            currencies,
            impacts,
            start,
            end,
            raw_dir,
            cache_dir,
            force,
            force_refresh=False,
            auto_fetch=True,
        ):
            captured["auto_fetch"] = auto_fetch
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--raw-dir", "out"])

        self.assertTrue(
            captured["auto_fetch"],
            "auto_fetch must default to True when --no-auto-fetch is absent",
        )

    def test_query_no_auto_fetch_flag_forwards_false(self):
        """--no-auto-fetch on query passes auto_fetch=False to run_query."""
        captured = {}

        def fake_run_query(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            captured["auto_fetch"] = auto_fetch
            return pathlib.Path("/tmp/fake.parquet")

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--impact",
                        "high",
                        "--no-auto-fetch",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertFalse(
            captured["auto_fetch"],
            "--no-auto-fetch must pass auto_fetch=False to run_query",
        )

    def test_query_without_no_auto_fetch_defaults_true(self):
        """Without --no-auto-fetch, auto_fetch=True is passed to run_query (default on)."""
        captured = {}

        def fake_run_query(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            captured["auto_fetch"] = auto_fetch
            return pathlib.Path("/tmp/fake.parquet")

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(["query", "--currency", "USD", "--impact", "high"])

        self.assertTrue(
            captured["auto_fetch"],
            "auto_fetch must default to True when --no-auto-fetch is absent",
        )


# ─────────────────────────────────────────────────────────────────────────────
# CACHE-05 / D-11/D-12: CLI matured-months banner tests
# ─────────────────────────────────────────────────────────────────────────────


class CliMaturedBannerTests(unittest.TestCase):
    """D-11/D-12: CLI query prints matured-months banner to stdout before path."""

    _FIXTURE_DAYS_WITH_ACTUAL = [
        {
            "events": [
                {
                    "currency": "USD",
                    "impactName": "High Impact Expected",
                    "name": "CPI y/y",
                    "dateline": 1746057600,
                    "id": "cpi-1",
                    "leaked": False,
                    "hasDataValues": True,
                    "forecast": "4.3%",
                    "actual": "4.5%",
                }
            ]
        }
    ]

    def _seed_matured_cache(self, cache_dir: pathlib.Path) -> None:
        """Seed a cache with a settled:false past month (2026-05)."""
        from datetime import date

        from forexfactory import _cache, _populate

        _cache.ensure_dirs(cache_dir)
        anchor = date(2026, 5, 1)
        stale_days = [
            {
                "events": [
                    {
                        "currency": "USD",
                        "impactName": "High Impact Expected",
                        "name": "CPI y/y",
                        "dateline": 1746057600,
                        "id": "cpi-1",
                        "leaked": False,
                        "hasDataValues": True,
                        "forecast": "4.3%",
                    }
                ]
            }
        ]
        _populate.build_month_parquet(
            cache_dir,
            anchor,
            stale_days,
            currencies=["USD"],
            impacts=["high", "holiday"],
        )
        _cache.write_manifest(
            cache_dir,
            {
                "scope": {"currencies": ["USD"], "impacts": ["high", "holiday"]},
                "months": {
                    "2026-05": {"scraped_at": "2026-01-01T00:00:00Z", "settled": False},
                },
            },
        )

    def test_matured_banner_printed_before_path(self):
        """D-12: CLI query prints matured banner to stdout before the parquet path line."""
        from forexfactory import _scrape

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = pathlib.Path(tmpdir) / "cache"
            self._seed_matured_cache(cache_dir)

            buf = io.StringIO()
            with (
                contextlib.redirect_stdout(buf),
                patch.object(_scrape, "scrape_month", return_value=self._FIXTURE_DAYS_WITH_ACTUAL),
            ):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "USD",
                        "--impact",
                        "high",
                        "--cache-dir",
                        str(cache_dir),
                    ]
                )

            output = buf.getvalue()
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]

            # Must contain the D-12 banner
            self.assertTrue(
                any("months matured since last run" in ln for ln in lines),
                f"D-12 matured banner must appear on stdout; got: {output!r}",
            )
            # Banner must be "1 months matured since last run — refreshing actuals..."
            banner_lines = [ln for ln in lines if "months matured" in ln]
            self.assertEqual(len(banner_lines), 1)
            self.assertIn("1 months matured since last run", banner_lines[0])

            # Final line must be the absolute parquet path
            last_line = lines[-1]
            result_path = pathlib.Path(last_line)
            self.assertTrue(result_path.is_absolute(), "last stdout line must be an absolute path")
            self.assertTrue(result_path.exists(), "result parquet path must exist on disk")

    def test_no_matured_months_no_banner(self):
        """D-12: no banner when all months are settled (fake run_query never fires callback)."""
        fake_path = pathlib.Path("/tmp/settled.parquet")

        def fake_run_query(
            *,
            currencies,
            impacts,
            start,
            end,
            include_no_data,
            cache_dir,
            progress=None,
            auto_fetch=True,
            session=None,
        ):
            # Simulate: run_query with settled cache — progress is never called
            return fake_path

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(["query", "--currency", "USD", "--impact", "high"])

        output = buf.getvalue()
        non_empty = [ln.strip() for ln in output.splitlines() if ln.strip()]
        self.assertEqual(
            len(non_empty), 1, "no banner when no matured months — exactly one stdout line (D-10)"
        )
        self.assertEqual(non_empty[0], str(fake_path))


# ─────────────────────────────────────────────────────────────────────────────
# CACHE-03 / D-11/D-12: CLI scope-miss banner and AutoFetchError handling
# ─────────────────────────────────────────────────────────────────────────────

_EUR_MEDIUM_DAYS_WITH_DATA = [
    {
        "events": [
            {
                "currency": "EUR",
                "impactName": "Medium Impact Expected",
                "name": "ECB Rate Decision",
                "dateline": 1746057600,
                "id": "ecb-1",
                "leaked": False,
                "hasDataValues": True,
            },
            {
                "currency": "USD",
                "impactName": "High Impact Expected",
                "name": "CPI y/y",
                "dateline": 1746057600,
                "id": "cpi-1",
                "leaked": False,
                "hasDataValues": True,
            },
        ]
    }
]


class CliScopeMissBannerTests(unittest.TestCase):
    """CACHE-03 / D-11/D-12: CLI query prints the scope-miss banner and handles AutoFetchError."""

    def _seed_usd_high_cache(self, cache_dir: pathlib.Path) -> None:
        """Seed a USD/high-only cache with one month (2026-05)."""
        from datetime import date

        from forexfactory import _cache, _populate

        _cache.ensure_dirs(cache_dir)
        anchor = date(2026, 5, 1)
        usd_days = [
            {
                "events": [
                    {
                        "currency": "USD",
                        "impactName": "High Impact Expected",
                        "name": "CPI y/y",
                        "dateline": 1746057600,
                        "id": "cpi-1",
                        "leaked": False,
                        "hasDataValues": True,
                    }
                ]
            }
        ]
        _populate.build_month_parquet(
            cache_dir,
            anchor,
            usd_days,
            currencies=["USD"],
            impacts=["high", "holiday"],
        )
        _cache.write_manifest(
            cache_dir,
            {
                "scope": {"currencies": ["USD"], "impacts": ["high", "holiday"]},
                "months": {
                    "2026-05": {"scraped_at": "2026-01-01T00:00:00Z", "settled": True},
                },
            },
        )

    def test_scope_miss_banner_printed_before_path(self):
        """D-12: CLI query prints scope-miss banner to stdout before the parquet path line."""
        from forexfactory import _scrape

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = pathlib.Path(tmpdir) / "cache"
            self._seed_usd_high_cache(cache_dir)

            buf = io.StringIO()
            with (
                contextlib.redirect_stdout(buf),
                patch.object(_scrape, "scrape_month", return_value=_EUR_MEDIUM_DAYS_WITH_DATA),
            ):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "EUR",
                        "--impact",
                        "medium",
                        "--cache-dir",
                        str(cache_dir),
                    ]
                )

            output = buf.getvalue()
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]

            # Must contain the D-12 scope-miss banner
            banner_lines = [ln for ln in lines if "not in cache" in ln]
            self.assertEqual(
                len(banner_lines),
                1,
                f"D-12 scope-miss banner must appear once on stdout; got: {output!r}",
            )
            self.assertIn("EUR/medium not in cache — fetching now...", banner_lines[0])

            # Final line must be the absolute parquet path
            last_line = lines[-1]
            result_path = pathlib.Path(last_line)
            self.assertTrue(result_path.is_absolute(), "last stdout line must be an absolute path")
            self.assertTrue(result_path.exists(), "result parquet path must exist on disk")

    def test_auto_fetch_failure_exits_code_1_with_stderr(self):
        """D-06: failed auto-widen exits code 1 and prints AutoFetchError to stderr (not stdout)."""
        from forexfactory import _scrape

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = pathlib.Path(tmpdir) / "cache"
            self._seed_usd_high_cache(cache_dir)

            buf_out = io.StringIO()
            buf_err = io.StringIO()
            with (
                contextlib.redirect_stdout(buf_out),
                contextlib.redirect_stderr(buf_err),
                self.assertRaises(SystemExit) as cm,
                patch.object(_scrape, "scrape_month", return_value=[]),
            ):
                cli.main(
                    [
                        "query",
                        "--currency",
                        "EUR",
                        "--impact",
                        "medium",
                        "--cache-dir",
                        str(cache_dir),
                    ]
                )

            self.assertEqual(cm.exception.code, 1, "failed auto-widen must exit with code 1")
            # Error must appear on stderr, NOT stdout
            self.assertGreater(
                len(buf_err.getvalue().strip()), 0, "error text must appear on stderr"
            )
            self.assertEqual(
                len(
                    [
                        ln
                        for ln in buf_out.getvalue().splitlines()
                        if ln.strip()
                        and "not in cache" not in ln  # banner may appear before the error
                    ]
                ),
                0,
                "no parquet path line must appear on stdout when auto-widen fails",
            )


# ─────────────────────────────────────────────────────────────────────────────
# CLI-01 / D-06: --version top-level action (plan 04-03)
# ─────────────────────────────────────────────────────────────────────────────


class CliVersionTests(unittest.TestCase):
    """CLI-01 / D-06: --version prints the installed version from the single source of truth."""

    def test_version_flag_exits_zero_and_prints_version(self):
        """--version prints 'forexfactory <version>' and exits 0."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            cli.main(["--version"])
        # argparse version action exits 0
        self.assertEqual(cm.exception.code, 0)
        output = buf.getvalue().strip()
        self.assertTrue(
            output.startswith("forexfactory "),
            f"Expected 'forexfactory <version>', got: {output!r}",
        )

    def test_version_matches_package_version(self):
        """--version output matches forexfactory.__version__ (single source of truth, D-08)."""
        import forexfactory

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["--version"])
        output = buf.getvalue().strip()
        self.assertIn(forexfactory.__version__, output)

    def test_version_not_hardcoded_in_cli_source(self):
        """Version literal '1.1.0' must NOT appear as a hardcoded string in cli.py (D-06/D-08)."""
        import inspect

        source = inspect.getsource(cli)
        # The version string should come from __version__ import, not a hardcoded literal
        self.assertNotIn('"1.1.0"', source)
        self.assertNotIn("'1.1.0'", source)


# ─────────────────────────────────────────────────────────────────────────────
# CLI-02 / D-05: status subcommand registration + dispatch (plan 04-03)
# ─────────────────────────────────────────────────────────────────────────────


class CliStatusRegistrationTests(unittest.TestCase):
    """CLI-02: status subcommand is registered with --cache-dir and --json options."""

    def test_status_help_lists_json_flag(self):
        """forexfactory status --help lists --json option."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            cli.main(["status", "--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("--json", buf.getvalue())

    def test_status_help_lists_cache_dir_flag(self):
        """forexfactory status --help lists --cache-dir option."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            cli.main(["status", "--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("--cache-dir", buf.getvalue())

    def test_status_no_start_end_does_not_raise_attribute_error(self):
        """status subcommand has no --start/--end args; must not raise AttributeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty cache dir — will print 'cache is empty' guidance
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = cli.main(["status", "--cache-dir", tmpdir])
        self.assertEqual(exit_code, 0)


class CliStatusDispatchTests(unittest.TestCase):
    """CLI-02 / D-05: status dispatch reads manifest and prints aligned text or JSON."""

    def _build_manifest(self) -> dict:
        return {
            "schema_version": "2",
            "scope": {
                "currencies": ["USD"],
                "impacts": ["high", "holiday"],
            },
            "months": {
                "2010-01": {"scraped_at": "2024-01-01T00:00:00Z", "settled": True},
                "2010-02": {"scraped_at": "2024-01-01T00:00:00Z", "settled": True},
                "2026-03": {"scraped_at": "2026-03-01T00:00:00Z", "settled": False},
            },
        }

    def test_status_text_mode_contains_required_fields(self):
        """status text output contains cache dir, schema ver, scope, date range, settled count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from forexfactory import _cache

            manifest = self._build_manifest()
            _cache.write_manifest(pathlib.Path(tmpdir), manifest)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = cli.main(["status", "--cache-dir", tmpdir])

        self.assertEqual(exit_code, 0)
        output = buf.getvalue()
        # Must contain the cache directory path
        self.assertIn(tmpdir, output)
        # Must contain schema version
        self.assertIn("2", output)
        # Must contain currency
        self.assertIn("USD", output)
        # Must contain date range start and end
        self.assertIn("2010-01", output)
        self.assertIn("2026-03", output)
        # Must contain settled count (2 of 3 months are settled)
        self.assertIn("2", output)

    def test_status_json_mode_returns_valid_json(self):
        """status --json emits valid JSON with required keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from forexfactory import _cache

            manifest = self._build_manifest()
            _cache.write_manifest(pathlib.Path(tmpdir), manifest)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = cli.main(["status", "--json", "--cache-dir", tmpdir])

        self.assertEqual(exit_code, 0)
        output = buf.getvalue().strip()
        data = json.loads(output)  # must be valid JSON

        # Required top-level keys
        self.assertIn("cache_dir", data)
        self.assertIn("schema_version", data)
        self.assertIn("scope", data)
        self.assertIn("date_range", data)
        self.assertIn("settled", data)
        self.assertIn("unsettled", data)

        # scope sub-keys
        self.assertIn("currencies", data["scope"])
        self.assertIn("impacts", data["scope"])

        # date_range sub-keys
        self.assertIn("start", data["date_range"])
        self.assertIn("end", data["date_range"])
        self.assertIn("count", data["date_range"])

        # Values must be correct
        self.assertEqual(data["scope"]["currencies"], ["USD"])
        self.assertEqual(data["date_range"]["start"], "2010-01")
        self.assertEqual(data["date_range"]["end"], "2026-03")
        self.assertEqual(data["date_range"]["count"], 3)
        self.assertEqual(data["settled"], 2)
        self.assertEqual(data["unsettled"], 1)

    def test_status_empty_cache_exits_zero_with_guidance(self):
        """status on empty cache exits 0 and prints 'cache is empty' guidance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exit_code = cli.main(["status", "--cache-dir", tmpdir])

        self.assertEqual(exit_code, 0)
        output = buf.getvalue().lower()
        self.assertIn("cache is empty", output)
        self.assertIn("populate", output)
