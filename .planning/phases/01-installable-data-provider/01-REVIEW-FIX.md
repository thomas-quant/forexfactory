---
phase: 01-installable-data-provider
fixed_at: 2026-06-08T12:00:00Z
review_path: .planning/phases/01-installable-data-provider/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-06-08T12:00:00Z
**Source review:** .planning/phases/01-installable-data-provider/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### BL-01: `run_populate` in-loop manifest reassignment silently skips months on wider-scope rebuild

**Files modified:** `src/forexfactory/_populate.py`, `tests/test_populate.py`
**Commit:** 2c9d090
**Applied fix:** Added `original_scope = manifest.get("scope", {})` immediately after reading the manifest (before the loop). Changed the skip-check to compare against this frozen `original_scope` snapshot instead of re-reading `manifest.get("scope", {})` inside the loop. The in-memory `manifest` variable is still mutated by `update_manifest_month` after each write (providing up-to-date month entries), but the scope comparison now uses the pre-loop snapshot. Added `test_wider_scope_rebuilds_all_months_not_just_first` regression test that populates 2 months at USD/high, then re-populates at USD+EUR/high+holiday, and asserts both parquets contain EUR rows.

---

### WR-01: Manifest `scope` is last-write, not per-month — can misrepresent coverage

**Files modified:** `src/forexfactory/_cache.py`, `tests/test_cache.py`
**Commit:** 41d3dfd
**Applied fix:** In `update_manifest_month`, replaced the direct overwrite of `manifest["scope"]` with a sorted set union of the existing scope's currencies/impacts merged with the caller-supplied currencies/impacts. Two populate batches with different scopes now accumulate coverage rather than the second batch erasing the first's scope. Added `test_update_manifest_month_union_merges_scope_across_two_calls` test asserting that `update_manifest_month(USD/high)` followed by `update_manifest_month(EUR/medium)` yields scope `{currencies:[EUR,USD], impacts:[high,medium]}`.

---

### WR-02: `pd.to_datetime` called on potentially empty date/time strings

**Files modified:** `src/forexfactory/_populate.py`, `src/forexfactory/_pipeline.py`, `tests/test_populate.py`
**Commit:** e18d00f
**Applied fix:** Added `errors="coerce"` at all three `pd.to_datetime` call sites: `_populate.build_month_parquet` (line ~75), `_pipeline.csv_to_parquet` (line ~187), and `_pipeline.run_pipeline` (line ~237). Rows with empty or null datelines (holiday-class events where `to_iso()` returns `("", "")`) now become `NaT` instead of raising a `ParserError` mid-run. Each site now logs/prints a warning with the NaT count. Added `test_null_dateline_holiday_event_does_not_crash` and `test_zero_dateline_holiday_event_does_not_crash` regression tests.

---

### WR-03: `run_scraper` skip-check ignores file size; pre-existing empty files permanently block re-scraping

**Files modified:** `src/forexfactory/_scrape.py`
**Commit:** 2e8eb68
**Applied fix:** Changed the skip-check from `if os.path.isfile(out_path):` to `if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:`. A pre-existing 0-byte file now triggers a fresh scrape attempt on the next run, aligning with the guard already used in `_refresh.run_refresh`.

---

### WR-04: `logging.basicConfig` called at module import time in five library modules

**Files modified:** `src/forexfactory/_cache.py`, `src/forexfactory/_populate.py`, `src/forexfactory/_query.py`, `src/forexfactory/_refresh.py`, `src/forexfactory/_scrape.py`
**Commit:** 751a950
**Applied fix:** Removed the `logging.basicConfig(...)` block from all five library modules. Each now only obtains a named logger via `logging.getLogger(__name__)`. The `basicConfig` call in `cli.py` (the entry point) is intentionally preserved.

---

### WR-05: `_validate_month` in CLI does not range-check the month integer

**Files modified:** `src/forexfactory/cli.py`, `tests/test_cli.py`
**Commit:** d6dba7b
**Applied fix:** Extended `_validate_month` to extract both `year` and `month` as integers and assert `1 <= month <= 12`. Inputs like `"2024-99"` or `"2024-00"` now raise `ValueError` inside the `try` block, which is caught and turned into a clean `logger.error` + `sys.exit(1)`. Added `CliValidateMonthTests` with four tests covering month values 99, 00, 13 (all produce exit code 1) and a valid month 03 (passes through).

---

_Fixed: 2026-06-08T12:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
