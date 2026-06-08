# Phase 2: Full Analytical Schema + Source Spike - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Three threads, all over the existing `forexfactory` package built in Phase 1:

1. **Full analytical schema in parquet** — widen the per-month parquet (and the
   `query` / `get()` result) from the Phase-1 core fields to the complete
   analytical schema: `forecast`/`actual`/`previous`/`revision` as **both raw
   strings and parsed numerics**, FF surprise flags (`actualBetterWorse`,
   `revisionBetterWorse`), identity (`ebaseId`, `country`), and `hasDataValues`.
   Drop FF UI/internal fields (DATA-04). Re-populate the existing cache from the
   on-disk raw JSON into the wider schema.
2. **Fixture-based regression tests** (QUAL-05) protecting the fragile
   `extract_days()` / `calendarComponentStates` parser — the project's
   highest-risk component.
3. **FF `apply-settings` POST endpoint spike** (SRC-01) — investigate as a cleaner
   structured-data source, adopt it as the primary fetcher if it clears the bar,
   keep HTML-scrape-and-parse as the fallback, and document the decision.

**In scope (Phase 2):** DATA-02, DATA-03, DATA-04, DATA-05, QUAL-05, SRC-01.

**Explicitly NOT this phase (→ Phase 3):** auto-widen cache on out-of-scope query
(CACHE-03), auto-refresh of matured future-dated months (CACHE-05), force-refresh /
overwrite flag (CACHE-06). New analytical capabilities (e.g. computed surprise
metrics, dashboards) are out of scope for the whole milestone (data provider only).

</domain>

<decisions>
## Implementation Decisions

### Schema & Numeric Parsing (DATA-02, DATA-03, DATA-04)

- **D-01: Full analytical column set.** Each event row carries, in addition to the
  Phase-1 core (`datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked`):
  - **Raw value strings** (verbatim from FF): `forecast_raw`, `actual_raw`,
    `previous_raw`, `revision_raw`.
  - **Parsed numerics** (float or null): `forecast`, `actual`, `previous`,
    `revision`.
  - **Surprise flags:** `actualBetterWorse`, `revisionBetterWorse`.
  - **Identity:** `ebaseId`, `country`.
  - **Data presence:** `hasDataValues`.
  - FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*`,
    `notice`, naming duplicates, etc.) are **dropped** (DATA-04).
  - Exact column **names, ordering, and pyarrow dtypes** are Claude's discretion
    (keep `datetime_utc` first, per the Phase-1 convention; SC1/SC2 names above are
    the contract).

- **D-02: Numeric parsing = faithful, percent-as-fraction.** The raw string is
  **always** retained; the parsed numeric is derived as:
  - Expand magnitude suffixes: `'1.5K'`→`1500`, `'2.3M'`→`2300000`,
    `'113B'`→`113000000000`, trailing `T`→×1e12.
  - **Percent → decimal fraction:** `'4.3%'`→`0.043` (divide by 100). Chosen so
    percent columns are ratio-ready for math without re-dividing.
  - Sign preserved (`'-0.2'`→`-0.2`); plain numbers pass through.
  - Unparseable / empty (`''`, `'<0.1%'`, `'~'`, `'Tentative'`, etc.) → **null**
    (NaN). Never raise; bad values become null, mirroring the Phase-1
    `errors="coerce"` posture.
  - A value with **no `%`** is taken at face value (we cannot infer it is a
    percent from the string alone) — only a literal `%` triggers the /100.

- **D-03: No derived surprise column.** Store raw + parsed values and FF's
  `actualBetterWorse` / `revisionBetterWorse` direction flags only. A consumer
  computes any `actual − forecast` delta themselves. Rationale: keep the provider a
  clean data layer ("consumers build their own views"), and the unit/percent-fraction
  mix makes a single baked-in delta column misleading across metrics.
  - `actualBetterWorse` / `revisionBetterWorse` are carried as their **raw integer**
    value; whether to additionally map them to a categorical (better/worse/inline)
    is Claude's discretion (raw int is the floor).

### Source Spike — `apply-settings` POST endpoint (SRC-01)

- **D-04: Prototype & compare, adopt-if-it-wins.** Build a minimal fetcher against
  the endpoint, diff its output vs the HTML parser across a sample of months. If it
  reliably returns the full structured data, **wire it in as the PRIMARY source with
  HTML-scrape-and-parse retained as the fallback** (SRC-02). If it does not clear
  the bar, keep HTML primary and document why. SC5 (a documented decision) is
  satisfied either way.

- **D-05: Spike runs independent of / parallel to schema extraction.** Schema
  extraction is driven by the **existing on-disk raw JSON** (no network needed) and
  the extraction logic operates on **event dicts source-agnostically** — so whichever
  source produces those dicts (HTML parse or API JSON), the schema/parsing code is
  the same. Swapping the fetcher underneath later does **not** redo schema work.
  Schema deliverables never block on the network spike.

- **D-06: Adopt-bar = ALL FOUR must-haves.** The endpoint replaces HTML as primary
  only if it:
  1. **No field regression** — returns the full schema (every raw value field,
     identity, surprise flags), nothing missing vs the HTML source.
  2. **Arbitrary historical months** — can fetch any month back to 2010, not just a
     current-navigation window.
  3. **Works via `curl_cffi`, no auth** — fetches with the existing Chrome TLS
     impersonation and no login/CSRF/session-token dance (or only a trivially
     obtainable one).
  4. **Stable at a polite rate** — reliable across repeated calls at a polite
     non-zero delay, not 403/429-throttled into failure during a multi-month fetch.

- **D-07: Live reconnaissance is part of the spike.** Before/while prototyping the
  `curl_cffi` fetcher, **load the live FF calendar page in a real
  browser/devtools-capable tool** and capture:
  - **All network requests**, especially the `apply-settings` POST — full URL,
    method, request headers, cookies, the POST body/params, and the response body +
    shape.
  - **The executed JavaScript** that forms those requests and assembles
    `window.calendarComponentStates`.

  Purpose: reproduce the real request **precisely** with `curl_cffi` (correct
  headers/params/body) instead of guessing — this both validates the endpoint against
  the adopt-bar and hardens any adoption.
  - **CONSTRAINT:** the browser / devtools / headless recon is **spike-only
    scaffolding**. It MUST NOT become a production dependency — the shipped fetcher
    stays `curl_cffi` (the project deliberately replaced Selenium/nodriver).
  - **Synergy:** save a page captured during recon as the realistic HTML **fixture**
    for QUAL-05 (D-11).

### No-Data Events & Query Filter (DATA-05)

- **D-08: Default query returns data-bearing events + holidays.** All
  speech/holiday/no-data events are **retained in the cache**; the query *hides* the
  no-data ones by default — **except bank holidays, which stay visible by default**
  (they move markets and were explicitly cached in Phase 1). This **refines SC3**,
  which lumped speech and holiday together ("absent when the filter is omitted") —
  holidays are an always-on special case, not hidden with speeches.
  - Practical default predicate: `hasDataValues == true OR impact == 'holiday'`.

- **D-09: `--include-no-data` toggle (lean).** A single `store_true` CLI flag plus a
  matching `include_no_data=False` library kwarg on `get()` (mirrors the D-12
  flag↔kwarg convention from Phase 1):
  - Omitted → default (data-bearing + holidays).
  - `--include-no-data` → also surface speeches/other no-data events (= everything).
  - The `hasDataValues` column is **always present** in the parquet, so any niche
    slice (only-speeches, data-without-holidays) is a one-liner on the column for the
    consumer — no extra CLI surface.
  - The old hard `'speaks'` **sanitize step is removed** — speeches are no longer
    dropped at pipeline time; they are retained and filtered (out by default) at query
    time.
  - **Verifier note:** SC3's literal example command (`query --has-data-values false`)
    is superseded by `query --include-no-data`; verify against the new flag.

### Parser Fixtures (QUAL-05)

- **D-10: Small fixture matrix (~3–5).** Cover the fragile parser's real branches and
  edge cases, not just the happy path:
  - **Both assignment forms** — `window.calendarComponentStates = {...}` and
    `window.calendarComponentStates[n] = {...}`.
  - A **rich data-values** month (non-empty forecast/actual/previous/revision).
  - A **no-data** case (speech and/or holiday).
  - An **empty / no-events** month.
  - The **multi-candidate `_select_best_days`** case (most days + most events wins).

- **D-11: Real captured HTML + targeted field assertions.** Capture **real FF pages**
  (including the page loaded during the D-07 spike recon), **trim** each to a
  representative slice of days to keep repo size sane, and **assert on the meaningful
  fields** per case — `currency`, `impact`, `title`, `id`, parsed
  `forecast`/`actual`/`previous`/`revision`, `hasDataValues`, `leaked`. Chosen over a
  full golden snapshot because Phase 2 is actively adding fields (a golden file would
  churn on every intentional schema addition) and the user prefers not to store
  golden JSON. Hand-crafted synthetic fragments are acceptable only to *supplement* an
  edge case (e.g. the `[n]={...}` branch) that is hard to capture naturally.

### Carried Forward (locked in Phase 1 — not re-discussed, restated for the planner)

- **JSON-drop exit condition (Phase-1 D-03):** Phase 2 MUST extract **every field of
  lasting value** (including the raw-string forms) into parquet, **re-populate the
  existing cache** to the wider schema, and **then drop the raw JSON staging layer**.
  After that, obtaining any new field requires a **re-scrape**, not a re-parse — this
  is accepted. The planner sequences the rebuild + JSON removal.
- **Parquet is the contract**, `zstd` compression; loud explicit failure over silent
  partial data.
- **Field names** `forecast`/`actual`/`previous`/`revision`, `actualBetterWorse`,
  `revisionBetterWorse`, `ebaseId`, `country` are fixed by ROADMAP SC1/SC2.

### Claude's Discretion
The planner/researcher decides these (no user constraint beyond the decisions above):
- Exact new parquet **column names, ordering, and dtypes** (SC1/SC2 names are the
  contract; `datetime_utc` stays first).
- **Where the parsing helper lives** and its implementation (regex vs hand-rolled),
  and the suffix/percent constant tables.
- Whether `actualBetterWorse`/`revisionBetterWorse` also get a **categorical mapping**
  (raw int is the floor).
- **How the cache is rebuilt** to the new schema (re-run populate from the on-disk raw
  JSON; whether to bump a schema version / wipe-and-rebuild vs detect-and-rebuild).
- The **spike fetcher module** location and the **recon tooling** choice (Playwright /
  manual devtools / headless capture) — recon is throwaway scaffolding (D-07).
- **Fixture file layout**, naming, and how aggressively each page is trimmed (D-11).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning (scope + requirements)
- `.planning/ROADMAP.md` §"Phase 2: Full Analytical Schema + Source Spike" — goal +
  the 5 success criteria this phase must make true (note SC3 is refined by D-08/D-09).
- `.planning/REQUIREMENTS.md` — Phase 2 owns DATA-02, DATA-03, DATA-04, DATA-05,
  QUAL-05, SRC-01 (plus the traceability table).
- `.planning/PROJECT.md` — Key Decisions table; **§Context holds the spike lead URL**
  `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` (the
  former `api.txt`, removed in Phase 1) and the "rich raw data already on disk
  (~50 fields)" note.
- `.planning/phases/01-installable-data-provider/01-CONTEXT.md` — **D-03 (JSON-drop
  exit condition)**, D-12 (flag↔kwarg mirroring), cache layout (per-month parquet +
  `manifest.json`, `raw/` staging).

### Existing code to extend (do NOT rewrite from scratch)
- `src/forexfactory/_pipeline.py` — `flatten_events()` is where the schema widens
  (today it keeps only 6 fields); `norm_impact()`, `to_iso()`, `_deduplicate_rows()`,
  `should_keep_row()` (the `'speaks'` drop to be removed per D-09), `write_parquet()`.
- `src/forexfactory/_scrape.py` — `extract_days()` and the `calendarComponentStates`
  parser (`_extract_state_json`, `_extract_assigned_state_objects`,
  `_select_best_days`, `_find_matching_brace`) — the QUAL-05 fixture target (D-10/D-11)
  and the SRC-01 fallback source.
- `src/forexfactory/_populate.py`, `src/forexfactory/_query.py`,
  `src/forexfactory/cli.py` — cache build / query filter / CLI surface that gain the
  new schema and the `--include-no-data` flag.
- `src/forexfactory/_refresh.py` — the network path the API fetcher would slot into if
  adopted (D-04).
- `tests/test_scrape.py`, `tests/test_pipeline.py` — existing patterns to extend;
  `tests/fixtures/` is currently **empty** (QUAL-05 fills it).

### Codebase maps
- `.planning/codebase/CONCERNS.md` — authoritative on the parser fragility (the
  highest-risk component) that QUAL-05 mitigates.
- `.planning/codebase/STRUCTURE.md` — current layout + "Where to Add New Code".
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md` — module
  responsibilities + naming/style to preserve.

### Data assets
- `out/days_YYYY_MM.json` (~195 months, 2010-01 → 2026-03) — the raw JSON the wider
  schema is extracted from with **no re-scrape**; each event carries the ~50 source
  fields (confirmed: `forecast`, `actual`, `previous`, `revision`, `actualBetterWorse`,
  `revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`, …).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_pipeline.flatten_events()` — the single choke point that currently discards all
  but 6 fields; widening it (plus a new parsing helper) delivers DATA-02/03/04. The
  raw event already contains every target field (verified against
  `out/days_2024_01.json`).
- `_scrape.extract_days()` + the `calendarComponentStates` parser — reused wholesale;
  it is the QUAL-05 fixture subject and the SRC-01 fallback. No rewrite intended.
- `_deduplicate_rows()` (keyed by `(id, date, time_utc)`) and `write_parquet()`
  (`zstd`/level 3) — carry forward unchanged.

### Established Patterns
- Flat snake_case modules, frozen `@dataclass` value objects, `argparse` CLIs with
  defaults from `UPPER_SNAKE_CASE` constants, keyword-only optional args, repeatable
  singular flags mirrored by list/scalar library kwargs (D-12). Preserve them.
- Scraper and pipeline communicate only through event dicts/files — keeps the SRC-01
  source swap (D-05) localized behind a source-agnostic boundary.

### Integration Points
- Cache home `~/.cache/forexfactory/`: per-month parquet (schema widens), `raw/` JSON
  staging (**dropped at the Phase-2 exit**, Phase-1 D-03), `manifest.json`, `queries/`
  result dir. The wider schema means the existing cache must be **re-populated** from
  raw before the JSON is removed.
- `query` / `get()` gain the `--include-no-data` flag / `include_no_data=False` kwarg
  (D-09); the default filter predicate changes to data-bearing + holidays (D-08).

</code_context>

<specifics>
## Specific Ideas

- **Live recon, not guesswork** (D-07): the user specifically wants the spike to load
  the page and read the actual network traffic + executed JS so the real
  `apply-settings` request is reproduced exactly — this is the heart of the spike, not
  an optional extra. Recon tooling stays out of the shipped package.
- **Percent as a true fraction** (D-02): the user wants percent columns ratio-ready
  (`4.3%`→`0.043`), accepting the rule "no `%` ⇒ taken at face value".
- **Minimalist provider surface** (D-03, D-09): expose columns, let consumers slice —
  no baked-in surprise metric, smallest viable CLI for the no-data filter.
- **Holidays are first-class** (D-08): not lumped with speeches; visible by default.
- Continued strong preference against durable JSON (Phase-1 D-03) — the raw JSON layer
  is removed at the end of this phase.

</specifics>

<deferred>
## Deferred Ideas

- **Computed surprise / expected-vs-surprise metrics** in the parquet (e.g.
  `actual − forecast`, normalized surprise z-scores) — deliberately left to consumers
  (D-03); could be a future analytical add-on, not this milestone.
- **Categorical encoding** of `actualBetterWorse`/`revisionBetterWorse` — optional;
  raw int ships, mapping is Claude's discretion.
- **Adopting the `apply-settings` endpoint as primary** only happens if it clears the
  D-06 bar this phase; if it is promising-but-not-ready, full adoption is a follow-up.
- Phase 3 items remain out of scope: auto-widen on scope miss (CACHE-03),
  matured-month auto-refresh (CACHE-05), force-refresh flag (CACHE-06).

*Discussion stayed within phase scope — no new capabilities were proposed.*

</deferred>

---

*Phase: 2-Full Analytical Schema + Source Spike*
*Context gathered: 2026-06-08*
