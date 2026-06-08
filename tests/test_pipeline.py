import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import forexfactory._pipeline as pipeline


class PipelineParquetCompressionTests(unittest.TestCase):
    def test_csv_to_parquet_uses_zstd_level_3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            csv_path = tmp_path / "events.csv"
            parquet_path = tmp_path / "events.parquet"

            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["date", "time_utc", "currency", "impact", "title", "id"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2026-03-01",
                        "time_utc": "12:30:00",
                        "currency": "USD",
                        "impact": "high",
                        "title": "Non-Farm Payrolls",
                        "id": "nfp-1",
                    }
                )

            with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
                pipeline.csv_to_parquet(str(csv_path), str(parquet_path))

            _, kwargs = to_parquet.call_args
            self.assertEqual(kwargs["compression"], "zstd")
            self.assertEqual(kwargs["compression_level"], 3)

    def test_run_pipeline_uses_zstd_level_3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            in_dir = tmp_path / "out"
            in_dir.mkdir()
            out_path = tmp_path / "economic_events.parquet"

            days_path = in_dir / "days_2026_03.json"
            days_path.write_text(
                json.dumps(
                    [
                        {
                            "events": [
                                {
                                    "currency": "USD",
                                    "impactName": "high",
                                    "name": "CPI y/y",
                                    "dateline": 1772368200,
                                    "id": "cpi-1",
                                }
                            ]
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
                pipeline.run_pipeline(out_parquet=str(out_path), in_dir=str(in_dir))

            _, kwargs = to_parquet.call_args
            self.assertEqual(kwargs["compression"], "zstd")
            self.assertEqual(kwargs["compression_level"], 3)


class PipelineLeakedFieldTests(unittest.TestCase):
    def test_parse_json_to_csv_includes_leaked_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            in_dir = tmp_path / "out"
            in_dir.mkdir()
            csv_path = tmp_path / "parsed.csv"

            (in_dir / "days_2026_03.json").write_text(
                json.dumps(
                    [
                        {
                            "events": [
                                {
                                    "currency": "USD",
                                    "impactName": "high",
                                    "name": "CPI y/y",
                                    "dateline": 1772368200,
                                    "id": "cpi-1",
                                    "leaked": True,
                                }
                            ]
                        }
                    ]
                ),
                encoding="utf-8",
            )

            pipeline.parse_json_to_csv(in_dir=str(in_dir), out_csv=str(csv_path))

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["leaked"], "True")

    def test_run_pipeline_preserves_leaked_in_parquet_dataframe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            in_dir = tmp_path / "out"
            in_dir.mkdir()
            out_path = tmp_path / "economic_events.parquet"

            (in_dir / "days_2026_03.json").write_text(
                json.dumps(
                    [
                        {
                            "events": [
                                {
                                    "currency": "USD",
                                    "impactName": "high",
                                    "name": "CPI y/y",
                                    "dateline": 1772368200,
                                    "id": "cpi-1",
                                    "leaked": True,
                                }
                            ]
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
                pipeline.run_pipeline(out_parquet=str(out_path), in_dir=str(in_dir))

            df = to_parquet.call_args.args[0]
            self.assertIn("leaked", df.columns)
            self.assertEqual(df.loc[0, "leaked"], True)


class PipelineDedupTests(unittest.TestCase):
    def test_deduplicate_rows_collapses_duplicate_id_rows_to_one(self):
        """_deduplicate_rows keeps the last-seen row for duplicate (id, date, time_utc)."""
        rows = [
            {"id": "cpi-1", "date": "2026-03-01", "time_utc": "12:30:00", "currency": "USD", "impact": "high", "title": "CPI y/y", "leaked": None},
            {"id": "cpi-1", "date": "2026-03-01", "time_utc": "12:30:00", "currency": "USD", "impact": "high", "title": "CPI y/y", "leaked": None},
        ]
        result = pipeline._deduplicate_rows(rows)
        self.assertEqual(len(result), 1)
        # Result must be sorted by (date, time_utc, title)
        self.assertEqual(result[0]["id"], "cpi-1")

    def test_deduplicate_rows_sorts_by_date_time_title(self):
        """_deduplicate_rows returns rows sorted by (date, time_utc, title)."""
        rows = [
            {"id": "b", "date": "2026-03-01", "time_utc": "14:00:00", "currency": "USD", "impact": "high", "title": "Zeta", "leaked": None},
            {"id": "a", "date": "2026-03-01", "time_utc": "12:30:00", "currency": "USD", "impact": "high", "title": "Alpha", "leaked": None},
        ]
        result = pipeline._deduplicate_rows(rows)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "a")
        self.assertEqual(result[1]["id"], "b")

    def test_run_pipeline_reads_from_passed_in_dir(self):
        """run_pipeline(in_dir=...) reads JSON from the passed directory, not the global IN_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            in_dir = tmp_path / "custom_in"
            in_dir.mkdir()
            out_path = tmp_path / "economic_events.parquet"

            # Write a fixture month only in the passed in_dir (not IN_DIR global)
            (in_dir / "days_2026_03.json").write_text(
                json.dumps(
                    [
                        {
                            "events": [
                                {
                                    "currency": "USD",
                                    "impactName": "high",
                                    "name": "CPI y/y",
                                    "dateline": 1772368200,
                                    "id": "cpi-1",
                                }
                            ]
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
                pipeline.run_pipeline(out_parquet=str(out_path), in_dir=str(in_dir))

            # to_parquet was called, meaning data from in_dir reached the DataFrame
            self.assertTrue(to_parquet.called)
            df = to_parquet.call_args.args[0]
            self.assertGreater(len(df), 0)


class ParseValueTests(unittest.TestCase):
    """Unit tests for _pipeline._parse_value() — D-02 numeric parsing."""

    def test_percent_becomes_fraction(self):
        """4.3% -> 0.043 (percent divides by 100 per D-02)."""
        self.assertAlmostEqual(pipeline._parse_value("4.3%"), 0.043)

    def test_negative_percent_preserves_sign(self):
        """-10.7% -> -0.107 (sign preserved)."""
        self.assertAlmostEqual(pipeline._parse_value("-10.7%"), -0.107)

    def test_magnitude_suffix_K(self):
        """-27.4K -> -27400.0 (K = 1e3)."""
        self.assertAlmostEqual(pipeline._parse_value("-27.4K"), -27400.0)

    def test_magnitude_suffix_M(self):
        """8.79M -> 8790000.0 (M = 1e6)."""
        self.assertAlmostEqual(pipeline._parse_value("8.79M"), 8790000.0)

    def test_magnitude_suffix_B(self):
        """2.0B -> 2000000000.0 (B = 1e9)."""
        self.assertAlmostEqual(pipeline._parse_value("2.0B"), 2000000000.0)

    def test_magnitude_suffix_T(self):
        """1.89T -> 1890000000000.0 (T = 1e12)."""
        self.assertAlmostEqual(pipeline._parse_value("1.89T"), 1890000000000.0)

    def test_plain_number_passes_through(self):
        """50.8 -> 50.8 (no suffix, no percent)."""
        self.assertAlmostEqual(pipeline._parse_value("50.8"), 50.8)

    def test_empty_string_returns_nan(self):
        """Empty string -> float('nan'), NEVER raises, NEVER returns None."""
        import math
        result = pipeline._parse_value("")
        self.assertTrue(math.isnan(result))

    def test_whitespace_only_returns_nan(self):
        """Whitespace-only string -> float('nan')."""
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("   ")))

    def test_angle_bracket_returns_nan(self):
        """'<0.10%' -> float('nan') (angle bracket prefix — unparseable)."""
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("<0.10%")))

    def test_pass_string_returns_nan(self):
        """'Pass' -> float('nan') (non-numeric parliamentary/vote outcome)."""
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("Pass")))

    def test_yes_string_returns_nan(self):
        """'Yes' -> float('nan') (non-numeric treaty vote outcome)."""
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("Yes")))

    def test_pipe_separated_returns_nan(self):
        """'1.34|2.6' -> float('nan') (bond auction yield|bid-to-cover — pipe blocks match)."""
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("1.34|2.6")))

    def test_lowercase_suffix_k_handled(self):
        """Lowercase 'k' suffix is handled case-insensitively."""
        self.assertAlmostEqual(pipeline._parse_value("1.5k"), 1500.0)

    def test_returns_float_not_none(self):
        """_parse_value must return float('nan'), not Python None, for unparseable input."""
        result = pipeline._parse_value("")
        self.assertIsInstance(result, float, "_parse_value must return float, not None")


class FlattenEventsWidenedTests(unittest.TestCase):
    """Phase-2 schema fields present in flatten_events output (D-01/DATA-02/03/04)."""

    _EVENT = {
        "currency": "USD",
        "impactName": "High Impact Expected",
        "prefixedName": "US CPI y/y",
        "dateline": 1772368200,
        "id": 12345,
        "leaked": False,
        "forecast": "4.3%",
        "actual": "4.5%",
        "previous": "4.1%",
        "revision": "",
        "actualBetterWorse": 1,
        "revisionBetterWorse": 0,
        "ebaseId": 999,
        "country": "US",
        "hasDataValues": True,
        # UI/internal fields that MUST be dropped (DATA-04)
        "checker": "x",
        "soloTitle": "CPI",
        "siteId": 42,
    }

    def _flatten_one(self):
        days = [{"events": [self._EVENT]}]
        return list(pipeline.flatten_events(days))[0]

    def test_forecast_raw_is_verbatim_string(self):
        """forecast_raw is the verbatim FF string ('4.3%'), not the parsed number."""
        r = self._flatten_one()
        self.assertEqual(r["forecast_raw"], "4.3%")

    def test_forecast_parsed_is_fraction(self):
        """forecast == _parse_value(forecast_raw) == 0.043."""
        r = self._flatten_one()
        self.assertAlmostEqual(r["forecast"], 0.043)

    def test_actual_raw_is_verbatim_string(self):
        """actual_raw is verbatim '4.5%'."""
        r = self._flatten_one()
        self.assertEqual(r["actual_raw"], "4.5%")

    def test_previous_raw_is_verbatim_string(self):
        """previous_raw is verbatim '4.1%'."""
        r = self._flatten_one()
        self.assertEqual(r["previous_raw"], "4.1%")

    def test_revision_raw_empty_string_when_absent(self):
        """revision_raw is '' when the FF field is empty."""
        r = self._flatten_one()
        self.assertEqual(r["revision_raw"], "")

    def test_all_phase2_source_keys_present(self):
        """All source keys that produce the 19 PHASE2_COLUMNS must be in the yielded dict."""
        r = self._flatten_one()
        expected_keys = [
            "date", "time_utc", "currency", "impact", "title", "id", "leaked",
            "forecast_raw", "actual_raw", "previous_raw", "revision_raw",
            "forecast", "actual", "previous", "revision",
            "actualBetterWorse", "revisionBetterWorse", "ebaseId", "country", "hasDataValues",
        ]
        for key in expected_keys:
            self.assertIn(key, r, f"key '{key}' missing from flatten_events output")

    def test_ui_fields_not_in_output(self):
        """DATA-04: UI/internal fields (checker, soloTitle, siteId) must be absent."""
        r = self._flatten_one()
        self.assertNotIn("checker", r)
        self.assertNotIn("soloTitle", r)
        self.assertNotIn("siteId", r)

    def test_actual_better_worse_preserved(self):
        """actualBetterWorse integer value is passed through unchanged."""
        r = self._flatten_one()
        self.assertEqual(r["actualBetterWorse"], 1)

    def test_ebase_id_preserved(self):
        """ebaseId integer is passed through unchanged."""
        r = self._flatten_one()
        self.assertEqual(r["ebaseId"], 999)

    def test_has_data_values_true(self):
        """hasDataValues=True is preserved from the event dict."""
        r = self._flatten_one()
        self.assertTrue(r["hasDataValues"])

    def test_country_preserved(self):
        """country field is passed through from the event dict."""
        r = self._flatten_one()
        self.assertEqual(r["country"], "US")

    def test_phase2_columns_constant_exists(self):
        """PHASE2_COLUMNS constant is importable, starts with datetime_utc, and contains new fields."""
        self.assertTrue(hasattr(pipeline, "PHASE2_COLUMNS"))
        self.assertEqual(pipeline.PHASE2_COLUMNS[0], "datetime_utc")
        self.assertIn("forecast_raw", pipeline.PHASE2_COLUMNS)
        self.assertIn("hasDataValues", pipeline.PHASE2_COLUMNS)
        self.assertIn("ebaseId", pipeline.PHASE2_COLUMNS)
        self.assertIn("actualBetterWorse", pipeline.PHASE2_COLUMNS)

    def test_solo_title_not_used_as_title_fallback(self):
        """soloTitle must NOT be used as title fallback (it is in the DATA-04 drop list)."""
        # Event with soloTitle but NO prefixedName or name
        ev_no_name = {
            "currency": "USD",
            "impactName": "High Impact Expected",
            "dateline": 1772368200,
            "soloTitle": "Solo CPI",
            "id": 1,
            "hasDataValues": False,
        }
        days = [{"events": [ev_no_name]}]
        r = list(pipeline.flatten_events(days))[0]
        # soloTitle must not be used; fallback is empty string
        self.assertNotEqual(r["title"], "Solo CPI")


if __name__ == "__main__":
    unittest.main()
