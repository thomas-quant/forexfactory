---
phase: 03-cache-lifecycle
plan: "02"
subsystem: cache-lifecycle
tags: [auto-fetch, matured-months, cache, cli, library-api, CACHE-05]
dependency_graph:
  requires: [force_refresh-kwarg-run_refresh]
  provides: [refresh_matured_months, auto_fetch-kwarg-run_query, auto_fetch-kwarg-run_populate, auto_fetch-kwarg-get, auto_fetch-kwarg-populate, cli-matured-banner]
  affects:
    - src/forexfactory/_refresh.py
    - src/forexfactory/_query.py
    - src/forexfactory/_populate.py
    - src/forexfactory/__init__.py
    - src/forexfactory/cli.py
tech_stack:
  added: []
  patterns: [lazy-import-inside-function, tdd-red-green, fail-open-stale-serve, progress-callback]
key_files:
  created: []
  modified:
    - src/forexfactory/_refresh.py
    - src/forexfactory/_query.py
    - src/forexfactory/_populate.py
    - src/forexfactory/__init__.py
    - src/forexfactory/cli.py
    - tests/test_refresh.py
    - tests/test_query.py
    - tests/test_populate.py
    - tests/test_cli.py
decisions:
  - "refresh_matured_months reads manifest scope once and re-fetches all matured months at full scope (D-08 no-cap)"
  - "D-10 fail-open: fetched==0 or failed>0 → logger.warning + continue; never raises"
  - "auto_fetch=False in callers gates the matured check; refresh_matured_months itself has no guard"
  - "run_query counts matured months from manifest before calling refresh_matured_months to drive D-12 progress banner"
  - "populate() and get() expose auto_fetch but not session/progress (D-11 library silent)"
  - "_print_progress maps event='matured' to D-12 banner string; 'scope_miss' added in 03-03"
metrics:
  duration: 8min
  completed: "2026-06-09"
  tasks: 3
  files: 9
requirements: [CACHE-05]
---

# Phase 03 Plan 02: matured-month auto-refresh vertical slice Summary

Matured-month auto-refresh vertical slice (CACHE-05): months scraped while future-dated (`settled: false`) that have since fully matured are automatically re-fetched on both `populate` and `query`/`get()` so their `actual` values fill in, with `auto_fetch=False` suppressing it and a failed re-fetch serving the stale (forecast-only, valid) cache and warning rather than crashing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Add failing tests for refresh_matured_months | c1b7e46 | tests/test_refresh.py |
| 1 GREEN | Implement refresh_matured_months helper | 81c52e8 | _refresh.py |
| 2 RED | Add failing tests for auto_fetch wiring | 5c8784b | tests/test_query.py, tests/test_populate.py |
| 2 GREEN | Wire auto_fetch into run_query, run_populate, get(), populate() | 57352d0 | _query.py, _populate.py, __init__.py, tests/ |
| 3 | CLI matured-months progress banner | 99d403c | cli.py, tests/test_cli.py |

## What Was Built

**`_refresh.refresh_matured_months(cache_dir, *, session, between_pages_delay, retry_delay) -> dict`** — New shared helper (CACHE-05 engine). Reads manifest once; collects all months with `settled=False` that now pass `_is_settled(anchor)`; re-fetches each at the full manifest scope (currencies/impacts union-merged with defaults) using `run_refresh(force_refresh=True)`. Returns `{"matured": N, "refreshed": M, "failed": F}`. D-08: all matured months in one call, no cap. D-10: if `run_refresh` returns `fetched==0` or `failed>0`, logs exactly one `logger.warning("[matured] re-fetch failed for ... — serving stale cached parquet")` and continues — never raises. When no matured months, returns immediately with zero counts and makes zero network calls.

**`run_query(auto_fetch=True, session=None, progress=None)`** — Three new keyword-only params. When `auto_fetch=True`, after manifest read a loop counts matured months (`settled=False` + `_is_settled` true). If count > 0: calls `progress("matured", count=count)` (if progress not None) BEFORE the re-fetch (D-12 banner precedes `[N/total]` log lines), then calls `refresh_matured_months`, then re-reads manifest so the scope check and parquet loop see refreshed state. The CACHE-05 block runs BEFORE the existing scope check (`_raise_scope_error`). `auto_fetch=False` skips the block entirely (D-07/D-09 strict cache-only). `_refresh` imported lazily inside the function to avoid circular import.

**`run_populate(auto_fetch=True, session=None)`** — Two new keyword-only params. When `auto_fetch=True and not force_refresh`, calls `_refresh.refresh_matured_months(resolved_cache, session=session)` once before the disk-ingest loop (D-08). No stdout output — D-11 reserves banners for the CLI query command. `auto_fetch=False` or `force_refresh=True` skips the matured check entirely.

**`forexfactory.get(auto_fetch=True)`** and **`forexfactory.populate(auto_fetch=True)`** — Both library entry points now expose `auto_fetch` and forward it to the engine. Neither exposes `session` or `progress` (D-11: library stays silent on stdout).

**`cli._print_progress(event, **kwargs)`** — New module-level helper in `cli.py`. Maps structured progress events to D-12 stdout banners: `event=="matured"` prints `"{count} months matured since last run — refreshing actuals..."`. The `scope_miss` branch will be added in 03-03 (CACHE-03). Passed as `progress=_print_progress` to `run_query` in the query dispatch so the banner fires before `[N/total]` log lines from `run_refresh`.

**Tests** — 13 new tests added (139→152):
- `RefreshMaturedMonthsTests` (3): re-fetched+parquet updated (SC2), no network when none matured, failed re-fetch serves stale + warns (D-10)
- `QueryAutoFetchTests` (5): auto_fetch=True matures, auto_fetch=False suppresses, progress callback fired+not fired, get(auto_fetch=False) forwarded
- `PopulateAutoFetchTests` (3): auto_fetch=True matures, auto_fetch=False suppresses, signature check
- `CliMaturedBannerTests` (2): banner+path when matured, path-only when settled

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing imports in test_query.py**
- **Found during:** Task 2 GREEN phase when running tests after RED commit
- **Issue:** Test file missing `from unittest.mock import patch` and `import math`; tests used `between_pages_delay/retry_delay` kwargs that `run_query` doesn't accept
- **Fix:** Added missing imports; removed unsupported kwargs from test calls (scrape_month is patched so delays are irrelevant)
- **Files modified:** tests/test_query.py
- **Commit:** 57352d0

**2. [Rule 1 - Bug] `curl_cffi` string in run_populate docstring**
- **Found during:** Task 2 GREEN — `test_no_curl_cffi_import` scans `inspect.getsource()` for literal `curl_cffi`
- **Issue:** Added `session: curl_cffi session to inject` in the docstring violated the existing test
- **Fix:** Changed to `session: HTTP session to inject into the matured re-fetch`
- **Files modified:** src/forexfactory/_populate.py
- **Commit:** 57352d0

## Verification

```
PYTHONPATH=src python3 -m pytest -q
152 passed in 3.14s
```

Success criteria met:
- `refresh_matured_months` re-fetches all matured months in one call at full scope (D-08)
- Failed re-fetch serves stale parquet + warns, never raises (D-10)
- `run_query(auto_fetch=True)` auto-matures; `auto_fetch=False` suppresses (D-07/D-09)
- `run_populate(auto_fetch=True)` auto-matures; `auto_fetch=False` suppresses (D-08/D-09)
- `get()`/`populate()` expose `auto_fetch`; library produces no stdout (D-11)
- CLI query prints D-12 matured banner before fetch progress (D-12)
- SC2 proven: future-dated months re-fetched with actuals on next populate or query

## Known Stubs

None — all implemented behavior is wired end-to-end.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond those already in the plan's threat model. T-03-04 (DoS via auto-triggered re-fetch) mitigated: delays inherited from `_scrape.BETWEEN_PAGES_DELAY`/`_scrape.RETRY_DELAY`; only naturally-small set of settled:false months triggers auto-fetch. T-03-05 (fail-open availability) mitigated: D-10 serve-stale path implemented.

## Self-Check: PASSED

Files modified (all exist):
- [x] `src/forexfactory/_refresh.py` — `refresh_matured_months` added
- [x] `src/forexfactory/_query.py` — `auto_fetch`, `session`, `progress` params added
- [x] `src/forexfactory/_populate.py` — `auto_fetch`, `session` params added
- [x] `src/forexfactory/__init__.py` — `auto_fetch` on `get()` and `populate()`
- [x] `src/forexfactory/cli.py` — `_print_progress` + query dispatch wired
- [x] `tests/test_refresh.py` — 3 new tests
- [x] `tests/test_query.py` — 5 new tests
- [x] `tests/test_populate.py` — 3 new tests
- [x] `tests/test_cli.py` — 2 new tests + 3 fake signatures updated

Commits verified:
- c1b7e46 (Task 1 RED)
- 81c52e8 (Task 1 GREEN)
- 5c8784b (Task 2 RED)
- 57352d0 (Task 2 GREEN)
- 99d403c (Task 3)
