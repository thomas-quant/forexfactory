# Contributing

Thank you for your interest in contributing to `forexfactory`.

## Prerequisites

- Python 3.12 or later
- Internet access (for scraping `https://www.forexfactory.com/calendar`)

## Development Setup

Clone the repository and install the package in editable mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

This installs `ruff`, `mypy`, `pytest`, and `pandas-stubs` alongside the package itself.

## Running the Checks

CI runs the following commands on every push and pull request (Python 3.12 + 3.13 matrix).
Run the same commands locally before opening a PR:

```bash
# Test suite
python -m pytest -q

# Lint check
ruff check .

# Format check
ruff format --check .

# Type check
mypy src/forexfactory
```

All four commands must exit 0. CI enforces the same requirement on both Python 3.12 and 3.13.

## Project Notes

- The scraper (`src/forexfactory/_scrape.py`) contains a character-by-character JS parser for
  the embedded `calendarComponentStates` object. It is fragile by design — covered by four
  golden HTML fixtures in `tests/fixtures/`. Avoid refactoring it without updating the fixtures.
- `curl_cffi` is an optional import at module level; a `# pragma: no cover` guard is intentional
  on the `ImportError` branch.
- Cache defaults to `~/.cache/forexfactory`; override with `--cache-dir` or the
  `FOREXFACTORY_CACHE_DIR` environment variable.
- `forexfactory` is a personal/research tool — respect Forex Factory's terms of service and
  rate limits. Non-zero delays between page fetches are enabled by default.
