<!-- refreshed: 2026-06-07 -->
# Architecture

**Analysis Date:** 2026-06-07

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                        CLI Entry Points                      │
│   `scrape.py` main()              `pipeline.py` main()       │
└───────────────────────┬─────────────────────────┬───────────┘
                        │                         │
                        ▼                         ▼
┌───────────────────────────────┐  ┌──────────────────────────┐
│        Scrape Layer           │  │      Pipeline Layer       │
│  `scrape.py`                  │  │  `pipeline.py`            │
│  - build_month_pages()        │  │  - load_days_files()      │
│  - build_session()            │  │  - flatten_events()       │
│  - scrape_month()             │  │  - parse_json_to_csv()    │
│  - run_scraper()              │  │  - sanitize_csv()         │
│  - extract_days()             │  │  - csv_to_parquet()       │
│  - _extract_state_json()      │  │  - run_pipeline()         │
│  - _loads_js_object()         │  │  - write_parquet()        │
└───────────────────────┬───────┘  └──────────┬───────────────┘
                        │                     │
                        ▼                     │
┌──────────────────────────────┐              │
│  out/days_YYYY_MM.json       │◄─────────────┘
│  (raw per-month JSON cache)  │
└──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────┐
│  economic_events.parquet     │
│  (final filtered dataset)    │
└──────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Scraper | Fetch FF calendar pages via curl_cffi, extract embedded JS state, write per-month JSON | `scrape.py` |
| JS state extractor | Parse `window.calendarComponentStates` from raw HTML, handle both `= {...}` and `[n] = {...}` assignment forms | `scrape.py` |
| Pipeline | Read per-month JSON files, filter/sanitize events, write Parquet | `pipeline.py` |
| parse step | JSON → filtered CSV (currency + impact filter, dedup) | `pipeline.py` |
| sanitize step | CSV → CSV (remove 'speaks' events) | `pipeline.py` |
| parquet step | CSV → Parquet (combine date+time into `datetime_utc`) | `pipeline.py` |
| full pipeline | JSON → Parquet entirely in-memory (no intermediate CSVs) | `pipeline.py` |

## Pattern Overview

**Overall:** Two-script sequential ETL pipeline — scrape then transform.

**Key Characteristics:**
- Flat module layout: no packages, no sub-modules; both scripts are importable top-level modules
- Scraper and pipeline are fully independent; they communicate only through files in `out/`
- Pipeline supports both an in-memory full run and step-by-step CSV-materialized run
- All configuration is via module-level constants, overridable via CLI arguments

## Layers

**Scrape Layer:**
- Purpose: Acquire raw calendar data from Forex Factory without browser automation
- Location: `scrape.py`
- Contains: HTTP session management, URL generation, HTML parsing, JSON file writing
- Depends on: `curl_cffi` (HTTP with TLS fingerprint impersonation), Python stdlib (`json`, `re`, `os`, `time`, `datetime`)
- Used by: `pipeline.py` indirectly (reads `out/` files produced here)

**Transform Layer:**
- Purpose: Parse, filter, sanitize, and serialize raw event data
- Location: `pipeline.py`
- Contains: JSON loading, event flattening, deduplication, filtering, Parquet output
- Depends on: `pandas`, `pyarrow`, Python stdlib (`json`, `csv`, `glob`, `os`, `datetime`)
- Used by: End consumers reading `economic_events.parquet`

**Test Layer:**
- Purpose: Regression coverage for both scrape and pipeline logic
- Location: `tests/test_scrape.py`, `tests/test_pipeline.py`, `tests/test_docs.py`
- Contains: unittest-style test classes run under pytest; no fixtures directory populated
- Depends on: `scrape`, `pipeline` modules imported directly from repo root

## Data Flow

### Full Pipeline (recommended path)

1. User runs `python scrape.py --start-date ... --end-date ...` (`scrape.py:415`)
2. `build_month_pages()` generates `MonthPage` objects (one per calendar month) (`scrape.py:90`)
3. `run_scraper()` iterates pages, skips existing `out/days_YYYY_MM.json`, fetches new ones (`scrape.py:351`)
4. `scrape_month()` sends GET via `curl_cffi` session with Chrome impersonation (`scrape.py:315`)
5. `extract_days()` → `_extract_state_json()` / `_extract_assigned_state_objects()` parse JS state from HTML (`scrape.py:295`)
6. `_select_best_days()` picks the state object with the most events (`scrape.py:262`)
7. Days written to `out/days_YYYY_MM.json` as compact JSON (`scrape.py:379`)
8. User runs `python pipeline.py` (`pipeline.py:236`)
9. `run_pipeline()` calls `load_days_files()` to glob `out/days_*.json` (`pipeline.py:202`)
10. `flatten_events()` yields normalized event dicts from nested `days[].events[]` structure (`pipeline.py:81`)
11. Events filtered by `KEEP_CURRENCIES` (`{"USD"}`) and `KEEP_IMPACTS` (`{"high", "holiday"}`) (`pipeline.py:206`)
12. Deduplication by `(id, date, time_utc)` key; sorted by `(date, time_utc, title)` (`pipeline.py:215`)
13. `should_keep_row()` removes 'speaks' events (`pipeline.py:223`)
14. DataFrame written to `economic_events.parquet` with `zstd` compression level 3 (`pipeline.py:232`)

### Incremental Scrape Path

1. `run_scraper()` checks `os.path.isfile(out_path)` before fetching each month (`scrape.py:369`)
2. Existing `out/days_YYYY_MM.json` files are skipped entirely — safe to re-run after interruption

### Step-by-step Pipeline Path

1. `python pipeline.py --step parse` → writes `ff_usd_high_holiday.csv`
2. `python pipeline.py --step sanitize` → writes `ff_usd_high_holiday_clean.csv`
3. `python pipeline.py --step parquet` → reads clean CSV, writes `economic_events.parquet`

**State Management:**
- No in-process persistent state; all state lives in files (`out/*.json`, `*.csv`, `*.parquet`)
- `curl_cffi.Session` is instantiated per `run_scraper()` call and not reused across invocations

## Key Abstractions

**MonthPage:**
- Purpose: Typed value object binding a month anchor date to its Forex Factory URL
- Examples: `scrape.py:64`
- Pattern: Frozen `@dataclass`; created by `build_month_pages()`, consumed by `run_scraper()` and `scrape_month()`

**ScrapeResult:**
- Purpose: Return value from `run_scraper()` summarizing success/fail/skip counts
- Examples: `scrape.py:71`
- Pattern: Frozen `@dataclass`; returned to `main()` and used in tests for assertions

**calendarComponentStates extraction:**
- Purpose: Forex Factory embeds calendar data as a JavaScript object in HTML; two assignment forms are handled
- Form 1: `window.calendarComponentStates = { "key": { days: [...] } }` — parsed by `_extract_state_json()` + `_loads_js_object()`
- Form 2: `window.calendarComponentStates[n] = { days: [...] }` — parsed by `_extract_assigned_state_objects()`
- Best candidate selected by `_select_best_days()` (most days + most events wins)
- Examples: `scrape.py:219`, `scrape.py:244`, `scrape.py:262`

## Entry Points

**scrape.py:**
- Location: `scrape.py:441` (`if __name__ == "__main__": main()`)
- Triggers: `python scrape.py [--start-date ...] [--end-date ...] [--out-dir ...] [--between-pages-delay ...] [--retry-delay ...]`
- Responsibilities: Parse CLI args, validate dates, build month page list, run scraper, log summary

**pipeline.py:**
- Location: `pipeline.py:280` (`if __name__ == "__main__": main()`)
- Triggers: `python pipeline.py [--step parse|sanitize|parquet] [--in-dir ...] [--csv ...] [--out ...]`
- Responsibilities: Route to individual step or full in-memory pipeline based on `--step` arg

## Architectural Constraints

- **Threading:** Single-threaded; no concurrency in scraper or pipeline. Months fetched sequentially.
- **Global state:** Module-level constants in both `scrape.py` and `pipeline.py` (e.g., `START_DATE`, `END_DATE`, `KEEP_CURRENCIES`, `KEEP_IMPACTS`) act as defaults. These are not mutated at runtime.
- **Circular imports:** None. `scrape` and `pipeline` are independent modules; neither imports the other.
- **File coupling:** Scraper and pipeline are coupled only through the `out/` directory and the `days_YYYY_MM.json` file naming convention.
- **curl_cffi optional import:** `scrape.py` catches `ImportError` for `curl_cffi` at module level (`scrape.py:22`) to allow importing the module in test environments without the dependency.

## Anti-Patterns

### Hardcoded date defaults

**What happens:** `START_DATE = "2021-01-01"` and `END_DATE = "2021-06-30"` are module-level string constants in `scrape.py:36-37`
**Why it's wrong:** Running `python scrape.py` without arguments silently fetches a fixed historical range rather than a recent range, which may surprise new users
**Do this instead:** Pass `--start-date` and `--end-date` explicitly on every invocation, or override defaults in the constants before running

### Module-level IN_DIR constant shared by pipeline steps and run_pipeline

**What happens:** `IN_DIR = "out"` in `pipeline.py:23` is used directly inside `run_pipeline()` without a parameter (`pipeline.py:206`)
**Why it's wrong:** Tests must `patch.object(pipeline, "IN_DIR", ...)` to redirect input; `--in-dir` CLI arg only affects the `--step parse` path, not `run_pipeline()`
**Do this instead:** Pass `in_dir` as a parameter to `run_pipeline()` (as `parse_json_to_csv` already does)

## Error Handling

**Strategy:** Retry transient failures in scraper; propagate hard errors from pipeline.

**Patterns:**
- `scrape_month()` catches all `Exception` subclasses per attempt and retries up to `max_attempts` times (`scrape.py:338`); logs warning on exhaustion and returns `[]`
- `run_scraper()` writes an empty JSON file and increments `fail_count` when `scrape_month` returns `[]`; execution continues to the next month
- `pipeline.py` raises `FileNotFoundError` if an expected input CSV is missing (`pipeline.py:148`)
- `load_days_files()` prints a warning and skips files with invalid JSON; does not raise (`pipeline.py:47`)
- `main()` in `scrape.py` calls `sys.exit(1)` on invalid date arguments

## Cross-Cutting Concerns

**Logging:** `scrape.py` uses `logging` with `INFO` level by default; format is `%(asctime)s [%(levelname)s] %(message)s`. `pipeline.py` uses `print()` statements only — no structured logging.
**Validation:** Date range validated in `scrape.py:main()`. Event field normalization happens in `norm_impact()` (`pipeline.py:51`) and `flatten_events()` (`pipeline.py:81`) with graceful fallbacks for missing/null fields.
**Authentication:** None. Forex Factory is accessed as a public website; `curl_cffi` impersonates a Chrome browser via TLS fingerprinting to avoid bot detection.

---

*Architecture analysis: 2026-06-07*
