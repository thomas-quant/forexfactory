---
phase: 01-installable-data-provider
plan: "01"
subsystem: packaging
tags: [pyproject.toml, setuptools, src-layout, pipeline, parquet, dedup]

requires: []
provides:
  - pip-installable forexfactory package (src layout, pyproject.toml)
  - src/forexfactory/__init__.py with get() -> Path contract
  - src/forexfactory/_pipeline.py (ETL engine, QUAL-01 + QUAL-02 fixed)
  - adapted tests/test_pipeline.py with QUAL regression tests
affects:
  - 01-02 (cache layer builds on the package skeleton)
  - 01-03 (populate uses _pipeline.py)
  - 01-04 (query implements _query.py, which get() delegates to)
  - 01-05 (CLI wires forexfactory.cli:main console-script)

tech-stack:
  added: [setuptools src-layout, pyproject.toml, pathlib.Path return type]
  patterns:
    - "Lazy import inside get() body keeps `import forexfactory` working before _query.py exists"
    - "git mv preserves pipeline.py history as src/forexfactory/_pipeline.py"
    - "_deduplicate_rows() single shared helper (QUAL-01) called by parse_json_to_csv and run_pipeline"
    - "run_pipeline(in_dir=...) parameter propagated through signature and main() (QUAL-02)"

key-files:
  created:
    - pyproject.toml
    - src/forexfactory/__init__.py
  modified:
    - src/forexfactory/_pipeline.py
    - tests/test_pipeline.py

key-decisions:
  - "D-13 honored: distribution name == import name == forexfactory; single console-script forexfactory.cli:main"
  - "Lazy import of _query inside get() body; module import succeeds without _query.py existing"
  - "git mv pipeline.py to preserve rename history in git log"
  - "No __all__ in __init__.py per project convention"

patterns-established:
  - "Lazy intra-package import defers resolution to call time (interface-first pattern)"
  - "QUAL fixes go in-place during relocation to avoid a second edit pass"

requirements-completed: [PKG-01, PKG-03, PKG-04, QUAL-01, QUAL-02, DATA-01]

duration: 3min
completed: 2026-06-08
---

# Phase 1 Plan 01: Package Skeleton + Pipeline Relocation Summary

**pip-installable `forexfactory` src-layout package with `get() -> Path` contract and ETL engine relocated from `pipeline.py` to `_pipeline.py` with QUAL-01 dedup helper and QUAL-02 `in_dir` parameter fixed**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-08T09:30:31Z
- **Completed:** 2026-06-08T09:33:52Z
- **Tasks:** 3
- **Files modified:** 4 (pyproject.toml created, src/forexfactory/__init__.py created, src/forexfactory/_pipeline.py relocated+edited, tests/test_pipeline.py adapted)

## Accomplishments

- Created `pyproject.toml` with setuptools src-layout, `requires-python = ">=3.12"`, runtime deps mirroring requirements.txt, and `forexfactory = "forexfactory.cli:main"` console-script (D-13)
- Created `src/forexfactory/__init__.py` with `get(*, currencies, impacts, start, end, cache_dir) -> Path` — lazy `_query` import inside the function body so `import forexfactory` exits 0 now (SC1)
- Relocated `pipeline.py` → `src/forexfactory/_pipeline.py` via `git mv` (history preserved); applied QUAL-01 (extracted `_deduplicate_rows()` shared helper, eliminating copy-paste in two sites) and QUAL-02 (`in_dir`/`keep_currencies`/`keep_impacts` parameters now propagated through `run_pipeline` and `main()`)
- Adapted `tests/test_pipeline.py`: updated import path, removed `patch.object(pipeline, "IN_DIR", ...)` wrappers (QUAL-02 proven by passing `in_dir=` directly), added `PipelineDedupTests` class with 3 new tests; 7/7 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml** - `b86725a` (feat)
2. **Task 2: Create src/forexfactory/__init__.py** - `159dbca` (feat)
3. **Task 3: Relocate pipeline.py -> _pipeline.py with QUAL-01 + QUAL-02 fixes** - `6169c10` (feat)

## Files Created/Modified

- `pyproject.toml` — Build system config, distribution metadata, console-script, src layout
- `src/forexfactory/__init__.py` — Package namespace, `get() -> Path`, `__version__ = "0.1.0"`, lazy `_query` import
- `src/forexfactory/_pipeline.py` — ETL engine (moved from root), `_deduplicate_rows()` helper, `run_pipeline(in_dir=...)` parameter
- `tests/test_pipeline.py` — Import updated; `in_dir` passed directly; 3 new `PipelineDedupTests` tests added

## Decisions Made

- Used `git mv` (not copy+delete) to preserve rename history in git log for `pipeline.py → _pipeline.py`
- Lazy import inside `get()` body is the simplest interface-first approach: `import forexfactory` succeeds now; `get()` fails only when called (plan 04 will implement `_query.py`)
- QUAL-01 and QUAL-02 fixes applied in-place during relocation to avoid a second edit pass on the same file

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ROADMAP Success Criterion 1 satisfied: `pip install -e .` exits 0 and `python -c "import forexfactory"` exits 0
- `forexfactory.get` callable with `Path` return annotation — ready for plan 04 (`_query.py`) to implement against
- QUAL-01 and QUAL-02 closed (verified by grep + 7/7 tests)
- Ready for plan 01-02: cache layer (`_cache.py`, `manifest.json`)

## Self-Check

- [x] `pyproject.toml` exists on disk
- [x] `src/forexfactory/__init__.py` exists on disk
- [x] `src/forexfactory/_pipeline.py` exists on disk
- [x] `tests/test_pipeline.py` updated and passing
- [x] Commits b86725a, 159dbca, 6169c10 exist in git log
- [x] `grep -c "def _deduplicate_rows" src/forexfactory/_pipeline.py` → 1
- [x] `grep -c "_deduplicate_rows(rows)" src/forexfactory/_pipeline.py` → 2
- [x] `python3 -m pytest tests/test_pipeline.py -q` → 7 passed

## Self-Check: PASSED

---
*Phase: 01-installable-data-provider*
*Completed: 2026-06-08*
