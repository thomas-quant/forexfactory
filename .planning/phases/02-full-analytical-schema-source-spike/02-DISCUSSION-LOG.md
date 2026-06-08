# Phase 2: Full Analytical Schema + Source Spike - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 2-Full Analytical Schema + Source Spike
**Areas discussed:** Numeric parsing rules, API spike depth & criteria, No-data events & filter, Fixture test coverage

---

## Numeric parsing rules

### Q1 — How literal should the parsed numeric be?

| Option | Description | Selected |
|--------|-------------|----------|
| Faithful magnitude | Expand suffixes, percent kept as displayed number (4.3%→4.3), unparseable→null | |
| Faithful, percent as fraction | Expand suffixes (1.5K→1500, 113B→1.13e11), percent→decimal (4.3%→0.043), unparseable→null | ✓ |
| Coefficient only | Strip all units incl. magnitude suffix (1.5K→1.5); loses magnitude | |

**User's choice:** Faithful, percent as fraction.
**Notes:** Raw string column always retained alongside. Percent columns are ratio-ready; a value with no `%` is taken at face value.

### Q2 — Store a derived numeric surprise column (parsed actual − parsed forecast)?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave to consumer | Store only raw + parsed values and FF's better/worse flags; consumer computes deltas | ✓ |
| Store surprise delta | Add a computed `surprise = actual − forecast` column | |

**User's choice:** Leave to consumer.
**Notes:** Keeps the provider a clean data layer; unit/percent-fraction mix makes a baked-in delta misleading across metrics. (Question was re-asked at the user's request; answer unchanged.)

---

## API spike depth & criteria

### Q1 — How far should the apply-settings spike go this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Prototype & compare, adopt if it wins | Build minimal fetcher, diff vs HTML, adopt as primary w/ HTML fallback if it reliably returns full data | ✓ |
| Probe & document only | Inspect endpoint, write decision, no integration this phase | |
| Commit to adoption | Build it as primary now, HTML demoted to fallback | |

**User's choice:** Prototype & compare, adopt if it wins.

### Q2 — Sequencing against schema extraction?

| Option | Description | Selected |
|--------|-------------|----------|
| Independent / parallel | Schema driven by on-disk raw JSON, source-agnostic extraction; spike runs alongside | ✓ |
| Spike first, gate schema | Finalize spike before designing schema | |

**User's choice:** Independent / parallel.

### Q3 — Which conditions must hold for the endpoint to REPLACE the HTML parser? (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| No field regression | Full schema, no missing fields vs HTML | ✓ |
| Arbitrary historical months | Any month back to 2010, not just current navigation | ✓ |
| Works via curl_cffi, no auth | Chrome impersonation, no login/CSRF/session dance | ✓ |
| Stable at polite rate | Not 403/429-throttled during a multi-month fetch | ✓ |

**User's choice:** All four are must-haves.

### Added directive (free-text, mid-area)

**User's request:** "Load the page yourself and analyze the network requests and any JavaScript executed from ForexFactory — during the spike."
**Notes:** Captured as D-07 — live recon (capture network requests incl. the apply-settings POST + executed JS) to reproduce the real request precisely with curl_cffi. Recon tooling is spike-only scaffolding, not a production dependency; captured page doubles as a QUAL-05 fixture.

---

## No-data events & filter

### Q1 — By default (no flag), which events should a query return?

| Option | Description | Selected |
|--------|-------------|----------|
| Data-bearing only | hasDataValues=true only; speeches AND holidays hidden by default (matches SC3 literally) | |
| Data-bearing + holidays | Hide speeches/no-data by default, always keep holidays visible | ✓ |
| Everything by default | All retained events; flag only narrows (conflicts with SC3) | |

**User's choice:** Data-bearing + holidays.
**Notes:** Deliberate refinement of SC3 — holidays treated as an always-on special case, not lumped with speeches.

### Q2 — How should the query expose hidden no-data events?

| Option | Description | Selected |
|--------|-------------|----------|
| Lean toggle: --include-no-data | store_true; default = data + holidays, flag surfaces everything; rely on hasDataValues column for niche slices | ✓ |
| Expressive filter: --has-data-values true\|false | Keeps SC3 flag name; tri-state + 'all'; larger surface, subtle semantics | |
| You decide | Planner picks | |

**User's choice:** Lean toggle `--include-no-data`.
**Notes:** Library `get()` gains matching `include_no_data=False`. Changes SC3 example command to `--include-no-data`. Old hard `'speaks'` sanitize step removed.

---

## Fixture test coverage

### Q1 — How much fixture coverage for the parser?

| Option | Description | Selected |
|--------|-------------|----------|
| Small matrix | ~3–5 fixtures: both assignment forms + rich-data + no-data + empty + _select_best_days | ✓ |
| Single realistic fixture | One saved fragment, common path (SC4 minimum) | |
| You decide | Planner picks | |

**User's choice:** Small matrix.

### Q2 — How should fixtures be sourced and asserted?

| Option | Description | Selected |
|--------|-------------|----------|
| Real HTML + targeted assertions | Capture real (incl. spike-recon) pages, trim, assert meaningful fields per case | ✓ |
| Real HTML + golden snapshot | Same fixtures, assert full output vs stored golden (churns during schema expansion) | |
| Hand-crafted fragments | Synthetic HTML fragments; won't catch real FF quirks | |

**User's choice:** Real HTML + targeted assertions.
**Notes:** Synthetic fragments acceptable only to supplement a hard-to-capture edge case (e.g. `[n]={...}`).

---

## Claude's Discretion

- Exact new parquet column names, ordering, and dtypes (SC1/SC2 names are the contract; `datetime_utc` stays first).
- Parsing helper location/implementation and the suffix/percent constant tables.
- Whether `actualBetterWorse`/`revisionBetterWorse` also get a categorical mapping (raw int is the floor).
- How the cache is rebuilt to the new schema (re-populate from raw; schema-version vs wipe-and-rebuild).
- Spike fetcher module location and recon tooling choice (throwaway scaffolding).
- Fixture file layout, naming, and trimming aggressiveness.

## Deferred Ideas

- Computed surprise / expected-vs-surprise metrics in parquet — left to consumers.
- Categorical encoding of better/worse flags — optional.
- Full adoption of apply-settings endpoint if promising-but-not-ready this phase — follow-up.
- Phase 3 items (CACHE-03 auto-widen, CACHE-05 matured-month refresh, CACHE-06 force-refresh) remain out of scope.
