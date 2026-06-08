---
phase: 02-full-analytical-schema-source-spike
reviewed: 2026-06-08T21:35:00Z
depth: quick
files_reviewed: 16
files_reviewed_list:
  - src/forexfactory/__init__.py
  - src/forexfactory/_cache.py
  - src/forexfactory/_pipeline.py
  - src/forexfactory/_populate.py
  - src/forexfactory/_query.py
  - src/forexfactory/cli.py
  - tests/fixtures/empty_month.html
  - tests/fixtures/form1_rich_month.html
  - tests/fixtures/form2_bracket_no_data.html
  - tests/fixtures/multi_candidate.html
  - tests/test_cli.py
  - tests/test_docs.py
  - tests/test_pipeline.py
  - tests/test_populate.py
  - tests/test_query.py
  - tests/test_scrape.py
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-08T21:35:00Z
**Depth:** quick
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the new `src/forexfactory/` package modules (`__init__`, `_cache`,
`_pipeline`, `_populate`, `_query`, `cli`), four HTML parser fixtures, and six
test modules at quick depth.

Quick pattern scans (hardcoded secrets, `eval`/`exec`/`subprocess`/`pickle`,
debug artifacts, bare `except:`) came back **clean** across `src/`. Input that
reaches the filesystem is guarded: `_query._safe_token` strips path-traversal
characters from query filenames, manifest writes are atomic via
`tempfile.mkstemp` + `os.replace`, and bad/missing JSON is warn-and-skipped.

The substantive concerns are correctness defects in the **cache-scope coverage
model** and in **input validation at module boundaries**, not security holes.
The headline issue (CR-01) is a confirmed false-positive in scope coverage that
causes `run_query` to silently return an empty result for a currency×impact pair
that was never actually populated — defeating the D-09 "not populated" guidance
that the rest of the design relies on. Both reported runtime behaviors were
reproduced with throwaway scripts (see each finding).

## Critical Issues

### CR-01: Union-merged scope produces false-positive coverage → silent empty query results

**File:** `src/forexfactory/_cache.py:145-171`, `src/forexfactory/_query.py:138-139`
**Issue:**
`update_manifest_month` stores scope as two *independent* union-merged sets
(`currencies`, `impacts`), and `_scope_covers` checks each request token against
those sets independently:

```python
return all(c in cached_currencies for c in currencies) and all(
    i in cached_impacts for i in impacts
)
```

This treats coverage as the **cross-product** of the two sets, but the cache only
ever contains the specific pairs that were actually populated. Two separate
populate batches at different scopes therefore manufacture coverage for pairs
that were never fetched. Reproduced:

```
batch1: populate USD / high
batch2: populate EUR / medium
merged scope: {'currencies': ['EUR','USD'], 'impacts': ['high','medium']}
_scope_covers(scope, ['USD'], ['medium']) -> True   # never populated together
```

Because the scope check at `_query.py:138` passes, `run_query(currencies=["USD"],
impacts=["medium"])` skips the D-09 "not populated — run: forexfactory populate"
error, reads the per-month parquets (which contain no USD/medium rows), filters
to zero rows, and writes/returns an **empty result parquet with no error and no
diagnostic**. For a tool whose core value is data fidelity for expected-vs-surprise
analysis, silently returning "no events" for data that was never acquired is a
data-integrity failure, and it is reachable through the supported multi-batch
populate workflow that the union-merge was specifically added to enable.

**Fix:** Track coverage per (currency, impact) pair rather than as two independent
sets. For example, record a set of covered pairs in the manifest and test
membership of the requested cross-product:

```python
# in update_manifest_month: accumulate explicit pairs
existing_pairs = set(tuple(p) for p in manifest.get("scope", {}).get("pairs", []))
new_pairs = {(c, i) for c in currencies for i in impacts}
manifest["scope"]["pairs"] = sorted(existing_pairs | new_pairs)

# in _scope_covers:
covered = {tuple(p) for p in scope.get("pairs", [])}
return all((c, i) in covered for c in currencies for i in impacts)
```

(Keep the old `currencies`/`impacts` keys only if still needed for display.)

## Warnings

### WR-01: `_validate_month` checks month range but not year — out-of-range year crashes the populate path

**File:** `src/forexfactory/cli.py:44-59`, `src/forexfactory/_populate.py:164-169`, `src/forexfactory/_populate.py:259-265`
**Issue:** `_validate_month` only range-checks `1 <= month <= 12`; it never
validates the year. Values such as `"10000-03"` or `"0-03"` pass CLI validation,
then `run_populate` calls `_parse_month_str(start)` (not wrapped in try/except),
which calls `date(int(year_str), ...)` and raises `ValueError`. The populate
dispatch in `cli.main` (unlike the query dispatch) has no `except ValueError`,
so the exception escapes as an unhandled traceback. Reproduced:

```
_validate_month('10000-03', '--start')  -> PASSED (no sys.exit)
_parse_month_str('10000-03')            -> ValueError (uncaught in run_populate)
```

This is the exact "unhandled ValueError traceback" outcome that WR-05 set out to
prevent for the month component; the year component was left unguarded.
**Fix:** Validate the full date shape in `_validate_month` (e.g. build
`date(year, month, 1)` inside the `try` so an invalid year is caught), or catch
`ValueError` around the `run_populate` dispatch and `sys.exit(1)` with a message,
mirroring the query branch.

### WR-02: `run_query` / `get()` never validate or normalize `start`/`end`; lexical filtering mis-selects months silently

**File:** `src/forexfactory/_query.py:56-71`, `src/forexfactory/_query.py:107-143`, `src/forexfactory/__init__.py:18-40`
**Issue:** `_validate_month` is only invoked from the CLI. The library entry
points `forexfactory.get()` and `_query.run_query()` accept `start`/`end`
unchecked and feed them to `_filter_months_by_range`, which performs raw lexical
string comparison (`k < start`, `k > end`). A non-canonical but plausible value
such as `"2026-3"` (no zero-pad) compares as `"2026-03" < "2026-3"` (since `'0'`
< `'3'`), so months get silently included/excluded incorrectly with no error.
**Fix:** Run the same YYYY-MM shape/normalization check inside `run_query` (or in
`get()`) before filtering, raising `ValueError` on malformed input rather than
relying on the CLI to be the only validator.

### WR-03: Partially-migrated cache silently drops pre-Phase-2 rows from default queries with no warning

**File:** `src/forexfactory/_query.py:177-184`
**Issue:** The no-data guard only emits the "hasDataValues column absent — stale
cache; run populate --force" warning when the column is missing from the *entire*
concatenated frame. In a mixed cache (some months rebuilt to Phase-2, some still
pre-Phase-2 — the exact intermediate state during this phase's migration),
`pd.concat` yields a `hasDataValues` column that is present but `NaN` for the old
rows. The default filter `df[df["hasDataValues"] | (df["impact"]=="holiday")]`
then treats those `NaN` values as falsy and **drops every pre-Phase-2 row**
(reproduced: a True row + a NaN row yields 1 row kept). Crucially the
`--force` warning never fires in this mixed case because the column *does* exist,
so old data-bearing events disappear from default query results with no
diagnostic at all.
**Fix:** Detect partial coverage explicitly — e.g. fill missing `hasDataValues`
with a sentinel and warn when any are null:
```python
if "hasDataValues" in df.columns:
    if df["hasDataValues"].isna().any():
        logger.warning("[query] stale rows lack hasDataValues — run populate --force")
    keep = df["hasDataValues"].fillna(False).astype(bool) | (df["impact"] == "holiday")
    df = df[keep]
```

## Info

### IN-01: Unused `src_path` parameter in `flatten_events`

**File:** `src/forexfactory/_pipeline.py:124`
**Issue:** `def flatten_events(days, src_path=None)` never references `src_path`
in the body. `parse_json_to_csv`/`run_pipeline` pass `path`, but it is dead.
**Fix:** Drop the parameter (and the `path` argument at the call sites) or use it
in a log/warning message to attribute parse errors to a source file.

### IN-02: Stale docstring in `get()` claims `_query.py` does not yet exist

**File:** `src/forexfactory/__init__.py:29-32`
**Issue:** The docstring says the lazy import exists so `import forexfactory`
works "before `_query.py` exists (it is implemented in plan 04)". `_query.py` now
ships in this phase, so the rationale is stale and misleading.
**Fix:** Update the comment to state the lazy import avoids importing pandas/
pyarrow at package import time.

### IN-03: `parquet_path: str = None` violates the project's modern-union typing convention

**File:** `src/forexfactory/_pipeline.py:256`
**Issue:** `csv_to_parquet(csv_path: str, parquet_path: str = None)` annotates a
`None`-default parameter as `str`. CLAUDE.md conventions mandate modern union
syntax (`str | None`) used consistently elsewhere in the package.
**Fix:** `def csv_to_parquet(csv_path: str, parquet_path: str | None = None) -> str:`

---

_Reviewed: 2026-06-08T21:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
