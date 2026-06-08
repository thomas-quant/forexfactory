# Walking Skeleton — forexfactory (Cached Economic Calendar Data Provider)

**Phase:** 1
**Generated:** 2026-06-08

## Capability Proven End-to-End

A user can `pip install -e .`, run `forexfactory populate` to re-process existing
on-disk months into a parquet cache (no network), and `forexfactory query --currency
USD --impact high` (or `forexfactory.get(currencies=["USD"], impacts=["high"])`) to get
back an absolute path to a valid parquet file.

> This is a CLI + library Python package, not a web app. The skeleton template's web
> vocabulary is mapped to this stack below (scaffold = pyproject/src layout; "route" =
> the `forexfactory` console script dispatching subcommands; "DB read+write" = the
> parquet cache read/write; "UI interaction" = the CLI/`get()` returning a parquet path;
> "deployment/local-run" = the documented `pip install -e .` → populate → query flow).

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Package layout | src layout: `src/forexfactory/`, distribution name = import name = `forexfactory` (D-13) | Locked upstream by PKG-01 + SC1; src layout avoids import-shadowing of the repo root |
| Build / install | setuptools backend via `pyproject.toml`; locally installable (`pip install -e .`); PyPI deferred (DIST-01 → v2) | Smallest viable packaging; mirrors existing `requirements.txt` pins, no new deps |
| Entry surface | single console script `forexfactory` → `cli.main` with `populate`/`refresh`/`query` subcommands (PKG-02); library `forexfactory.get(...) -> pathlib.Path` (PKG-03, D-07) | One name everywhere (D-13); `query` is path-only on stdout (D-10) for scripting |
| Cache layer | per-month parquet `~/.cache/forexfactory/<YYYY-MM>.parquet` (D-01) + `manifest.json` sidecar (scope + provenance/settled, D-02) + `raw/` staging (D-03) + `queries/` results (D-08); cache dir overridable via `FOREXFACTORY_CACHE_DIR`/`--cache-dir`/arg (CACHE-01) | Month is the natural scrape/refresh unit; manifest records scope + settled for CACHE-04 and scope-miss detection (D-09) |
| Reused engine | `pipeline.py` → `_pipeline.py` (QUAL-01/02 fixes), `scrape.py` → `_scrape.py` (QUAL-03/04 + polite delay, SRC-02); fragile `calendarComponentStates` parser moved byte-for-byte | PKG-04: re-process the ~195 on-disk months, do not re-acquire or rewrite proven logic |
| Default scope/range | populate defaults to USD + {high, holiday} (D-04) over all on-disk months (D-05); incremental + scope-aware re-run (D-06) | Matches the existing `economic_events.parquet`; smallest cache, zero surprise |
| Failure posture | out-of-scope query errors with populate guidance (D-09); empty/failed raw is never cached/skipped (QUAL-03/SC5) | Loud explicit failure over silent partial data for a research provider |

## Stack Touched in Phase 1

- [x] Project scaffold — `pyproject.toml`, src layout, console script, deps (plan 01)
- [x] "Routing" — the `forexfactory` console script dispatching `populate`/`refresh`/`query` (plan 05, plan 06)
- [x] Cache "DB" write — `populate` ingests real on-disk months → per-month parquet + manifest (plan 03)
- [x] Cache "DB" read — `query`/`get()` reads per-month parquet → consolidated result parquet path (plan 04)
- [x] "UI interaction" — CLI `query` + library `get()` returning a real `pathlib.Path` that `pd.read_parquet` opens (plans 04/05)
- [x] Local-run command — README documents `pip install -e .` → `forexfactory populate` → `forexfactory query --currency USD --impact high` (plan 07)

**Skeleton spans plans 01–05** (scaffold → cache → populate → query → CLI end-to-end).
Plans 06–07 add the `refresh` network slice and finalize docs without changing any
architectural decision above.

## Out of Scope (Deferred to Later Slices)

- Rich analytical schema — forecast/actual/previous/revision (raw+parsed), surprise
  flags, `ebaseId`, `country`, `hasDataValues` retention → **Phase 2** (DATA-02..05)
- Fixture-based regression tests for the `calendarComponentStates` parser → **Phase 2** (QUAL-05)
- FF `apply-settings` POST endpoint investigation → **Phase 2** (SRC-01)
- Auto-widen cache on out-of-scope query → **Phase 3** (CACHE-03); Phase 1 errors (D-09)
- Auto-refresh of matured future-dated months → **Phase 3** (CACHE-05)
- Force-refresh / overwrite of already-cached months → **Phase 3** (CACHE-06)
- Dropping the raw JSON staging layer → **Phase 2 exit condition** (D-03)

## Subsequent Slice Plan

Each later phase adds vertical slices on top of this skeleton without altering its
architectural decisions:

- **Phase 2:** Full analytical schema in the parquet (forecast/actual/surprise/identity,
  raw+parsed), fixture-test the fragile parser, investigate the apply-settings endpoint.
- **Phase 3:** Self-managing cache — auto-widen on scope miss, auto-refresh matured
  future months, force-refresh on demand.
