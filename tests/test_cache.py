"""
Regression tests for src/forexfactory/_cache.py.

Covers: path helpers, manifest round-trip, env override, ensure_dirs,
update_manifest_month, and scope-coverage logic.
"""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from forexfactory import _cache


class CacheTests(unittest.TestCase):
    """Cache path resolution, manifest I/O, and scope-coverage tests."""

    # ------------------------------------------------------------------
    # Default cache dir
    # ------------------------------------------------------------------

    def test_default_cache_dir_resolves_to_home_cache(self):
        expected = Path.home() / ".cache" / "forexfactory"
        self.assertEqual(_cache.DEFAULT_CACHE_DIR, expected)

    # ------------------------------------------------------------------
    # resolve_cache_dir — CACHE-01 override chain
    # ------------------------------------------------------------------

    def test_resolve_cache_dir_default(self):
        path = _cache.resolve_cache_dir()
        self.assertEqual(path, Path.home() / ".cache" / "forexfactory")

    def test_resolve_cache_dir_env_override(self):
        with patch.dict(os.environ, {"FOREXFACTORY_CACHE_DIR": "/tmp/ffc_env"}):
            path = _cache.resolve_cache_dir()
        self.assertEqual(path, Path("/tmp/ffc_env"))

    def test_resolve_cache_dir_explicit_arg_wins_over_env(self):
        with patch.dict(os.environ, {"FOREXFACTORY_CACHE_DIR": "/tmp/env_dir"}):
            path = _cache.resolve_cache_dir(Path("/tmp/explicit"))
        self.assertEqual(path, Path("/tmp/explicit"))

    # ------------------------------------------------------------------
    # Path helpers — D-01, D-03, D-08
    # ------------------------------------------------------------------

    def test_month_parquet_path_format(self):
        p = _cache.month_parquet_path(Path("/c"), date(2024, 3, 1))
        self.assertTrue(str(p).endswith("2024-03.parquet"))

    def test_raw_json_path_format(self):
        p = _cache.raw_json_path(Path("/c"), date(2024, 3, 1))
        self.assertTrue(str(p).endswith(os.path.join("raw", "days_2024_03.json")))

    def test_queries_dir_is_queries_subdir(self):
        p = _cache.queries_dir(Path("/c"))
        self.assertEqual(p, Path("/c/queries"))

    # ------------------------------------------------------------------
    # ensure_dirs
    # ------------------------------------------------------------------

    def test_ensure_dirs_creates_raw_and_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cache_dir = tmp_path / "cache"
            _cache.ensure_dirs(cache_dir)
            self.assertTrue((cache_dir / "raw").is_dir())
            self.assertTrue((cache_dir / "queries").is_dir())

    # ------------------------------------------------------------------
    # read_manifest + write_manifest round-trip — D-02
    # ------------------------------------------------------------------

    def test_read_manifest_returns_empty_on_missing_file(self):
        result = _cache.read_manifest(Path("/nonexistent-xyz-abc-99"))
        self.assertEqual(result, {})

    def test_write_and_read_manifest_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            manifest = {
                "scope": {"currencies": ["USD"], "impacts": ["high"]},
                "months": {
                    "2024-03": {"scraped_at": "2026-06-08T12:00:00Z", "settled": True}
                },
            }
            _cache.write_manifest(cache_dir, manifest)
            loaded = _cache.read_manifest(cache_dir)
        self.assertEqual(loaded, manifest)

    # ------------------------------------------------------------------
    # update_manifest_month — D-02 provenance
    # ------------------------------------------------------------------

    def test_update_manifest_month_records_scraped_at_and_settled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            result = _cache.update_manifest_month(
                cache_dir,
                date(2024, 3, 1),
                scraped_at="2026-06-08T10:00:00Z",
                settled=True,
                currencies=["USD"],
                impacts=["high"],
            )
        self.assertEqual(result["months"]["2024-03"]["scraped_at"], "2026-06-08T10:00:00Z")
        self.assertTrue(result["months"]["2024-03"]["settled"])

    def test_update_manifest_month_sets_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            result = _cache.update_manifest_month(
                cache_dir,
                date(2024, 3, 1),
                scraped_at="2026-06-08T10:00:00Z",
                settled=True,
                currencies=["EUR", "USD"],
                impacts=["holiday", "high"],
            )
        # Scope currencies/impacts should be sorted
        self.assertEqual(result["scope"]["currencies"], ["EUR", "USD"])
        self.assertEqual(result["scope"]["impacts"], ["high", "holiday"])

    # ------------------------------------------------------------------
    # _scope_covers — scope-miss detection
    # ------------------------------------------------------------------

    def test_scope_covers_true_when_all_requested_present(self):
        scope = {"currencies": ["USD", "EUR"], "impacts": ["high"]}
        self.assertTrue(_cache._scope_covers(scope, ["USD"], ["high"]))

    def test_scope_covers_false_missing_currency(self):
        scope = {"currencies": ["USD"], "impacts": ["high"]}
        self.assertFalse(_cache._scope_covers(scope, ["EUR"], ["high"]))

    def test_scope_covers_false_missing_impact(self):
        scope = {"currencies": ["USD"], "impacts": ["high"]}
        self.assertFalse(_cache._scope_covers(scope, ["USD"], ["medium"]))

    def test_scope_covers_false_empty_scope(self):
        self.assertFalse(_cache._scope_covers({}, ["USD"], ["high"]))


if __name__ == "__main__":
    unittest.main()
