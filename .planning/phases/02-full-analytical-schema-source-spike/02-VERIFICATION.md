---
phase: 02-full-analytical-schema-source-spike
verified: 2026-06-08T21:30:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 2: Full Analytical Schema + Source Spike Verification Report

**Phase Goal:** The cached parquet contains all fields needed for expected-vs-surprise analysis (forecast/actual/previous/revision as raw strings and parsed numerics, surprise flags, identity fields); the fragile HTML/JS parser is protected by fixture-based regression tests; and the FF apply-settings POST endpoint has been investigated with a documented decision on whether to adopt it.

**Verified:** 2026-06-08T21:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | A row from cache parquet contains forecast_raw/actual_raw/previous_raw/revision_raw (str) alongside forecast/actual/previous/revision (float/null) | VERIFIED | `pd.read_parquet('~/.cache/forexfactory/2024-01.parquet')` shows all 8 columns present; `forecast.dtype = float64`; real values e.g. forecast_raw='47.2', forecast=47.2; forecast_raw='0.3%', forecast=0.003 |
| SC2 | A row from cache parquet contains actualBetterWorse, revisionBetterWorse, ebaseId, country | VERIFIED | All 4 columns present in rebuilt parquet; `actualBetterWorse.dtype = Int64` (nullable); 195-month cache at schema_version "2" |
| SC3 | Speech/holiday events appear in cache; absent from default query, visible with flag | VERIFIED (with noted deviation) | 64 hasDataValues=False rows found across first 10 parquets; `QueryIncludeNoDataTests::test_default_hides_speeches` PASSED; `test_include_no_data_surfaces_speeches` PASSED; flag is `--include-no-data` (not the literal `--has-data-values false` in ROADMAP wording — see note below) |
| SC4 | pytest tests/ passes including fixture-based extract_days test asserting correct event output | VERIFIED | 128 passed (0 failed); `ExtractDaysFixtureTests` has 4 tests across all 4 HTML fixtures, all PASSED; form1 asserts currency/impactName/prefixedName/id/forecast/hasDataValues on real FF data |
| SC5 | Documented decision in PROJECT.md Key Decisions on whether apply-settings replaces HTML parser | VERIFIED | PROJECT.md line 54+96 record "NOT ADOPTED (SC5): apply-settings is a settings-save endpoint only; /calendar/more is a validated clean-JSON fallback; HTML ?month= GET stays bulk primary"; 02-SRC01-SPIKE.md records full D-06 four-criteria evaluation |

**Score: 5/5 ROADMAP success criteria verified**

**SC3 Deviation Note:** The ROADMAP SC3 literal example command is `forexfactory query --has-data-values false`. The implementation uses `--include-no-data` (a store_true flag) instead. The 02-CONTEXT.md explicitly contains a verifier note: "SC3's literal example command (`query --has-data-values false`) is superseded by `query --include-no-data`; verify against the new flag." This is a preemptive design override in the canonical phase planning document. The semantic intent of SC3 (speeches in cache, absent by default, surfaced with flag) is fully implemented and tested. This is informational only — not a blocker.

---

### Required Artifacts

#### Plan 02-01 (Schema Core)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/forexfactory/_pipeline.py` | `_parse_value`, `PHASE2_COLUMNS`, widened `flatten_events`, `extrasaction="ignore"` | VERIFIED | All present; `_NUMERIC_RE`, `_SUFFIX_MAP`, `PHASE2_COLUMNS` (19-col list, `datetime_utc` first), `flatten_events` yields 20 source keys, `DictWriter` has `extrasaction="ignore"` |
| `src/forexfactory/_populate.py` | `build_month_parquet` widened, no `should_keep_row` call, `force=` kwarg, `schema_version` stamp | VERIFIED | No `should_keep_row` call found (`grep` returns empty); `force: bool = False` in signature; `schema_version` stamped after any populated/skipped run; `INT_NULLABLE_COLS` constant present |
| `src/forexfactory/_cache.py` | `SCHEMA_VERSION = "2"` constant | VERIFIED | Line 25: `SCHEMA_VERSION: str = "2"` |
| `tests/test_pipeline.py` | `ParseValueTests` (14 cases), `FlattenEventsWidenedTests` (13 cases) | VERIFIED | 14 `ParseValueTests` PASSED, 11 `FlattenEventsWidenedTests` PASSED; all 37 pipeline tests green |
| `tests/test_populate.py` | `PopulatePhase2SchemaTests` (7 cases including speaks retention, force=True, schema_version, dtypes) | VERIFIED | All 7 `PopulatePhase2SchemaTests` PASSED; `test_speaks_event_retained_in_parquet`, `test_force_true_overwrites_cached_month`, `test_schema_version_in_manifest_after_populate` all green |

#### Plan 02-02 (Query Filter + CLI Flags)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/forexfactory/_query.py` | `include_no_data` kwarg, D-08 filter, PHASE2_COLUMNS fallback, `_DATA01_COLUMNS` removed | VERIFIED | `include_no_data: bool = False` in signature; `df[df["hasDataValues"] \| (df["impact"] == "holiday")]` filter present; `PHASE2_COLUMNS` used in empty-df fallback; `_DATA01_COLUMNS` grep returns 0 |
| `src/forexfactory/__init__.py` | `get(include_no_data=False)` passthrough | VERIFIED | `include_no_data=False` in `get()` signature, passed through to `run_query` |
| `src/forexfactory/cli.py` | `--include-no-data` (query), `--force` (populate), both wired | VERIFIED | `--include-no-data` store_true present; `--force` store_true present; `include_no_data=args.include_no_data` wired (count=1); `force=args.force` wired (count=1) |
| `tests/test_query.py` | `QueryIncludeNoDataTests` (5 cases) | VERIFIED | All 5 PASSED: default hides speeches, include_no_data=True, holiday visible, stale-cache degrades, get() forwarding |
| `tests/test_cli.py` | `CliIncludeNoDataTests` (2), `CliForcePopulateTests` (2), skeleton fixture updated | VERIFIED | All 4 PASSED; `_FIXTURE_DAYS` has `hasDataValues: True` on NFP event |

#### Plan 02-03 (HTML Fixtures + QUAL-05)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/fixtures/form1_rich_month.html` | Whole-object `= {...}` assignment, data-bearing events, unquoted keys, single-quoted string | VERIFIED | 3 USD events (ISM PMI, JOLTS, Construction Spending); `extract_days` returns 3 events; forecast fields present; exercises `_quote_js_object_keys` + `_replace_single_quoted_strings` |
| `tests/fixtures/form2_bracket_no_data.html` | Bracket `[n] = {...}` assignment, hasDataValues=False events | VERIFIED | 2 speech events (FOMC Member Kohn Speaks, BOE Gov Bailey Speaks); `extract_days` returns 2 events with `hasDataValues=false` |
| `tests/fixtures/empty_month.html` | Zero-events month | VERIFIED | `extract_days` returns 0 total events |
| `tests/fixtures/multi_candidate.html` | Two state objects; `_select_best_days` picks richest | VERIFIED | "short" (0 events) vs "month" (3 events); `extract_days` returns 3 events proving correct candidate selected |
| `tests/test_scrape.py` | `ExtractDaysFixtureTests` (4 tests) | VERIFIED | All 4 PASSED: form1 whole-object, form2 bracket, empty month, multi-candidate |

#### Plan 02-04 (SRC-01 Spike)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/PROJECT.md` | Resolved SRC-01 decision in Key Decisions table | VERIFIED | "NOT ADOPTED (SC5): apply-settings is settings-save only; /calendar/more validated clean-JSON fallback (clears all 4 D-06 criteria) but append-paginated so HTML ?month= GET stays bulk primary; /calendar/graph filed as high-value future enhancement" |
| `.planning/phases/02-full-analytical-schema-source-spike/02-SRC01-SPIKE.md` | D-06 four-criteria evaluation, endpoint inventory | VERIFIED | Full 3-part spike document; Parts 1-3 cover automated recon, corrected findings, and final NOT-ADOPTED rationale with D-06 table |
| No `src/forexfactory/_api.py` | Should NOT exist (not adopted) | VERIFIED | `ls src/forexfactory/` shows no `_api.py`; `_refresh.py` unchanged |

#### Plan 02-05 (Cache Rebuild + Docs)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `~/.cache/forexfactory/*.parquet` (195 months) | Rebuilt at schema_version "2" with Phase-2 schema | VERIFIED | 195 months in manifest; 2024-01.parquet has all 19 PHASE2_COLUMNS; dtypes: `forecast=float64`, `hasDataValues=bool`, `actualBetterWorse=Int64`, `id=Int64` |
| `~/.cache/forexfactory/manifest.json` | `schema_version: "2"`, 195 months | VERIFIED | `schema_version: 2`, `months count: 195` |
| `out/days_*.json` | Dropped (0 files) | VERIFIED | `find out -name 'days_*.json'` returns 0 files |
| `~/.cache/forexfactory/raw/` | Removed | VERIFIED | Directory does not exist |
| `README.md` | Phase-2 columns documented with `--include-no-data`, `--force` flags | VERIFIED | All Phase-2 columns present in schema table; `--force`, `--include-no-data` in usage examples |
| `tests/test_docs.py` | Asserts Phase-2 columns in README | VERIFIED | `test_readme_schema_documents_current_parquet_columns` asserts all 13 Phase-2 column rows; `test_project_structure_chart` asserts `re-scrape` framing for `out/` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_populate.py build_month_parquet` | `_pipeline.PHASE2_COLUMNS` | `import _pipeline; pd.DataFrame(columns=_pipeline.PHASE2_COLUMNS)` | VERIFIED | Empty-df fallback line 71; import at module top `from forexfactory import _cache, _pipeline` |
| `flatten_events` | `_parse_value` | calls `_parse_value(forecast_raw)`, `_parse_value(actual_raw)`, etc. | VERIFIED | Lines 162-165 of `_pipeline.py`; 4 call sites for all value fields |
| `cli.py query dispatch` | `_query.run_query` | `include_no_data=args.include_no_data` | VERIFIED | Line 244 of `cli.py`; `grep -c` returns 1 |
| `cli.py populate dispatch` | `_populate.run_populate` | `force=args.force` | VERIFIED | Line 228 of `cli.py`; `grep -c` returns 1 |
| `_query.py default filter` | `hasDataValues column` | `df[df["hasDataValues"] \| (df["impact"] == "holiday")]` | VERIFIED | Lines 178-179 of `_query.py`; stale-cache guard at line 178 |
| `__init__.get()` | `_query.run_query` | `include_no_data=include_no_data` passthrough | VERIFIED | Line 36 of `__init__.py` |
| `ExtractDaysFixtureTests` | `fixtures/*.html` | `Path(__file__).parent / "fixtures" / name` helper | VERIFIED | `_fixture()` helper present; all 4 fixture paths load without error |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `~/.cache/forexfactory/2024-01.parquet` | `forecast`, `forecast_raw`, `actualBetterWorse` | `flatten_events()` → `build_month_parquet()` → `run_populate()` | Yes — direct parquet inspection shows forecast_raw='47.2', forecast=47.2; forecast_raw='0.3%', forecast=0.003; forecast_raw='8.84M', forecast=8840000.0 | FLOWING |
| `_query.run_query` result parquet | `hasDataValues`, `impact` filter | per-month parquets concatenated | Yes — `QueryIncludeNoDataTests` writes real hasDataValues=True/False rows and verifies filter behavior | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_parse_value` handles all 12 edge cases | `python3 -c "assert p._parse_value('4.3%')==0.043; assert p._parse_value('-27.4K')==-27400.0; assert math.isnan(p._parse_value(''))..."` | All assertions pass | PASS |
| PHASE2_COLUMNS has correct structure | `assert 'forecast_raw' in p.PHASE2_COLUMNS and p.PHASE2_COLUMNS[0]=='datetime_utc'` | Passes | PASS |
| flatten_events excludes DATA-04 fields | Verify checker/soloTitle/siteId absent from yielded dict | All absent; analytical fields present | PASS |
| Cache parquet has Phase-2 schema + dtypes | `pd.read_parquet('2024-01.parquet')` | 19 columns, float64/bool/Int64 confirmed | PASS |
| Speeches retained in cache | Count hasDataValues=False rows in parquets | 64 speech/holiday rows in first 10 parquets | PASS |
| All 128 tests pass | `python3 -m pytest tests/ -q` | `128 passed in 2.74s` | PASS |
| SRC-01 decision in PROJECT.md | `grep -n 'NOT ADOPTED\|SRC-01' .planning/PROJECT.md` | "NOT ADOPTED (SC5): apply-settings is settings-save only..." at lines 54, 96 | PASS |
| No browser tooling shipped | `grep -ci 'playwright\|selenium\|nodriver' pyproject.toml` | Returns 0 | PASS |
| Raw JSON staging dropped | `find out -name 'days_*.json'` | 0 files; `~/.cache/forexfactory/raw/` does not exist | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-02 | 02-01, 02-05 | Each event carries forecast/actual/previous/revision as raw strings and parsed numeric | SATISFIED | All 8 columns (4 raw str + 4 float64) present in rebuilt parquets; real values confirmed on 2024-01.parquet |
| DATA-03 | 02-01, 02-05 | Each event carries actualBetterWorse, revisionBetterWorse, ebaseId, country | SATISFIED | All 4 columns present, Int64/str dtypes confirmed |
| DATA-04 | 02-01 | FF UI/internal fields dropped | SATISFIED | `checker`, `soloTitle`, `siteId`, `releaser`, `enableActualComponent`, `notice` all absent from `flatten_events` output; `soloTitle` explicitly not in title fallback chain |
| DATA-05 | 02-02 | Speeches/holidays retained in cache; filtering is query-time optional | SATISFIED | `should_keep_row` call removed from `build_month_parquet`; `hasDataValues` column in parquet; `--include-no-data` flag hides/shows speeches; holidays always visible; 5 `QueryIncludeNoDataTests` PASSED |
| QUAL-05 | 02-03 | Fixture-based regression tests cover `extract_days()` against realistic saved HTML | SATISFIED | 4 HTML fixtures (form1/form2/empty/multi); `ExtractDaysFixtureTests` 4 tests PASSED; both JS-quirk branches exercised; real FF event data sourced from out/days_2024_01.json |
| SRC-01 | 02-04 | apply-settings endpoint investigated; documented decision on adoption | SATISFIED | "NOT ADOPTED (SC5)" in PROJECT.md Key Decisions; D-06 four-criteria evaluation in 02-SRC01-SPIKE.md; no _api.py shipped; HTML ?month= GET remains primary |

---

### Anti-Patterns Found

No blockers or warnings detected.

| Scan | Files Checked | Result |
|------|--------------|--------|
| TBD / FIXME / XXX markers | All 12 phase-modified source + test + doc files | None found |
| TODO / HACK / PLACEHOLDER markers | All 6 source module files | None found |
| Stub returns (return null / return {}) | Source modules | None in public API paths |
| Hardcoded empty data | Source modules | None blocking data flow |

---

### Human Verification Required

None. All observable behaviors were verified programmatically:
- Parquet contents inspected directly via pandas
- Test suite run and 128/128 passing confirmed
- CLI flags verified via help output and dispatch grep
- Cache state verified via manifest + filesystem checks
- SRC-01 decision verified by direct PROJECT.md content search

---

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are verified. All plan-level must-haves are verified at all four levels (exists, substantive, wired, data-flowing). The 128-test suite passes with zero failures.

**One informational deviation (not a blocker):** ROADMAP SC3 literally says `forexfactory query --has-data-values false` surfaces speeches. The implementation uses `--include-no-data` (store_true, no `false` argument). The phase's own 02-CONTEXT.md explicitly preempts this with a verifier note: "SC3's literal example command (`query --has-data-values false`) is superseded by `query --include-no-data`; verify against the new flag." The semantic intent is fully implemented and covered by two dedicated CLI tests.

---

_Verified: 2026-06-08T21:30:00Z_
_Verifier: Claude (gsd-verifier)_
