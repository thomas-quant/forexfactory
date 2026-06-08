# Phase 1: Installable Data Provider - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 1-Installable Data Provider
**Areas discussed:** Cache layout, Populate defaults, Query contract, CLI surface

---

## Cache layout

### On-disk organization

| Option | Description | Selected |
|--------|-------------|----------|
| Per-month parquet files | One parquet per month; refresh rewrites only those files; cleanest fit for Phase-3 lifecycle | ✓ |
| Single combined parquet | One file like today; any refresh rewrites the whole file | |
| Partitioned by currency/impact | Scope-widening = adding folders; month-granular refresh awkward | |

**User's choice:** Per-month parquet files
**Notes:** Matches the natural scrape/refresh unit (one month).

### Cache state tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Manifest sidecar file | `manifest.json` records populated scope + per-month provenance (scrape time, settled-vs-future) | ✓ |
| Derive from the files | Infer coverage from filenames, scope from distinct values present | |
| You decide | Defer mechanism; require scope + settled status recoverable | |

**User's choice:** Manifest sidecar file
**Notes:** Needed now for CACHE-04; sets up Phase 3 scope-miss + maturity.

### Raw JSON layer location/lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Both under cache dir | raw/ JSON + per-month parquet + manifest all under the cache home | |
| Raw stays separate input dir | Cache holds only parquet; raw read from configurable input dir | |
| You decide | Defer layout; require raw retained durably for Phase 2 | |

**User's choice:** *Free text* — "discarded once parquet is built. for now it can live in the cache dir, but once phase 2 is done, we're dropping json. I despise json."
**Notes:** Reframed as: raw JSON is a temporary staging layer in the cache dir for Phase 1; dropped after Phase 2 once the full schema lands in parquet. Recorded the consequence — post-Phase-2, new fields require a re-scrape (accepted) — as a Phase-2 exit condition (D-03).

---

## Populate defaults

### Default scope (no flags)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse USD + high/holiday | Today's proven scope; smallest cache; matches existing parquet | ✓ |
| Require explicit scope | Error unless --currency/--impact given | |
| Populate everything on disk | All currencies/impacts; widest but heaviest | |

**User's choice:** Reuse USD + high/holiday
**Notes:** Widen explicitly; auto-widen is Phase 3.

### Default date range (local, no network)

| Option | Description | Selected |
|--------|-------------|----------|
| All months on disk | ~195 months (2010-01 → 2026-03); --start/--end narrow | ✓ |
| Recent window (e.g. 24 months) | Smaller first cache | |
| Require explicit range | Force --start/--end | |

**User's choice:** All months on disk
**Notes:** Clean replacement for the stale 2021 hardcoded default (QUAL-04).

### Re-run behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Incremental + scope-aware | Skip a month only if cached at requested scope; failed/empty retried | ✓ |
| Always rebuild in-range | Rewrite all in-range months every run | |
| You decide | Defer; require failed months never permanently skipped | |

**User's choice:** Incremental + scope-aware
**Notes:** Mechanism behind success-criterion 5 and the QUAL-03 fix.

---

## Query contract

### What query returns

| Option | Description | Selected |
|--------|-------------|----------|
| Derived result parquet | Filter per-month files → one consolidated parquet; return its path | ✓ |
| Canonical cache paths | Return underlying file path(s) directly (many, unfiltered) | |
| You decide | Defer materialization; require a single readable filtered path | |

**User's choice:** Derived result parquet
**Notes:** Required because storage is per-month but contract is one path.

### Result file location / repeat queries

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic path, regenerated | Stable filter-keyed path, overwritten each query | ✓ |
| Fresh temp file each call | Unique file per call; path changes every time | |
| Deterministic + reuse if unchanged | Stable path, skip regen when cache unchanged | |

**User's choice:** Deterministic path, regenerated
**Notes:** Stable + never stale + no sprawl; reuse-if-unchanged is a later optimization.

### Out-of-scope query (Phase 1, pre-auto-widen)

| Option | Description | Selected |
|--------|-------------|----------|
| Error with guidance | Detect via manifest; exit with actionable populate command | ✓ |
| Return cached subset + warn | Return overlap + warning about un-populated portion | |
| Empty result + warn | Zero-row parquet + warning | |

**User's choice:** Error with guidance
**Notes:** No silent partial data; Phase 3 replaces with auto-fetch.

---

## CLI surface

### query stdout format

| Option | Description | Selected |
|--------|-------------|----------|
| Path only on stdout | stdout = just the path (pipeable); diagnostics to stderr | ✓ |
| Path + human summary | Path plus rows/range/scope text | |
| You decide | Defer formatting; require machine-extractable path | |

**User's choice:** Path only on stdout

### refresh role in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch missing months (network) | Wire in scrape.py; add not-yet-cached months; overwrite/force + maturity → Phase 3 | ✓ |
| Stub, defer to Phase 3 | populate + query only; refresh errors 'not implemented' | |
| You decide | Defer depth; require scrape wired in (SRC-02), refresh not dead | |

**User's choice:** Fetch missing months (network)
**Notes:** On-disk data stops at 2026-03; without a network path the cache can't reach the current month. Flagged the rate-limit default (CONCERNS: 0.0s delays) for the planner.

### Scope flag style

| Option | Description | Selected |
|--------|-------------|----------|
| Repeatable singular flags | --currency USD --currency EUR (argparse append); mirrors library list args | ✓ |
| Comma-separated plural | --currencies USD,EUR | |
| Accept both forms | Support singular + comma plural | |

**User's choice:** Repeatable singular flags

---

## Claude's Discretion

- Internal package module structure (`src/forexfactory/`).
- Exact `manifest.json` schema/format.
- Result-parquet subdir name + deterministic key/hash scheme (D-08).
- `refresh` default network range (sensible: last cached month → current).
- Polite non-zero default scrape delay value.
- Mechanics of QUAL-01..04 fixes (intent locked by REQUIREMENTS).

## Deferred Ideas

- Drop raw JSON layer entirely — sequenced as the Phase-2 exit condition (not backlog).
- Force-refresh/overwrite (CACHE-06) — Phase 3.
- Auto-widen on out-of-scope query (CACHE-03) — Phase 3.
- Auto-refresh matured future months (CACHE-05) — Phase 3.
- Reuse-if-unchanged query result files — optional optimization.
