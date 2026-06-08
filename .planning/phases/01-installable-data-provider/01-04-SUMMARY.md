---
phase: 01-installable-data-provider
plan: "04"
subsystem: cache
tags: [parquet, query, filter, pathlib, pandas, deterministic, scope-check]

# Dependency graph
requires:
  - phase: 01-installable-data-provider
    plan: "01"
    provides: src/forexfactory/__init__.py (get() lazy import already wired to _query.run_query)
  - phase: 01-installable-data-provider
    plan: "01"
    provides: src/forexfactory/_pipeline.py (write_parquet reused for result file)
  - phase: 01-installable-data-provider
    plan: "02"
    provides: src/forexfactory/_cache.py (resolve_cache_dir, month_parquet_path, queries_dir, read_manifest, _scope_covers, ensure_dirs)
  - phase: 01-installable-data-provider
    plan: "03"
    provides: per-month parquet cache written by _populate.py (what run_query reads)

provides:
  - src/forexfactory/_query.py with run_query() — reads per-month parquets, filters, writes ONE consolidated result parquet, returns absolute Path
  - SC4 satisfied: forexfactory.get() returns pathlib.Path to filtered parquet
  - D-07/D-08: consolidated result parquet at deterministic filter-keyed path under queries_dir
  - D-09: out-of-scope request raises ValueError with actionable populate guidance
  - T-01-03: path-traversal guard in filename sanitization
  - tests/test_query.py with 12 tests covering all D-07/D-08/D-09/SC4/DATA-01 behaviors

affects:
  - 01-05 (cli.py query subcommand calls run_query and prints the returned path to stdout)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "run_query returns resolved absolute Path — library callers get pathlib.Path, CLI prints it"
    - "Deterministic result filename: sorted(currencies)__sorted(impacts)__start_end.parquet"
    - "_safe_token() strips non-alphanumeric/-hyphen chars from all filename components (T-01-03)"
    - "D-09 raises before any parquet reads — no partial/empty result file on scope miss"
    - "Empty manifest treated as no scope — any request raises ValueError"

key-files:
  created:
    - src/forexfactory/_query.py
    - tests/test_query.py
  modified: []

key-decisions:
  - "D-09 scope check implemented in Task 1 GREEN as Rule 2 (missing critical functionality) — it's the first guard inside run_query, executed before any parquet reads; no silent partial result ever written"
  - "_safe_token() uses re.sub([^a-zA-Z0-9-], '') to sanitize all filename tokens (T-01-03 path traversal guard)"
  - "Empty manifest (no 'scope' key) treated identically to out-of-scope — ValueError raised for any request"
  - "Candidate months sourced from manifest['months'] keys, not filesystem scan — avoids reading stale/deleted parquets"

patterns-established:
  - "Query pattern: resolve_cache_dir → ensure_dirs → read_manifest → scope_check → filter months → concat → filter df → write_parquet → return resolved Path"
  - "Scope error message format: '{C}/{I} not populated — run: forexfactory populate --currency {C} --impact {I}'"

requirements-completed: [PKG-02, PKG-03, CACHE-02, DATA-01]

# Metrics
duration: 8min
completed: 2026-06-08
---

# Phase 1 Plan 04: Query Engine Summary

**`_query.py` with `run_query()` — reads per-month cache parquets, applies currency/impact filter, writes ONE consolidated result parquet at a deterministic path, returns its absolute `pathlib.Path`; `forexfactory.get()` resolves through to it (SC4)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-08T09:47:10Z
- **Completed:** 2026-06-08T09:55:03Z
- **Tasks:** 2 (TDD: Task 1 RED+GREEN, Task 2 tests confirm existing behavior)
- **Files modified:** 2

## Accomplishments

- Implemented `src/forexfactory/_query.py` with `run_query(*, currencies, impacts, start, end, cache_dir) -> Path`: resolves cache dir, loads manifest, checks D-09 scope guard, iterates candidate months from manifest, reads per-month parquets, concats, filters by currency+impact, writes consolidated result parquet to deterministic path under `queries_dir`, returns `Path(...).resolve()`
- SC4 satisfied: `forexfactory.get(currencies=["USD"], impacts=["high"], cache_dir=...)` returns the identical `pathlib.Path` as `run_query` (lazy import in `__init__.py` from plan 01 resolved correctly)
- D-07/D-08: result parquet written to `queries/<currencies>__<impacts>__<start>_<end>.parquet`, overwritten on every call
- D-09: scope check raises `ValueError` before any reads when request exceeds populated scope; message contains `forexfactory populate --currency <C> --impact <I>` for each uncovered pair
- T-01-03: `_safe_token()` strips non-alphanumeric/-hyphen characters from all filename components
- D-10: all diagnostics via `logger`, no stdout output
- Created `tests/test_query.py` with 12 tests: 7 happy-path (Task 1) + 5 D-09 scope-error (Task 2)
- Full suite: 61 tests pass (49 prior + 12 new)

## Task Commits

1. **Task 1 RED — failing tests for run_query happy path** - `070c413` (test)
2. **Task 1 GREEN — implement _query.py** - `fc9b257` (feat)
3. **Task 2 — D-09 scope-error tests** - `451d902` (test)

_Note: Task 2 has no separate feat() commit — D-09 was implemented in Task 1 GREEN as Rule 2 (see Deviations)._

## Files Created/Modified

- `src/forexfactory/_query.py` — Query engine: DEFAULT_CURRENCIES/IMPACTS config; `_safe_token()` sanitizer; `_result_filename()` deterministic name builder; `_filter_months_by_range()` helper; `_raise_scope_error()` D-09 error builder; `run_query()`
- `tests/test_query.py` — 12-method regression suite: `QueryHappyPathTests` (7 tests) + `QueryScopeErrorTests` (5 tests)

## Decisions Made

- D-09 scope check implemented in Task 1 GREEN as Rule 2 missing-critical-functionality auto-fix: the guard is the first substantive line of `run_query`, before any parquet reads, making it impossible to accidentally produce a partial result file — it belongs logically in the same commit as the rest of `run_query`
- `_safe_token()` uses `re.sub(r"[^a-zA-Z0-9-]", "")` — strips any character that could be used for path traversal (T-01-03 mitigated)
- Empty manifest `{}` triggers D-09 identically to an out-of-scope manifest — any request against an unpopulated cache fails loudly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] D-09 scope check implemented in Task 1 GREEN**
- **Found during:** Task 1 implementation
- **Issue:** Plan sequenced D-09 scope check into Task 2. However, `run_query` must never produce a partial/empty result on a scope miss — D-09 is a correctness invariant of the function, not an additive feature. Deferring it would leave Task 1 GREEN in a state where out-of-scope queries silently produce empty parquets.
- **Fix:** Added `_raise_scope_error()` and the scope check at the top of `run_query` in the Task 1 GREEN commit (fc9b257).
- **Files modified:** `src/forexfactory/_query.py`
- **Verification:** `tests/test_query.py::QueryScopeErrorTests` — 5 tests pass; `tests/test_query.py::QueryHappyPathTests` — all 7 pass (no regression)
- **Committed in:** fc9b257 (Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality)
**Impact on plan:** D-09 behavior is identical to what Task 2 specified. Task 2's TDD RED tests confirmed the existing behavior rather than driving new implementation. No scope creep.

## Issues Encountered

None — Task 2 RED tests passed immediately because D-09 was already in place, which is expected after the Rule 2 auto-fix. Per TDD protocol "RED doesn't fail → investigate": investigation confirmed the feature exists and the tests are correct.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SC4 satisfied: `forexfactory.get()` returns a parquet `Path` (confirmed by test)
- D-07/D-08/D-09 all exercised and green (61 tests)
- `run_query` is the read-half of the walking skeleton; `_populate.py` is the write-half
- Ready for plan 01-05: `cli.py` — wire the `query` subcommand to call `run_query` and print the path to stdout (D-10); wire `populate` subcommand to `run_populate`

## Self-Check

- [x] `src/forexfactory/_query.py` exists on disk
- [x] `tests/test_query.py` exists on disk
- [x] Commits 070c413, fc9b257, 451d902 exist in git log
- [x] `python -m pytest tests/test_query.py -q` → 12 passed
- [x] `python -m pytest -q` → 61 passed (all prior tests still green)
- [x] `isinstance(result, pathlib.Path)` and `result.exists()` verified by test
- [x] DATA-01 columns confirmed: datetime_utc, currency, impact, title, id, leaked
- [x] D-09 ValueError raised with "forexfactory populate" in message
- [x] T-01-03: `_safe_token()` present in `_query.py`

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
