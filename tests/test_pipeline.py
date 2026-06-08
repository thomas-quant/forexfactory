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


if __name__ == "__main__":
    unittest.main()
