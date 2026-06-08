"""
Failing tests for _cache.py (RED phase — Task 1).

Covers the core behaviors specified in the plan's <behavior> block.
The comprehensive CacheTests class is added in Task 2.
"""
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from forexfactory import _cache


class CacheBehaviorTests(unittest.TestCase):
    """Minimal RED-phase tests for _cache behavior."""

    def test_resolve_cache_dir_default(self):
        path = _cache.resolve_cache_dir()
        self.assertEqual(path, Path.home() / ".cache" / "forexfactory")

    def test_resolve_cache_dir_env_override(self):
        with patch.dict(os.environ, {"FOREXFACTORY_CACHE_DIR": "/tmp/ffc_test"}):
            path = _cache.resolve_cache_dir()
        self.assertEqual(path, Path("/tmp/ffc_test"))

    def test_resolve_cache_dir_explicit_wins_over_env(self):
        with patch.dict(os.environ, {"FOREXFACTORY_CACHE_DIR": "/tmp/env_dir"}):
            path = _cache.resolve_cache_dir(Path("/tmp/explicit_dir"))
        self.assertEqual(path, Path("/tmp/explicit_dir"))

    def test_read_manifest_missing_returns_empty(self):
        result = _cache.read_manifest(Path("/nonexistent-xyz-abc"))
        self.assertEqual(result, {})

    def test_month_parquet_path_pattern(self):
        p = _cache.month_parquet_path(Path("/c"), date(2024, 3, 1))
        self.assertTrue(str(p).endswith("2024-03.parquet"))

    def test_raw_json_path_pattern(self):
        p = _cache.raw_json_path(Path("/c"), date(2024, 3, 1))
        self.assertTrue(str(p).endswith(os.path.join("raw", "days_2024_03.json")))

    def test_scope_covers_true(self):
        scope = {"currencies": ["USD", "EUR"], "impacts": ["high"]}
        self.assertTrue(_cache._scope_covers(scope, ["USD"], ["high"]))

    def test_scope_covers_false_currency(self):
        scope = {"currencies": ["USD"], "impacts": ["high"]}
        self.assertFalse(_cache._scope_covers(scope, ["EUR"], ["high"]))


if __name__ == "__main__":
    unittest.main()
