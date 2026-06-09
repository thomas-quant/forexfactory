---
phase: 03-cache-lifecycle
plan: "03"
subsystem: cache-lifecycle
tags: [auto-widen, scope-miss, cache, cli, library-api, CACHE-03]
dependency_graph:
  requires: [force_refresh-kwarg-run_refresh, auto_fetch-kwarg-run_query, auto_fetch-kwarg-run_populate, cli-matured-banner]
  provides: [AutoFetchError, widen_scope_to_cover, scope-miss-auto-widen, cli-scope-miss-banner]
  affects:
    - src/forexfactory/_exceptions.py
    - src/forexfactory/_refresh.py
    - src/forexfactory/_query.py
    - src/forexfactory/cli.py
tech_stack:
  added: []
  patterns: [tdd-red-green, fail-closed-raise, lazy-import-inside-function, progress-callback]
key_files:
  created:
    - src/forexfactory/_exceptions.py
  modified:
    - src/forexfactory/_refresh.py
    - src/forexfactory/_query.py
    - src/forexfactory/cli.py
    - tests/test_refresh.py
    - tests/test_query.py
    - tests/test_cli.py
decisions:
  - "AutoFetchError(RuntimeError) in dedicated _exceptions.py — allows callers to catch specifically (Option B from PATTERNS.md)"
  - "widen_scope_to_cover wraps run_refresh exceptions as AutoFetchError; also raises if _scope_covers is False after run_refresh (D-06 fail-closed)"
  - "Scope-miss branch in run_query fires progress('scope_miss', ...) per uncovered pair BEFORE calling widen (D-12 banner ordering)"
  - "AutoFetchError caught before ValueError in CLI dispatch so widen failure gives clean exit-1, not traceback (D-06)"
  - "Existing QueryScopeErrorTests updated to auto_fetch=False to preserve D-09/D-07 raise semantics"
metrics:
  duration: 12min
  completed: "2026-06-09"
  tasks: 3
  files: 7
requirements: [CACHE-03]
---

# Phase 03 Plan 03: scope-miss auto-widen vertical slice Summary

Scope-miss auto-widen vertical slice (CACHE-03): when `query()`/`get()` detects a currency/impact combination absent from the manifest scope, `run_query(auto_fetch=True)` automatically fetches the full cached month range at the union scope via `widen_scope_to_cover()`, permanently widens the manifest, and returns matching rows — no manual `populate` step needed. SC1 is now fully proven.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Add failing tests for AutoFetchError and widen_scope_to_cover | 3902ceb | tests/test_refresh.py |
| 1 GREEN | Add AutoFetchError and widen_scope_to_cover | c65ed92 | _exceptions.py, _refresh.py |
| 2 RED | Add failing tests for scope-miss auto-widen in run_query | a298c3c | tests/test_query.py |
| 2 GREEN | Convert scope-miss path to conditional auto-widen | 5a2d0b5 | _query.py, tests/test_query.py |
| 3 | CLI prints scope-miss banner and surfaces AutoFetchError | cf4190b | cli.py, tests/test_cli.py |

## What Was Built

**`_exceptions.AutoFetchError(RuntimeError)`** — New module `src/forexfactory/_exceptions.py` with a single custom exception class. Allows callers to catch scope-miss widen failures specifically, separate from `ValueError` (user input errors) and `FileNotFoundError` (missing inputs).

**`_refresh.widen_scope_to_cover(cache_dir, currencies, impacts, *, session, between_pages_delay, retry_delay) -> None`** — New public helper in `_refresh.py`. Reads manifest to determine the full cached month range (`min..max` of manifest month keys; falls back to current month if cache is empty of months). Computes the union scope: `sorted(set(existing_scope.currencies) | set(currencies))` and same for impacts. Calls `run_refresh(force_refresh=True)` with the union scope across the full range. Wraps any `run_refresh` exception as `AutoFetchError`. After `run_refresh` returns, re-reads manifest and raises `AutoFetchError` if `_scope_covers` is still False (D-06 fail-closed, no partial data). On success the manifest scope is permanently widened (via `update_manifest_month`'s union-merge inside `run_refresh`).

**`run_query` scope-miss conditional (CACHE-03)** — Replaces the unconditional `_raise_scope_error` at line 175 with a two-branch conditional:
- `auto_fetch=False` → calls `_raise_scope_error(currencies, impacts, scope)` exactly as before (D-07 strict cache-only, zero network calls).
- `auto_fetch=True` → fires `progress("scope_miss", currency=c, impact=i)` per uncovered pair BEFORE fetching (D-12 banner ordering), calls `_refresh.widen_scope_to_cover(...)` (AutoFetchError propagates as-is — D-06), re-reads manifest, then proceeds to the parquet read loop.
`all_month_keys` / `candidate_keys` computed after the scope block (always up-to-date after any widen).

**`cli._print_progress` scope_miss branch** — Added `elif event == "scope_miss":` printing exactly `"{currency}/{impact} not in cache — fetching now..."` to stdout (D-12). `AutoFetchError` caught before `ValueError` in the query dispatch: exits 1 with the error on stderr (clean non-zero exit, not a traceback — D-06). The `ValueError` catch remains for the `auto_fetch=False` guidance path (D-07).

**Tests** — 10 new tests added (152 → 162):
- `RefreshWidenScopeTests` (3): widen succeeds + unions scope, full range fetched (D-05), failure raises AutoFetchError + manifest unchanged (D-06)
- `QueryScopeErrorTests` updated (6 existing + 1 new): all calls now use `auto_fetch=False` to preserve D-07/D-09 raise semantics; new `test_auto_fetch_false_makes_zero_network_calls`
- `QueryScopeMissAutoWidenTests` (4): auto_fetch=True returns rows (SC1), permanent widen (D-05 zero re-fetch), progress fired before widen (D-12), AutoFetchError propagates (D-06)
- `CliScopeMissBannerTests` (2): scope-miss banner on stdout before path, failed widen exits 1 to stderr

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
PYTHONPATH=src python3 -m pytest -q
162 passed in 3.22s
```

Success criteria met:
- SC1: querying EUR/medium when only USD/high is cached auto-fetches and returns rows (no manual populate)
- D-05: widen fetches full cached range (not just query window); manifest permanently widened after success
- D-06: widen failure raises AutoFetchError (fail-closed, no partial data); CLI converts to exit-1 + stderr
- D-07: `auto_fetch=False` preserves existing `_raise_scope_error` ValueError + guidance (zero network calls)
- D-12: `_print_progress` fires `scope_miss` banner before per-month `[N/total]` log lines

## Known Stubs

None — all implemented behavior is wired end-to-end.

## Threat Flags

No new network endpoints, auth paths, or schema changes beyond those already in the plan's threat model. T-03-06 (DoS via full-range widen) mitigated: delays inherited from `_scrape.BETWEEN_PAGES_DELAY`/`RETRY_DELAY`; permanent manifest widen means the auto-fetch fires once per missing combo. T-03-07 (fail-closed) mitigated: `AutoFetchError` raised on any failure; no partial/stale data served. T-03-08 (tampering / scope consistency) mitigated: widen uses union scope so existing currencies/impacts are preserved in rebuilt parquets.

## Self-Check: PASSED

Files created/modified:
- [x] `src/forexfactory/_exceptions.py` — exists
- [x] `src/forexfactory/_refresh.py` — `widen_scope_to_cover` added
- [x] `src/forexfactory/_query.py` — scope-miss conditional added
- [x] `src/forexfactory/cli.py` — `scope_miss` branch + `AutoFetchError` catch added
- [x] `tests/test_refresh.py` — 3 new tests
- [x] `tests/test_query.py` — 5 new tests + 6 existing updated
- [x] `tests/test_cli.py` — 2 new tests

Commits verified:
- 3902ceb (Task 1 RED)
- c65ed92 (Task 1 GREEN)
- a298c3c (Task 2 RED)
- 5a2d0b5 (Task 2 GREEN)
- cf4190b (Task 3)
