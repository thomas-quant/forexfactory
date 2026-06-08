# Requirements: forexfactory

**Defined:** 2026-06-08
**Core Value:** Fetch the Forex Factory calendar once and reuse it everywhere from a shared local cache, with the data fidelity needed for expected-vs-surprise analysis.

## v1 Requirements

Requirements for the initial packaged release. Each maps to a roadmap phase.

### Packaging & Distribution

- [x] **PKG-01**: Project is a pip-installable package (src layout, `pyproject.toml`, importable as `forexfactory`)
- [x] **PKG-02**: A unified CLI entry point exposes populate, refresh, and query commands
- [x] **PKG-03**: A programmatic library API exposes a main call that returns a path to a parquet file
- [x] **PKG-04**: Existing scrape/pipeline logic is reused (not rewritten) and the ~195 cached months are re-processed into the new schema without re-scraping

### Cache

- [x] **CACHE-01**: Data is cached as parquet in a shared user cache dir (default `~/.cache/forexfactory` / OS equivalent), overridable via path/env var
- [x] **CACHE-02**: Cache scope (currencies, impacts) is chosen when the cache is populated
- [ ] **CACHE-03**: A query that exceeds cached scope auto-fetches the missing data and widens the cache
- [x] **CACHE-04**: Settled (fully-past) months are never re-fetched automatically — manual refresh only
- [ ] **CACHE-05**: Months cached while future-dated are auto-refreshed once the whole month has passed, to fill in `actual` values
- [ ] **CACHE-06**: A force-refresh capability can re-scrape a given range on demand (CLI flag + library arg)

### Data Schema

- [x] **DATA-01**: Each event record carries the core fields: `datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked`
- [x] **DATA-02**: Each event carries data values `forecast`, `actual`, `previous`, `revision`, `hasDataValues`, stored as both raw strings and parsed numeric
- [x] **DATA-03**: Each event carries surprise/identity fields `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country`
- [x] **DATA-04**: FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*`, `notice`, naming duplicates) are dropped
- [x] **DATA-05**: Speech/holiday/no-data events are retained in the cache (distinguished by `hasDataValues`); dropping them becomes an optional query-time filter rather than a hard pipeline step

### Data Source

- [x] **SRC-01**: The FF JSON/POST endpoint (`apply-settings`) is investigated as a spike; if it reliably returns structured data, it replaces the HTML/JS parser as the primary source
- [x] **SRC-02**: HTML-scrape-and-parse-embedded-JS is retained as a fallback source

### Code Quality

- [x] **QUAL-01**: Deduplication logic is extracted into a single shared helper (no copy-paste between parse and full-pipeline paths)
- [x] **QUAL-02**: The `--in-dir` (input directory) option is honored in all execution paths (no silent no-op)
- [x] **QUAL-03**: Failed scrapes no longer write empty JSON files that permanently poison the skip logic
- [x] **QUAL-04**: Stale hardcoded date defaults are removed in favor of explicit/sensible behavior
- [x] **QUAL-05**: Fixture-based regression tests cover the `calendarComponentStates` parser against realistic saved HTML

## v2 Requirements

Deferred — acknowledged but not in the current roadmap.

### Distribution

- **DIST-01**: Publish the package to PyPI (v1 ships as a buildable wheel installable from local/git)

### Cache

- **CACHE-V2-01**: Chunked/streaming processing for very wide cache scopes (all currencies + all impacts)

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time / streaming calendar updates | Manual refresh + matured-month auto-refresh is sufficient |
| Hosted API server or database backend | This is a local data provider; the parquet cache is the contract |
| Dashboard / GUI | Data provider only; consumers build their own views |
| Storing FF UI/internal fields | No analytical value (see DATA-04) |
| Caching currencies/impacts never queried | Cache stays scoped to what is populated/requested |

## Traceability

Populated during roadmap creation — each requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-01 | Phase 1 | Complete |
| PKG-02 | Phase 1 | Complete |
| PKG-03 | Phase 1 | Complete |
| PKG-04 | Phase 1 | Complete |
| CACHE-01 | Phase 1 | Complete |
| CACHE-02 | Phase 1 | Complete |
| CACHE-03 | Phase 3 | Pending |
| CACHE-04 | Phase 1 | Complete |
| CACHE-05 | Phase 3 | Pending |
| CACHE-06 | Phase 3 | Pending |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 2 | Complete |
| DATA-03 | Phase 2 | Complete |
| DATA-04 | Phase 2 | Complete |
| DATA-05 | Phase 2 | Complete |
| SRC-01 | Phase 2 | Complete |
| SRC-02 | Phase 1 | Complete |
| QUAL-01 | Phase 1 | Complete |
| QUAL-02 | Phase 1 | Complete |
| QUAL-03 | Phase 1 | Complete |
| QUAL-04 | Phase 1 | Complete |
| QUAL-05 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-08*
*Last updated: 2026-06-08 after roadmap creation — all 22 requirements mapped*
