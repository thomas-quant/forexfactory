---
phase: 01-installable-data-provider
reviewed: 2026-06-08T10:37:57Z
depth: deep
files_reviewed: 16
files_reviewed_list:
  - src/forexfactory/__init__.py
  - src/forexfactory/_cache.py
  - src/forexfactory/_pipeline.py
  - src/forexfactory/_populate.py
  - src/forexfactory/_query.py
  - src/forexfactory/_refresh.py
  - src/forexfactory/_scrape.py
  - src/forexfactory/cli.py
  - tests/test_cache.py
  - tests/test_cli.py
  - tests/test_docs.py
  - tests/test_pipeline.py
  - tests/test_populate.py
  - tests/test_query.py
  - tests/test_refresh.py
  - tests/test_scrape.py
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: resolved
resolved: 2026-06-08T11:50:00Z
resolution: BL-01 + WR-01..05 fixed (commits 2c9d090, 41d3dfd, e18d00f, 2e8eb68, 751a950, d6dba7b) with 8 regression tests; suite 72→80 green. IN-01/IN-02 (low) deferred by decision.
---

# Phase 01: Code Review Report

> **Resolution (2026-06-08):** The BLOCKER (BL-01) and all five warnings (WR-01..05)
> were fixed and committed atomically with 8 new regression tests (suite 72 → 80,
> all green). BL-01 was additionally re-verified end-to-end through the installed CLI:
> a wider-scope re-`populate` now rebuilds every month (not just the first), and a
> union-scope manifest lets EUR and USD queries both succeed. The two LOW info items
> (IN-01 settled-logic duplication, IN-02 JS escape sequences) were deliberately
> deferred as low-risk.

**Reviewed:** 2026-06-08T10:37:57Z
**Depth:** deep
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The phase wraps two flat scripts into a proper `forexfactory` package with cache, populate, query, and refresh layers. The overall architecture is sound: path helpers are centralised in `_cache.py`, ETL logic is reused from `_pipeline.py`, network calls are isolated to `_refresh.py`, and the public API is a single `get() -> Path`. The walking-skeleton end-to-end tests pass and the structural design is clean. One blocker was found: in `_populate.run_populate` the in-memory `manifest` variable is reassigned to the return value of `update_manifest_month` after each successful month rebuild; because `update_manifest_month` writes the new (wider) scope to disk, subsequent iterations read back the wider scope in the skip-check and prematurely skip months that have not yet been rebuilt at the new scope. Five medium/warning-level issues are also documented below.

---

## Critical Issues (BLOCKER)

### BL-01: `run_populate` in-loop manifest reassignment silently skips months on wider-scope rebuild

**File:** `src/forexfactory/_populate.py:154, 182–184, 199–206`

**Severity:** BLOCKER

**Issue:**
`manifest` is read once before the loop (line 154). After each successful rebuild the loop reassigns `manifest` to the return value of `update_manifest_month` (line 199–206). `update_manifest_month` immediately writes the new scope (the caller-supplied currencies/impacts) to disk AND returns the full manifest with that updated scope. On the very next iteration the skip-check on lines 182–184 reads `cached_scope = manifest.get("scope", {})` from the now-mutated in-memory dict; because the scope already contains the wider currencies/impacts, every subsequent month that has a pre-existing manifest entry passes `_scope_covers` and is silently skipped — even though its parquet file was built at the old, narrower scope.

**Concrete trace** (two months, upgrading from `USD/high` to `USD+EUR/high+holiday`):

```
manifest at loop start: scope={currencies:[USD], impacts:[high]}
                        months:{2026-01:{...}, 2026-02:{...}}

i=1, anchor=2026-01:
  cached_scope = {currencies:[USD], impacts:[high]}      # narrow — EUR not covered
  _scope_covers([USD,EUR], [high,holiday]) -> False     # NOT skipped, rebuilt OK
  update_manifest_month sets scope={currencies:[EUR,USD], impacts:[high,holiday]}
  manifest (in-memory) is replaced with the returned manifest (scope now WIDE)

i=2, anchor=2026-02:
  cached_scope = {currencies:[EUR,USD], impacts:[high,holiday]}  # WIDE (just set)
  cached_entry  = old entry from previous run  (not None)
  _scope_covers([USD,EUR], [high,holiday]) -> True               # SKIPPED!
  parquet for 2026-02 still only contains USD/high data
```

The manifest then records `scope={EUR,USD}/{high,holiday}` but only the first month has EUR/holiday rows. All subsequent queries for EUR succeed the scope guard and return incomplete data.

**Fix:**
Save the pre-loop scope and keep it frozen throughout the loop. Only the disk is updated after each month; the skip-check must compare against the scope that was in force at the start of the run.

```python
# BEFORE the loop:
manifest = _cache.read_manifest(resolved_cache)
original_scope = manifest.get("scope", {})   # <-- add this

# INSIDE the loop (skip-check):
cached_entry = manifest.get("months", {}).get(month_key)
if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
    # ... skip
    continue

# The call to update_manifest_month still writes the new scope to disk each time,
# but the in-memory `manifest` is only used to look up month *entries*,
# not to drive the scope comparison.
```

---

## Warnings

### WR-01: Manifest `scope` is last-write, not per-month — can misrepresent coverage

**File:** `src/forexfactory/_cache.py:148–151`

**Severity:** WARNING

**Issue:**
`update_manifest_month` unconditionally overwrites the global `scope` field with whatever the current call passes. Running populate in two separate batches with different scope parameters (e.g., batch A = USD/high, then batch B = EUR/medium on a subset of months) leaves the manifest recording only the last batch's scope. If batch B covers only three months, the scope now claims EUR/medium across all months, but the earlier months' parquets contain only USD/high. A `run_query(currencies=["EUR"])` will pass the scope guard and return results from only the three months that were actually rebuilt — silently. Conversely, after a batch-B run the scope no longer mentions USD, so a `run_query(currencies=["USD"])` raises a spurious scope error even though USD parquets are intact.

The comment in the code acknowledges "union/last-write" but the implementation is purely last-write. For the single-scope use case this is benign, but it will surprise users who experiment with multiple scopes.

**Fix:**
Record scope per-month entry (under `manifest["months"][month_key]["scope"]`) instead of (or in addition to) the global `scope` field, or union-merge the global scope rather than replacing it:

```python
# In update_manifest_month — union-merge instead of overwrite:
existing_scope = manifest.get("scope", {})
merged_currencies = sorted(set(existing_scope.get("currencies", [])) | set(currencies))
merged_impacts    = sorted(set(existing_scope.get("impacts", []))    | set(impacts))
manifest["scope"] = {"currencies": merged_currencies, "impacts": merged_impacts}
```

Note: a union-merge on scope alone still doesn't solve the per-month data gap (BL-01 is the primary fix), but it would prevent the spurious scope-error false negatives described above.

---

### WR-02: `pd.to_datetime` called on potentially empty date/time strings

**File:** `src/forexfactory/_populate.py:75`, `src/forexfactory/_pipeline.py:187, 237`

**Severity:** WARNING

**Issue:**
`to_iso(dateline)` returns `("", "")` when `dateline` is `None`, `0`, or any other falsy value (via `if not dt_epoch`). If any row that passes the currency/impact/speaks filter has an empty date or time string, the expression `df["date"] + " " + df["time_utc"]` produces `" "`, and `pd.to_datetime([" "], utc=True)` raises a `ParserError` (subclass of `ValueError`). This exception is unhandled in `build_month_parquet` and will abort the whole `run_populate` call mid-run, leaving the manifest in a partially-updated state. Holiday-class events, which sometimes carry `dateline=null`, are within the default scope and could trigger this.

**Fix:**
Use `errors="coerce"` so unparseable rows become `NaT` instead of crashing, then optionally warn on nulls:

```python
df["datetime_utc"] = pd.to_datetime(
    df["date"] + " " + df["time_utc"], utc=True, errors="coerce"
)
null_count = df["datetime_utc"].isna().sum()
if null_count:
    logger.warning("[populate] %d rows have no parseable dateline → NaT", null_count)
```

---

### WR-03: `run_scraper` skip-check ignores file size; pre-existing empty files permanently block re-scraping

**File:** `src/forexfactory/_scrape.py:369–371`

**Severity:** WARNING

**Issue:**
`run_scraper` (the standalone scraper used for legacy `out/` writes) skips a month whenever `os.path.isfile(out_path)` is true, with no check on file size. In contrast, `_refresh.run_refresh` correctly guards with `raw_path.stat().st_size > 0` (line 115). Any `days_YYYY_MM.json` file left at 0 bytes by an older version of the code (QUAL-03 was supposed to prevent empty writes going forward, but cannot retroactively fix pre-existing files) will permanently suppress re-scraping that month via `run_scraper`. The scraper was meant to repair empty files on the next run; the skip-check defeats this.

**Fix:**
```python
# In run_scraper, replace:
if os.path.isfile(out_path):
# with:
if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
```

---

### WR-04: `logging.basicConfig` called at module import time in five library modules

**File:** `src/forexfactory/_cache.py:27`, `_populate.py:30`, `_query.py:27`, `_refresh.py:41`, `_scrape.py:29` (also `cli.py:32`)

**Severity:** WARNING

**Issue:**
`logging.basicConfig` is a no-op when the root logger already has handlers. Which module wins depends on import order, making log configuration non-deterministic. More critically, since `forexfactory` is a pip-installable library, calling `basicConfig` at import time is an established anti-pattern: it will override the host application's log level, format, and handlers the first time any `forexfactory` submodule is imported. The `cli.py` entry point is the only appropriate place to call `basicConfig`; the library modules should only obtain a logger via `logging.getLogger(__name__)` and let the application configure the root handler.

**Fix:**
Remove `logging.basicConfig(...)` from all five library modules (`_cache`, `_populate`, `_query`, `_refresh`, `_scrape`). Keep `logger = logging.getLogger(__name__)`. Leave the `basicConfig` call in `cli.py` only (or better, use `logging.lastResort` / a `NullHandler` as recommended by the Python docs for library authors).

---

### WR-05: `_validate_month` in CLI does not range-check the month integer

**File:** `src/forexfactory/cli.py:44–56`

**Severity:** WARNING

**Issue:**
`_validate_month` only checks that the two dash-separated parts are integers; it does not verify that the month integer is in [1, 12]. A value like `"2024-99"` or `"2024-00"` passes validation and then reaches `_parse_month_str`, which calls `date(2024, 99, 1)`, raising an unhandled `ValueError` that produces a Python traceback instead of a clean error message and `sys.exit(1)`.

**Fix:**
```python
year, month = int(parts[0]), int(parts[1])
if not (1 <= month <= 12):
    raise ValueError(f"month {month} out of range 1–12")
```

---

## Info

### IN-01: Settled calculation duplicated between `_populate.py` and `_refresh._is_settled`

**File:** `src/forexfactory/_populate.py:196–197`, `src/forexfactory/_refresh.py:230–234`

**Severity:** LOW

**Issue:**
The "next month start <= today" settled test is implemented inline in `run_populate` and also as the `_is_settled` function in `_refresh`. The two implementations are consistent now, but any future change to the definition of "settled" (e.g., adding a grace period) needs to be made in two places. `_is_settled` cannot be imported from `_refresh` into `_populate` without creating a circular import, so the helper belongs in `_cache`.

**Fix:**
Move `_is_settled` to `_cache.py` (alongside the other provenance helpers) and call `_cache._is_settled(anchor)` from both `_populate` and `_refresh`.

---

### IN-02: `_replace_single_quoted_strings` does not handle JS non-trivial escape sequences

**File:** `src/forexfactory/_scrape.py:159–211`

**Severity:** LOW

**Issue:**
The single-quoted string converter handles `\\` and `\'` correctly, but silently corrupts other JS escape sequences. For example:
- `'\n'` (JS newline) → `chars.append('n')` → `json.dumps('n')` → produces the literal letter `n` instead of a newline character.
- `'\t'` → `t`, `'\r'` → `r`, `'\uXXXX'` → `uXXXX` (stripped to literal characters).

The Forex Factory calendar HTML is unlikely to use these sequences in the calendar state object in practice (it would break the site's own JS parser), and the existing test suite covers the patterns seen in the wild. But the function is documented as a general JS-string normaliser and would silently mangle any string that happens to use these sequences.

**Fix:**
Add explicit escape-sequence dispatch inside the `escaped_single=True` branch:

```python
_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', "'": "'", '"': '"'}
if escaped_single:
    chars.append(_ESCAPES.get(inner, inner))   # fall back to bare char for unknown
    escaped_single = False
```

---

_Reviewed: 2026-06-08T10:37:57Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
