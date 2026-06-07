# Coding Conventions

**Analysis Date:** 2026-06-07

## Naming Patterns

**Files:**
- Flat snake_case module names at the repo root: `scrape.py`, `pipeline.py`
- Test files prefixed with `test_` mirroring the module they cover: `tests/test_scrape.py`, `tests/test_pipeline.py`
- One doc-regression test file: `tests/test_docs.py`

**Functions:**
- Public functions: `snake_case` — e.g. `extract_days`, `build_month_pages`, `run_scraper`, `parse_json_to_csv`
- Private/internal helpers: leading underscore `_snake_case` — e.g. `_find_matching_brace`, `_extract_state_json`, `_quote_js_object_keys`, `_select_best_days`

**Variables:**
- Local variables: `snake_case` — e.g. `last_error`, `open_index`, `in_string`
- Module-level config constants: `UPPER_SNAKE_CASE` — e.g. `START_DATE`, `OUT_DIR`, `MAX_ATTEMPTS`, `KEEP_CURRENCIES`, `PARQUET_COMPRESSION`

**Types / Classes:**
- `PascalCase` for dataclasses and test helper classes: `MonthPage`, `ScrapeResult`, `FakeResponse`, `FakeSession`
- Test suite classes: `PascalCase` ending in `Tests` — e.g. `ScrapeTests`, `PipelineParquetCompressionTests`, `PipelineLeakedFieldTests`

## Code Style

**Formatting:**
- No formatter config file present (no `pyproject.toml`, `.flake8`, `setup.cfg`)
- Code follows PEP 8 visually: 4-space indentation, blank lines between top-level definitions
- Long strings broken with parentheses and explicit concatenation, not backslash continuation

**Linting:**
- No linting config detected; no `# noqa` suppressions
- One `# pragma: no cover` comment used for an `except ImportError` branch that is exercised only in user environments without `curl_cffi` (`scrape.py:24`)

**Type Hints:**
- Used consistently in function signatures for public and private helpers
- Modern union syntax: `str | None`, `Exception | None`, `list[MonthPage]` (Python 3.10+ style)
- `from typing import Any` imported for untyped dict payloads
- Return types annotated on most functions

**Dataclasses:**
- Used for plain data containers; always frozen: `@dataclass(frozen=True)` — `MonthPage`, `ScrapeResult` in `scrape.py`

## Import Organization

**Order (observed in both modules):**
1. Standard library (`os`, `json`, `glob`, `csv`, `argparse`, `re`, `sys`, `time`, `logging`, `datetime`, `dataclasses`, `typing`)
2. Third-party (`curl_cffi`, `pandas`)
3. No local package imports (flat module layout, tests import modules directly by name)

**Conditional imports:**
- Optional dependency guarded with try/except at module top; `None` sentinel used to defer the error to call time:
  ```python
  try:
      from curl_cffi import requests as curl_requests
  except ImportError:  # pragma: no cover
      curl_requests = None
  ```

## Config Constants

- Both modules define a `# CONFIG` section near the top with all tuneable values as module-level `UPPER_SNAKE_CASE` constants
- `scrape.py` uses a visual delimiter (`# ====== CONFIG ======` / `# ====================`)
- `pipeline.py` uses a visual delimiter (`# ========= CONFIG =========` / `# ==========================`)
- Default values for CLI args always derive from the matching constant (e.g. `default=START_DATE`)

## Keyword-Only Arguments

- Functions with optional behavioral parameters use `*` to enforce keyword-only call sites:
  ```python
  def scrape_month(session, page, *, max_attempts=MAX_ATTEMPTS, retry_delay=RETRY_DELAY) -> list:
  def run_scraper(pages, *, out_dir=OUT_DIR, session=None, between_pages_delay=..., retry_delay=...) -> ScrapeResult:
  ```

## Error Handling

**Patterns:**
- Validate CLI args in `main()` and call `sys.exit(1)` on fatal input errors (`scrape.py:422-427`)
- Raise `ValueError` from low-level parsing helpers when invariants are broken (`_find_matching_brace`, `_extract_state_json`)
- Retry loop in `scrape_month` catches broad `Exception` to handle any transient fetch or parse failure; comment explains intent (`scrape.py:338`)
- `FileNotFoundError` raised explicitly on missing input in pipeline step functions (`pipeline.py:149`)
- `json.JSONDecodeError` silently skipped for bad JSON files with a `print("[warn] ...")` message (`pipeline.py:47-48`)
- Never silently swallow errors in the happy path; failures are logged or raised

## Logging

**Scraper (`scrape.py`):**
- Module-level logger: `logger = logging.getLogger(__name__)`
- `logging.basicConfig` called at module import with `INFO` level and timestamped format `"%(asctime)s [%(levelname)s] %(message)s"`
- Uses `logger.info`, `logger.debug`, `logger.warning`, `logger.error`
- Progress messages use `[N/total]` prefix pattern

**Pipeline (`pipeline.py`):**
- Uses `print()` for all user-facing step output, not `logging`
- Prefix convention: `[parse]`, `[sanitize]`, `[parquet]`, `[done]`, `[warn]`

## Comments

**When to Comment:**
- Section delimiters used to visually separate major pipeline stages (dashed lines + ALL-CAPS label in `pipeline.py`)
- Inline comments on non-obvious logic (e.g. millisecond-to-second conversion, `# De-duplicate`)
- `# pragma: no cover` on branches that cannot be exercised in the test suite

**Docstrings:**
- One-line docstrings on all public functions
- No docstrings on private helpers (they rely on the function name being self-descriptive)
- Module-level docstrings on both `scrape.py` and `pipeline.py` with purpose, usage example

## Function Design

**Size:** Functions are small and single-purpose; no function exceeds ~45 lines
**Parameters:** Positional for required data, keyword-only for behavioral options
**Return Values:** Functions return meaningful values (`ScrapeResult`, `list`, `str` path); `main()` in `scrape.py` returns `ScrapeResult` to allow testing; `main()` in `pipeline.py` returns `None`

## Module Design

**Exports:** No `__all__` defined; all public names are importable
**Entry Points:** Both modules use the `if __name__ == "__main__": main()` guard
**`main()` design:** `main()` accepts optional `argv` in `scrape.py` (enables CLI testing without subprocess); `pipeline.py`'s `main()` uses `sys.argv` implicitly via `argparse`

---

*Convention analysis: 2026-06-07*
