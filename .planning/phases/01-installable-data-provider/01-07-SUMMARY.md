---
phase: 01-installable-data-provider
plan: "07"
subsystem: testing
tags: [docs, readme, test_docs, regression, src-layout, schema, DATA-01]

requires:
  - phase: 01-installable-data-provider
    plan: "05"
    provides: src/forexfactory/cli.py (populate/query subcommands, D-10 path-only stdout)
  - phase: 01-installable-data-provider
    plan: "06"
    provides: src/forexfactory/_scrape.py + _refresh.py (refresh subcommand, D-11)

provides:
  - README.md rewritten for the packaged forexfactory provider (install/populate/query/refresh flow, DATA-01 schema, src-layout structure chart)
  - tests/test_docs.py updated to assert new src/forexfactory/ layout and DATA-01 schema columns
  - api.txt removed (stale scratch note)

affects: []

tech-stack:
  added: []
  patterns:
    - "Structure chart uses combined src/forexfactory/ path (single-child src/ collapsed to one line) so 'src/forexfactory' is a contiguous substring for automated verification"

key-files:
  created: []
  modified:
    - README.md
    - tests/test_docs.py
  deleted:
    - api.txt

key-decisions:
  - "src/forexfactory/ shown as combined path in structure chart (not split into src/ + forexfactory/) so the plan's verify command 'src/forexfactory' in t passes as a contiguous substring"
  - "out/ kept in structure chart as last top-level item (still the raw JSON input for populate); economic_events.parquet dropped (superseded by cache)"

patterns-established:
  - "Doc regression test asserts both layout substrings and schema column rows; failure pinpoints exactly which section diverged from reality"

requirements-completed: [PKG-01, PKG-02, DATA-01]

duration: 5min
completed: 2026-06-08
---

# Phase 1 Plan 07: Docs Alignment + Doc-Regression Gate Summary

**README rewritten for the packaged `forexfactory` CLI (populate/query/refresh), DATA-01 schema table, and `src/forexfactory/` structure chart; `test_docs.py` updated to assert new layout; `api.txt` removed; full 72-test suite green**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-08T10:23:54Z
- **Completed:** 2026-06-08T10:29:29Z
- **Tasks:** 2
- **Files modified:** 3 (README.md rewritten, tests/test_docs.py updated, api.txt deleted)

## Accomplishments

- Rewrote `README.md` for the package era: install (`pip install -e .`), populate (zero-HTTP, D-04 defaults, D-12 repeatable flags), query (D-10 path-only stdout with shell capture example, D-09 scope-miss guidance), refresh (D-11 network gap-fill); library API section, DATA-01 schema table, cache layout diagram, and `src/forexfactory/` structure chart replacing the stale loose-script layout
- Updated `tests/test_docs.py`: removed false assertions for `api.txt`, root `scrape.py`, root `pipeline.py`, `.gitignore`, `AGENTS.md`, `economic_events.parquet`; added assertions for `pyproject.toml`, `src/forexfactory/`, `__init__.py`, `cli.py`, `_scrape.py`, `tests/`, and expanded schema assertions to cover all DATA-01 columns
- Deleted `api.txt` via `git rm --ignore-unmatch`
- Full suite: 72/72 tests pass; no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite README for packaged provider** - `86aa0d4` (docs)
2. **Task 2: Update test_docs.py + remove api.txt** - `af55063` (fix)

## Files Created/Modified

- `README.md` — Full rewrite: install→populate→query→refresh quickstart, DATA-01 schema table, cache layout, src/forexfactory/ structure chart
- `tests/test_docs.py` — Structure chart and schema assertions updated to match new README (removed 6 stale assertions, added 10 new assertions)
- `api.txt` — Deleted (stale scratch note, no code consumer)

## Decisions Made

- Combined `src/forexfactory/` as a single line in the structure chart (rather than separate `src/` → `forexfactory/` levels) because `src/` has exactly one child and the plan's verify command required `'src/forexfactory' in t` as a contiguous substring
- Kept `out/` in the structure chart as the last top-level entry (still the raw JSON input that `populate` reads from); dropped `economic_events.parquet` (superseded by the `~/.cache/forexfactory/` cache)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Combined src/forexfactory/ path in structure chart**
- **Found during:** Task 1 (README rewrite)
- **Issue:** Plan's automated verify command checks `'src/forexfactory' in t` as a contiguous substring; initial two-level chart (`|-- src/` + `` |   `-- forexfactory/ ``) failed this check because the path was split across lines
- **Fix:** Combined to `|-- src/forexfactory/` on one line (valid for a single-child directory; no loss of information)
- **Files modified:** README.md
- **Verification:** `python -c "t=open('README.md').read(); assert 'src/forexfactory' in t"` exits 0
- **Committed in:** 86aa0d4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — verify command substring check)
**Impact on plan:** Minor cosmetic chart format; no content or behavior change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 is complete: all 7 plans executed, 72/72 tests pass
- README accurately documents the installed package and the full CLI workflow
- Doc-regression gate (`python -m pytest tests/test_docs.py -q`) passes
- api.txt removed; no stale docs remain
- Ready for Phase 2 (rich schema + API spike)

## Self-Check

- [x] `README.md` exists on disk and contains `pip install -e .`
- [x] `tests/test_docs.py` exists on disk and contains `src/forexfactory`
- [x] `api.txt` does not exist (`test ! -f api.txt` → OK)
- [x] Commits 86aa0d4 (docs) and af55063 (fix) exist in git log
- [x] `python -m pytest tests/test_docs.py -q` → 2 passed
- [x] `python -m pytest tests/ -q` → 72 passed

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
