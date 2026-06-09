---
phase: 03-cache-lifecycle
plan: "01"
subsystem: cache-lifecycle
tags: [force-refresh, cache, cli, library-api]
dependency_graph:
  requires: []
  provides: [force_refresh-kwarg-run_refresh, force_refresh-kwarg-run_populate, forexfactory.populate, cli-force-refresh-flag]
  affects: [src/forexfactory/_refresh.py, src/forexfactory/_populate.py, src/forexfactory/__init__.py, src/forexfactory/cli.py]
tech_stack:
  added: []
  patterns: [lazy-import-inside-function, early-return-delegation, scope-union-on-force-refresh]
key_files:
  created: []
  modified:
    - src/forexfactory/_refresh.py
    - src/forexfactory/_populate.py
    - src/forexfactory/__init__.py
    - src/forexfactory/cli.py
    - tests/test_refresh.py
    - tests/test_populate.py
    - tests/test_cli.py
decisions:
  - "force_refresh kwarg added after retry_delay in run_refresh; skip block guarded with 'if not force_refresh:'"
  - "run_populate force_refresh early-exits before disk loop, unions scope with manifest to avoid narrowing, delegates to run_refresh"
  - "forexfactory.populate() uses lazy import of _populate; raw_dir excluded from kwargs when None to preserve engine default"
  - "Populate CLI summary log branches on args.force_refresh to log fetched/skipped/failed vs populated/skipped/empty"
metrics:
  duration: 5min
  completed: "2026-06-09"
  tasks: 3
  files: 7
requirements: [CACHE-06]
---

# Phase 03 Plan 01: force-refresh vertical slice Summary

Force-refresh vertical slice (CACHE-06): `--force-refresh` flag on `populate` and `refresh` CLI commands, mirrored `force_refresh` library kwarg on `run_refresh`/`run_populate`, new `forexfactory.populate()` library entry point, and skip-bypass engine change enabling on-demand re-scrape and parquet overwrite.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add force_refresh skip-bypass to run_refresh | 36bc1db | _refresh.py, test_refresh.py |
| 2 | Route run_populate(force_refresh) to run_refresh + add forexfactory.populate() | a3561d1 | _populate.py, __init__.py, test_populate.py |
| 3 | Wire --force-refresh into CLI populate and refresh commands | 95ac961 | cli.py, test_cli.py, test_refresh.py |

## What Was Built

**`run_refresh(force_refresh=False)`** — New keyword-only param after `retry_delay`. When `True`, the per-month `if raw_path.exists() and raw_path.stat().st_size > 0` skip block is bypassed with `if not force_refresh:`, causing already-cached months to be re-scraped and their staged raw JSON and parquet overwritten. Module docstring updated to reflect CACHE-06 is now implemented. Default `False` is byte-for-byte unchanged (D-02).

**`run_populate(force_refresh=False)`** — New keyword-only param after `force`, clearly distinguished in docstring (D-01). When `True`, short-circuits before the disk-ingest loop: lazily imports `_refresh` (avoids `_refresh↔_populate` circular import), reads manifest, computes `effective_currencies/impacts` as sorted set-union of requested + existing manifest scope (prevents narrowing), then returns `_refresh.run_refresh(..., force_refresh=True)` directly — returning the `{"fetched","skipped","failed"}` dict (D-04). The disk-ingest path with `force_refresh=False` is unchanged.

**`forexfactory.populate()`** — New public library function in `__init__.py` with all `run_populate` kwargs plus `force_refresh`. Lazily imports `_populate` and delegates. `raw_dir` excluded from kwargs when `None` so the engine default applies. Returns the same dict as the engine (D-03).

**CLI `--force-refresh`** — `store_true` flag added to both `populate` and `refresh` subparsers with distinct help text. Populate dispatch: `force_refresh=args.force_refresh` threaded; summary log branches on `args.force_refresh` to log `fetched/skipped/failed` (D-04) vs `populated/skipped/empty`. Refresh dispatch: `force_refresh=args.force_refresh` threaded (refresh summary already logs `fetched/skipped/failed`).

**Tests** — 11 new tests added (128→139):
- `RefreshForceRefreshTests` (2): force_refresh=True calls session.get + fetched=1; force_refresh=False skips as before
- `PopulateForceRefreshTests` (5): force_refresh route returns correct dict; disk-ingest unchanged; parquet overwritten on force-refresh; library mirror returns correct dict; signature check
- `CliForceRefreshTests` (4): populate flag forwarded True/False; refresh flag forwarded True/False

Existing fake signatures in `test_cli.py` and `test_refresh.py` updated with `force_refresh=False` default to prevent TypeError (no behavior change).

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
PYTHONPATH=src python3 -m pytest -q
139 passed in 2.86s
```

Success criteria met:
- `run_refresh(force_refresh=True)` re-scrapes and overwrites cached months; `force_refresh=False` (default) unchanged
- `run_populate(force_refresh=True)` delegates to run_refresh and returns `fetched/skipped/failed` (D-04); disk-ingest default unchanged
- `forexfactory.populate(force_refresh=True, ...)` callable (D-03)
- CLI `populate` and `refresh` both accept `--force-refresh` and thread it correctly
- Full test suite passes (139 tests)

## Self-Check: PASSED

Files created/modified:
- [x] `src/forexfactory/_refresh.py` — exists
- [x] `src/forexfactory/_populate.py` — exists
- [x] `src/forexfactory/__init__.py` — exists
- [x] `src/forexfactory/cli.py` — exists
- [x] `tests/test_refresh.py` — exists
- [x] `tests/test_populate.py` — exists
- [x] `tests/test_cli.py` — exists

Commits verified:
- 36bc1db (Task 1)
- a3561d1 (Task 2)
- 95ac961 (Task 3)
