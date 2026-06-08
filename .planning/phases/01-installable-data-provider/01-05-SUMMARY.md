---
phase: 01-installable-data-provider
plan: "05"
subsystem: cli
tags: [argparse, cli, populate, query, subcommands, parquet, path-only-stdout]

requires:
  - phase: 01-installable-data-provider
    plan: "01"
    provides: pyproject.toml console-script forexfactory.cli:main declaration
  - phase: 01-installable-data-provider
    plan: "03"
    provides: src/forexfactory/_populate.py with run_populate() + RAW_INPUT_DIR
  - phase: 01-installable-data-provider
    plan: "04"
    provides: src/forexfactory/_query.py with run_query() + D-09 ValueError

provides:
  - src/forexfactory/cli.py with main(argv=None) dispatching populate and query subcommands
  - forexfactory populate subcommand wiring run_populate (zero HTTP, SC2)
  - forexfactory query subcommand wiring run_query + print(path) path-only stdout (D-10, SC3)
  - D-12 repeatable --currency/--impact append flags for both subcommands
  - D-09 ValueError catch + sys.exit(1) with guidance on stderr
  - CACHE-01 --cache-dir override forwarded to both services
  - tests/test_cli.py: SkeletonEndToEndTests (populate→query→parquet) + CliRoutingTests (5 unit tests)

affects:
  - 01-06 (_refresh.py adds the refresh subparser to the existing cli.py in plan 06)
  - 01-07 (README documents the CLI commands proven here)

tech-stack:
  added: []
  patterns:
    - "main(argv=None) -> int pattern: accept argv list for test injection (mirrors scrape.py)"
    - "action='append' argparse flags for repeatable --currency/--impact scope (D-12)"
    - "D-09 handled at CLI boundary: catch ValueError from run_query, print to stderr, sys.exit(1)"
    - "D-10 enforced: print(path) is the ONLY stdout write; all diagnostics go to logger"
    - "cache_dir forwarded as Path | None to services which call resolve_cache_dir internally"

key-files:
  created:
    - src/forexfactory/cli.py
    - tests/test_cli.py
  modified: []

key-decisions:
  - "D-10 enforced at cli.py boundary: only one print(path) on stdout; everything else uses logger"
  - "D-12: action='append' with default=None; services receive None or a list; service applies D-04 default when None"
  - "D-09: ValueError from run_query caught in main(), message to sys.stderr, sys.exit(1) — not re-raised"
  - "_validate_month: YYYY-MM validation with sys.exit(1) mirrors scrape.py date validation pattern"

patterns-established:
  - "CLI main() returns int 0 on success; sys.exit(1) for all error paths (never raises except via sys.exit)"
  - "SkeletonEndToEndTests: tempdir-seeded populate + captured-stdout query + pd.read_parquet assertion"

requirements-completed: [PKG-02, CACHE-01, CACHE-02, DATA-01]

duration: 5min
completed: 2026-06-08
---

# Phase 1 Plan 05: CLI — populate + query Subcommands Summary

**`cli.py` with `main(argv=None)` wiring `forexfactory populate` and `forexfactory query` subcommands end-to-end: D-10 path-only stdout, D-12 repeatable append flags, D-09 out-of-scope exit, and a walking-skeleton test proving install→populate→query→`pd.read_parquet`**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-08T09:58:00Z
- **Completed:** 2026-06-08T10:03:18Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Created `src/forexfactory/cli.py` with `main(argv=None) -> int`: top-level argparse with `add_subparsers(dest="command")`, populate + query subparsers, `--currency`/`--impact` with `action="append"` (D-12), `--start`/`--end` YYYY-MM validation with `sys.exit(1)`, `--cache-dir` CACHE-01 override, and `--raw-dir` for populate
- populate handler dispatches to `_populate.run_populate(currencies, impacts, start, end, raw_dir, cache_dir)` — zero HTTP (SC2)
- query handler dispatches to `_query.run_query(...)`, catches `ValueError` and exits code 1 with guidance on stderr (D-09), then `print(path)` to stdout only (D-10, SC3)
- Created `tests/test_cli.py` with 6 tests: `SkeletonEndToEndTests` (populate fixture → query → `pd.read_parquet` with DATA-01 columns and USD/high rows) + `CliRoutingTests` (5 unit tests covering D-12 append, D-10 path-only, D-09 non-zero exit with stderr, populate routing, impact append)
- Full suite: 67 tests pass (61 prior + 6 new); no regressions

## Task Commits

TDD RED → GREEN:

1. **Task 1 RED — failing skeleton + routing tests** - `223c0a0` (test)
2. **Task 2 GREEN — implement cli.py** - `2e347c9` (feat)

## Files Created/Modified

- `src/forexfactory/cli.py` — 177-line CLI: module docstring, logging setup, `_validate_month()`, `main()` with argparse subparsers, populate + query dispatch, D-10/D-12/D-09 all enforced
- `tests/test_cli.py` — 6 tests: `SkeletonEndToEndTests` (walking skeleton), `CliRoutingTests` (routing, D-10, D-12, D-09)

## Decisions Made

- Passed `currencies=None` / `impacts=None` through to services when flags are omitted — services apply the D-04 default (USD + high/holiday) internally rather than the CLI duplicating the default values
- `sys.exit(1)` for error paths (invalid month format, no subcommand, D-09 scope miss) — mirrors scrape.py pattern
- `_validate_month()` validates YYYY-MM by splitting on `-` and trying `int()` conversion; matches the scrape.py date-validation style without adding a new dependency

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ROADMAP Success Criteria 2 and 3 satisfied: `forexfactory populate` and `forexfactory query` work end-to-end; walking-skeleton test passes (67/67)
- D-10/D-12/D-09 verified by automated tests
- `cli.py` is ready for plan 01-06 to add the `refresh` subparser (only new subcommand needed; existing structure unchanged)
- Console-script entry point `forexfactory = "forexfactory.cli:main"` declared in plan 01 pyproject.toml now has a live implementation

## Self-Check

- [x] `src/forexfactory/cli.py` exists on disk
- [x] `tests/test_cli.py` exists on disk
- [x] Commits 223c0a0 (test) and 2e347c9 (feat) exist in git log
- [x] `python -m pytest tests/test_cli.py -q` → 6 passed
- [x] `python -m pytest -q` → 67 passed (all prior tests still green)
- [x] `grep -c "def main" src/forexfactory/cli.py` → 1
- [x] `grep -c "run_populate\|run_query" src/forexfactory/cli.py` → 3
- [x] `grep -c "print(" src/forexfactory/cli.py` → 2 (D-10 path + D-09 stderr guidance)
- [x] No stubs or TODOs in new files

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
