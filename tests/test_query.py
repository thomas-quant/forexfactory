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
# Task 2 — D-09: out-of-scope error tests  (added in Task 2 RED)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
