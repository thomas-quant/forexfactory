# Phase 1: Installable Data Provider - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Wrap the existing `scrape.py` + `pipeline.py` into a pip-installable `forexfactory`
package (src layout, `pyproject.toml`) that exposes a unified CLI
(`populate` / `refresh` / `query`) and a library API whose main call returns a
parquet **path**. Back it with a parquet cache in `~/.cache/forexfactory`,
populated from the existing ~195 months of raw JSON **without any HTTP**, and pay
down the mapped code-quality debt (QUAL-01..04).

**In scope (Phase 1):** PKG-01..04, CACHE-01, CACHE-02, CACHE-04, DATA-01 (core
fields only), SRC-02 (HTML scrape wired in as a source), QUAL-01..04.

**Explicitly NOT this phase:**
- Rich analytical schema — forecast/actual/previous/revision, surprise flags,
  `ebaseId`, `country`, raw+parsed values, `hasDataValues` retention → **Phase 2**
  (DATA-02..05, QUAL-05, SRC-01 API spike).
- Auto-widen cache on scope miss, auto-refresh matured future months,
  force-refresh/overwrite flag → **Phase 3** (CACHE-03, CACHE-05, CACHE-06).

</domain>

<decisions>
## Implementation Decisions

### Cache Layout
- **D-01: Per-month parquet files.** The cache stores one parquet per calendar
  month (e.g. `2024-03.parquet`, or an equivalent month-partitioned pyarrow
  dataset). Chosen because the month is the natural scrape/refresh unit:
  refreshing a single month or (Phase 3) force-refreshing a range rewrites only
  those files. Rejected: single combined parquet (any refresh rewrites the whole
  file), partition-by-currency/impact (month-granular refresh becomes awkward).
- **D-02: `manifest.json` sidecar** at the cache root tracks (a) the populated
  **scope** — which currencies/impacts have been populated — and (b) per-month
  **provenance**: when each month was scraped and whether it was **settled**
  (fully in the past) vs future-dated at scrape time. Phase 1 uses it to honor
  CACHE-04 (never auto-refetch settled months) and for scope-miss detection
  (query error, D-09); Phase 3 reads it for auto-widen and matured-month refresh.
  Rejected: deriving scope from distinct values present in the parquet (can't
  distinguish "only USD populated" from "this month had no EUR events", and can't
  record scrape time).
- **D-03: Raw JSON is a temporary staging layer.** For Phase 1 the raw per-month
  JSON lives inside the cache dir (e.g. `~/.cache/forexfactory/raw/`) and backs
  the parquet build. It is the source of truth **only until Phase 2** extracts the
  full analytical schema into parquet, after which the JSON layer is **dropped**
  and parquet becomes the sole persistent store. (User: "I despise json.")
  - **Cross-phase consequence (Phase-2 exit condition):** Phase 2 MUST extract
    every field of lasting value (incl. raw-string forms) into parquet *before*
    removing the JSON. After that, obtaining any new field requires a **re-scrape**,
    not a re-parse — this is accepted.

### Populate Defaults
- **D-04: Default scope = USD + high/holiday** when `populate` runs with no
  `--currency`/`--impact` flags. Matches today's proven `KEEP_CURRENCIES` /
  `KEEP_IMPACTS` and the existing `economic_events.parquet`; smallest cache, zero
  surprise. Widen explicitly with flags (auto-widen is Phase 3).
- **D-05: Default range = all months on disk** (~195, 2010-01 → 2026-03).
  `populate` reads the local raw layer with no network; `--start`/`--end` narrow
  it. This is the QUAL-04 replacement for the stale hardcoded
  `2021-01-01 → 2021-06-30` default.
- **D-06: Re-run is incremental + scope-aware.** A month is skipped only if the
  manifest shows it is already cached **at the requested scope**; months that are
  missing or cached at a *narrower* scope are (re)built. Empty/failed raw JSON
  counts as "not cached" so it is retried, never permanently skipped — this is the
  mechanism behind success-criterion 5 and the QUAL-03 fix (stop empty-JSON
  skip-poisoning).

### Query Contract
- **D-07: `query` / `get()` returns a derived result parquet.** It reads the
  relevant per-month cache files, applies the currency/impact/date filter, writes
  ONE consolidated parquet, and returns its absolute path (`pathlib.Path` from the
  library, printed path from the CLI). Required because storage is per-month but
  the contract is a single parquet path.
- **D-08: Result file = deterministic path, regenerated each query.** Written to a
  stable path keyed by the filter (e.g.
  `~/.cache/forexfactory/queries/USD_high_<range>.parquet`) and **overwritten** from
  the current cache on every call. Stable path callers can rely on, never stale,
  no temp-file sprawl. (Reuse-if-unchanged is a fine later optimization but not
  required now.)
- **D-09: Out-of-scope query → error with guidance.** When the manifest shows the
  request exceeds the populated scope, `query` exits non-zero with an actionable
  message (e.g. `EUR/medium not populated — run: forexfactory populate --currency
  EUR --impact medium`). No silent partial/empty results. Phase 3 replaces this
  hard error with auto-fetch + widen.

### CLI Surface
- **D-10: `query` writes path-only to stdout.** stdout = just the absolute parquet
  path, so `PARQUET=$(forexfactory query --currency USD --impact high)` works.
  Summaries/diagnostics (row count, scope, timing) go to stderr / logging.
- **D-11: `refresh` fetches missing months over the network** in Phase 1 — it
  wires in the existing `scrape.py` logic (SRC-02) to fetch a range from Forex
  Factory, adds months **not yet cached** (e.g. 2026-04..current), and builds their
  parquet. It does **not** overwrite already-cached months (force-refresh =
  CACHE-06, Phase 3) and has no auto-maturity (CACHE-05, Phase 3). This keeps
  `refresh` a real, advertised command (PKG-02) and lets the cache extend past the
  on-disk 2026-03 boundary.
  - **Note:** introducing the network path makes the scrape rate-limit default
    matter — CONCERNS flags today's `BETWEEN_PAGES_DELAY = 0.0` / `RETRY_DELAY = 0.0`;
    the planner should set a polite non-zero default.
- **D-12: Scope passed via repeatable singular flags** — `--currency USD
  --currency EUR`, `--impact high --impact holiday` (argparse `append`). Mirrors
  the library list args (`currencies=["USD"]`, `impacts=["high"]`); no
  comma-splitting.

### Package Identity
- **D-13: The name is `forexfactory` everywhere** — import name, library namespace
  (`forexfactory.get(...)`), and the single console-script command
  (`forexfactory populate` / `refresh` / `query`). This is **locked upstream**, not
  a discussion choice: REQUIREMENTS.md PKG-01 ("importable as `forexfactory`") and
  ROADMAP.md Phase-1 Success Criterion 1 (`import forexfactory`). Recorded here
  only to make it explicit for the planner.
  - **Distribution name** (`[project] name` in `pyproject.toml`) = `forexfactory`,
    kept identical to the import name. PyPI publishing is deferred to v2 (DIST-01),
    so v1 only needs to be locally/git pip-installable (`pip install -e .`).
  - **src layout:** package lives at `src/forexfactory/`.
  - **No short CLI alias** (e.g. `ff`) by default — single entry point
    `forexfactory`. (Easy to add later if wanted.)

### Claude's Discretion
The planner/researcher decides these (no user constraint beyond the decisions above):
- Internal package module structure / decomposition (src layout under
  `src/forexfactory/`).
- Exact `manifest.json` schema and serialization format.
- The result-parquet subdir name and the deterministic key/hash scheme for D-08.
- `refresh`'s default network range — sensible default is gap-fill from the last
  cached month through the current month.
- The polite non-zero default scrape delay value (D-11 note).
- Mechanics of the QUAL fixes whose intent is already locked by REQUIREMENTS:
  shared `_deduplicate_rows()` helper (QUAL-01), threading `--in-dir` through all
  paths (QUAL-02), not writing empty JSON on failed scrapes (QUAL-03), removing
  stale date defaults (QUAL-04).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning (scope + requirements)
- `.planning/PROJECT.md` — project vision, Key Decisions table (distribution
  model, parquet cache dir, library-returns-path, full restructure).
- `.planning/REQUIREMENTS.md` — the 22 v1 requirements + traceability; Phase 1
  owns PKG-01..04, CACHE-01/02/04, DATA-01, SRC-02, QUAL-01..04.
- `.planning/ROADMAP.md` §"Phase 1: Installable Data Provider" — goal + the 5
  success criteria this phase must make true.

### Existing code to reuse (do NOT rewrite from scratch)
- `scrape.py` — browserless FF scraper; `extract_days()` / `run_scraper()` and the
  `calendarComponentStates` parser to be wired into the package (`refresh`, SRC-02).
- `pipeline.py` — JSON→Parquet ETL; `flatten_events()` / `run_pipeline()` are the
  basis for `populate`. Note the dedup duplication (QUAL-01) and `--in-dir` no-op
  (QUAL-02) live here.
- `tests/test_scrape.py`, `tests/test_pipeline.py`, `tests/test_docs.py` — existing
  regression suite to carry forward / adapt; `tests/fixtures/` is empty (fixtures
  are Phase 2, QUAL-05).

### Codebase maps
- `.planning/codebase/CONCERNS.md` — authoritative source for the QUAL-01..04 fixes
  (stale dates, dup dedup, `--in-dir` no-op, empty-JSON poisoning) with file/line
  pointers.
- `.planning/codebase/STRUCTURE.md` — current layout + "Where to Add New Code".
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md` —
  module responsibilities and naming/style conventions to preserve in the package.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline.py:run_pipeline()` / `flatten_events()` / `parse_json_to_csv()` — the
  filter + dedup + parquet-write logic that `populate` is built from. Extract the
  copy-pasted dedup block into a shared `_deduplicate_rows()` (QUAL-01) while doing so.
- `scrape.py:run_scraper()` / `extract_days()` + the `calendarComponentStates`
  parser — reused wholesale to back `refresh` (SRC-02). The month-skip logic and
  the empty-JSON-on-failure bug (`scrape.py:379-387`) must change to satisfy
  D-06 / QUAL-03.
- Module-level config constants (`KEEP_CURRENCIES`, `KEEP_IMPACTS`, compression
  settings) — become package defaults (USD + high/holiday per D-04).
- `economic_events.parquet` + `out/days_YYYY_MM.json` (~195 months) — the existing
  data assets; `populate` ingests `out/` with no re-scrape (PKG-04, D-05).

### Established Patterns
- Flat snake_case modules, frozen `@dataclass` value objects (`MonthPage`,
  `ScrapeResult`), `argparse` CLIs with defaults derived from UPPER_SNAKE_CASE
  constants, keyword-only optional args. Preserve in the package
  (`.planning/codebase/CONVENTIONS.md`).
- Scraper and pipeline communicate only through files — keep them as independent
  internal layers behind the new package API.

### Integration Points
- New `forexfactory` package (`src/forexfactory/`) sits over both scripts: CLI
  (`populate`/`refresh`/`query`) + library `get(...)` → parquet path.
- Cache home `~/.cache/forexfactory/` (overridable via path/env, CACHE-01) holds:
  per-month parquet, `raw/` JSON (temporary, D-03), `manifest.json` (D-02), and a
  `queries/` result dir (D-08).

</code_context>

<specifics>
## Specific Ideas

- Strong user preference against JSON as a durable format — it is staging-only and
  is removed at the end of Phase 2 (D-03). Parquet is the contract.
- Bias toward loud, explicit failure over silent partial data for a research data
  provider (drives D-09: error on out-of-scope query).
- `query` should be script-friendly first (path-only stdout, D-10).

</specifics>

<deferred>
## Deferred Ideas

- **Drop the raw JSON layer entirely** — sequenced as the **Phase 2 exit
  condition** once the full schema is in parquet (D-03), not a backlog item.
- **Force-refresh / overwrite of already-cached months** (CACHE-06) — Phase 3.
- **Auto-widen cache on out-of-scope query** (CACHE-03) — Phase 3; Phase 1 errors
  with guidance instead (D-09).
- **Auto-refresh of matured future-dated months** (CACHE-05) — Phase 3.
- **Reuse-if-unchanged for query result files** — optional optimization over D-08,
  not required now.

*Discussion stayed within phase scope — no new capabilities were proposed.*

</deferred>

---

*Phase: 1-Installable Data Provider*
*Context gathered: 2026-06-08*
