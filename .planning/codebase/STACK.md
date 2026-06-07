# Technology Stack

**Analysis Date:** 2026-06-07

## Languages

**Primary:**
- Python 3.12 - All source code (`scrape.py`, `pipeline.py`, `tests/`)

**Secondary:**
- None

## Runtime

**Environment:**
- CPython 3.12.x (3.12.3 observed in dev environment)
- No async runtime; all I/O is synchronous via `curl_cffi` sessions

**Package Manager:**
- pip
- Lockfile: Not present (only `requirements.txt` with minimum version pins)

## Frameworks

**Core:**
- None — plain Python scripts with `argparse` CLIs

**Testing:**
- pytest (invoked as `python3 -m pytest -q`) — test runner
- unittest (stdlib) — test case base class used throughout `tests/`

**Build/Dev:**
- None — no build system, no Makefile, no tox

## Key Dependencies

**Critical:**
- `curl_cffi>=0.13.0` — HTTP client with browser TLS fingerprint impersonation; replaces Selenium/nodriver; guards behind `try/except ImportError` in `scrape.py`
- `pandas>=2.0.0` — DataFrame construction and Parquet I/O in `pipeline.py`
- `pyarrow>=14.0.0` — Parquet write engine used by pandas (`compression="zstd"`, level 3)

**Infrastructure:**
- `setuptools>=65.0.0` — Required for Python 3.12 where `distutils` was removed from stdlib

## Configuration

**Environment:**
- No `.env` file or environment variables used
- All configuration is via in-module constants at the top of each script:
  - `scrape.py`: `START_DATE`, `END_DATE`, `OUT_DIR`, `IMPERSONATE`, `REQUEST_TIMEOUT`, `MAX_ATTEMPTS`, `BETWEEN_PAGES_DELAY`, `RETRY_DELAY`
  - `pipeline.py`: `IN_DIR`, `PARSED_CSV`, `CLEAN_CSV`, `OUT_PARQUET`, `KEEP_CURRENCIES`, `KEEP_IMPACTS`, `PARQUET_COMPRESSION`, `PARQUET_COMPRESSION_LEVEL`

**Build:**
- No build config files (no `pyproject.toml`, `setup.cfg`, `Makefile`)
- `requirements.txt` is the sole dependency manifest

## Platform Requirements

**Development:**
- Python 3.12+
- `pip install -r requirements.txt`
- Internet access for scraping `https://www.forexfactory.com/calendar`

**Production:**
- No deployment target — scripts are run locally on demand
- Output artifacts (`out/days_YYYY_MM.json`, `economic_events.parquet`) are local files, not committed to git

---

*Stack analysis: 2026-06-07*
