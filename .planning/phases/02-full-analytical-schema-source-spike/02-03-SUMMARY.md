---
phase: 02-full-analytical-schema-source-spike
plan: 03
subsystem: test-fixtures
tags: [testing, fixtures, parser, regression, QUAL-05]
requires: []
provides: [qual-05-fixture-matrix, ExtractDaysFixtureTests]
affects: [tests/test_scrape.py, tests/fixtures/]
tech_stack:
  added: []
  patterns: [html-fixture-file-loading, Path-fixture-helper, unittest-fixture-class]
key_files:
  created:
    - tests/fixtures/form1_rich_month.html
    - tests/fixtures/form2_bracket_no_data.html
    - tests/fixtures/empty_month.html
    - tests/fixtures/multi_candidate.html
  modified:
    - tests/test_scrape.py
decisions:
  - "Fixture event data sourced from real out/days_2024_01.json (ISM PMI, JOLTS, Construction Spending) and out/days_2010_01.json (FOMC Speaks) — authentic field values, trimmed to 1-3 days per fixture (D-11)"
  - "form1 outer structure uses unquoted 'days:' key and 'upNext: feb.2024' single-quoted value to exercise both _quote_js_object_keys and _replace_single_quoted_strings in the whole-object form path"
  - "form2 uses bracket [n]={...} form with unquoted 'days:' key (required by _extract_days_array_from_state_object regex search) plus speech/no-data events (hasDataValues=false)"
  - "multi_candidate has 'short' (1 day, 0 events) and 'month' (2 days, 3 events); _select_best_days picks 'month' because it wins on both days-count and event-count comparators"
  - "test assertions stay on raw parser output only — no parsed-numeric assertions (those are in FlattenEventsWidenedTests from plan 02-01, keeping the two test classes independent)"
metrics:
  duration: 2min
  completed: "2026-06-08T19:09:25Z"
  tasks: 2
  files: 5
---

# Phase 02 Plan 03: Fixture-Based Parser Regression Tests (QUAL-05) Summary

**One-liner:** Four realistic HTML fixtures (both calendarComponentStates assignment forms, rich/no-data/empty/multi-candidate) plus `ExtractDaysFixtureTests` covering the fragile JS-state parser — CI now fails loudly on any silent `extract_days()` regression.

## What Was Built

### Task 1 — HTML fixture matrix

Created `tests/fixtures/` with four trimmed, real-data-backed HTML files:

**form1_rich_month.html** — whole-object `= {...}` assignment form. Contains 2 days (Jan 2–3 2024) with 3 USD data-bearing events sourced from `out/days_2024_01.json`: ISM Manufacturing PMI (forecast `47.2`), Construction Spending m/m (forecast `0.6%`), JOLTS Job Openings (forecast `8.84M`). The outer state object uses an unquoted `days:` key and `upNext: 'feb.2024'` (single-quoted value) to exercise `_quote_js_object_keys` and `_replace_single_quoted_strings` in the whole-object parse path.

**form2_bracket_no_data.html** — bracket `[1] = {...}` assignment form. Contains 1 day with 2 speech/no-data events sourced from `out/days_2010_01.json` and `out/days_2024_08.json`: `US FOMC Member Kohn Speaks` and `UK BOE Gov Bailey Speaks`, both `hasDataValues: false`. Uses unquoted `days:` key (required for `_extract_days_array_from_state_object`) and `time: '2:50am'` single-quoted scalar.

**empty_month.html** — whole-object form with an empty `"days": []` array. Confirms `extract_days()` returns zero total events — the regression case where a site-side bundle change might silently wipe event output.

**multi_candidate.html** — two state objects: `"short"` (1 day, 0 events) and `"month"` (2 days, 3 events — ISM PMI, JOLTS, ADP Non-Farm). Exercises `_select_best_days` with a clear winner on both days-count and event-count axes.

### Task 2 — ExtractDaysFixtureTests

Appended `ExtractDaysFixtureTests(unittest.TestCase)` to `tests/test_scrape.py` with 4 tests:

- `test_form1_whole_object_assignment_rich_month`: loads form1, asserts `len(days) > 0`, finds data-bearing events, checks `currency`, `impactName`, `prefixedName`, `id`, non-empty `forecast`, `hasDataValues True`
- `test_form2_bracket_assignment_no_data`: loads form2, asserts >=1 event with `hasDataValues False` and empty `forecast` string
- `test_empty_month_returns_no_events`: loads empty_month, asserts `total_events == 0`
- `test_multi_candidate_selects_best_days`: loads multi_candidate, asserts `total_events > 1` (proves richest candidate selected)

Added `_fixture(self, name)` helper using `Path(__file__).parent / "fixtures" / name` pattern (matches PATTERNS.md spec).

## Test Coverage

- 4 new tests in `ExtractDaysFixtureTests`
- Full suite: 119 passed (115 pre-plan + 4 new)
- Both JS-quirk branches exercised: `_quote_js_object_keys` (unquoted `days:`, `upNext:`), `_replace_single_quoted_strings` (`'feb.2024'`, `'2:50am'`)
- Both `calendarComponentStates` assignment forms covered: `= {...}` (form1, empty, multi) and `[n] = {...}` (form2)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 42e056f | feat(02-03) | Add HTML fixture matrix for calendarComponentStates parser regression |
| 15fccb8 | feat(02-03) | Add ExtractDaysFixtureTests for QUAL-05 parser regression coverage |

## Deviations from Plan

None — plan executed exactly as written. Fixture event data sourced directly from `out/days_2024_01.json` (Jan 2024 rich months) and `out/days_2010_01.json` (FOMC speech) as specified by D-11.

## Known Stubs

None. All fixtures contain complete event dicts with authentic field values from real `out/*.json` files.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Fixtures contain only public economic-calendar data (no secrets/PII), trimmed to 1-3 days per file (T-02-06 accepted). The fixture matrix implements the T-02-05 mitigation: parser behavior across both assignment forms and JS quirks is now pinned by CI-runnable tests.

## Self-Check

### Created files check
- `tests/fixtures/form1_rich_month.html` — FOUND (42e056f)
- `tests/fixtures/form2_bracket_no_data.html` — FOUND (42e056f)
- `tests/fixtures/empty_month.html` — FOUND (42e056f)
- `tests/fixtures/multi_candidate.html` — FOUND (42e056f)

### Modified files check
- `tests/test_scrape.py` — FOUND, ExtractDaysFixtureTests class with 4 tests present (15fccb8)

### Commits check
- 42e056f — confirmed in git log
- 15fccb8 — confirmed in git log

### Test suite check
`python3 -m pytest tests/ -q` → 119 passed (no failures)

## Self-Check: PASSED
