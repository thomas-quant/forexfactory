---
phase: 03-cache-lifecycle
reviewed: 2026-06-09T00:00:00Z
depth: quick
files_reviewed: 10
files_reviewed_list:
  - src/forexfactory/__init__.py
  - src/forexfactory/_exceptions.py
  - src/forexfactory/_populate.py
  - src/forexfactory/_query.py
  - src/forexfactory/_refresh.py
  - src/forexfactory/cli.py
  - tests/test_cli.py
  - tests/test_populate.py
  - tests/test_query.py
  - tests/test_refresh.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: remediated
remediation:
  fixed: [CR-01, WR-01, WR-02, WR-03]
  deferred: [IN-01, IN-02]
  commits:
    - "7972cf8 fix(03): CR-01 union manifest scope before force-refresh rebuild in run_refresh"
    - "b1e0dc8 fix(03): WR-01 derive force-refresh range from manifest months when start/end unset"
    - "19c8cc9 fix(03): WR-02 reconcile stale zero-network-calls docs and add --no-auto-fetch CLI flag"
    - "d56ed12 fix(03): WR-03 forward injected session to run_refresh on populate force-refresh path"
  test_count: 169
---

> **Remediation (2026-06-09):** CR-01 + WR-01/WR-02/WR-03 fixed in the four commits above
> (suite 162 → 169 passing). IN-01/IN-02 (refactor-only) deferred. See per-commit diffs.


# Phase 3: Code Review Report

**Reviewed:** 2026-06-09T00:00:00Z
**Depth:** quick (escalated to contract-level tracing per the asymmetric-contract / scope-union concerns called out in the brief)
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 3 adds three network-triggering auto-fetch paths: force-refresh (CACHE-06), matured-month auto-refresh (CACHE-05), and scope-miss auto-widen (CACHE-03). The asymmetric failure contracts are implemented correctly where I could trace them — `widen_scope_to_cover` raises `AutoFetchError` and `run_query` propagates it (D-06); `refresh_matured_months` swallows all errors and preserves the stale parquet (D-10); and `auto_fetch=False` correctly suppresses both *implicit* triggers in `run_query` and the matured trigger in `run_populate`.

However, the scope-union protection that prevents silent data loss is applied inconsistently. The `populate --force-refresh` path (`run_populate`) and `widen_scope_to_cover` both union the requested scope with the existing manifest scope before rebuilding parquets — but the **direct `refresh --force-refresh` path (`run_refresh`) does not**. This produces a real, silent data-loss path (CR-01). There are also two contract/documentation drifts around the "zero network calls" guarantee and the default force-refresh range that defeat the documented behavior of the populate force-refresh feature.

## Critical Issues

### CR-01: `refresh --force-refresh` with a currency/impact subset silently destroys previously-cached data while the manifest still advertises it

**File:** `src/forexfactory/_refresh.py:120-159`, dispatched from `src/forexfactory/cli.py:242-251`

**Issue:**
`run_refresh(force_refresh=True)` rebuilds each month's parquet using *only* the `currencies`/`impacts` it was handed, with no union against the existing manifest scope:

```python
# _refresh.py — inside run_refresh, force_refresh path
_populate.build_month_parquet(
    resolved_cache, anchor, days,
    currencies=currencies,   # request as-is, NOT unioned with manifest scope
    impacts=impacts,
)
...
_cache.update_manifest_month(            # <-- this UNIONS scope (per _cache WR-01)
    resolved_cache, anchor,
    scraped_at=scraped_at, settled=settled,
    currencies=currencies, impacts=impacts,
)
```

`build_month_parquet` **overwrites** the month parquet with only the rows matching the narrow request, but `update_manifest_month` **union-merges** the scope. The result is an inconsistency:

Concrete repro — cache already holds 2026-05 populated at USD/high+holiday, then:
```
forexfactory refresh --force-refresh --currency EUR --start 2026-05 --end 2026-05
```
1. `run_refresh(currencies=["EUR"], impacts=["high","holiday"], force_refresh=True)` re-scrapes 2026-05.
2. `build_month_parquet` filters to `currency in {"EUR"}` → **the USD rows are dropped and `2026-05.parquet` is overwritten with EUR-only data.**
3. `update_manifest_month` unions scope → manifest scope becomes `{USD, EUR}/{high, holiday}` — still claiming USD coverage.
4. A later `query --currency USD` passes `_scope_covers` (USD is in scope) and reads `2026-05.parquet`, which no longer contains any USD rows → **empty result, no error, USD data silently lost.**

The other two force paths avoid this by pre-unioning: `run_populate` (`_populate.py:176-191`) and `widen_scope_to_cover` (`_refresh.py:298-318`). The direct `refresh` path is the one spot that was missed, and the existing `RefreshForceRefreshTests` never catch it because they re-scrape at the *same* scope already cached.

This satisfies the BLOCKER bar (data-loss risk + manifest/parquet inconsistency) and directly violates the stated invariant: "force-refresh ... must not silently narrow previously-cached scope."

**Fix:** Union the effective scope with the existing manifest scope inside `run_refresh` whenever `force_refresh=True`, mirroring `run_populate`:

```python
# _refresh.py, after resolving defaults and resolved_cache, before the page loop:
if force_refresh:
    existing_scope = _cache.read_manifest(resolved_cache).get("scope", {})
    currencies = sorted(set(currencies) | set(existing_scope.get("currencies", [])))
    impacts = sorted(set(impacts) | set(existing_scope.get("impacts", [])))
```

Add a regression test: seed a USD/high cache, run `run_refresh(currencies=["EUR"], force_refresh=True, ...)`, and assert the rebuilt month parquet still contains USD rows.

## Warnings

### WR-01: `populate --force-refresh` with no `--start/--end` re-scrapes only the current month, not the "existing cached parquets" it documents

**File:** `src/forexfactory/_populate.py:184-191` (delegation) + `src/forexfactory/_refresh.py:361-365` (`_compute_date_range` gap-fill)

**Issue:**
The library docstring (`__init__.py:71-73`) and CLI help (`cli.py:131-140`) promise that force-refresh "re-scrapes the requested range ... and **overwrites existing cached parquets**." But `run_populate` delegates with `start=start, end=end` unchanged, and when both are `None`, `run_refresh._compute_date_range` falls into gap-fill: `start = month after _latest_raw_month(cache)`.

For a cache built via the disk-ingest path, `cache_dir/raw/` is **empty** (disk-ingest reads from the external `raw_dir` and never stages into `cache_dir/raw/`). So `_latest_raw_month` returns `None`, and the range collapses to `(current_month, current_month)`. Net effect: `forexfactory populate --force-refresh` (no range) on a fully-populated cache re-scrapes **only the current month** and silently leaves every previously-cached month untouched — the opposite of the documented "overwrite existing cached parquets," while still reporting `fetched=…` success. All `PopulateForceRefreshTests` pass explicit `start/end`, so this default-range gap is untested.

**Fix:** When `force_refresh=True` and `start`/`end` are unset, derive the range from the cached manifest months (min..max of `manifest["months"]`) rather than from `cache_dir/raw/`, e.g.:

```python
if force_refresh and start is None and end is None:
    month_keys = sorted(manifest.get("months", {}).keys())
    if month_keys:
        start, end = month_keys[0], month_keys[-1]
```

### WR-02: "zero network calls (SC2)" is now false for the default populate path — `auto_fetch=True` triggers a matured-month network refresh, and there is no CLI flag to disable it

**File:** `src/forexfactory/_populate.py:4-5,122,166-168`; `src/forexfactory/__init__.py:67-69`; `src/forexfactory/cli.py:94-97`

**Issue:**
Multiple docstrings still assert a hard "zero network calls" invariant:
- `_populate.py:4-5` — "Makes ZERO network calls (SC2)."
- `_populate.py:122` — "Makes zero network calls."
- `__init__.py:68-69` — "With force_refresh=False (default): reads on-disk raw JSON and builds parquet (zero network calls)."
- `cli.py:96` — populate help: "Build the parquet cache from on-disk raw JSON files (zero network calls)."

But `run_populate` now defaults `auto_fetch=True` and unconditionally runs `_refresh.refresh_matured_months(...)` (`_populate.py:166-168`) on the default (`force_refresh=False`) path, which **does** issue live network requests whenever the cache has any `settled:false` month that has since matured (confirmed by `test_populate_auto_fetch_true_matures_month`). The CLI `populate` subparser exposes no flag to set `auto_fetch=False` (and the dispatch at `cli.py:258-269` never forwards it), so a CLI user cannot obtain the documented zero-network behavior at all. This is a behavioral surprise plus stale-invariant documentation.

**Fix:** Reconcile docs with behavior — update the four docstrings/help strings to state that the default path auto-refreshes matured months over the network (and that `auto_fetch=False` is required for strict cache-only). Optionally add a `--no-auto-fetch`/`--cache-only` flag to the `populate` (and `query`) subparsers and forward it as `auto_fetch=...`.

### WR-03: `run_populate` drops an injected `session` on the force-refresh path

**File:** `src/forexfactory/_populate.py:184-191`

**Issue:**
`run_populate` accepts `session=None` (`_populate.py:120`) and correctly forwards it on the matured path (`_populate.py:168`: `refresh_matured_months(..., session=session)`). But the `force_refresh` delegation to `run_refresh` omits `session`:

```python
return _refresh.run_refresh(
    currencies=effective_currencies,
    impacts=effective_impacts,
    start=start, end=end,
    cache_dir=resolved_cache,
    force_refresh=True,
    # session=session  <-- missing
)
```

`run_refresh` then falls back to `_scrape.build_session()` and issues real HTTP, silently ignoring the caller's injected session. This breaks dependency injection for the force-refresh path and is an inconsistency with the matured path. Tests don't catch it because they additionally patch `_scrape.build_session`.

**Fix:** Forward `session=session` (and, for symmetry, `between_pages_delay`/`retry_delay` if exposed) in the `run_refresh` call.

## Info

### IN-01: Union-scope and "settled" computations are duplicated across modules

**File:** `src/forexfactory/_populate.py:178-183` and `:273-274`; `src/forexfactory/_refresh.py:298-304` and `:394-398`; `src/forexfactory/_cache.py:145-156`

**Issue:** The sorted-set scope union appears in three places (`run_populate`, `widen_scope_to_cover`, `update_manifest_month`), and the "whole month strictly before today" settled test is inlined in `run_populate` (`:273-274`) while also existing as `_refresh._is_settled`. The duplication is precisely what allowed CR-01 to slip through (one of the union sites was missed).

**Fix:** Extract a single `_cache._union_scope(scope, currencies, impacts)` helper and call it from all force paths; have `run_populate` reuse a shared `is_settled(anchor)` helper instead of inlining the date math.

### IN-02: Silent `except (ValueError, AttributeError): pass` in the matured-count loop

**File:** `src/forexfactory/_query.py:162-163`

**Issue:** Unparseable month keys are swallowed with a bare `pass` while computing the D-12 banner count, with no log line (unlike the parallel parse failure at `_query.py:214-216`, which warns). A malformed manifest key would silently under-count matured months for the banner. Low impact, but inconsistent with the warn-and-skip convention used elsewhere.

**Fix:** Log at debug/warning level in the `except` instead of `pass`, mirroring the per-month parse-error handling later in the same function.

---

_Reviewed: 2026-06-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
