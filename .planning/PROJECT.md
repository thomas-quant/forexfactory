# forexfactory — Cached Economic Calendar Data Provider

## What This Is

A pip-installable Python package that scrapes the [Forex Factory](https://www.forexfactory.com/calendar) economic calendar and serves it from a shared local cache. Install once, fetch once, and read the data from any project — via a CLI or as a library. It replaces today's two loose scripts (`scrape.py`, `pipeline.py`) with a proper package, a parquet-based cache, and a richer event schema. For personal/research use.

## Core Value

**Fetch the calendar once and reuse it everywhere, without re-scraping** — a durable shared cache that any of the user's projects can read, with the data fidelity needed for expected-vs-surprise analysis.

## Requirements

### Validated

<!-- Inferred from the existing, working codebase (see .planning/codebase/). -->

- ✓ Browserless scraping of the FF calendar via `curl_cffi` with Chrome TLS impersonation — existing
- ✓ Incremental, month-by-month scraping that skips already-downloaded months (safe to resume) — existing
- ✓ Extraction of the embedded `calendarComponentStates` JS state (both `= {...}` and `[n] = {...}` forms) — existing
- ✓ ETL pipeline: raw JSON → filtered, deduplicated Parquet (currency + impact filter, "speaks" sanitize) — existing
- ✓ Parquet output with `zstd` compression — existing
- ✓ Regression test suite covering scrape, pipeline, and docs — existing
- ✓ ~195 months of raw data already scraped locally (2010-01 → 2026-03) — existing asset

### Active

<!-- This milestone: turn the toolkit into a cached, packaged data provider. Hypotheses until shipped. -->

**Packaging & interfaces**
- [ ] Distribute as a pip-installable package (src layout, `pyproject.toml`)
- [ ] Unified CLI entry point (populate / refresh / query)
- [ ] Programmatic library API whose main call **returns a path to a parquet file**

**Cache**
- [ ] Shared, parquet-based cache (not raw JSON) in a configurable user cache dir (default `~/.cache/forexfactory` / OS equivalent)
- [ ] Cache scope (currencies / impacts) chosen when the cache is populated
- [ ] When a query exceeds the cached scope, auto-fetch the missing data and widen the cache
- [ ] Settled history is manual-refresh only (no silent re-scraping of the past)
- [ ] Future-dated months auto-refresh once the whole month has passed, to fill in `actual` values (forecast-only events mature into expected-vs-surprise)

**Data schema**
- [ ] Core fields: `datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked`
- [ ] Data values: `forecast`, `actual`, `previous`, `revision`, `hasDataValues` — stored as **raw strings + parsed numeric**
- [ ] Surprise + identity: `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country`

**Data source**
- [ ] Investigate the FF JSON/POST endpoint (`apply-settings`); switch to it if it reliably returns structured data, keeping HTML-scrape-and-parse as a fallback

**Code quality (full restructure + fix mapped concerns)**
- [ ] Extract shared deduplication helper (remove copy-paste between `parse_json_to_csv` / `run_pipeline`)
- [ ] Fix `--in-dir` silent no-op in full-pipeline mode
- [ ] Stop writing empty JSON on failed scrapes (no permanent skip-poisoning)
- [ ] Replace stale hardcoded date defaults with sensible/explicit behavior
- [ ] Add a force-refresh / re-scrape capability
- [ ] Add fixture-based tests for the fragile `calendarComponentStates` parser

### Out of Scope

- FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*` flags, `notice`, naming duplicates) — no analytical value
- Real-time / streaming updates — manual refresh + matured-month auto-refresh is sufficient
- Hosted API server, database backend, or dashboard/GUI — this is a data provider; the parquet cache is the contract
- Currencies/impacts the user never queries — cache stays scoped to what's populated/requested

## Context

- **Existing system:** Two independent scripts communicating only through files. `scrape.py` fetches HTML → `out/days_YYYY_MM.json`; `pipeline.py` reads those → `economic_events.parquet`. See `.planning/codebase/ARCHITECTURE.md`.
- **The fragile core:** `extract_days()` walks embedded JS character-by-character to convert it to JSON. Any change to FF's bundle silently breaks it; `tests/fixtures/` is currently empty (highest-priority coverage gap). This is the main risk the "investigate the API endpoint" decision aims to reduce.
- **Rich raw data already on disk:** each raw event carries ~50 fields (forecast/actual/previous/revision, `actualBetterWorse`, `ebaseId`, etc.); today's pipeline discards all but 6. Re-processing existing `out/` data into the new schema requires no re-scraping.
- **Known concerns** are catalogued in `.planning/codebase/CONCERNS.md` (tech debt, bugs, fragile areas, test gaps) and feed the Active code-quality requirements.
- **`api.txt`** holds the single lead for the data-source investigation: `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` ("possibly can send post requests?").

## Constraints

- **Tech stack**: Python 3.12+, `curl_cffi`, `pandas`, `pyarrow` — keep; proven and already in use
- **Usage**: Personal/research — respect Forex Factory's terms of service and rate limits (non-zero default delays advised; see CONCERNS.md)
- **Access**: No authentication (public site); `curl_cffi` TLS fingerprint impersonation is the anti-bot measure
- **Compatibility**: Re-use the existing scrape logic and the ~195 cached months rather than re-acquiring data

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Distribution model: cached data provider, not a bundled dataset or pure tooling lib | Fetch once, reuse across projects; data isn't shipped in the package | — Pending |
| Cache stored as parquet, shared user cache dir (configurable) | One machine-wide cache serves all projects; parquet is the read format anyway | — Pending |
| Cache scope configurable at populate time; auto-widen on out-of-scope query | Avoid caching everything up front, but never block a legitimate request | — Pending |
| Freshness: manual for settled history; auto-refresh only matured future months | Past is immutable; only future-dated forecasts need to mature into actuals | — Pending |
| Schema: core + values (raw+parsed) + FF surprise flags + `ebaseId` | Supports expected-vs-surprise and joining a metric's release history | — Pending |
| Library main call returns a parquet path (not a DataFrame) | Consistent with the parquet cache contract; caller loads as needed | — Pending |
| Investigate FF JSON/POST endpoint, switch if cleaner, HTML fallback | Reduce reliance on the fragile char-by-char JS parser | — Pending |
| Full restructure + fix mapped concerns (vs minimal wrap) | Packaging is the moment to pay down the catalogued debt | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-08 after initialization*
