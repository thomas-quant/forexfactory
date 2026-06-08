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
            }
        ]
    }
]


class SkeletonEndToEndTests(unittest.TestCase):

    def test_populate_then_query_returns_valid_parquet_path(self):
        """install→populate(on-disk JSON)→query→pd.read_parquet succeeds (SC2, SC3)."""
        with tempfile.TemporaryDirectory() as raw_dir_str:
            with tempfile.TemporaryDirectory() as cache_dir_str:
                raw_dir = pathlib.Path(raw_dir_str)
                cache_dir = pathlib.Path(cache_dir_str)

                # Write one real-shaped USD/high fixture month (zero HTTP, SC2)
                (raw_dir / "days_2026_03.json").write_text(
                    json.dumps(_FIXTURE_DAYS), encoding="utf-8"
                )

                # Populate from raw dir — must make zero network calls (SC2)
                cli.main([
                    "populate",
                    "--raw-dir", str(raw_dir),
                    "--cache-dir", str(cache_dir),
                ])

                # Query — capture stdout; D-10 demands path-only output
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    cli.main([
                        "query",
                        "--currency", "USD",
                        "--impact", "high",
                        "--cache-dir", str(cache_dir),
                    ])

                output = buf.getvalue()
                non_empty_lines = [ln for ln in output.splitlines() if ln.strip()]

                # D-10: exactly one line on stdout
                self.assertEqual(
                    len(non_empty_lines), 1,
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
                usd_high = df[
                    (df["currency"] == "USD") & (df["impact"] == "high")
                ]
                self.assertGreater(
                    len(usd_high), 0,
                    "No USD/high rows found in query result parquet",
                )


# ─────────────────────────────────────────────────────────────────────────────
# CLI routing + contract tests (D-10, D-12, D-09, populate dispatch)
# ─────────────────────────────────────────────────────────────────────────────

class CliRoutingTests(unittest.TestCase):

    def test_query_repeatable_currency_flags_produce_list(self):
        """D-12: --currency USD --currency EUR yields currencies == ["USD", "EUR"]."""
        captured = {}

        def fake_run_query(*, currencies, impacts, start, end, cache_dir):
            captured["currencies"] = currencies
            captured["impacts"] = impacts
            return pathlib.Path("/tmp/fake.parquet")  # cli.main just prints it

        with patch.object(cli._query, "run_query", side_effect=fake_run_query):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main([
                    "query",
                    "--currency", "USD",
                    "--currency", "EUR",
                    "--impact", "high",
                ])

        self.assertEqual(captured["currencies"], ["USD", "EUR"])

    def test_query_prints_only_path_to_stdout(self):
        """D-10: query subcommand writes exactly the parquet path to stdout, nothing else."""
        fake_path = pathlib.Path("/tmp/fake_result.parquet")

        with patch.object(cli._query, "run_query", return_value=fake_path):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main(["query", "--currency", "USD", "--impact", "high"])

        output = buf.getvalue()
        non_empty = [ln.strip() for ln in output.splitlines() if ln.strip()]
        self.assertEqual(
            len(non_empty), 1,
            f"Expected exactly one line on stdout, got: {output!r}",
        )
        self.assertEqual(non_empty[0], str(fake_path))

    def test_query_out_of_scope_exits_code_1_with_stderr_guidance(self):
        """D-09: ValueError from run_query → sys.exit(1) with guidance message on stderr."""
        err_msg = (
            "EUR/medium not populated — run: forexfactory populate"
            " --currency EUR --impact medium"
        )

        with patch.object(cli._query, "run_query", side_effect=ValueError(err_msg)):
            buf_err = io.StringIO()
            with contextlib.redirect_stderr(buf_err):
                with self.assertRaises(SystemExit) as cm:
                    cli.main(["query", "--currency", "EUR", "--impact", "medium"])

        self.assertEqual(cm.exception.code, 1)
        stderr_text = buf_err.getvalue()
        self.assertIn("EUR", stderr_text)
        self.assertIn("forexfactory populate", stderr_text)

    def test_populate_routes_to_run_populate_with_forwarded_args(self):
        """populate subcommand routes to _populate.run_populate with correct args."""
        captured = {}

        def fake_run_populate(*, currencies, impacts, start, end, raw_dir, cache_dir):
            captured["currencies"] = currencies
            captured["raw_dir"] = raw_dir
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main([
                "populate",
                "--currency", "USD",
                "--impact", "high",
                "--raw-dir", "out",
            ])

        self.assertEqual(captured["currencies"], ["USD"])
        self.assertEqual(captured["raw_dir"], "out")

    def test_repeatable_impact_flags_produce_list(self):
        """D-12: --impact high --impact holiday yields impacts == ["high", "holiday"]."""
        captured = {}

        def fake_run_populate(*, currencies, impacts, start, end, raw_dir, cache_dir):
            captured["impacts"] = impacts
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main([
                "populate",
                "--impact", "high",
                "--impact", "holiday",
                "--raw-dir", "out",
            ])

        self.assertEqual(captured["impacts"], ["high", "holiday"])


class CliValidateMonthTests(unittest.TestCase):
    """WR-05: _validate_month must range-check the month integer to [1, 12]."""

    def test_month_99_exits_code_1(self):
        """'2024-99' must produce sys.exit(1) with an error message, not a traceback."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["populate", "--start", "2024-99", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_month_00_exits_code_1(self):
        """'2024-00' must produce sys.exit(1) with an error message, not a traceback."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["populate", "--end", "2024-00", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_month_13_exits_code_1(self):
        """'2024-13' must produce sys.exit(1) — 13 is out of the 1–12 range."""
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["populate", "--start", "2024-13", "--raw-dir", "out"])
        self.assertEqual(cm.exception.code, 1)

    def test_valid_month_does_not_exit(self):
        """A valid month string '2024-03' passes validation without sys.exit."""
        captured = {}

        def fake_run_populate(*, currencies, impacts, start, end, raw_dir, cache_dir):
            captured["start"] = start
            return {"populated": 0, "skipped": 0, "empty": 0}

        with patch.object(cli._populate, "run_populate", side_effect=fake_run_populate):
            cli.main(["populate", "--start", "2024-03", "--raw-dir", "out"])

        self.assertEqual(captured["start"], "2024-03")
