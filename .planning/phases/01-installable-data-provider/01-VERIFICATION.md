---
phase: 01-installable-data-provider
verified: 2026-06-08T11:35:00Z
status: passed
score: 5/5
overrides_applied: 0
---

# Phase 1: Installable Data Provider — Verification Report

**Phase Goal:** Users can install the package, populate the shared cache from the existing 195 months of raw data without any HTTP requests, and query it to receive a valid parquet file path.
**Verified:** 2026-06-08T11:35:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pip install -e .` succeeds and `import forexfactory` works in a fresh Python environment without importing scrape.py or pipeline.py | VERIFIED | `pyproject.toml` declares src-layout + `setuptools.packages.find where=["src"]`; `__init__.py` does not import root scripts; orchestrator confirmed venv install |
| 2 | `forexfactory populate` re-processes existing `out/` months into `~/.cache/forexfactory/` without any HTTP requests | VERIFIED | `_populate.py` has no `curl_cffi` import; `grep -c "curl_cffi" src/forexfactory/_populate.py` = 0; orchestrator confirmed `populated=3 skipped=0 empty=0` with ZERO HTTP |
| 3 | `forexfactory query --currency USD --impact high` prints an absolute path to a parquet file that opens cleanly with `pd.read_parquet()` | VERIFIED | Runtime test confirmed: stdout = exactly one absolute path, `pd.read_parquet` reads successfully, D-10 stdout-only contract confirmed |
| 4 | Library call `forexfactory.get(currencies=["USD"], impacts=["high"])` returns a `pathlib.Path` pointing to the populated parquet | VERIFIED | `__init__.get()` has `-> Path` annotation, lazily imports `_query.run_query`; `isinstance(result, pathlib.Path)` and `result.exists()` confirmed |
| 5 | Running `forexfactory populate` on months where a prior scrape failed does not permanently skip those months due to a stale empty JSON file | VERIFIED | Runtime test: two successive `run_populate` calls on an empty `[]` raw file both show `empty=1, skipped=0` — never recorded as cached |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Installable src-layout package metadata + console-script entry point | VERIFIED | `name = "forexfactory"`, `forexfactory = "forexfactory.cli:main"`, `where = ["src"]` all present |
| `src/forexfactory/__init__.py` | Library namespace + `get() -> Path` contract | VERIFIED | `def get(...) -> Path:` with lazy `from . import _query`, `__version__ = "0.1.0"` |
| `src/forexfactory/_pipeline.py` | Reused ETL engine with QUAL-01/QUAL-02 fixes | VERIFIED | `def _deduplicate_rows` defined once, called in both `parse_json_to_csv` (line 132) and `run_pipeline` (line 229); `run_pipeline(in_dir=...)` flows `in_dir` to `load_days_files` |
| `src/forexfactory/_cache.py` | Cache path resolution + manifest read/write/scope helpers | VERIFIED | `FOREXFACTORY_CACHE_DIR` env override, `resolve_cache_dir`, `month_parquet_path`, `raw_json_path`, `queries_dir`, `read_manifest`/`write_manifest` (atomic `os.replace`), `_scope_covers` all present |
| `src/forexfactory/_populate.py` | Per-month populate-from-disk engine + manifest provenance | VERIFIED | `run_populate` reads all `days_*.json`, calls `build_month_parquet`, writes manifest; no `curl_cffi`; `empty_count` incremented for empty raw, no manifest write for empty |
| `src/forexfactory/_query.py` | Cache read → filter → consolidated result parquet | VERIFIED | `run_query` raises `ValueError` with populate guidance for out-of-scope; writes deterministic path under `queries/`; returns `Path(...).resolve()` |
| `src/forexfactory/cli.py` | Unified `forexfactory` console script: populate + query + refresh subcommands | VERIFIED | `def main(argv=None) -> int:` with three subparsers, `action="append"` scope flags, `print(path)` for query (D-10), `sys.exit(1)` on ValueError (D-09) |
| `src/forexfactory/_scrape.py` | Relocated browserless scraper with QUAL-03/QUAL-04 fixes + polite delay | VERIFIED | `BETWEEN_PAGES_DELAY = 1.0`, `RETRY_DELAY = 1.0`; file write guarded by `if days:` (line 380); no `2021-01-01`/`2021-06-30` constants |
| `src/forexfactory/_refresh.py` | Network gap-fill refresh: stages raw + builds per-month parquet | VERIFIED | `run_refresh` skips months with existing non-empty raw JSON; empty scrape writes no file; `_compute_date_range` provides dynamic gap-fill default |
| `tests/test_pipeline.py` | Adapted + QUAL regression tests | VERIFIED | `import forexfactory._pipeline as pipeline`; passes `in_dir=str(in_dir)` rather than patching global; `PipelineDedupTests` class present |
| `tests/test_cache.py` | Round-trip + default-dir + env-override regression tests | VERIFIED | >= 7 test methods; all pass |
| `tests/test_populate.py` | Skip-logic, per-month-write, default-scope, SC5 reprocess tests | VERIFIED | All pass including empty-raw reprocess case |
| `tests/test_query.py` | Result-path, get()-returns-Path, and D-09 out-of-scope tests | VERIFIED | All pass |
| `tests/test_cli.py` | Routing, append-flag, path-only-stdout, and walking-skeleton end-to-end test | VERIFIED | `SkeletonEndToEndTests` passes; routing tests confirm D-12 append, D-09 exit code 1 |
| `tests/test_scrape.py` | Adapted import + QUAL-03 no-empty-write test | VERIFIED | All pass; `import forexfactory._scrape as scraper` |
| `tests/test_refresh.py` | Empty-scrape-no-write, skip-existing, manifest-update tests | VERIFIED | All pass using injected FakeSession (no live HTTP) |
| `README.md` | Package-era quickstart, CLI usage, schema table, src-layout structure chart | VERIFIED | Contains all required substrings; structure chart shows `src/forexfactory/` without root `scrape.py`/`pipeline.py`/`api.txt` |
| `tests/test_docs.py` | Doc-regression tests matching new structure + schema | VERIFIED | 2/2 tests pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml` | `forexfactory.cli:main` | `[project.scripts]` console entry point | VERIFIED | `forexfactory = "forexfactory.cli:main"` present |
| `src/forexfactory/__init__.py` | `forexfactory._query.run_query` | lazy import inside `get()` | VERIFIED | `from . import _query; return _query.run_query(...)` |
| `src/forexfactory/_cache.py` | `manifest.json` | atomic write via `os.replace` | VERIFIED | `os.replace(tmp_path, path)` in `write_manifest` |
| `src/forexfactory/_populate.py` | `_pipeline._deduplicate_rows` | QUAL-01 reuse call | VERIFIED | `rows = _pipeline._deduplicate_rows(rows)` in `build_month_parquet` |
| `src/forexfactory/_populate.py` | `manifest.json` | `_cache.update_manifest_month` after each write | VERIFIED | Called after `build_month_parquet` succeeds, never after empty raw |
| `src/forexfactory/_query.py` | `cache_dir/queries/*.parquet` | `_pipeline.write_parquet` to `_cache.queries_dir` path | VERIFIED | `result_path = _cache.queries_dir(cache_dir) / result_filename` |
| `forexfactory.get` | `forexfactory._query.run_query` | lazy import in `__init__.get()` | VERIFIED | Pattern confirmed in source |
| `src/forexfactory/cli.py` | `_populate.run_populate` / `_query.run_query` | subcommand handlers | VERIFIED | Both dispatch branches present and tested |
| `src/forexfactory/cli.py (query)` | stdout | `print(path)` — path only (D-10) | VERIFIED | Single `print(path)` after `run_query`; all other output via `logger` |
| `src/forexfactory/_refresh.py` | `forexfactory._scrape.run_scraper` / `scrape_month` | SRC-02 scraper reuse | VERIFIED | `_scrape.scrape_month(effective_session, page, ...)` called in refresh loop |
| `src/forexfactory/_refresh.py` | `_populate.build_month_parquet` | build parquet for each scraped month | VERIFIED | Called on non-empty scrape result |
| `tests/test_docs.py` | `README.md` | structure-chart + schema substring assertions | VERIFIED | `assert "|-- src/forexfactory/"` and schema table assertions all present |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cli.py (query)` | `path` | `_query.run_query(...)` | Yes — reads per-month `.parquet` files via `pd.read_parquet`, filters, writes consolidated parquet | FLOWING |
| `_query.py` | `dfs` | `pd.read_parquet(_cache.month_parquet_path(...))` for each manifest month | Yes — reads real parquet files written by `_populate.build_month_parquet` | FLOWING |
| `_populate.py` | `df` | `_pipeline.flatten_events(days)` over real raw JSON | Yes — parses real event dicts from `days_*.json` files | FLOWING |
| `_refresh.py` | `days` | `_scrape.scrape_month(session, page, ...)` | Yes — extracted from FF HTML (or injected FakeSession in tests) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| D-10: query stdout is exactly one absolute path | Runtime: capture stdout from `cli.main(["query",...])`; count lines | 1 line, absolute path | PASS |
| D-09: out-of-scope query raises ValueError with `forexfactory populate` guidance | `run_query(currencies=["EUR"], impacts=["medium"], cache_dir=empty)` | `ValueError: EUR/medium not populated — run: forexfactory populate ...` | PASS |
| SC5 / QUAL-03: empty raw JSON never permanently skipped | Two successive `run_populate` on `[]` raw file | Both runs: `empty=1, skipped=0` | PASS |
| D-11: polite delay defaults | `assert s.BETWEEN_PAGES_DELAY==1.0 and s.RETRY_DELAY==1.0` | Both 1.0 | PASS |
| CACHE-02 + D-02: manifest records scope + provenance | `run_populate` then `read_manifest` | `scope = {currencies:[USD], impacts:[high,holiday]}`, month entry with `scraped_at` and `settled` | PASS |
| Full unit suite | `PYTHONPATH=src python3 -m pytest -q` | 72 passed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PKG-01 | 01-01, 01-07 | pip-installable package, importable as `forexfactory` | SATISFIED | `pyproject.toml` + `src/forexfactory/` layout; `pip install -e .` confirmed |
| PKG-02 | 01-05, 01-06, 01-07 | Unified CLI: populate, refresh, query | SATISFIED | `cli.py` with 3 subparsers; all dispatch tested |
| PKG-03 | 01-01, 01-04 | Library API returns parquet path | SATISFIED | `forexfactory.get() -> Path` wired through `_query.run_query` |
| PKG-04 | 01-01, 01-03 | Existing scrape/pipeline reused; ~195 months re-processed without re-scraping | SATISFIED | `_pipeline.py` via `git mv` from `pipeline.py`; `_populate` reads from `out/` with zero network |
| CACHE-01 | 01-02 | Shared user cache dir; overridable | SATISFIED | `resolve_cache_dir` precedence: arg > `FOREXFACTORY_CACHE_DIR` env > `~/.cache/forexfactory` |
| CACHE-02 | 01-03, 01-04, 01-05 | Scope chosen at populate time | SATISFIED | `manifest["scope"]` written on every successful `build_month_parquet`; query checks it |
| CACHE-04 | 01-03, 01-06 | Settled months never auto-refetched | SATISFIED | `run_refresh` skips months with existing non-empty raw JSON (D-11 no-overwrite) |
| DATA-01 | 01-01, 01-03, 01-04, 01-07 | Core fields: datetime_utc, currency, impact, title, id, leaked | SATISFIED | `flatten_events` yields 7 fields; `build_month_parquet` creates `datetime_utc` via `pd.to_datetime`; parquet opens with all 6 columns |
| SRC-02 | 01-06 | HTML-scrape-and-parse retained as fallback source | SATISFIED | `_scrape.py` via `git mv` from `scrape.py`; `calendarComponentStates` parser unchanged; `_refresh.py` wires it in |
| QUAL-01 | 01-01 | Deduplication in single shared helper | SATISFIED | `_deduplicate_rows()` defined once; called in both `parse_json_to_csv` (line 132) and `run_pipeline` (line 229) |
| QUAL-02 | 01-01 | `--in-dir` honored in all execution paths | SATISFIED | `run_pipeline(in_dir=...)` passes `in_dir` to `load_days_files`; test removed `patch.object(pipeline, "IN_DIR", ...)` pattern |
| QUAL-03 | 01-03, 01-06 | Failed scrapes no longer write empty JSON | SATISFIED | `_scrape.py`: `if days: open(out_path...)` (line 380–382); `_populate.py`: empty raw increments `empty_count` without manifest write; `_refresh.py`: `if not days:` skips write |
| QUAL-04 | 01-06 | Stale 2021 date defaults removed | SATISFIED | `grep "2021-01-01\|2021-06-30" src/forexfactory/_scrape.py` = 0; `_refresh._compute_date_range` provides dynamic gap-fill |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any phase-modified file |

---

### Human Verification Required

None. All behaviors verifiable programmatically for this data-pipeline phase. No UI, no real-time behavior, no visual appearance to assess.

The `forexfactory refresh` command makes live network calls, but its behavior under injection (FakeSession) is fully tested (72/72 passing), polite delays are confirmed (1.0s), and live-site behavior is a ToS concern already addressed in the CONCERNS.md threat model — no new human check required for Phase 1.

---

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are verified in the codebase. All 12 Phase-1 requirement IDs are satisfied. All plan must-haves confirmed at artifact existence, substantive implementation, and wiring/data-flow levels.

---

_Verified: 2026-06-08T11:35:00Z_
_Verifier: Claude (gsd-verifier)_
