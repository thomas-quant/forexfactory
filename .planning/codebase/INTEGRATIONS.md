# External Integrations

**Analysis Date:** 2026-06-07

## APIs & External Services

**Web Scraping Target:**
- Forex Factory Economic Calendar — source of all economic event data
  - Base URL: `https://www.forexfactory.com/calendar`
  - Request pattern: `GET /calendar?month=<mon>.<year>` (e.g. `?month=jan.2026`)
  - SDK/Client: `curl_cffi` session (`scrape.py`, `build_session()`)
  - Auth: None — public page, no API key required
  - Anti-bot bypass: TLS fingerprint impersonation via `impersonate="chrome"` in every `session.get()` call
  - Headers: spoofed Chrome `User-Agent`, `Accept`, `Referer`, and cache-control headers defined in `HEADERS` dict in `scrape.py`

**Possible POST endpoint (unexplored):**
- `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` — noted in `api.txt` as a candidate for POST-based data retrieval; not currently implemented

## Data Storage

**Databases:**
- None — no database of any kind

**File Storage:**
- Local filesystem only
  - Raw scraped data: `out/days_YYYY_MM.json` — one JSON file per calendar month, written by `scrape.py`
  - Final output: `economic_events.parquet` — Parquet file written by `pipeline.py` using zstd compression (level 3)
  - Intermediate CSV files: `ff_usd_high_holiday.csv`, `ff_usd_high_holiday_clean.csv` — produced only when running individual pipeline steps; gitignored

**Caching:**
- Implicit file-based cache: `run_scraper()` in `scrape.py` skips a month if its `out/days_YYYY_MM.json` already exists on disk

## Authentication & Identity

**Auth Provider:**
- None — no user authentication, no sessions, no tokens

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service

**Logs:**
- stdlib `logging` module (`scrape.py`)
  - Level: `INFO` by default
  - Format: `%(asctime)s [%(levelname)s] %(message)s` with `%Y-%m-%d %H:%M:%S` timestamps
  - Logger name: `__name__` (module-level)
- `pipeline.py` uses `print()` for progress output (no structured logging)

## CI/CD & Deployment

**Hosting:**
- Not deployed — local execution only

**CI Pipeline:**
- None detected (no GitHub Actions, no `.github/` directory, no CI config)

## Environment Configuration

**Required env vars:**
- None — the project uses no environment variables

**Secrets location:**
- Not applicable — no secrets required

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Data Flow Summary

```
forexfactory.com/calendar?month=<token>
        |
        | HTTP GET (curl_cffi, Chrome impersonation)
        v
  scrape.py -> out/days_YYYY_MM.json  (one file per month, JSON)
        |
        v
  pipeline.py -> economic_events.parquet
                 (filters: currency=USD, impact=high|holiday,
                  removes 'speaks' events, zstd level-3 compression)
```

---

*Integration audit: 2026-06-07*
