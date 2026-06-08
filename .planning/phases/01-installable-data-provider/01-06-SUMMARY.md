---
phase: 01-installable-data-provider
plan: "06"
subsystem: scraper
tags: [curl_cffi, scrape, refresh, network, parquet, manifest, QUAL-03, QUAL-04, D-11]

requires:
  - phase: 01-installable-data-provider
    plan: "03"
    provides: src/forexfactory/_populate.py (build_month_parquet — reused to build each scraped month)
  - phase: 01-installable-data-provider
    plan: "05"
    provides: src/forexfactory/cli.py (existing subparsers to extend with refresh)

provides:
  - src/forexfactory/_scrape.py (browserless scraper relocated from scrape.py with QUAL-03/QUAL-04/D-11 fixes)
  - src/forexfactory/_refresh.py (run_refresh — network gap-fill: raw JSON + parquet + manifest)
  - forexfactory refresh subcommand in cli.py (D-11/D-12 append flags)
  - tests/test_scrape.py adapted to new import + 1 new QUAL-03 test
  - tests/test_refresh.py with 4 tests (empty-scrape, skip-existing, full-pipeline, CLI routing)

affects:
  - 01-07 (README documents refresh command proven here)

tech-stack:
  added: []
  patterns:
    - "git mv scrape.py src/forexfactory/_scrape.py preserves rename history"
    - "QUAL-03 guard: if days: write file (else warn + fail_count); no empty JSON ever written"
    - "_refresh.run_refresh: check raw_json_path.exists() + size > 0 before calling scrape_month"
    - "FakeSession/FakeResponse injection pattern (from test_scrape.py) reused in test_refresh.py"
    - "between_pages_delay/retry_delay forwarded from CLI to run_refresh to scrape_month"

key-files:
  created:
    - src/forexfactory/_refresh.py
    - tests/test_refresh.py
  modified:
    - src/forexfactory/_scrape.py
    - src/forexfactory/cli.py
    - tests/test_scrape.py

key-decisions:
  - "QUAL-03 applied in both _scrape.run_scraper and _refresh.run_refresh: empty scrape writes nothing"
  - "QUAL-04: START_DATE/END_DATE constants removed; _scrape parse_args defaults to None; main() requires explicit dates"
  - "D-11: BETWEEN_PAGES_DELAY = RETRY_DELAY = 1.0 (was 0.0); gap-fill default range computed dynamically in _refresh"
  - "SRC-02: _refresh.run_refresh calls _scrape.scrape_month (not reimplementing the fragile parser)"
  - "skip-if-cached based on raw_json_path.exists() AND size > 0 (re-fetches stale empty files from pre-QUAL-03 runs)"

patterns-established:
  - "FakeSession injection in _refresh tests: pass session= kwarg; scrape_month is patchable"
  - "_refresh._compute_date_range: gap-fill = _add_month(latest_raw_month) → current month"

requirements-completed: [SRC-02, PKG-02, QUAL-03, QUAL-04]

duration: 5min
completed: 2026-06-08
---

# Phase 1 Plan 06: Refresh Network Slice Summary

**`_scrape.py` relocated (with QUAL-03/QUAL-04/D-11 fixes) and `_refresh.py` added — `forexfactory refresh` gap-fills the cache over the network, staging raw JSON and building per-month parquet without overwriting settled months**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-08T10:15:11Z
- **Completed:** 2026-06-08T10:20:44Z
- **Tasks:** 3 (each TDD RED → GREEN)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- Relocated `scrape.py` → `src/forexfactory/_scrape.py` via `git mv` (history preserved); applied three correctness fixes in-place: QUAL-03 (empty scrape writes no JSON file), QUAL-04 (removed stale 2021 date constants; `parse_args` defaults to `None`), D-11 (`BETWEEN_PAGES_DELAY = RETRY_DELAY = 1.0` polite default)
- Created `src/forexfactory/_refresh.py` with `run_refresh(...)`: resolves cache dir, computes gap-fill date range (last raw month + 1 → current month), skips already-cached months (size > 0 check), calls `_scrape.scrape_month` for missing months, stages raw JSON, calls `_populate.build_month_parquet`, records manifest entry; returns `{"fetched", "skipped", "failed"}`
- Added `refresh` subparser to `cli.py`: `--currency`/`--impact` append (D-12), `--start`/`--end`, `--cache-dir` (CACHE-01), `--between-pages-delay`/`--retry-delay` with 1.0s polite defaults
- `tests/test_scrape.py` adapted: import changed to `forexfactory._scrape`, delay default test updated to 1.0, new `test_run_scraper_does_not_write_file_on_empty_scrape` added
- `tests/test_refresh.py` (new, 4 tests): empty-scrape-no-write, skip-existing-no-network-call, fresh-month-full-pipeline (raw+parquet+manifest), CLI routing with D-12 append
- Full suite: 72 tests pass (67 prior + 5 new)

## Task Commits

TDD RED → GREEN per task:

1. **Task 1 RED — failing tests for QUAL-03 and D-11** - `779e06d` (test)
2. **Task 1 GREEN — QUAL-03/QUAL-04/D-11 fixes to _scrape.py** - `5cc6755` (feat)
3. **Task 2 RED — failing tests for _refresh.py** - `f6226e7` (test)
4. **Task 2 GREEN — implement _refresh.py** - `2f4a907` (feat)
5. **Task 3 GREEN — refresh subcommand in cli.py** - `e7ae234` (feat)

## Files Created/Modified

- `src/forexfactory/_scrape.py` — Relocated scraper; QUAL-03 write guard, QUAL-04 date defaults removed, D-11 polite delays (1.0s), updated docstring
- `src/forexfactory/_refresh.py` — Network gap-fill: `run_refresh()`, `_compute_date_range()`, `_latest_raw_month()`, `_add_month()`, `_is_settled()`, `_parse_month_str()`
- `src/forexfactory/cli.py` — Added `refresh` subparser + dispatch; imports `_refresh` and `_scrape`
- `tests/test_scrape.py` — Import updated; delay default test asserts 1.0; new QUAL-03 no-write test
- `tests/test_refresh.py` — 4 tests covering empty-scrape, skip-existing, fresh-month pipeline, CLI routing

## Decisions Made

- Applied QUAL-03 guard (`if days: write file`) in both `_scrape.run_scraper` and `_refresh.run_refresh` so either code path is safe
- The size > 0 skip-check in `_refresh` re-fetches any zero-byte files that a pre-QUAL-03 run may have written — ensures legacy empty files don't permanently block a month
- `_scrape.parse_args` dates default to `None`; `main()` checks and `sys.exit(1)` if absent — matches the pattern "require explicit dates rather than shipping a hardcoded window"
- Task 3 used the existing RED from the `test_refresh.py` file (CLI routing test written in Task 2 RED commit) rather than a separate RED commit — this is correct TDD sequencing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `grep -c "2021-01-01\|2021-06-30"` acceptance criterion initially returned 1 because I wrote the old date strings inside a comment. Fixed by rephrasing the comment to "stale hardcoded date defaults removed". No behavior impact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QUAL-03, QUAL-04, SRC-02, PKG-02 all closed and verified
- D-11 polite delay default and no-overwrite-of-cached-months behavior verified by tests
- `forexfactory refresh` is a real subcommand; the cache can extend past 2026-03 over the network
- Full suite: 72/72 tests pass; no regressions
- Ready for plan 01-07: README + test_docs.py (doc tests still reference old scrape.py structure)

## Self-Check

- [x] `src/forexfactory/_scrape.py` exists on disk
- [x] `src/forexfactory/_refresh.py` exists on disk
- [x] `tests/test_refresh.py` exists on disk
- [x] `scrape.py` no longer exists at repo root
- [x] `grep -c "2021-01-01\|2021-06-30" src/forexfactory/_scrape.py` → 0 (QUAL-04)
- [x] `python -c "import forexfactory._scrape as s; assert s.BETWEEN_PAGES_DELAY==1.0 and s.RETRY_DELAY==1.0"` exits 0 (D-11)
- [x] Commits 779e06d, 5cc6755, f6226e7, 2f4a907, e7ae234 in git log
- [x] `python -m pytest tests/ -q` → 72 passed
- [x] No live HTTP calls in tests (FakeSession/patch.object only)

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
