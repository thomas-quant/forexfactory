# Codebase Structure

**Analysis Date:** 2026-06-07

## Directory Layout

```
forexfactory/
├── scrape.py           # Browserless Forex Factory calendar scraper (curl_cffi)
├── pipeline.py         # ETL pipeline: JSON -> filtered Parquet
├── requirements.txt    # Python dependencies
├── AGENTS.md           # Contributor workflow and style guidelines
├── README.md           # User-facing usage and output schema reference
├── api.txt             # Notes/scratch (not used by code)
├── .gitignore          # Ignores out/, .venv/, .worktrees/, caches
├── economic_events.parquet  # Final pipeline output (generated, not committed)
├── out/                # Per-month raw JSON cache (generated, not committed)
│   └── days_YYYY_MM.json    # One file per scraped month
└── tests/              # Regression test suite
    ├── test_scrape.py  # Tests for scrape.py functions
    ├── test_pipeline.py # Tests for pipeline.py functions
    ├── test_docs.py    # Documentation regression tests (README structure/schema)
    └── fixtures/       # Empty — no fixture files currently present
```

## Directory Purposes

**Root (`/`):**
- Purpose: All production code lives directly at the root — no src/ package layout
- Contains: The two runnable scripts (`scrape.py`, `pipeline.py`), dependency manifest, docs
- Key files: `scrape.py`, `pipeline.py`, `requirements.txt`

**`out/`:**
- Purpose: Stores per-month raw JSON downloaded from Forex Factory
- Contains: `days_YYYY_MM.json` files (one per calendar month scraped)
- Generated: Yes — created by `scrape.py` via `os.makedirs(out_dir, exist_ok=True)`
- Committed: No — listed in `.gitignore`
- Note: Currently contains data from 2010-01 through 2026-03

**`tests/`:**
- Purpose: pytest-compatible regression suite covering scraper and pipeline logic
- Contains: Three test modules; `fixtures/` directory is present but currently empty
- Key files: `tests/test_scrape.py`, `tests/test_pipeline.py`, `tests/test_docs.py`

**`.planning/codebase/`:**
- Purpose: Architecture and structure documentation written by GSD mapper
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md`
- Generated: Yes — by GSD tooling
- Committed: Up to project discretion

## Key File Locations

**Entry Points:**
- `scrape.py`: Scraper CLI — `python scrape.py [--start-date ...] [--end-date ...]`
- `pipeline.py`: Pipeline CLI — `python pipeline.py [--step parse|sanitize|parquet]`

**Configuration (module-level constants):**
- `scrape.py:36-46`: `START_DATE`, `END_DATE`, `OUT_DIR`, `IMPERSONATE`, `REQUEST_TIMEOUT`, `MAX_ATTEMPTS`, `BETWEEN_PAGES_DELAY`, `RETRY_DELAY`
- `pipeline.py:23-30`: `IN_DIR`, `PARSED_CSV`, `CLEAN_CSV`, `OUT_PARQUET`, `KEEP_CURRENCIES`, `KEEP_IMPACTS`, `PARQUET_COMPRESSION`, `PARQUET_COMPRESSION_LEVEL`

**Core Logic:**
- `scrape.py:295` — `extract_days()`: top-level HTML → days list entry point
- `scrape.py:351` — `run_scraper()`: orchestrates page iteration, file skipping, writing
- `pipeline.py:81` — `flatten_events()`: nested JSON → flat event dicts
- `pipeline.py:202` — `run_pipeline()`: full in-memory ETL path

**Testing:**
- `tests/test_scrape.py`: `ScrapeTests` class — 8 tests covering URL generation, HTML extraction, retry logic, file skip behavior, CLI argument passing
- `tests/test_pipeline.py`: `PipelineParquetCompressionTests`, `PipelineLeakedFieldTests` — 4 tests covering compression settings and `leaked` field propagation
- `tests/test_docs.py`: 2 tests asserting README structure chart matches repo layout and schema table includes `leaked` column

**Output:**
- `out/days_YYYY_MM.json`: Raw scraped data, one file per month
- `economic_events.parquet`: Final filtered dataset (root-level by default)
- `ff_usd_high_holiday.csv`: Intermediate parsed CSV (step pipeline only, not committed)
- `ff_usd_high_holiday_clean.csv`: Intermediate sanitized CSV (step pipeline only, not committed)

## Naming Conventions

**Files:**
- Snake_case for Python source files: `scrape.py`, `pipeline.py`, `test_scrape.py`, `test_pipeline.py`
- Snake_case with underscores for generated data: `days_YYYY_MM.json`, `economic_events.parquet`, `ff_usd_high_holiday.csv`
- UPPERCASE for documentation: `README.md`, `AGENTS.md`

**Functions:**
- Snake_case for all functions: `build_month_pages()`, `extract_days()`, `run_scraper()`, `flatten_events()`
- Leading underscore for internal/private helpers: `_extract_state_json()`, `_loads_js_object()`, `_find_matching_brace()`, `_quote_js_object_keys()`

**Constants:**
- SCREAMING_SNAKE_CASE for all module-level config: `START_DATE`, `KEEP_CURRENCIES`, `PARQUET_COMPRESSION`

**Dataclasses:**
- PascalCase: `MonthPage`, `ScrapeResult`

**Test classes:**
- PascalCase with descriptive suffix: `ScrapeTests`, `PipelineParquetCompressionTests`, `PipelineLeakedFieldTests`, `FakeResponse`, `FakeSession`

## Where to Add New Code

**New scraper feature (e.g., additional HTML extraction fallback):**
- Implementation: Add helper function in `scrape.py` with leading underscore if internal; call from `extract_days()` (`scrape.py:295`)
- Tests: Add test method to `ScrapeTests` in `tests/test_scrape.py`

**New pipeline filter or transformation:**
- Implementation: Add function in `pipeline.py`; wire into `run_pipeline()` (`pipeline.py:202`) and the relevant `--step` branch in `main()` (`pipeline.py:260`)
- Tests: Add test class or method in `tests/test_pipeline.py`

**New output column:**
- Add field in `flatten_events()` (`pipeline.py:81`)
- Add column name to `cols` list in `parse_json_to_csv()` (`pipeline.py:126`)
- Update schema table in `README.md`
- Add assertion to `test_readme_schema_documents_current_parquet_columns` in `tests/test_docs.py`

**New CLI argument:**
- Scraper: Add `parser.add_argument(...)` in `scrape.py:parse_args()` (`scrape.py:395`); pass through `main()` to `run_scraper()`
- Pipeline: Add `parser.add_argument(...)` in `pipeline.py:main()` (`pipeline.py:237`); wire into relevant step or `run_pipeline()`

**New test fixture file:**
- Place in `tests/fixtures/`; load via `Path(__file__).parent / "fixtures" / "filename"`

## Special Directories

**`out/`:**
- Purpose: Raw per-month JSON cache produced by scraper
- Generated: Yes
- Committed: No

**`tests/fixtures/`:**
- Purpose: Reserved for static test data files; currently empty
- Generated: No
- Committed: Yes (directory tracked, contents would be committed)

**`.worktrees/`:**
- Purpose: Local git worktree checkouts
- Generated: Yes (local only)
- Committed: No

**`.planning/`:**
- Purpose: GSD planning documents
- Generated: Yes (by GSD tooling)
- Committed: Up to project discretion

---

*Structure analysis: 2026-06-07*
