---
phase: 02-full-analytical-schema-source-spike
plan: 02
subsystem: query-filter
tags: [query, filter, cli, include_no_data, speeches, holidays, tdd, data-values]
requires: [02-01]
provides: [include_no_data-filter, PHASE2_COLUMNS-query-fallback, --include-no-data-flag, --force-flag]
affects: [_query.py, __init__.py, cli.py, test_query.py, test_cli.py]
tech_stack:
  added: []
  patterns: [query-time-default-filter, stale-cache-warn-and-continue, store_true-flag-kwarg-mirroring]
key_files:
  created: []
  modified:
    - src/forexfactory/_query.py
    - src/forexfactory/__init__.py
    - src/forexfactory/cli.py
    - tests/test_query.py
    - tests/test_cli.py
decisions:
  - "D-08 default predicate: hasDataValues==True OR impact=='holiday' — speeches hidden by default, holidays always visible"
  - "RESEARCH Pitfall 4 guard: if 'hasDataValues' in df.columns before filter; log warning on stale cache instead of raising KeyError"
  - "_DATA01_COLUMNS removed from _query.py; empty-df fallback uses _pipeline.PHASE2_COLUMNS (single source of truth per RESEARCH Pitfall 3)"
metrics:
  duration: 5min
  completed: "2026-06-08T20:31:17Z"
  tasks: 2
  files: 5
---

# Phase 02 Plan 02: include_no_data Filter + CLI Flags Summary

**One-liner:** Query-time `include_no_data=False` filter (hides speeches, keeps holidays by default), mirrored as `--include-no-data` CLI flag and `get(include_no_data=)` kwarg, plus `--force` populate flag wired to the 02-01 rebuild kwarg; `_DATA01_COLUMNS` replaced with `PHASE2_COLUMNS` in the empty-df fallback.

## What Was Built

### Task 1 — include_no_data filter in run_query + get(); PHASE2_COLUMNS fallback (TDD)

- Removed `_DATA01_COLUMNS` constant from `_query.py`; empty-df fallback now uses `_pipeline.PHASE2_COLUMNS` (prevents three-way staleness, RESEARCH Pitfall 3)
- Added `include_no_data: bool = False` keyword-only kwarg to `run_query()`
- D-08 default filter: `df = df[df["hasDataValues"] | (df["impact"] == "holiday")]` applied when `include_no_data=False`
- Stale-cache guard: `if "hasDataValues" in df.columns` — logs warning and skips filter when the column is absent (RESEARCH Pitfall 4 degrades gracefully, T-02-03 mitigated)
- Added `include_no_data=False` to `get()` in `__init__.py`; passes through to `run_query` (D-12)
- 5 new tests in `QueryIncludeNoDataTests`: default hides speeches, include_no_data=True surfaces speeches, holiday visible by default, stale cache degrades gracefully, get() forwarding

### Task 2 — --include-no-data (query) and --force (populate) CLI flags

- `cli.py` query subparser: `--include-no-data` store_true → `include_no_data=args.include_no_data` at dispatch
- `cli.py` populate subparser: `--force` store_true → `force=args.force` at dispatch
- `_FIXTURE_DAYS` in `test_cli.py` updated to include `hasDataValues: True` on NFP event (walking-skeleton end-to-end stays green after D-08 filter is active)
- All existing `fake_run_populate` / `fake_run_query` stubs in `CliRoutingTests` / `CliValidateMonthTests` updated to accept new kwargs (Rule 3 auto-fix — blocking signature mismatch)
- 4 new tests: `CliIncludeNoDataTests` (default hides speech, flag surfaces it), `CliForcePopulateTests` (--force forwarded as True, defaults False)

## Test Coverage

- `QueryIncludeNoDataTests`: 5 cases — default hides speeches, include_no_data=True, holiday visible, stale-cache graceful, get() forwarding
- `CliIncludeNoDataTests`: 2 cases — end-to-end default vs flag
- `CliForcePopulateTests`: 2 cases — force=True wired, force defaults False

**Final test count:** 128 passed (119 pre-plan + 9 new)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| ed9dc6e | test(RED) | Add failing tests for include_no_data filter (QueryIncludeNoDataTests) |
| 6d332c6 | feat(GREEN) | Add include_no_data filter to run_query and get(); use PHASE2_COLUMNS fallback |
| 050d055 | feat | Add --include-no-data (query) and --force (populate) CLI flags |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated fake function signatures in CliRoutingTests / CliValidateMonthTests**
- **Found during:** Task 2 implementation
- **Issue:** After adding `force=args.force` to the populate dispatch, existing test fakes `def fake_run_populate(*, currencies, impacts, start, end, raw_dir, cache_dir):` would receive an unexpected `force` keyword argument and raise TypeError. Similarly for `fake_run_query` missing `include_no_data`.
- **Fix:** Updated all fake function signatures to accept the new kwargs (`force` for populate fakes, `include_no_data` for query fakes).
- **Files modified:** `tests/test_cli.py`
- **Commit:** 050d055

## Known Stubs

None. All new kwargs (`include_no_data`, `force`) are fully wired from CLI flags through dispatch to service functions, with query-time filtering applied.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what is specified in the plan's threat model.

Implemented mitigations match the plan:
- T-02-03 (DoS/Info — stale cache KeyError): `if "hasDataValues" in df.columns` guard logs warning and skips filter — IMPLEMENTED
- T-02-04 (Tampering — CLI injection): New flags are `store_true` boolean only; no injectable strings — ACCEPTED (unchanged)

## Self-Check

### Modified files check
- `src/forexfactory/_query.py` — include_no_data kwarg present, _DATA01_COLUMNS absent, PHASE2_COLUMNS used, hasDataValues filter present
- `src/forexfactory/__init__.py` — include_no_data=False in get() signature, passed through to run_query
- `src/forexfactory/cli.py` — --include-no-data in query subparser, --force in populate subparser, both wired at dispatch
- `tests/test_query.py` — QueryIncludeNoDataTests with 5 test methods present
- `tests/test_cli.py` — _FIXTURE_DAYS has hasDataValues: True; CliIncludeNoDataTests + CliForcePopulateTests present

### Commits check
- ed9dc6e — confirmed (test RED)
- 6d332c6 — confirmed (feat GREEN)
- 050d055 — confirmed (feat Task 2)

### Test suite check
`python3 -m pytest tests/ -q` → 128 passed (no failures)

## Self-Check: PASSED
