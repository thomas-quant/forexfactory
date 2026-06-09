---
phase: 03-cache-lifecycle
verified: 2026-06-09T00:00:00Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 3: Cache Lifecycle Verification Report

**Phase Goal:** The cache self-manages — a query that exceeds cached scope triggers automatic fetch and widening (CACHE-03); months scraped while future-dated automatically re-fetch once fully matured, populating their `actual` values (CACHE-05); and a force-refresh flag bypasses the skip-if-exists logic for any given range (CACHE-06).
**Verified:** 2026-06-09T00:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1/CACHE-03) Querying EUR/medium when only USD/high is cached auto-fetches the missing scope for the full cached range and returns matching rows, no manual populate | VERIFIED | `_query.run_query` scope-miss conditional at `_query.py:175-194` calls `_refresh.widen_scope_to_cover`; `test_auto_widen_returns_rows_sc1` passes |
| 2 | (SC1) After a successful auto-widen the manifest scope is permanently widened so repeat queries do not re-trigger a fetch (D-05) | VERIFIED | `widen_scope_to_cover` re-reads manifest after `run_refresh` completes; `test_auto_widen_permanent_scope_d05` verifies zero network calls on repeat query |
| 3 | (SC1) The auto-widen fetches the FULL cached month range, not just the query window (D-05) | VERIFIED | `widen_scope_to_cover` at `_refresh.py:296-306` computes `start=min(month_keys)`, `end=max(month_keys)` from manifest — not from the query's start/end; `test_widen_scope_covers_full_cached_range_not_query_window` passes |
| 4 | (SC1) `get(auto_fetch=False)` on a scope miss raises `ValueError` with populate guidance (D-07) | VERIFIED | `_query.py:176-178` calls `_raise_scope_error` when `auto_fetch=False`; `test_auto_fetch_false_makes_zero_network_calls` + `QueryScopeErrorTests` (6 cases, all pass `auto_fetch=False`) |
| 5 | (SC1) A failed auto-widen raises `AutoFetchError` — no silent partial data; aborts on first failure (D-06) | VERIFIED | `widen_scope_to_cover` wraps `run_refresh` exceptions as `AutoFetchError` and also raises when `_scope_covers` is False after fetch; `test_widen_scope_failure_raises_auto_fetch_error` passes |
| 6 | (SC2/CACHE-05) A manifest month stored `settled:false` that has now fully matured is auto-re-fetched on the next query, filling its actual values (SC2) | VERIFIED | `run_query(auto_fetch=True)` calls `refresh_matured_months` before the read loop at `_query.py:148-172`; `test_query_auto_fetch_true_matures_month` asserts non-NaN `actual` after re-fetch |
| 7 | (SC2) The same matured month is auto-re-fetched on the next populate call (D-08) | VERIFIED | `run_populate(auto_fetch=True)` calls `_refresh.refresh_matured_months(resolved_cache, session=session)` at `_populate.py:175-177`; `test_populate_auto_fetch_true_matures_month` passes |
| 8 | (SC2) All matured months are refreshed in one call — no per-call cap (D-08) | VERIFIED | `refresh_matured_months` collects ALL matured keys then iterates them; no limit; `test_matured_month_is_refetched_and_parquet_updated` passes |
| 9 | (SC2) `auto_fetch=False` suppresses the matured re-fetch — strict cache-only (D-07/D-09) | VERIFIED | `run_query`/`run_populate` both guard the matured block with `if auto_fetch:`; `test_query_auto_fetch_false_suppresses_matured` asserts zero scrape calls |
| 10 | (SC2) A failed matured re-fetch serves the stale parquet and emits exactly one `logger.warning`, never raises (D-10) | VERIFIED | `refresh_matured_months` `try/except` at `_refresh.py:255-260` catches all exceptions, logs warning, continues; `test_failed_refetch_serves_stale_parquet_and_warns` passes |
| 11 | (SC2/SC1) CLI query command prints the D-12 matured/scope-miss banners to stdout BEFORE per-month fetch progress (D-11/D-12) | VERIFIED | `_print_progress` in `cli.py:45-56`; `progress=_print_progress` passed to `run_query` at `cli.py:316`; callbacks fire BEFORE `refresh_matured_months`/`widen_scope_to_cover` calls in `_query.py:167-168` and `_query.py:182-188` |
| 12 | (SC3/CACHE-06) `forexfactory populate --force-refresh --start 2025-01` re-scrapes the range over the network and overwrites the cached parquet regardless of existing cache state (D-01) | VERIFIED | `cli.py:136-144` defines `--force-refresh` on populate; `cli.py:290` routes to `run_populate(force_refresh=args.force_refresh)`; `run_populate(force_refresh=True)` at `_populate.py:183-211` delegates to `run_refresh(force_refresh=True)` |
| 13 | (SC3) `forexfactory.populate(force_refresh=True, start='2025-01')` is the library equivalent and returns a result dict (D-03) | VERIFIED | `__init__.py:54-96` defines `populate(force_refresh=False, ...)` wrapper; delegates to `_populate.run_populate` |
| 14 | (SC3) `run_refresh(force_refresh=True)` overwrites cached months; `force_refresh=False` preserves skip behavior unchanged (D-02) | VERIFIED | `_refresh.py:129`: `if not force_refresh and raw_path.exists() and raw_path.stat().st_size > 0:`; `RefreshForceRefreshTests` (2 tests) confirm both branches |
| 15 | (CR-01 fix) `run_refresh(force_refresh=True)` unions the requested currencies/impacts with the existing manifest scope before rebuilding parquets, preventing silent data loss | VERIFIED | `_refresh.py:97-100`: manifest scope read and union computed before the page loop; `test_force_refresh_unions_existing_manifest_scope` seeds USD/high cache, force-refreshes at EUR-only scope, asserts USD rows survive |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/forexfactory/_exceptions.py` | `AutoFetchError(RuntimeError)` for CACHE-03 failures | VERIFIED | Exists; `class AutoFetchError(RuntimeError)` present with docstring referencing D-06 |
| `src/forexfactory/_refresh.py` | `force_refresh` kwarg on `run_refresh`; `refresh_matured_months()`; `widen_scope_to_cover()` | VERIFIED | All three present; `force_refresh: bool = False` in signature at line 56; `def refresh_matured_months` at line 183; `def widen_scope_to_cover` at line 269 |
| `src/forexfactory/_query.py` | `auto_fetch`, `session`, `progress` params + matured block + scope-miss conditional | VERIFIED | All params on `run_query` signature at lines 116-118; matured block at lines 148-172; scope-miss conditional at lines 174-194 |
| `src/forexfactory/_populate.py` | `force_refresh`, `auto_fetch`, `session` params; force-refresh delegation to `run_refresh`; matured auto-fetch call | VERIFIED | Params at lines 122-124; delegation at lines 183-211; matured call at lines 175-177 |
| `src/forexfactory/__init__.py` | `forexfactory.populate()` and `forexfactory.get()` both expose `auto_fetch`; `populate()` exposes `force_refresh` | VERIFIED | `get()` at lines 21-51 has `auto_fetch: bool = True`; `populate()` at lines 54-96 has both `force_refresh=False` and `auto_fetch: bool = True` |
| `src/forexfactory/cli.py` | `--force-refresh` on populate and refresh; `--no-auto-fetch` on populate and query; `_print_progress` helper with matured+scope_miss branches; `AutoFetchError` catch in query dispatch | VERIFIED | `--force-refresh` on populate at line 135, refresh at line 200; `--no-auto-fetch` on populate at line 145, query at line 241; `_print_progress` at lines 45-56; `AutoFetchError` catch at lines 319-322 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_query.py` | `_refresh.py` | `run_query` matured block calls `refresh_matured_months` | VERIFIED | `_refresh.refresh_matured_months(cache_dir, session=session)` at `_query.py:169` (lazy import) |
| `_query.py` | `_refresh.py` | `run_query` scope-miss + `auto_fetch=True` calls `widen_scope_to_cover` | VERIFIED | `_refresh.widen_scope_to_cover(cache_dir, currencies, impacts, session=session)` at `_query.py:191` |
| `_populate.py` | `_refresh.py` | `run_populate` matured block calls `refresh_matured_months` | VERIFIED | `_refresh.refresh_matured_months(resolved_cache, session=session)` at `_populate.py:177` |
| `_populate.py` | `_refresh.py` | `run_populate(force_refresh=True)` delegates to `run_refresh(force_refresh=True)` | VERIFIED | `_refresh.run_refresh(..., force_refresh=True, session=session)` at `_populate.py:203-211`; WR-03: `session=session` present |
| `_refresh.py` | `_exceptions.py` | `widen_scope_to_cover` failure raises `AutoFetchError` | VERIFIED | `from forexfactory._exceptions import AutoFetchError` at `_refresh.py:289`; raised at lines 329-331 and 337-338 |
| `cli.py` | `run_query` progress callback | `progress=_print_progress` routes `matured`/`scope_miss` events to D-12 banner strings | VERIFIED | `progress=_print_progress` at `cli.py:316`; both branches implemented in `_print_progress` |
| `cli.py` | `run_query`/`run_populate`/`run_refresh` | `--force-refresh` → `force_refresh=args.force_refresh` in both populate and refresh dispatches | VERIFIED | `cli.py:272` (refresh), `cli.py:290` (populate) |
| `cli.py` | `run_query`/`run_populate` | `--no-auto-fetch` → `auto_fetch=not args.no_auto_fetch` in both query and populate dispatches | VERIFIED | `cli.py:291` (populate), `cli.py:317` (query) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_query.py` — `run_query` scope-miss path | manifest scope + parquet rows | `widen_scope_to_cover` → `run_refresh` → `build_month_parquet` | Yes — real scrape via `_scrape.scrape_month` → parquet write | FLOWING |
| `_query.py` — `run_query` matured path | manifest months `settled` field | `refresh_matured_months` → `run_refresh` → `build_month_parquet` | Yes — real scrape on matured months; stale parquet served on failure (D-10) | FLOWING |
| `_populate.py` — `run_populate` force-refresh path | result dict from `run_refresh` | `run_refresh(force_refresh=True)` with union scope (CR-01 fix) and session forwarded (WR-03 fix) | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 regression test: force-refresh at narrow scope retains existing currency rows | `PYTHONPATH=src python3 -m pytest -q tests/test_refresh.py::RefreshForceRefreshTests::test_force_refresh_unions_existing_manifest_scope` | 1 passed | PASS |
| SC1 test: auto-widen returns EUR/medium rows from USD/high-only cache | `PYTHONPATH=src python3 -m pytest -q tests/test_query.py::QueryScopeMissAutoWidenTests::test_auto_widen_returns_rows_sc1` | 1 passed | PASS |
| SC2 test: matured query re-fetches and returns non-NaN actual | `PYTHONPATH=src python3 -m pytest -q tests/test_query.py::QueryAutoFetchTests::test_query_auto_fetch_true_matures_month` | 1 passed | PASS |
| Full suite (169 tests, including all four remediation-commit additions) | `PYTHONPATH=src python3 -m pytest -q` | 169 passed in 4.50s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CACHE-03 | 03-03-PLAN.md | A query that exceeds cached scope auto-fetches the missing data and widens the cache | SATISFIED | `widen_scope_to_cover` + scope-miss conditional in `run_query`; `AutoFetchError` on failure; 4 `QueryScopeMissAutoWidenTests` pass |
| CACHE-05 | 03-02-PLAN.md | Months cached while future-dated are auto-refreshed once the whole month has passed | SATISFIED | `refresh_matured_months` shared helper; `auto_fetch` knob on `run_query`/`run_populate`/`get()`/`populate()`; 3 `RefreshMaturedMonthsTests` + 5 `QueryAutoFetchTests` + 3 `PopulateAutoFetchTests` pass |
| CACHE-06 | 03-01-PLAN.md | A force-refresh capability can re-scrape a given range on demand (CLI flag + library arg) | SATISFIED | `force_refresh` kwarg on `run_refresh`/`run_populate`; `forexfactory.populate()`; `--force-refresh` CLI flag on both populate and refresh; CR-01 union fix prevents scope narrowing |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/forexfactory/_query.py` | 162–163 | `except (ValueError, AttributeError): pass` — silently swallows unparseable month keys in the matured-count loop | Info | Low; the parallel parse-failure path at line 214–216 uses `logger.warning`; this inconsistency was flagged as IN-02 in the code review and explicitly deferred as a refactor-only issue |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified file. The `except pass` is not a BLOCKER (it under-counts the D-12 banner in pathological cases but never silences a re-fetch; the actual re-fetch happens in `refresh_matured_months` which has its own manifest iteration with `continue` on parse failure).

### Code Review Remediation Verification

The phase was reviewed (03-REVIEW.md, status: remediated). All four remediation commits confirmed present via `git log`:

| Commit | Fix | Verification |
|--------|-----|--------------|
| `7972cf8` | CR-01: union manifest scope before force-refresh rebuild in `run_refresh` | `_refresh.py:97-100` confirmed; `test_force_refresh_unions_existing_manifest_scope` passes |
| `b1e0dc8` | WR-01: derive force-refresh range from manifest months when start/end unset | `_populate.py:198-201` confirmed; no longer collapses to current month for populated caches |
| `19c8cc9` | WR-02: reconcile stale "zero network calls" docs; add `--no-auto-fetch` CLI flag | `cli.py:145-153` (populate) and `cli.py:241-249` (query) confirmed; `_populate.py` module docstring updated |
| `d56ed12` | WR-03: forward injected session to `run_refresh` on populate force-refresh path | `_populate.py:210`: `session=session` present in `run_refresh` call |

Deferred (IN-01, IN-02): scope-union and settled-check extraction (refactor-only), silent `except pass` in matured-count loop. Neither is a BLOCKER.

### Human Verification Required

None. All behaviors are exercised by the 169-test suite: D-12 banners (tested via stdout capture), D-10 stale-serve (tested via `assertLogs`), SC1/SC2/SC3 end-to-end flows (tested against temp caches with patched `scrape_month`).

### Gaps Summary

None. All 15 must-haves verified, all three ROADMAP success criteria met, all three requirement IDs (CACHE-03/05/06) satisfied, full test suite at 169 passing, all code-review blockers and warnings remediated.

---

_Verified: 2026-06-09T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
