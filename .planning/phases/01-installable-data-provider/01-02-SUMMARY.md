---
phase: 01-installable-data-provider
plan: "02"
subsystem: cache
tags: [pathlib, manifest, parquet, json, os.replace, atomic-write]

requires:
  - phase: 01-installable-data-provider
    plan: "01"
    provides: pip-installable forexfactory package skeleton (src layout, __init__.py)

provides:
  - src/forexfactory/_cache.py with all cache path helpers and manifest I/O
  - CACHE-01 satisfied: resolve_cache_dir with env + explicit arg override
  - D-01 month_parquet_path, D-03 raw_json_path, D-08 queries_dir path helpers
  - D-02 manifest.json atomic read/write with scope + per-month provenance
  - tests/test_cache.py with 16 test methods covering all cache behaviors

affects:
  - 01-03 (_populate.py calls resolve_cache_dir, month_parquet_path, update_manifest_month)
  - 01-04 (_query.py calls queries_dir, read_manifest, _scope_covers)
  - 01-05 (cli.py passes cache_dir through to populate/query/refresh)
  - 01-06 (_refresh.py calls raw_json_path, update_manifest_month, ensure_dirs)

tech-stack:
  added: []
  patterns:
    - "Atomic manifest write: write to tempfile.mkstemp then os.replace (no partial writes)"
    - "Warn-and-skip on corrupt manifest JSON (same pattern as pipeline.py load_days_files)"
    - "resolve_cache_dir: explicit arg > FOREXFACTORY_CACHE_DIR env > DEFAULT_CACHE_DIR"
    - "All cache sub-path helpers take cache_dir as first positional arg (no global state)"

key-files:
  created:
    - src/forexfactory/_cache.py
    - tests/test_cache.py
  modified: []

key-decisions:
  - "CACHE-01 implemented via resolve_cache_dir() — single override point; all callers use this function, never access DEFAULT_CACHE_DIR directly"
  - "manifest.json schema: top-level 'scope' + 'months' keys (D-02 from PATTERNS.md)"
  - "Atomic write uses tempfile.mkstemp in the same directory as the target to ensure os.replace is an atomic rename on the same filesystem"

patterns-established:
  - "Cache path resolution always goes through resolve_cache_dir(); no module hard-codes DEFAULT_CACHE_DIR"
  - "Manifest reads degrade to {} on missing/corrupt file; never raise"

requirements-completed: [CACHE-01]

duration: 2min
completed: 2026-06-08
---

# Phase 1 Plan 02: Cache Layer Summary

**`_cache.py` cache filesystem layout — deterministic path helpers (D-01/D-03/D-08), atomic manifest I/O (D-02), and CACHE-01 env/arg override — backed by 16 regression tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-08T09:37:37Z
- **Completed:** 2026-06-08T09:40:12Z
- **Tasks:** 2 (TDD: RED + GREEN each)
- **Files modified:** 2

## Accomplishments

- Implemented `src/forexfactory/_cache.py` with all path helpers and manifest contract: `resolve_cache_dir` (CACHE-01), `month_parquet_path` (D-01), `raw_json_path` (D-03), `queries_dir` (D-08), `manifest_path`, `ensure_dirs`, `read_manifest`, `write_manifest`, `update_manifest_month`, `_scope_covers`
- Manifest writes are atomic via `tempfile.mkstemp` + `os.replace`; reads degrade gracefully to `{}` on missing or corrupt JSON (warn-and-skip pattern from `pipeline.py`)
- Created `tests/test_cache.py` with `CacheTests` (16 test methods): covers default dir, env/arg override precedence, all path patterns, `ensure_dirs`, manifest round-trip, `update_manifest_month` provenance + scope, `_scope_covers` True/False cases
- Full suite: 35 tests pass (19 pre-existing + 16 new)

## Task Commits

TDD RED → GREEN per task:

1. **Task 1 RED — failing tests for _cache behavior** - `f63dce7` (test)
2. **Task 1 GREEN — implement _cache.py** - `d7f1d88` (feat)
3. **Task 2 — complete test_cache.py (16 methods)** - `9f81067` (feat)

## Files Created/Modified

- `src/forexfactory/_cache.py` — Cache path resolution + manifest read/write/scope helpers
- `tests/test_cache.py` — 16-method regression suite for all cache behaviors

## Decisions Made

- Atomic write uses `tempfile.mkstemp` in the **same directory** as the target manifest, ensuring `os.replace` is an atomic rename on the same filesystem (cross-filesystem moves are not atomic)
- `resolve_cache_dir` is the single CACHE-01 override point; callers never read `DEFAULT_CACHE_DIR` directly
- `_scope_covers` is a private helper (leading underscore) since it is only called by populate and query layers

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CACHE-01 satisfied: `~/.cache/forexfactory` default with env + arg override, verified by tests
- D-01/D-02/D-03/D-08 path and manifest contracts are in place for plans 03 (_populate), 04 (_query), 06 (_refresh)
- Ready for plan 01-03: populate layer (`_populate.py`)

## Self-Check

- [x] `src/forexfactory/_cache.py` exists on disk
- [x] `tests/test_cache.py` exists on disk
- [x] Commits f63dce7, d7f1d88, 9f81067 exist in git log
- [x] `python -m pytest tests/test_cache.py -q` → 16 passed
- [x] `python -m pytest -q` → 35 passed (all existing tests still green)
- [x] Acceptance criteria Task 1: all 4 pass
- [x] Acceptance criteria Task 2: grep -c "def test_" → 16 (≥7)

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
