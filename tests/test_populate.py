"""
Tests for src/forexfactory/_populate.py — per-month populate engine.

Covers: happy path, default scope (D-04), all-months default (D-05),
        DATA-01 column schema, incremental skip (D-06), scope-aware rebuild,
        empty-raw reprocess (QUAL-03 / SC5).
"""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch, call


class PopulateHappyPathTests(unittest.TestCase):
    """Task 1 — happy path: per-month parquet + manifest provenance (D-01/D-02/D-04/D-05)."""

    def _write_raw(self, raw_dir: Path, year: int, month: int, events: list) -> Path:
        """Write a days_YYYY_MM.json fixture to raw_dir and return its path."""
        path = raw_dir / f"days_{year:04d}_{month:02d}.json"
        path.write_text(
            json.dumps([{"events": events}]),
            encoding="utf-8",
        )
        return path

    def _usd_high_event(self, dateline: int = 1772368200) -> dict:
        return {
            "currency": "USD",
            "impactName": "High Impact Expected",
            "name": "CPI y/y",
            "dateline": dateline,
            "id": "cpi-1",
            "leaked": False,
        }

    def _eur_high_event(self, dateline: int = 1772368200) -> dict:
        return {
            "currency": "EUR",
            "impactName": "High Impact Expected",
            "name": "ECB Rate Decision",
            "dateline": dateline,
            "id": "ecb-1",
            "leaked": False,
        }

    def test_writes_per_month_parquet(self):
        """run_populate writes a parquet file for each processed month (D-01)."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event()])

            result = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            parquet_path = cache_dir / "2026-03.parquet"
            self.assertTrue(parquet_path.exists(), "per-month parquet not written")
            self.assertEqual(result["populated"], 1)
            self.assertEqual(result["skipped"], 0)
            self.assertEqual(result["empty"], 0)

    def test_parquet_has_data01_columns(self):
        """Written parquet has exactly the DATA-01 columns: datetime_utc, currency, impact, title, id, leaked."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event()])

            _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            df = pd.read_parquet(cache_dir / "2026-03.parquet")
            self.assertIn("datetime_utc", df.columns)
            self.assertIn("currency", df.columns)
            self.assertIn("impact", df.columns)
            self.assertIn("title", df.columns)
            self.assertIn("id", df.columns)
            self.assertIn("leaked", df.columns)
            # date and time_utc must be merged, not present as raw columns
            self.assertNotIn("date", df.columns)
            self.assertNotIn("time_utc", df.columns)

    def test_manifest_has_settled_and_scraped_at(self):
        """Manifest entry for the populated month has settled + scraped_at (D-02/CACHE-04)."""
        import json
        from forexfactory import _populate, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event()])

            _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            manifest = _cache.read_manifest(cache_dir)
            self.assertIn("2026-03", manifest.get("months", {}))
            entry = manifest["months"]["2026-03"]
            self.assertIn("scraped_at", entry)
            self.assertIn("settled", entry)

    def test_manifest_scope_is_default_usd_high_holiday(self):
        """Default scope in manifest is currencies=[USD], impacts=[high, holiday] (D-04)."""
        from forexfactory import _populate, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event()])

            _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            manifest = _cache.read_manifest(cache_dir)
            scope = manifest.get("scope", {})
            self.assertEqual(scope.get("currencies"), ["USD"])
            self.assertCountEqual(scope.get("impacts", []), ["high", "holiday"])

    def test_eur_event_filtered_out_by_default_scope(self):
        """EUR events are filtered out when running with default scope (D-04)."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            # Only EUR event — parquet should have 0 rows under default scope
            self._write_raw(raw_dir, 2026, 3, [self._eur_high_event()])

            _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            # parquet exists but contains no rows
            parquet_path = cache_dir / "2026-03.parquet"
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                self.assertEqual(len(df), 0)

    def test_processes_all_months_by_default(self):
        """With no start/end, all days_*.json months are processed (D-05)."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 1, [self._usd_high_event(1769734800)])
            self._write_raw(raw_dir, 2026, 2, [self._usd_high_event(1772413200)])
            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event(1775004800)])

            result = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            self.assertEqual(result["populated"], 3)
            self.assertTrue((cache_dir / "2026-01.parquet").exists())
            self.assertTrue((cache_dir / "2026-02.parquet").exists())
            self.assertTrue((cache_dir / "2026-03.parquet").exists())

    def test_no_curl_cffi_import(self):
        """_populate.py does not import curl_cffi (no network, SC2)."""
        import forexfactory._populate as populate_module
        import ast, inspect

        src = inspect.getsource(populate_module)
        self.assertNotIn("curl_cffi", src, "_populate.py must not import curl_cffi")

    def test_start_end_narrows_months(self):
        """Providing start/end narrows the months processed (D-05 partial range)."""
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 1, [self._usd_high_event(1769734800)])
            self._write_raw(raw_dir, 2026, 2, [self._usd_high_event(1772413200)])
            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event(1775004800)])

            result = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                start="2026-02",
                end="2026-02",
            )

            self.assertEqual(result["populated"], 1)
            self.assertFalse((cache_dir / "2026-01.parquet").exists())
            self.assertTrue((cache_dir / "2026-02.parquet").exists())
            self.assertFalse((cache_dir / "2026-03.parquet").exists())


class PopulateIncrementalTests(unittest.TestCase):
    """Task 2 — incremental skip + scope-aware rebuild + SC5 empty-raw reprocess."""

    def _write_raw(self, raw_dir: Path, year: int, month: int, events: list) -> Path:
        path = raw_dir / f"days_{year:04d}_{month:02d}.json"
        path.write_text(
            json.dumps([{"events": events}]),
            encoding="utf-8",
        )
        return path

    def _usd_high_event(self, dateline: int = 1772368200) -> dict:
        return {
            "currency": "USD",
            "impactName": "High Impact Expected",
            "name": "CPI y/y",
            "dateline": dateline,
            "id": "cpi-1",
            "leaked": False,
        }

    def test_same_scope_rerun_skips_cached_month(self):
        """Second run_populate at same scope skips already-cached month (D-06)."""
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            self._write_raw(raw_dir, 2026, 3, [self._usd_high_event()])

            # First run — populates the month
            r1 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
            self.assertEqual(r1["populated"], 1)

            # Capture mtime of parquet before second run
            parquet_path = cache_dir / "2026-03.parquet"
            mtime_before = parquet_path.stat().st_mtime

            # Second run at same scope — should skip
            r2 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
            self.assertEqual(r2["skipped"], 1)
            self.assertEqual(r2["populated"], 0)

            # Parquet not rewritten
            mtime_after = parquet_path.stat().st_mtime
            self.assertEqual(mtime_before, mtime_after, "parquet was rewritten on skip")

    def test_widened_scope_rerun_rebuilds_month(self):
        """Run at a wider scope rebuilds a month that was cached at a narrower scope (D-06)."""
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            # USD + high event; also EUR event to see rebuild picks up EUR
            events = [
                self._usd_high_event(),
                {
                    "currency": "EUR",
                    "impactName": "High Impact Expected",
                    "name": "ECB Rate",
                    "dateline": 1772368200,
                    "id": "ecb-1",
                    "leaked": False,
                },
            ]
            self._write_raw(raw_dir, 2026, 3, events)

            # First run: narrow scope — USD only, high only
            r1 = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD"],
                impacts=["high"],
            )
            self.assertEqual(r1["populated"], 1)

            # Second run: wider scope — add EUR and holiday
            r2 = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD", "EUR"],
                impacts=["high", "holiday"],
            )
            self.assertEqual(r2["populated"], 1, "widened scope must rebuild the month")
            self.assertEqual(r2["skipped"], 0)

    def test_empty_raw_increments_empty_counter(self):
        """A days_*.json with empty list [] increments empty counter (not populated/skipped)."""
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            # Write empty raw file
            (raw_dir / "days_2026_04.json").write_text("[]", encoding="utf-8")

            result = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            self.assertEqual(result["empty"], 1)
            self.assertEqual(result["populated"], 0)
            self.assertEqual(result["skipped"], 0)

    def test_empty_raw_not_recorded_in_manifest(self):
        """Empty raw JSON must not produce a manifest entry (SC5 / QUAL-03)."""
        from forexfactory import _populate, _cache

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            (raw_dir / "days_2026_04.json").write_text("[]", encoding="utf-8")

            _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            manifest = _cache.read_manifest(cache_dir)
            months = manifest.get("months", {})
            self.assertNotIn("2026-04", months, "empty raw must not produce manifest entry")

    def test_empty_raw_reprocessed_on_second_run(self):
        """After an empty raw month, two successive run_populate calls both ATTEMPT the month (SC5).

        The month is never permanently skipped because it has no manifest entry.
        """
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            (raw_dir / "days_2026_04.json").write_text("[]", encoding="utf-8")

            # Both runs should count it as empty (attempted, not skipped)
            r1 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
            r2 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))

            self.assertEqual(r1["empty"], 1, "first run should count empty month")
            self.assertEqual(r2["empty"], 1, "second run must also attempt (not skip) empty month")
            self.assertEqual(r1["skipped"], 0)
            self.assertEqual(r2["skipped"], 0)

    def test_bad_json_warned_and_skipped(self):
        """A days_*.json with invalid JSON is warned and skipped (T-01-01 threat mitigation)."""
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            (raw_dir / "days_2026_05.json").write_text("{not valid json}", encoding="utf-8")

            # Should not raise; bad JSON file is skipped
            result = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
            # Bad JSON treated as empty (no events extractable)
            self.assertEqual(result["populated"], 0)

    def test_wider_scope_rebuilds_all_months_not_just_first(self):
        """BL-01 regression: wider-scope rebuild must rebuild ALL months, not only the first.

        Before the fix, after successfully rebuilding month-1 the in-memory
        manifest scope was replaced with the new (wider) scope, causing the
        skip-check on month-2 to see a fully-covering scope and silently skip
        it — leaving month-2 parquet with the OLD narrow-scope data.
        """
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            # Both months contain USD/high AND EUR/high events.
            events = [
                {
                    "currency": "USD",
                    "impactName": "High Impact Expected",
                    "name": "CPI y/y",
                    "dateline": 1772368200,
                    "id": "usd-1",
                    "leaked": False,
                },
                {
                    "currency": "EUR",
                    "impactName": "High Impact Expected",
                    "name": "ECB Rate",
                    "dateline": 1772368200,
                    "id": "eur-1",
                    "leaked": False,
                },
            ]
            (raw_dir / "days_2026_01.json").write_text(
                json.dumps([{"events": events}]), encoding="utf-8"
            )
            (raw_dir / "days_2026_02.json").write_text(
                json.dumps([{"events": events}]), encoding="utf-8"
            )

            # First run: narrow scope — USD/high only.
            r1 = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD"],
                impacts=["high"],
            )
            self.assertEqual(r1["populated"], 2)

            # Second run: wider scope — USD+EUR, high+holiday.
            r2 = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD", "EUR"],
                impacts=["high", "holiday"],
            )
            self.assertEqual(
                r2["populated"], 2,
                "BL-01: ALL months must be rebuilt on wider-scope run, not just the first",
            )
            self.assertEqual(r2["skipped"], 0)

            # Both parquets must contain EUR rows (proving they were rebuilt, not skipped).
            for month in ["2026-01", "2026-02"]:
                df = pd.read_parquet(cache_dir / f"{month}.parquet")
                eur_rows = df[df["currency"] == "EUR"]
                self.assertGreater(
                    len(eur_rows), 0,
                    f"BL-01: {month} parquet must contain EUR rows after wider-scope rebuild",
                )


class PopulateNullDatelineTests(unittest.TestCase):
    """WR-02 regression: holiday-class events with null datelines must not crash populate."""

    def test_null_dateline_holiday_event_does_not_crash(self):
        """WR-02: a holiday event with dateline=None becomes NaT instead of raising ParserError."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            # Holiday event with no dateline — to_iso returns ("", "") for these.
            holiday_event = {
                "currency": "USD",
                "impactName": "Holiday",
                "name": "Bank Holiday",
                "dateline": None,
                "id": "holiday-1",
                "leaked": False,
            }
            (raw_dir / "days_2026_03.json").write_text(
                json.dumps([{"events": [holiday_event]}]), encoding="utf-8"
            )

            # Must not raise; previously pd.to_datetime(" ", utc=True) raised ParserError.
            result = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD"],
                impacts=["holiday"],
            )
            self.assertEqual(result["populated"], 1)

            df = pd.read_parquet(cache_dir / "2026-03.parquet")
            self.assertEqual(len(df), 1, "holiday row should be in the parquet")
            # The datetime_utc column must exist and the row's value must be NaT.
            self.assertIn("datetime_utc", df.columns)
            self.assertTrue(
                pd.isna(df["datetime_utc"].iloc[0]),
                "null-dateline row must have NaT in datetime_utc",
            )

    def test_zero_dateline_holiday_event_does_not_crash(self):
        """WR-02: a holiday event with dateline=0 (falsy) becomes NaT instead of crashing."""
        import pandas as pd
        from forexfactory import _populate

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_dir = tmp_path / "raw"
            raw_dir.mkdir()
            cache_dir = tmp_path / "cache"
            cache_dir.mkdir()

            holiday_event = {
                "currency": "USD",
                "impactName": "Holiday",
                "name": "New Year",
                "dateline": 0,
                "id": "ny-1",
                "leaked": False,
            }
            (raw_dir / "days_2026_01.json").write_text(
                json.dumps([{"events": [holiday_event]}]), encoding="utf-8"
            )

            result = _populate.run_populate(
                cache_dir=cache_dir,
                raw_dir=str(raw_dir),
                currencies=["USD"],
                impacts=["holiday"],
            )
            self.assertEqual(result["populated"], 1)

            df = pd.read_parquet(cache_dir / "2026-01.parquet")
            self.assertEqual(len(df), 1)
            self.assertTrue(
                pd.isna(df["datetime_utc"].iloc[0]),
                "zero-dateline row must have NaT in datetime_utc",
            )


if __name__ == "__main__":
    unittest.main()
