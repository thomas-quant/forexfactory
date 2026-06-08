---
phase: 02-full-analytical-schema-source-spike
plan: "05"
subsystem: data
tags: [parquet, pandas, cache, schema, raw-json, doc-regression]

requires:
  - phase: 02-full-analytical-schema-source-spike
    provides: "forexfactory populate --force, SC1/SC2 columns in _pipeline.py flatten_events, schema_version 2 cache"

provides:
  - "195-month parquet cache rebuilt at schema_version 2 with SC1/SC2 columns (forecast_raw/actual_raw/previous_raw/revision_raw, parsed numerics, actualBetterWorse/revisionBetterWorse/ebaseId/country/hasDataValues)"
  - "Raw JSON staging layer dropped (out/days_*.json deleted, ~/.cache/forexfactory/raw/ removed) — Phase-1 D-03 exit condition fulfilled"
  - "README parquet-schema table documents all Phase-2 columns with types and descriptions"
  - "tests/test_docs.py doc-regression asserts Phase-2 columns + honest out/ framing"

affects: [phase-03-cache-lifecycle]

tech-stack:
  added: []
  patterns:
    - "Doc-regression: test_docs.py asserts README schema table covers all canonical columns; keeps doc honest on schema evolution"

key-files:
  created:
    - .planning/phases/02-full-analytical-schema-source-spike/02-05-SUMMARY.md
  modified:
    - README.md
    - tests/test_docs.py

key-decisions:
  - "D-03 exit condition fulfilled: out/days_*.json (195 files) deleted and ~/.cache/forexfactory/raw/ removed after SC1/SC2 spot-verification of rebuilt parquets; approved by user at Task 2 checkpoint"
  - "out/ framed as optional raw-staging dir in README project-structure chart (populated on re-scrape, empty after populate-only build); doc-regression updated to match"

patterns-established:
  - "JSON-drop gating: irreversible data deletion is always gated behind a blocking human-verify checkpoint that fires only after full rebuild + dtype/column spot-verification"

requirements-completed: [DATA-02, DATA-03, DATA-04]

duration: 10min
completed: 2026-06-08
---

# Phase 02 Plan 05: Drop Raw JSON Staging Layer + Doc Regression

**195-month parquet cache rebuilt at schema_version 2, raw JSON staging dropped per D-03 exit, README + test_docs.py updated to honest post-drop layout**

## Performance

- **Duration:** ~10 min (continuation after human-verify checkpoint)
- **Started:** 2026-06-08T20:36:46Z (Task 1 commit)
- **Completed:** 2026-06-08T20:46:32Z (Task 3 commit)
- **Tasks:** 3 (Task 1 auto, Task 2 human-verify checkpoint, Task 3 auto)
- **Files modified:** 2 (README.md, tests/test_docs.py)

## Accomplishments

- Dropped 195 `out/days_*.json` files and `~/.cache/forexfactory/raw/` per the locked Phase-1 D-03 exit condition (after user approval at Task 2 checkpoint)
- README project-structure chart updated to frame `out/` as optional raw-staging dir (populated on re-scrape) rather than claiming live JSON files are present
- `tests/test_docs.py` doc-regression updated to match new repo layout: removed stale `days_YYYY_MM.json` / `...` assertions, added `re-scrape` framing check
- Full 128-test suite green after changes; durable 195-parquet cache + manifest.json (schema_version "2") completely intact

## Task Commits

Each task was committed atomically:

1. **Task 1: Rebuild cache to wide schema, spot-verify SC1/SC2, update docs** - `f593dbd` (docs)
2. **Task 2: Human-verify checkpoint** - (no commit; resolved by user approval)
3. **Task 3: Drop raw JSON staging layer** - `0973679` (chore)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `/mnt/e/backup/code/Finance/misc/Forexfactory/README.md` — project-structure chart: `out/` entry simplified to one-line comment "optional raw-staging dir (populated on re-scrape)"
- `/mnt/e/backup/code/Finance/misc/Forexfactory/tests/test_docs.py` — removed `days_YYYY_MM.json` + `...` assertions from `test_project_structure_chart_uses_plain_ascii_and_matches_repo_layout`; added `re-scrape` framing check

## Decisions Made

- **D-03 exit fulfilled:** User explicitly approved irreversible deletion at Task 2 checkpoint after the orchestrator independently spot-verified SC1/SC2 columns, dtypes, and schema_version "2" on 2024-03, 2025-03, 2010-01 sample parquets. Decision was locked per Phase-1 D-03 carry-forward.
- **out/ framing:** Rather than deleting the `out/` directory entry from the README chart (it is still a valid re-scrape target), the entry was simplified to a one-line comment making it clear the directory is empty after a populate-only build.

## Deviations from Plan

None — plan executed exactly as written. The doc-regression guard described in Task 3 was applied exactly as specified.

## Issues Encountered

None. The `~/.cache/forexfactory/raw/` directory was empty (as expected for a populate-only rebuild), so `rm -rf` was a no-op on files.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 2 is now **complete**: all DATA-02/03/04 requirements are materialized in the 195-month parquet cache at schema_version 2
- Phase 3 (cache-lifecycle) can proceed with the assumption that the durable cache is the only on-disk representation of the historical data; no raw JSON exists to fall back on
- The `out/` directory remains as a valid staging area if the user ever wants to re-scrape months (e.g., `forexfactory refresh` populates it again)

---
*Phase: 02-full-analytical-schema-source-spike*
*Completed: 2026-06-08*
