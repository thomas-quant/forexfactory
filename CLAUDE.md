<!-- GSD:project-start source:PROJECT.md -->
## Project

**forexfactory — Cached Economic Calendar Data Provider**

A pip-installable Python package that scrapes the [Forex Factory](https://www.forexfactory.com/calendar) economic calendar and serves it from a shared local cache. Install once, fetch once, and read the data from any project — via a CLI or as a library. It replaces today's two loose scripts (`scrape.py`, `pipeline.py`) with a proper package, a parquet-based cache, and a richer event schema. For personal/research use.

**Core Value:** **Fetch the calendar once and reuse it everywhere, without re-scraping** — a durable shared cache that any of the user's projects can read, with the data fidelity needed for expected-vs-surprise analysis.

### Constraints

- **Tech stack**: Python 3.12+, `curl_cffi`, `pandas`, `pyarrow` — keep; proven and already in use
- **Usage**: Personal/research — respect Forex Factory's terms of service and rate limits (non-zero default delays advised; see CONCERNS.md)
- **Access**: No authentication (public site); `curl_cffi` TLS fingerprint impersonation is the anti-bot measure
- **Compatibility**: Re-use the existing scrape logic and the ~195 cached months rather than re-acquiring data
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - All source code (`scrape.py`, `pipeline.py`, `tests/`)
- None
## Runtime
- CPython 3.12.x (3.12.3 observed in dev environment)
- No async runtime; all I/O is synchronous via `curl_cffi` sessions
- pip
- Lockfile: Not present (only `requirements.txt` with minimum version pins)
## Frameworks
- None — plain Python scripts with `argparse` CLIs
- pytest (invoked as `python3 -m pytest -q`) — test runner
- unittest (stdlib) — test case base class used throughout `tests/`
- None — no build system, no Makefile, no tox
## Key Dependencies
- `curl_cffi>=0.13.0` — HTTP client with browser TLS fingerprint impersonation; replaces Selenium/nodriver; guards behind `try/except ImportError` in `scrape.py`
- `pandas>=2.0.0` — DataFrame construction and Parquet I/O in `pipeline.py`
- `pyarrow>=14.0.0` — Parquet write engine used by pandas (`compression="zstd"`, level 3)
- `setuptools>=65.0.0` — Required for Python 3.12 where `distutils` was removed from stdlib
## Configuration
- No `.env` file or environment variables used
- All configuration is via in-module constants at the top of each script:
- No build config files (no `pyproject.toml`, `setup.cfg`, `Makefile`)
- `requirements.txt` is the sole dependency manifest
## Platform Requirements
- Python 3.12+
- `pip install -r requirements.txt`
- Internet access for scraping `https://www.forexfactory.com/calendar`
- No deployment target — scripts are run locally on demand
- Output artifacts (`out/days_YYYY_MM.json`, `economic_events.parquet`) are local files, not committed to git
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Flat snake_case module names at the repo root: `scrape.py`, `pipeline.py`
- Test files prefixed with `test_` mirroring the module they cover: `tests/test_scrape.py`, `tests/test_pipeline.py`
- One doc-regression test file: `tests/test_docs.py`
- Public functions: `snake_case` — e.g. `extract_days`, `build_month_pages`, `run_scraper`, `parse_json_to_csv`
- Private/internal helpers: leading underscore `_snake_case` — e.g. `_find_matching_brace`, `_extract_state_json`, `_quote_js_object_keys`, `_select_best_days`
- Local variables: `snake_case` — e.g. `last_error`, `open_index`, `in_string`
- Module-level config constants: `UPPER_SNAKE_CASE` — e.g. `START_DATE`, `OUT_DIR`, `MAX_ATTEMPTS`, `KEEP_CURRENCIES`, `PARQUET_COMPRESSION`
- `PascalCase` for dataclasses and test helper classes: `MonthPage`, `ScrapeResult`, `FakeResponse`, `FakeSession`
- Test suite classes: `PascalCase` ending in `Tests` — e.g. `ScrapeTests`, `PipelineParquetCompressionTests`, `PipelineLeakedFieldTests`
## Code Style
- No formatter config file present (no `pyproject.toml`, `.flake8`, `setup.cfg`)
- Code follows PEP 8 visually: 4-space indentation, blank lines between top-level definitions
- Long strings broken with parentheses and explicit concatenation, not backslash continuation
- No linting config detected; no `# noqa` suppressions
- One `# pragma: no cover` comment used for an `except ImportError` branch that is exercised only in user environments without `curl_cffi` (`scrape.py:24`)
- Used consistently in function signatures for public and private helpers
- Modern union syntax: `str | None`, `Exception | None`, `list[MonthPage]` (Python 3.10+ style)
- `from typing import Any` imported for untyped dict payloads
- Return types annotated on most functions
- Used for plain data containers; always frozen: `@dataclass(frozen=True)` — `MonthPage`, `ScrapeResult` in `scrape.py`
## Import Organization
- Optional dependency guarded with try/except at module top; `None` sentinel used to defer the error to call time:
## Config Constants
- Both modules define a `# CONFIG` section near the top with all tuneable values as module-level `UPPER_SNAKE_CASE` constants
- `scrape.py` uses a visual delimiter (`# ====== CONFIG ======` / `# ====================`)
- `pipeline.py` uses a visual delimiter (`# ========= CONFIG =========` / `# ==========================`)
- Default values for CLI args always derive from the matching constant (e.g. `default=START_DATE`)
## Keyword-Only Arguments
- Functions with optional behavioral parameters use `*` to enforce keyword-only call sites:
## Error Handling
- Validate CLI args in `main()` and call `sys.exit(1)` on fatal input errors (`scrape.py:422-427`)
- Raise `ValueError` from low-level parsing helpers when invariants are broken (`_find_matching_brace`, `_extract_state_json`)
- Retry loop in `scrape_month` catches broad `Exception` to handle any transient fetch or parse failure; comment explains intent (`scrape.py:338`)
- `FileNotFoundError` raised explicitly on missing input in pipeline step functions (`pipeline.py:149`)
- `json.JSONDecodeError` silently skipped for bad JSON files with a `print("[warn] ...")` message (`pipeline.py:47-48`)
- Never silently swallow errors in the happy path; failures are logged or raised
## Logging
- Module-level logger: `logger = logging.getLogger(__name__)`
- `logging.basicConfig` called at module import with `INFO` level and timestamped format `"%(asctime)s [%(levelname)s] %(message)s"`
- Uses `logger.info`, `logger.debug`, `logger.warning`, `logger.error`
- Progress messages use `[N/total]` prefix pattern
- Uses `print()` for all user-facing step output, not `logging`
- Prefix convention: `[parse]`, `[sanitize]`, `[parquet]`, `[done]`, `[warn]`
## Comments
- Section delimiters used to visually separate major pipeline stages (dashed lines + ALL-CAPS label in `pipeline.py`)
- Inline comments on non-obvious logic (e.g. millisecond-to-second conversion, `# De-duplicate`)
- `# pragma: no cover` on branches that cannot be exercised in the test suite
- One-line docstrings on all public functions
- No docstrings on private helpers (they rely on the function name being self-descriptive)
- Module-level docstrings on both `scrape.py` and `pipeline.py` with purpose, usage example
## Function Design
## Module Design
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- Flat module layout: no packages, no sub-modules; both scripts are importable top-level modules
- Scraper and pipeline are fully independent; they communicate only through files in `out/`
- Pipeline supports both an in-memory full run and step-by-step CSV-materialized run
- All configuration is via module-level constants, overridable via CLI arguments
## Layers
- Purpose: Acquire raw calendar data from Forex Factory without browser automation
- Location: `scrape.py`
- Contains: HTTP session management, URL generation, HTML parsing, JSON file writing
- Depends on: `curl_cffi` (HTTP with TLS fingerprint impersonation), Python stdlib (`json`, `re`, `os`, `time`, `datetime`)
- Used by: `pipeline.py` indirectly (reads `out/` files produced here)
- Purpose: Parse, filter, sanitize, and serialize raw event data
- Location: `pipeline.py`
- Contains: JSON loading, event flattening, deduplication, filtering, Parquet output
- Depends on: `pandas`, `pyarrow`, Python stdlib (`json`, `csv`, `glob`, `os`, `datetime`)
- Used by: End consumers reading `economic_events.parquet`
- Purpose: Regression coverage for both scrape and pipeline logic
- Location: `tests/test_scrape.py`, `tests/test_pipeline.py`, `tests/test_docs.py`
- Contains: unittest-style test classes run under pytest; no fixtures directory populated
- Depends on: `scrape`, `pipeline` modules imported directly from repo root
## Data Flow
### Full Pipeline (recommended path)
### Incremental Scrape Path
### Step-by-step Pipeline Path
- No in-process persistent state; all state lives in files (`out/*.json`, `*.csv`, `*.parquet`)
- `curl_cffi.Session` is instantiated per `run_scraper()` call and not reused across invocations
## Key Abstractions
- Purpose: Typed value object binding a month anchor date to its Forex Factory URL
- Examples: `scrape.py:64`
- Pattern: Frozen `@dataclass`; created by `build_month_pages()`, consumed by `run_scraper()` and `scrape_month()`
- Purpose: Return value from `run_scraper()` summarizing success/fail/skip counts
- Examples: `scrape.py:71`
- Pattern: Frozen `@dataclass`; returned to `main()` and used in tests for assertions
- Purpose: Forex Factory embeds calendar data as a JavaScript object in HTML; two assignment forms are handled
- Form 1: `window.calendarComponentStates = { "key": { days: [...] } }` — parsed by `_extract_state_json()` + `_loads_js_object()`
- Form 2: `window.calendarComponentStates[n] = { days: [...] }` — parsed by `_extract_assigned_state_objects()`
- Best candidate selected by `_select_best_days()` (most days + most events wins)
- Examples: `scrape.py:219`, `scrape.py:244`, `scrape.py:262`
## Entry Points
- Location: `scrape.py:441` (`if __name__ == "__main__": main()`)
- Triggers: `python scrape.py [--start-date ...] [--end-date ...] [--out-dir ...] [--between-pages-delay ...] [--retry-delay ...]`
- Responsibilities: Parse CLI args, validate dates, build month page list, run scraper, log summary
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
### Module-level IN_DIR constant shared by pipeline steps and run_pipeline
## Error Handling
- `scrape_month()` catches all `Exception` subclasses per attempt and retries up to `max_attempts` times (`scrape.py:338`); logs warning on exhaustion and returns `[]`
- `run_scraper()` writes an empty JSON file and increments `fail_count` when `scrape_month` returns `[]`; execution continues to the next month
- `pipeline.py` raises `FileNotFoundError` if an expected input CSV is missing (`pipeline.py:148`)
- `load_days_files()` prints a warning and skips files with invalid JSON; does not raise (`pipeline.py:47`)
- `main()` in `scrape.py` calls `sys.exit(1)` on invalid date arguments
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
