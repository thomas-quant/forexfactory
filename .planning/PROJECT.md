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

**Shipped in Phase 1 — Installable Data Provider (2026-06-08):**

- ✓ pip-installable `forexfactory` package (src layout, `pyproject.toml`); `import forexfactory` works — PKG-01
- ✓ Unified `forexfactory` CLI: `populate` / `query` / `refresh` — PKG-02
- ✓ Library API `forexfactory.get(currencies=[...], impacts=[...]) -> pathlib.Path` (returns a parquet path) — PKG-03
- ✓ Existing `scrape.py` / `pipeline.py` reused (relocated under `src/forexfactory/`, not rewritten); ~195 months re-processed with zero HTTP — PKG-04
- ✓ Shared parquet cache in a configurable user dir (`~/.cache/forexfactory`, env/`--cache-dir` override); per-month parquet + `manifest.json` sidecar — CACHE-01, CACHE-02
- ✓ Settled (fully-past) months never auto-refetched — CACHE-04
- ✓ Core schema `datetime_utc, currency, impact, title, id, leaked` — DATA-01
- ✓ HTML-scrape-and-parse retained as the source, wired into `refresh` — SRC-02
- ✓ Code-quality debt paid down: shared `_deduplicate_rows()` (QUAL-01), `--in-dir` honored (QUAL-02), no empty-JSON skip-poisoning (QUAL-03), stale date defaults removed (QUAL-04)

**Shipped in Phase 2 — Full Analytical Schema + Source Spike (2026-06-08):**

- ✓ Analytical value fields stored as **raw strings + parsed numerics**: `forecast(_raw)`, `actual(_raw)`, `previous(_raw)`, `revision(_raw)`, plus `hasDataValues` — DATA-02, DATA-03
- ✓ Surprise + identity fields: `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country` — DATA-04
- ✓ No-data events (speeches/holidays) first-class in the cache and filterable via `query --include-no-data` / `get(include_no_data=...)` — DATA-05
- ✓ Fixture-based regression tests for the fragile `calendarComponentStates` parser (4 golden HTML fixtures: both assignment forms + empty + multi-candidate) — QUAL-05
- ✓ FF `apply-settings` endpoint investigated; documented **NOT-ADOPTED** decision (HTML parse stays primary; `/calendar/more` validated JSON fallback; `/calendar/graph` filed as future enhancement) — SRC-01
- ✓ Cache rebuilt to `schema_version "2"` across all 195 months (zero re-scrape); raw JSON staging layer dropped per the locked D-03 exit condition

### Active

<!-- This milestone: turn the toolkit into a cached, packaged data provider. Hypotheses until shipped. -->

**Packaging & interfaces** — ✓ all shipped in Phase 1 (see Validated above)

**Cache** (remaining for later phases)
- [ ] When a query exceeds the cached scope, auto-fetch the missing data and widen the cache — Phase 3 (Phase 1 errors with guidance instead)
- [ ] Future-dated months auto-refresh once the whole month has passed, to fill in `actual` values (forecast-only events mature into expected-vs-surprise) — Phase 3

**Data schema** — ✓ all shipped (Phase 1 core + Phase 2 values/surprise/identity)
- [x] Core fields: `datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked` — ✓ Phase 1
- [x] Data values: `forecast`, `actual`, `previous`, `revision`, `hasDataValues` — stored as **raw strings + parsed numeric** — ✓ Phase 2 (DATA-02, DATA-03, DATA-05)
- [x] Surprise + identity: `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country` — ✓ Phase 2 (DATA-04)

**Data source**
- [x] HTML-scrape-and-parse retained as the source (wired into `refresh`) — ✓ Phase 1 (SRC-02)
- [x] Investigate the FF JSON/POST endpoint (`apply-settings`) — NOT ADOPTED (SC5): apply-settings is a settings-save endpoint only; `/calendar/more` is a validated clean-JSON fallback that clears all 4 D-06 criteria but is append-paginated; HTML `?month=` GET stays bulk primary — Phase 2 (SRC-01 spike)

**Code quality (full restructure + fix mapped concerns)**
- [x] Extract shared deduplication helper (remove copy-paste between `parse_json_to_csv` / `run_pipeline`) — ✓ Phase 1
- [x] Fix `--in-dir` silent no-op in full-pipeline mode — ✓ Phase 1
- [x] Stop writing empty JSON on failed scrapes (no permanent skip-poisoning) — ✓ Phase 1
- [x] Replace stale hardcoded date defaults with sensible/explicit behavior — ✓ Phase 1
- [ ] Add a force-refresh / re-scrape capability — Phase 3
- [x] Add fixture-based tests for the fragile `calendarComponentStates` parser — ✓ Phase 2 (QUAL-05)

### Out of Scope

- FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*` flags, `notice`, naming duplicates) — no analytical value
- Real-time / streaming updates — manual refresh + matured-month auto-refresh is sufficient
- Hosted API server, database backend, or dashboard/GUI — this is a data provider; the parquet cache is the contract
- Currencies/impacts the user never queries — cache stays scoped to what's populated/requested

## Context

- **Existing system:** Two independent scripts communicating only through files. `scrape.py` fetches HTML → `out/days_YYYY_MM.json`; `pipeline.py` reads those → `economic_events.parquet`. See `.planning/codebase/ARCHITECTURE.md`.
- **The fragile core:** `extract_days()` walks embedded JS character-by-character to convert it to JSON. Any change to FF's bundle silently breaks it. As of Phase 2 it is protected by golden HTML fixtures in `tests/fixtures/` (QUAL-05); the SRC-01 spike investigated a JSON endpoint to reduce reliance on it and concluded HTML parse stays primary (`/calendar/more` JSON exists as a validated fallback).
- **Rich raw data already on disk:** each raw event carries ~50 fields (forecast/actual/previous/revision, `actualBetterWorse`, `ebaseId`, etc.); today's pipeline discards all but 6. Re-processing existing `out/` data into the new schema requires no re-scraping.
- **Known concerns** are catalogued in `.planning/codebase/CONCERNS.md` (tech debt, bugs, fragile areas, test gaps) and feed the Active code-quality requirements.
- **`api.txt`** (removed in Phase 1) held the single lead for the data-source investigation: `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1`. The SRC-01 spike (Phase 2) confirmed apply-settings is a settings-save endpoint only; `/calendar/more` is a validated clean-JSON fallback; HTML `?month=` GET remains the bulk primary (see Key Decisions + `02-SRC01-SPIKE.md`).

## Constraints

- **Tech stack**: Python 3.12+, `curl_cffi`, `pandas`, `pyarrow` — keep; proven and already in use
- **Usage**: Personal/research — respect Forex Factory's terms of service and rate limits (non-zero default delays advised; see CONCERNS.md)
- **Access**: No authentication (public site); `curl_cffi` TLS fingerprint impersonation is the anti-bot measure
- **Compatibility**: Re-use the existing scrape logic and the ~195 cached months rather than re-acquiring data

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Distribution model: cached data provider, not a bundled dataset or pure tooling lib | Fetch once, reuse across projects; data isn't shipped in the package | ✓ Phase 1 |
| Cache stored as parquet, shared user cache dir (configurable) | One machine-wide cache serves all projects; parquet is the read format anyway | ✓ Phase 1 (per-month parquet + manifest) |
| Cache scope configurable at populate time; auto-widen on out-of-scope query | Avoid caching everything up front, but never block a legitimate request | Partial — populate-time scope ✓ Phase 1; auto-widen → Phase 3 (Phase 1 errors with guidance) |
| Freshness: manual for settled history; auto-refresh only matured future months | Past is immutable; only future-dated forecasts need to mature into actuals | Partial — manual settled ✓ Phase 1; matured auto-refresh → Phase 3 |
| Schema: core + values (raw+parsed) + FF surprise flags + `ebaseId` | Supports expected-vs-surprise and joining a metric's release history | ✓ core fields Phase 1; values/surprise/identity Phase 2 (schema_version "2") |
| Library main call returns a parquet path (not a DataFrame) | Consistent with the parquet cache contract; caller loads as needed | ✓ Phase 1 (`forexfactory.get() -> Path`) |
| Investigate FF JSON/POST endpoint (SRC-01) — NOT ADOPTED (SC5): apply-settings is settings-save only; `/calendar/more` validated clean-JSON fallback (clears all 4 D-06 criteria) but append-paginated so HTML `?month=` GET stays bulk primary; `/calendar/graph` filed as high-value future enhancement (numeric per-event time-series) | Reduce reliance on the fragile char-by-char JS parser; HTML `?month=` parse wins ergonomically (1 request/month vs 4–5 weekly POSTs for `/calendar/more`) | NOT ADOPTED — Phase 2 (SRC-01 spike, 2026-06-08) |
| Full restructure + fix mapped concerns (vs minimal wrap) | Packaging is the moment to pay down the catalogued debt | ✓ Phase 1 (QUAL-01..04); QUAL-05 + force-refresh → Phase 2/3 |

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
*Last updated: 2026-06-08 — Phase 2 (Full Analytical Schema + Source Spike) complete: parquet schema_version "2" with raw+parsed value fields, surprise/identity fields, `hasDataValues` + `--include-no-data`; fixture-protected parser (QUAL-05); SRC-01 spike resolved NOT-ADOPTED (HTML parse primary; `/calendar/more` JSON fallback, `/calendar/graph` future enhancement); cache rebuilt across 195 months, raw JSON staging dropped (D-03). Next: Phase 3 — cache lifecycle (auto-widen, matured-month auto-refresh, force-refresh).*
