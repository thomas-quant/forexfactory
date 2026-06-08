---
phase: 01-installable-data-provider
plan: "03"
subsystem: cache
tags: [parquet, manifest, populate, incremental, scope-aware, pandas, pyarrow]

requires:
  - phase: 01-installable-data-provider
    plan: "01"
    provides: src/forexfactory/_pipeline.py (flatten_events, _deduplicate_rows, should_keep_row, write_parquet)
  - phase: 01-installable-data-provider
    plan: "02"
    provides: src/forexfactory/_cache.py (resolve_cache_dir, month_parquet_path, update_manifest_month, _scope_covers)

provides:
  - src/forexfactory/_populate.py with run_populate() + build_month_parquet()
  - Per-month parquet cache from on-disk raw JSON, zero network (SC2 groundwork)
  - Incremental scope-aware skip and widened-scope rebuild (D-06)
  - SC5 / QUAL-03: empty/failed raw JSON retried, never permanently skipped
  - tests/test_populate.py with 14 tests (happy path + incremental + SC5)

affects:
  - 01-05 (cli.py wires forexfactory populate subcommand to run_populate)
  - 01-06 (_refresh.py reuses build_month_parquet for HTTP-fetched months)

tech-stack:
  added: []
  patterns:
    - "build_month_parquet() is the reusable per-month ETL unit; _refresh.py calls it too"
    - "D-06 skip-check: read_manifest once outside loop, skip only if _scope_covers returns True"
    - "SC5 / QUAL-03: empty days list increments empty counter, no manifest entry, always retried"
    - "settled flag: next-month anchor <= date.today() determines if month is fully in the past"
    - "glob + filename parse (days_YYYY_MM.json → date(year,month,1)) for D-05 all-months default"

key-files:
  created:
    - src/forexfactory/_populate.py
    - tests/test_populate.py
  modified: []

key-decisions:
  - "build_month_parquet extracted as a reusable function so _refresh.py (plan 06) can call it without duplicating ETL logic"
  - "Empty raw [] counted as 'empty', no manifest entry written — retried on every run (SC5 / QUAL-03)"
  - "D-06 skip: manifest.scope is read once before the loop, _scope_covers checks every requested currency+impact is covered"
  - "settled = first day of next month <= date.today() (strict past boundary, CACHE-04)"
  - "Bad JSON (JSONDecodeError) treated same as empty: warn+skip without raising (T-01-01 mitigation)"

patterns-established:
  - "Per-month parquet builder pattern: flatten → filter → dedup → should_keep_row → DataFrame → write_parquet"
  - "Incremental skip guard: read manifest once, check scope coverage before each month, never skip empty-raw months"

requirements-completed: [PKG-04, CACHE-02, CACHE-04, DATA-01, QUAL-03]

duration: 2min
completed: 2026-06-08
---

# Phase 1 Plan 03: Populate Cache Engine Summary

**`_populate.py` with `run_populate()` + `build_month_parquet()` — per-month parquet cache from on-disk raw JSON with zero network, incremental scope-aware skipping, and SC5 empty-raw retry guard**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-08T09:43:07Z
- **Completed:** 2026-06-08T09:45:59Z
- **Tasks:** 2 (TDD: RED + GREEN covering both tasks together)
- **Files modified:** 2

## Accomplishments

- Implemented `src/forexfactory/_populate.py` with `build_month_parquet()` (reusable per-month ETL: flatten/filter/dedup/should_keep_row/write_parquet) and `run_populate()` (globs raw dir, D-05 all-months default, optional start/end window, D-06 incremental skip, D-04 USD+high/holiday default scope, D-02 manifest provenance with settled+scraped_at, zero network calls)
- SC5 / QUAL-03 correct: empty raw `[]` increments `empty` counter, writes no manifest entry, so every subsequent `run_populate` re-attempts the month without permanent poisoning
- D-06 correct: month is skipped only when `_cache._scope_covers(manifest.scope, currencies, impacts)` returns True; widened scope triggers rebuild
- Created `tests/test_populate.py` with 14 tests across two classes (PopulateHappyPathTests + PopulateIncrementalTests): per-month parquet write, DATA-01 columns, manifest settled+scraped_at, default scope, EUR filtered out, all-months default, no curl_cffi, start/end narrowing, same-scope skip (mtime unchanged), widened-scope rebuild, empty counter, no manifest entry for empty, SC5 reprocess on second run, bad-JSON warn-and-skip
- Full suite: 49 tests pass (35 prior + 14 new)

## Task Commits

TDD RED → GREEN (both tasks covered together):

1. **Task 1+2 RED — failing tests** - `cebc842` (test)
2. **Task 1+2 GREEN — implement _populate.py** - `b9c9762` (feat)

## Files Created/Modified

- `src/forexfactory/_populate.py` — Populate engine: RAW_INPUT_DIR, DEFAULT_CURRENCIES, DEFAULT_IMPACTS config; `build_month_parquet()`; `run_populate()`; `_parse_month_str()` helper
- `tests/test_populate.py` — 14-method regression suite for all populate behaviors

## Decisions Made

- Extracted `build_month_parquet()` as a separate reusable function (not inlined in `run_populate`) because `_refresh.py` (plan 06) needs to call the same per-month ETL after a network fetch — avoids duplication
- Empty `[]` and bad-JSON (JSONDecodeError) both treated as `empty` (no manifest entry) so the SC5 invariant holds for both failure modes
- `settled` computed as `date(next_year, next_month, 1) <= date.today()` — the whole calendar month must be in the past, not just the anchor date

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SC2 groundwork complete: `run_populate` re-processes the existing `out/` months with zero HTTP (ready to wire into CLI in plan 05)
- SC5 satisfied: empty/failed raw is retried, not permanently skipped
- CACHE-02/CACHE-04/D-01/D-02/D-04/D-05/D-06 all exercised by tests
- `build_month_parquet` ready for reuse by `_refresh.py` in plan 06
- Ready for plan 01-04: `_query.py` (read per-month parquet, apply filter, write result parquet)

## Self-Check

- [x] `src/forexfactory/_populate.py` exists on disk
- [x] `tests/test_populate.py` exists on disk
- [x] Commits cebc842, b9c9762 exist in git log
- [x] `python -m pytest tests/test_populate.py -q` → 14 passed
- [x] `python -m pytest -q` → 49 passed (all existing tests still green)
- [x] `grep -c "curl_cffi" src/forexfactory/_populate.py` → 0
- [x] Manual acceptance check: parquet exists, columns {datetime_utc, currency, impact, title, id, leaked}, manifest has settled+scraped_at+scope

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
