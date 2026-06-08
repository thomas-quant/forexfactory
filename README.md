# Forex Factory Economic Calendar Data Provider

A pip-installable Python package that scrapes the [Forex Factory](https://www.forexfactory.com/calendar) economic calendar and serves it from a shared local parquet cache. Install once, populate once, and read the same data from any project — via a CLI or as a library.

## Features

- **Shared local cache** — one `~/.cache/forexfactory/` directory readable from any project
- **Browserless scraping** — `curl_cffi` TLS fingerprint impersonation, no browser automation
- **Incremental refresh** — `forexfactory refresh` gap-fills missing months over the network; never overwrites settled months
- **Script-friendly query** — `forexfactory query` prints only the parquet path to stdout (`PARQUET=$(forexfactory query ...)`)
- **Library API** — `forexfactory.get(currencies=[...], impacts=[...]) -> pathlib.Path`

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Populate the Cache

Build the parquet cache from the on-disk raw JSON files (zero network calls):

```bash
forexfactory populate
```

Default scope: **USD** currency, **high** and **holiday** impact, all months on disk (~195 months, 2010-01 → 2026-03). Widen the scope with repeatable flags:

```bash
forexfactory populate --currency USD --currency EUR --impact high --impact medium
```

Override the cache directory (default: `~/.cache/forexfactory/`):

```bash
forexfactory populate --cache-dir /path/to/cache
```

Force-rebuild every month unconditionally (bypasses the manifest skip-check — use after a schema migration):

```bash
forexfactory populate --force --raw-dir out
```

### 3. Query the Cache

```bash
forexfactory query --currency USD --impact high
```

`query` prints **only** the absolute path of the result parquet to stdout — no other output — making it shell-friendly:

```bash
PARQUET=$(forexfactory query --currency USD --impact high)
python -c "import pandas as pd; print(pd.read_parquet('$PARQUET').head())"
```

By default `query` returns **data-bearing events** (with `forecast`/`actual` fields) and **bank holidays**. To include speeches and other no-data events:

```bash
forexfactory query --currency USD --impact high --include-no-data
```

If the requested currency/impact combination has not been populated, `query` exits non-zero and prints actionable guidance to stderr (run `forexfactory populate --currency ... --impact ...` first).

### 4. Refresh (Network)

Fetch months not yet in the cache from Forex Factory over the network:

```bash
forexfactory refresh
```

By default `refresh` gap-fills from the last cached month through the current month, with a polite 1-second delay between requests. It does not overwrite already-cached months.

## Library API

```python
import forexfactory
from pathlib import Path

path: Path = forexfactory.get(currencies=["USD"], impacts=["high"])

import pandas as pd
df = pd.read_parquet(path)
```

## Output Schema

The cache stores data as parquet with the following columns (schema_version 2):

**Core fields (DATA-01)**

| Column | Type | Description |
|--------|------|-------------|
| `datetime_utc` | datetime64[ns, UTC] | Event timestamp in UTC |
| `currency` | string | Currency code (e.g. USD) |
| `impact` | string | Impact level (high, holiday, medium, low) |
| `title` | string | Event name |
| `id` | Int64 | Forex Factory event ID (nullable) |
| `leaked` | boolean | Whether Forex Factory marked the event as leaked |

**Raw value strings (verbatim from FF)**

| Column | Type | Description |
|--------|------|-------------|
| `forecast_raw` | string | Raw forecast value string (e.g. `"4.3%"`, `"202K"`, `""`) |
| `actual_raw` | string | Raw actual value string |
| `previous_raw` | string | Raw previous value string |
| `revision_raw` | string | Raw revision value string |

**Parsed numerics**

Magnitude suffixes expanded (K=×1e3, M=×1e6, B=×1e9, T=×1e12). Percent divided by 100 (`"4.3%"` → 0.043). Unparseable or empty strings become null (NaN).

| Column | Type | Description |
|--------|------|-------------|
| `forecast` | float64 | Parsed forecast numeric (null if unparseable) |
| `actual` | float64 | Parsed actual numeric |
| `previous` | float64 | Parsed previous numeric |
| `revision` | float64 | Parsed revision numeric |

**Surprise flags and identity**

| Column | Type | Description |
|--------|------|-------------|
| `actualBetterWorse` | Int64 | FF surprise flag: 1=better, 2=worse, 0=neutral/n/a (nullable) |
| `revisionBetterWorse` | Int64 | FF revision flag: 1=better, 2=worse, 0=neutral/n/a (nullable) |
| `ebaseId` | Int64 | FF metric series identifier (nullable) |
| `country` | string | Country code (e.g. US, UK, JN, EZ) |
| `hasDataValues` | boolean | True for data releases with forecast/actual/previous; False for speeches and holidays |

## Cache Layout

The cache lives at `~/.cache/forexfactory/` by default (override with `--cache-dir` or the
`FOREXFACTORY_CACHE_DIR` environment variable):

```
~/.cache/forexfactory/
|-- manifest.json          # populated scope + per-month provenance
|-- raw/                   # staging JSON (temporary; removed in Phase 2)
|   `-- days_YYYY_MM.json
|-- queries/               # per-scope result parquets
|   `-- USD_high_....parquet
`-- YYYY-MM.parquet        # one file per calendar month
```

## Project Structure

```text
forexfactory/
|-- pyproject.toml
|-- requirements.txt
|-- README.md
|-- src/forexfactory/
|   |-- __init__.py
|   |-- cli.py
|   |-- _cache.py
|   |-- _pipeline.py
|   |-- _populate.py
|   |-- _query.py
|   |-- _refresh.py
|   `-- _scrape.py
|-- tests/
|   |-- test_cache.py
|   |-- test_cli.py
|   |-- test_docs.py
|   |-- test_pipeline.py
|   |-- test_populate.py
|   |-- test_query.py
|   |-- test_refresh.py
|   `-- test_scrape.py
`-- out/                    # optional raw-staging dir (populated on re-scrape)
```

## Performance

For **2021-01-01 → 2021-06-30**:

| Scraper | Time | Notes |
|---------|------|-------|
| `scrape_selenium.py` | 16.5s | legacy `undetected-chromedriver` figure from the old README |
| old nodriver `scrape.py` | 10.3s | legacy nodriver figure from the old README |
| current `curl_cffi` scraper | **6.171s** | current implementation |

Stepwise speedups on that same 6-month span:

- nodriver was **37.6% faster** than `undetected-chromedriver`
- `curl_cffi` is **40.1% faster** than nodriver
- `curl_cffi` is **62.6% faster** than `undetected-chromedriver` overall

The current scraper also matched the old headed nodriver output exactly on the tested 6-month comparison span.

## Data Source

Data is scraped from the Forex Factory economic calendar. This tool is for personal/research use. Please respect their terms of service and rate limits.

## License

MIT
