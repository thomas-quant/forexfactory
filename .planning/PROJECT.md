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

**Shipped in Phase 3 — Cache Lifecycle (2026-06-09):**

- ✓ Scope-miss auto-widen: a `query`/`get()` for an uncached currency/impact combo auto-fetches the full missing scope and permanently widens the cache, no manual `populate` step (`widen_scope_to_cover`, full cached-range union scope); failure raises `AutoFetchError` (fail-closed, no partial data) — CACHE-03 (D-05/D-06)
- ✓ Matured-month auto-refresh: `settled:false` months that have fully matured auto re-fetch on the next `populate`/`query` to fill in `actual` values; re-fetch failure serves the stale forecast-only parquet and warns (never crashes) — CACHE-05 (D-08/D-10)
- ✓ Single `auto_fetch` knob (default `True`) suppresses BOTH auto-triggers for strict cache-only reads; exposed as `get(auto_fetch=…)`/`populate(auto_fetch=…)` and CLI `--no-auto-fetch` on `populate`/`query` — CACHE-05 (D-07/D-09)
- ✓ Force-refresh on demand: `--force-refresh` on `populate` and `refresh` (and `force_refresh=` library kwarg + new `forexfactory.populate()`) re-scrapes a range over the network and overwrites cached parquets, bypassing skip-if-cached; partial failures keep prior parquets and report `fetched/skipped/failed` — CACHE-06 (D-01/D-02/D-03/D-04)
- ✓ CLI auto-fetch progress banners (scope-miss + matured) print from `cli.py` only; the library stays stdout-silent (D-11/D-12)
- ✓ Code review (quick) found + remediated a critical data-loss bug (CR-01: `refresh --force-refresh` at a subset scope silently narrowed cached parquets) plus 3 warnings; force-refresh now unions manifest scope before rebuild — see `03-REVIEW.md`. Suite at 169 tests.

### Active

All v1.0 requirements shipped. Active requirements for the next milestone (v1.1 / v2.0) will be defined via `/gsd-new-milestone`.

### Out of Scope

- FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*` flags, `notice`, naming duplicates) — no analytical value
- Real-time / streaming updates — manual refresh + matured-month auto-refresh is sufficient
- Hosted API server, database backend, or dashboard/GUI — this is a data provider; the parquet cache is the contract
- Currencies/impacts the user never queries — cache stays scoped to what's populated/requested

## Context

**v1.0 shipped 2026-06-09.** The package is fully functional and self-managing:

- **Current state:** pip-installable `forexfactory` package (`src/forexfactory/`, ~2,440 LOC + 4,444 test LOC); 169 tests passing; durable `~/.cache/forexfactory/` parquet cache at `schema_version "2"` covering 195 months (2010-01 → 2026-03)
- **The fragile core:** `extract_days()` walks embedded JS character-by-character to convert it to JSON. Protected by 4 golden HTML fixtures in `tests/fixtures/` (QUAL-05). `/calendar/more` exists as a validated clean-JSON fallback if it breaks (see Key Decisions).
- **SRC-GRAPH-01** (`GET /calendar/graph/{eventId}`) is the highest-value future enhancement: returns clean numeric per-event historical time-series (actual/forecast/revision) for expected-vs-surprise analysis without month-by-month scraping. Requires event `id` + `siteId`. Filed as future enhancement.
- **Known tech debt:** IN-01 (scope-union/settled-check extraction, refactor-only), IN-02 (silent `except pass` in matured loop, under-counts banner in pathological cases only). Both low severity.
- **Known concerns** are catalogued in `.planning/codebase/CONCERNS.md`.

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
| Cache scope configurable at populate time; auto-widen on out-of-scope query | Avoid caching everything up front, but never block a legitimate request | ✓ populate-time scope Phase 1; ✓ auto-widen Phase 3 (CACHE-03, raise `AutoFetchError` on fetch failure) |
| Freshness: manual for settled history; auto-refresh only matured future months | Past is immutable; only future-dated forecasts need to mature into actuals | ✓ manual settled Phase 1; ✓ matured auto-refresh Phase 3 (CACHE-05, serve-stale-on-failure) |
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
*Last updated: 2026-06-09 after v1.0 milestone — all 22 CACHE/PKG/DATA/SRC/QUAL requirements shipped. 169 tests passing. Next milestone: `/gsd-new-milestone`.*
