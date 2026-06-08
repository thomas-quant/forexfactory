---
phase: 02-full-analytical-schema-source-spike
plan: 01
subsystem: etl-schema
tags: [schema, parsing, parquet, tdd, data-values]
requires: []
provides: [phase2-parquet-schema, _parse_value, PHASE2_COLUMNS, force-populate, schema_version]
affects: [_pipeline.py, _populate.py, _cache.py, test_pipeline.py, test_populate.py]
tech_stack:
  added: []
  patterns: [nullable-Int64-cast, float-nan-for-unparseable, PHASE2_COLUMNS-shared-constant, schema_version-stamp, force-kwarg-bypass]
key_files:
  created: []
  modified:
    - src/forexfactory/_pipeline.py
    - src/forexfactory/_populate.py
    - src/forexfactory/_cache.py
    - tests/test_pipeline.py
    - tests/test_populate.py
decisions:
  - "_parse_value returns float('nan') not None — guarantees float64 dtype inference for all-null columns (RESEARCH Pitfall 1)"
  - "pd.to_numeric(errors='coerce') pre-coercion before Int64 cast — handles string IDs in test fixtures gracefully"
  - "soloTitle dropped from title fallback chain — DATA-04 internal field"
  - "schema_version stamped only when populated_count or skipped_count > 0 — avoids bare manifest on all-empty runs"
metrics:
  duration: 7min
  completed: "2026-06-08T19:02:09Z"
  tasks: 2
  files: 5
---

# Phase 02 Plan 01: Widen Analytical Schema at ETL Choke Point Summary

**One-liner:** Full 19-field analytical schema (`_parse_value`, `PHASE2_COLUMNS`, widened `flatten_events`, nullable `Int64` dtypes, speech retention, `force=` rebuild, `schema_version` stamp) implemented via TDD across `_pipeline.py`, `_populate.py`, `_cache.py`.

## What Was Built

This plan is the foundational Phase-2 slice — every other Phase-2 thread builds on it.

### Task 1 — _parse_value + PHASE2_COLUMNS + widened flatten_events

- Added `_NUMERIC_RE` and `_SUFFIX_MAP` module-level constants to `_pipeline.py`
- Added `_parse_value(s: str) -> float`: regex-based, handles K/M/B/T suffixes, percent-as-fraction, signed values, always returns `float('nan')` on unparseable input (never `None`, never raises — D-02, T-02-01)
- Added `PHASE2_COLUMNS` constant (19-column list, `datetime_utc` first) importable by `_populate.py` and `_query.py` to prevent stale-column-list drift (RESEARCH Pitfall 3)
- Widened `flatten_events()` from 7-field to 20-field yield (date + time_utc as intermediates for datetime_utc, plus all 18 analytical columns)
- Dropped `soloTitle` from title fallback chain (DATA-04)
- Changed `id` fallback from `""` to `None` (enables Int64 nullable casting)
- Added `extrasaction="ignore"` to legacy `parse_json_to_csv` DictWriter (legacy CSV path still writes 7 columns, new fields silently ignored)

### Task 2 — Widened build_month_parquet + force= + schema_version

- Added `SCHEMA_VERSION = "2"` to `_cache.py` CONFIG block
- Added `INT_NULLABLE_COLS` constant to `_populate.py` CONFIG block
- Removed `should_keep_row` call from `build_month_parquet()` — speeches retained in cache per D-09 (definition stays intact in `_pipeline.py` for legacy `run_pipeline()` path)
- Replaced empty-df fallback column list with `_pipeline.PHASE2_COLUMNS` import
- Added nullable-Int64 cast loop after DataFrame construction (pre-coerces with `pd.to_numeric(errors='coerce')` to handle mixed-type id values safely — T-02-02)
- Added `force: bool = False` kwarg to `run_populate()`; wrapped skip-check in `if not force:`
- Added `schema_version` stamp in manifest after any populated/skipped run
- 35 new tests across `ParseValueTests`, `FlattenEventsWidenedTests`, `PopulatePhase2SchemaTests`

## Test Coverage

- `ParseValueTests`: 14 cases — percent-as-fraction, K/M/B/T suffixes, signed values, empty, angle-bracket `<0.10%`, non-numeric strings `Pass`/`Yes`, pipe-separated `1.34|2.6`, lowercase suffix, float-not-None return type
- `FlattenEventsWidenedTests`: 13 cases — all 20 source keys present, DATA-04 UI field exclusion, PHASE2_COLUMNS constant, soloTitle not used as fallback
- `PopulatePhase2SchemaTests`: 7 cases — Phase-2 column presence, `float64`/`bool`/`Int64` dtypes, speaks event retention (D-09), `force=True` overwrite, `schema_version` in manifest, SCHEMA_VERSION constant, force kwarg signature

**Final test count:** 115 passed (80 pre-plan + 35 new)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| caffc1e | test(RED) | Add failing tests for _parse_value and widened flatten_events |
| 0e5cdfe | feat(GREEN) | Add _parse_value, PHASE2_COLUMNS, widen flatten_events in _pipeline.py |
| a9334a8 | test(RED) | Add failing tests for Phase-2 populate changes |
| 503bd23 | feat(GREEN) | Widen build_month_parquet, add force= + schema_version, SCHEMA_VERSION |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-coerce with pd.to_numeric before Int64 cast**
- **Found during:** Task 2 GREEN implementation — first test run
- **Issue:** The `Int64` cast `df[col].astype("Int64")` raises `ValueError` when the column contains string values like `"cpi-1"` (used as id in existing test fixtures). Pandas cannot cast `object` dtype string to `Int64` directly.
- **Fix:** Wrapped each cast with `pd.to_numeric(df[col], errors='coerce').astype("Int64")` — non-numeric strings become `<NA>` (nullable Int64 null) instead of raising. This matches the RESEARCH "pd.to_numeric(errors='coerce') as fallback dtype normalizer" pattern exactly.
- **Files modified:** `src/forexfactory/_populate.py`
- **Commit:** 503bd23

### Docstring Update

Removed references to `should_keep_row` from the `build_month_parquet` docstring to satisfy the acceptance criteria grep check (`grep -n 'should_keep_row' _populate.py | grep -v '^#'` returns nothing). The docstring now describes the D-09 behavior without naming the removed function.

## Known Stubs

None. All 19 PHASE2_COLUMNS fields are wired from the raw JSON event dict through `flatten_events()` into the parquet.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what is specified in the plan's threat model. The implemented mitigations match the plan:
- T-02-01 (Tampering/DoS on _parse_value): bounded regex match, no eval/exec, never raises — IMPLEMENTED
- T-02-02 (Tampering on dtype enforcement): explicit Int64 cast with pre-coercion — IMPLEMENTED

## Self-Check

### Created files check
- `.planning/phases/02-full-analytical-schema-source-spike/02-01-SUMMARY.md` — this file

### Modified files check
- `src/forexfactory/_pipeline.py` — verified: `_parse_value`, `PHASE2_COLUMNS`, widened `flatten_events`, `extrasaction` all present
- `src/forexfactory/_populate.py` — verified: `INT_NULLABLE_COLS`, `force=` kwarg, `schema_version` stamp, no `should_keep_row` call
- `src/forexfactory/_cache.py` — verified: `SCHEMA_VERSION = "2"` present
- `tests/test_pipeline.py` — verified: `ParseValueTests` + `FlattenEventsWidenedTests` present
- `tests/test_populate.py` — verified: `PopulatePhase2SchemaTests` present

### Commits check
- caffc1e — confirmed in `git log`
- 0e5cdfe — confirmed in `git log`
- a9334a8 — confirmed in `git log`
- 503bd23 — confirmed in `git log`

### Test suite check
`python3 -m pytest tests/ -q` → 115 passed (no failures)

## Self-Check: PASSED
