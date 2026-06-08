# Roadmap: forexfactory — Cached Economic Calendar Data Provider

## Overview

Starting from two working loose scripts and ~195 months of raw data on disk, this milestone turns the toolkit into a pip-installable cached data provider. Phase 1 delivers the thin but real end-to-end path: install, populate from existing data, query, get a parquet path back. Phase 2 layers in the full analytical schema (forecast/actual/surprise fields) and investigates the FF API endpoint as a cleaner source. Phase 3 makes the cache self-managing: auto-widen on scope miss, auto-mature past-future months, and force-refresh on demand.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Installable Data Provider** - Package scaffold + basic cache + restructured pipeline; delivers the install → populate → query → parquet-path end-to-end path (completed 2026-06-08)
- [ ] **Phase 2: Full Analytical Schema + Source Spike** - Expand the parquet schema with forecast/actual/surprise/identity fields; fixture-test the fragile parser; investigate the FF API endpoint
- [ ] **Phase 3: Cache Lifecycle** - Auto-widen cache on scope miss; auto-refresh matured future months; force-refresh on demand

## Phase Details

### Phase 1: Installable Data Provider

**Goal**: Users can install the package, populate the shared cache from the existing 195 months of raw data without any HTTP requests, and query it to receive a valid parquet file path.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, CACHE-01, CACHE-02, CACHE-04, DATA-01, SRC-02, QUAL-01, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):

  1. `pip install -e .` succeeds and `import forexfactory` works in a fresh Python environment without importing scrape.py or pipeline.py directly
  2. `forexfactory populate` re-processes the existing `out/` months into `~/.cache/forexfactory/` without making any HTTP requests
  3. `forexfactory query --currency USD --impact high` prints an absolute path to a parquet file that opens cleanly with `pd.read_parquet()`
  4. The library call `forexfactory.get(currencies=["USD"], impacts=["high"])` returns a `pathlib.Path` pointing to the populated parquet
  5. Running `forexfactory populate` on months where a prior scrape failed does not permanently skip those months due to a stale empty JSON file**Plans**: 7 plans

**Wave 1**

  - [x] 01-01-PLAN.md — Installable package scaffold + reused pipeline engine (QUAL-01/02)

**Wave 2** *(blocked on Wave 1 completion)*

  - [x] 01-02-PLAN.md — Cache layer: per-month paths + manifest sidecar (CACHE-01, D-01/02/03/08)

**Wave 3** *(blocked on Wave 2 completion)*

  - [x] 01-03-PLAN.md — Populate slice: ingest on-disk months → per-month parquet cache (D-04/05/06, SC5)
  - [x] 01-04-PLAN.md — Query slice: cache read → consolidated result parquet, library get() (D-07/08/09)

**Wave 4** *(blocked on Wave 3 completion)*

  - [x] 01-05-PLAN.md — CLI integration + walking-skeleton end-to-end (PKG-02, D-10/12)

**Wave 5** *(blocked on Wave 4 completion)*

  - [x] 01-06-PLAN.md — Refresh network slice + scrape relocation (SRC-02, QUAL-03/04, D-11)

**Wave 6** *(blocked on Wave 5 completion)*

  - [x] 01-07-PLAN.md — Docs + doc-regression sweep (README/CLI/schema, remove api.txt)

### Phase 2: Full Analytical Schema + Source Spike

**Goal**: The cached parquet contains all fields needed for expected-vs-surprise analysis (forecast/actual/previous/revision as raw strings and parsed numerics, surprise flags, identity fields); the fragile HTML/JS parser is protected by fixture-based regression tests; and the FF apply-settings POST endpoint has been investigated with a documented decision on whether to adopt it.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: DATA-02, DATA-03, DATA-04, DATA-05, QUAL-05, SRC-01
**Success Criteria** (what must be TRUE):

  1. A row loaded from the cache parquet contains `forecast_raw`, `actual_raw`, `previous_raw`, `revision_raw` (str) alongside `forecast`, `actual`, `previous`, `revision` (float or null) columns
  2. A row loaded from the cache parquet contains `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, and `country` fields
  3. Speech and holiday events appear in the cache; `forexfactory query --has-data-values false` returns them and they are absent when that filter is omitted
  4. `pytest tests/` passes including at least one fixture-based test that feeds a realistic saved HTML fragment into `extract_days()` and asserts correct event output
  5. A documented decision exists (PROJECT.md Key Decisions or inline in the source) stating whether the apply-settings endpoint replaces or remains a documented fallback to the HTML parser

**Plans**: 5 plans

**Wave 1**

  - [x] 02-01-PLAN.md — Schema core: _parse_value + widened flatten_events + force rebuild (DATA-02/03/04)
  - [ ] 02-03-PLAN.md — QUAL-05 parser fixtures + ExtractDaysFixtureTests
  - [ ] 02-04-PLAN.md — SRC-01 apply-settings spike + documented decision (SRC-01)

**Wave 2** *(blocked on Wave 1 completion)*

  - [ ] 02-02-PLAN.md — Query no-data filter + --include-no-data/--force CLI surface (DATA-05)

**Wave 3** *(blocked on Wave 2 completion)*

  - [ ] 02-05-PLAN.md — Cache rebuild to wide schema + raw-JSON drop (phase exit)

### Phase 3: Cache Lifecycle

**Goal**: The cache self-manages: a query that exceeds cached scope triggers automatic fetch and widening; months that were scraped while future-dated automatically re-fetch once they have fully matured; and a force-refresh flag bypasses the skip-if-exists logic for any given range.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CACHE-03, CACHE-05, CACHE-06
**Success Criteria** (what must be TRUE):

  1. Querying for a currency/impact combination absent from the cache (e.g., EUR/medium when only USD/high is populated) automatically fetches the missing scope and widens the cache without any manual populate step
  2. Months that were scraped while future-dated and are now fully in the past are automatically re-fetched on the next `populate` or `query` call, with their `actual` values populated in the cache
  3. `forexfactory populate --force-refresh --start 2025-01` (and equivalent library argument) re-scrapes the specified range and overwrites the cached parquet regardless of existing cache state

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Installable Data Provider | 7/7 | Complete    | 2026-06-08 |
| 2. Full Analytical Schema + Source Spike | 1/5 | In Progress|  |
| 3. Cache Lifecycle | 0/TBD | Not started | - |
