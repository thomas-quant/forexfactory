# Phase 1: Installable Data Provider - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 17 new/modified files
**Analogs found:** 15 / 17 (2 have no direct codebase analog — pyproject.toml and _cache.py)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pyproject.toml` | config | N/A | none | no analog |
| `src/forexfactory/__init__.py` | provider | request-response | `scrape.py` top-of-file + conditional import | partial |
| `src/forexfactory/_scrape.py` | service | request-response (HTTP) | `scrape.py` | exact |
| `src/forexfactory/_pipeline.py` | service | batch + file-I/O | `pipeline.py` | exact |
| `src/forexfactory/_cache.py` | utility | file-I/O + CRUD | `scrape.py:351-392` (file write loop) + `pipeline.py:38-48` (file read) | partial |
| `src/forexfactory/_populate.py` | service | batch + file-I/O | `pipeline.py:202-233` (`run_pipeline`) | exact |
| `src/forexfactory/_refresh.py` | service | request-response (HTTP) | `scrape.py:351-392` (`run_scraper`) | exact |
| `src/forexfactory/_query.py` | service | batch + file-I/O | `pipeline.py:202-233` + `pipeline.py:187-195` (`write_parquet`) | role-match |
| `src/forexfactory/cli.py` | controller | request-response | `scrape.py:395-442` (`parse_args`/`main`) + `pipeline.py:236-281` (`main`) | role-match |
| `tests/test_scrape.py` | test | N/A | `tests/test_scrape.py` | exact (adapt imports) |
| `tests/test_pipeline.py` | test | N/A | `tests/test_pipeline.py` | exact (adapt imports) |
| `tests/test_populate.py` | test | N/A | `tests/test_pipeline.py` | role-match |
| `tests/test_refresh.py` | test | N/A | `tests/test_scrape.py` | role-match |
| `tests/test_cache.py` | test | N/A | `tests/test_pipeline.py` (tempdir pattern) | role-match |
| `tests/test_query.py` | test | N/A | `tests/test_pipeline.py` | role-match |
| `tests/test_cli.py` | test | N/A | `tests/test_scrape.py:116-146` (`test_main_passes_cli_delays`) | role-match |
| `tests/test_docs.py` | test | N/A | `tests/test_docs.py` | exact (update assertions) |

---

## Pattern Assignments

### `pyproject.toml` (config, N/A)

**Analog:** None in codebase. Use standard pyproject.toml with setuptools.

**Key constraints from CONTEXT.md D-13 and REQUIREMENTS.md PKG-01:**
- `[project] name = "forexfactory"` — distribution name identical to import name
- `[project] requires-python = ">=3.12"`
- Console script: `forexfactory = "forexfactory.cli:main"` (single entry point, no `ff` alias)
- Dependencies mirror `requirements.txt`: `curl_cffi>=0.13.0`, `pandas>=2.0.0`, `pyarrow>=14.0.0`, `setuptools>=65.0.0`
- Source layout: `[tool.setuptools.packages.find] where = ["src"]`
- Locally installable only (`pip install -e .`); no PyPI metadata needed yet (DIST-01 deferred)

---

### `src/forexfactory/__init__.py` (provider, request-response)

**Analog:** `scrape.py` lines 1-25 (module docstring, conditional import pattern), `pipeline.py` lines 1-31

**Module docstring pattern** (`scrape.py:1-9`):
```python
"""
Forex Factory Calendar Scraper (curl_cffi version)
===============================================================
Fetches calendar pages without a browser and extracts the embedded calendar
state from the HTML.

Usage:
    python scrape.py
"""
```

**Conditional import pattern** (`scrape.py:22-25`):
```python
try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - exercised by users without dependency
    curl_requests = None
```

**What to implement:**
- Module docstring describing the library, `forexfactory.get(...)` usage example
- `get()` function: thin wrapper over `_query.py` returning `pathlib.Path`
- Re-export `get` so callers write `import forexfactory; forexfactory.get(...)`
- No `__all__`; follow project convention (CONVENTIONS.md: "No `__all__` defined; all public names are importable")
- Type hint: `def get(...) -> Path:` using `pathlib.Path` (not `str`)

---

### `src/forexfactory/_scrape.py` (service, request-response)

**Analog:** `scrape.py` — move wholesale, apply QUAL-03 fix

**Imports block** (`scrape.py:11-25`):
```python
import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - exercised by users without dependency
    curl_requests = None
```

**Logging setup pattern** (`scrape.py:27-33`):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

**Config constants pattern** (`scrape.py:35-61`):
```python
# ====== CONFIG ======
START_DATE = "2021-01-01"   # <-- QUAL-04: replace with None or compute from cache
END_DATE = "2021-06-30"     # <-- QUAL-04: replace with None or today
OUT_DIR = "out"             # <-- becomes CACHE_DIR default from _cache.py
IMPERSONATE = "chrome"
REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3
BETWEEN_PAGES_DELAY = 0.0   # <-- D-11/CONCERNS: change to polite non-zero default (1.0)
RETRY_DELAY = 0.0            # <-- D-11/CONCERNS: change to polite non-zero default (1.0)
# ====================
```

**Frozen dataclass pattern** (`scrape.py:64-74`):
```python
@dataclass(frozen=True)
class MonthPage:
    anchor: date
    url: str

@dataclass(frozen=True)
class ScrapeResult:
    success_count: int
    fail_count: int
    skip_count: int
```

**Keyword-only function signature pattern** (`scrape.py:315-321`):
```python
def scrape_month(
    session,
    page: MonthPage,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    retry_delay: float = RETRY_DELAY,
) -> list:
```

**QUAL-03 fix — stop writing empty JSON on failure** (`scrape.py:379-387`, current buggy code):
```python
# CURRENT (BUG — writes empty file even on failure):
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(days, handle, ensure_ascii=False, separators=(",", ":"))

if days:
    logger.info("  Saved: %s", out_path)
    success_count += 1
else:
    logger.warning("  Saved empty: %s", out_path)
    fail_count += 1
```

Fix: only open/write when `days` is non-empty; on failure increment `fail_count` and `continue` without touching the filesystem:
```python
# FIX (D-06 / QUAL-03):
if days:
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(days, handle, ensure_ascii=False, separators=(",", ":"))
    logger.info("  Saved: %s", out_path)
    success_count += 1
else:
    logger.warning("  Skipping write for %s — no days extracted", page.anchor)
    fail_count += 1
```

**QUAL-04 fix — stale hardcoded date defaults** (`scrape.py:36-37`):
```python
# CURRENT (bug):
START_DATE = "2021-01-01"
END_DATE = "2021-06-30"
```
In `_refresh.py`, replace with dynamic defaults (gap-fill from last cached month to current month per D-11/Claude's Discretion). Do not keep hardcoded historical defaults.

---

### `src/forexfactory/_pipeline.py` (service, batch + file-I/O)

**Analog:** `pipeline.py` — move wholesale, apply QUAL-01 and QUAL-02 fixes

**Config constants pattern** (`pipeline.py:22-31`):
```python
# ========= CONFIG =========
IN_DIR = "out"
PARSED_CSV = "ff_usd_high_holiday.csv"
CLEAN_CSV = "ff_usd_high_holiday_clean.csv"
OUT_PARQUET = "economic_events.parquet"
KEEP_CURRENCIES = {"USD"}
KEEP_IMPACTS = {"high", "holiday"}
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
# ==========================
```

**QUAL-01 fix — duplicated dedup logic** (`pipeline.py:117-123` and `pipeline.py:214-220`, both identical):
```python
# CURRENT (copy-paste in parse_json_to_csv AND run_pipeline):
dedup = {}
for r in rows:
    key = (r["id"], r["date"], r["time_utc"]) if r["id"] else (r["date"], r["time_utc"], r["currency"], r["title"])
    dedup[key] = r
rows = list(dedup.values())
rows.sort(key=lambda x: (x["date"], x["time_utc"], x["title"]))
```

Fix: extract into a private helper:
```python
def _deduplicate_rows(rows: list[dict]) -> list[dict]:
    dedup = {}
    for r in rows:
        key = (r["id"], r["date"], r["time_utc"]) if r["id"] else (r["date"], r["time_utc"], r["currency"], r["title"])
        dedup[key] = r
    result = list(dedup.values())
    result.sort(key=lambda x: (x["date"], x["time_utc"], x["title"]))
    return result
```
Then call `rows = _deduplicate_rows(rows)` in both `parse_json_to_csv` and `run_pipeline`.

**QUAL-02 fix — `run_pipeline()` ignores `--in-dir`** (`pipeline.py:202-206`, current signature and body):
```python
# CURRENT (bug — ignores in_dir entirely, always reads IN_DIR global):
def run_pipeline(out_parquet: str = OUT_PARQUET):
    rows = []
    for path, days in load_days_files(IN_DIR):   # <-- hardcoded global
        ...
```

Fix: add `in_dir`, `keep_currencies`, `keep_impacts` parameters:
```python
def run_pipeline(
    out_parquet: str = OUT_PARQUET,
    *,
    in_dir: str = IN_DIR,
    keep_currencies: set = KEEP_CURRENCIES,
    keep_impacts: set = KEEP_IMPACTS,
) -> None:
    rows = []
    for path, days in load_days_files(in_dir):   # <-- parameter, not global
        for r in flatten_events(days, path):
            if keep_currencies and r["currency"] not in keep_currencies:
                continue
            if keep_impacts and r["impact"] not in keep_impacts:
                continue
            rows.append(r)
```

And in `main()` (`pipeline.py:274-277`), forward the arg:
```python
# CURRENT (bug — does not forward in_dir):
out_parquet = args.out or OUT_PARQUET
run_pipeline(out_parquet=out_parquet)

# FIX:
out_parquet = args.out or OUT_PARQUET
run_pipeline(out_parquet=out_parquet, in_dir=args.in_dir)
```

**Parquet write pattern** (`pipeline.py:187-195`):
```python
def write_parquet(df: pd.DataFrame, parquet_path: str) -> str:
    """Write parquet files with the project's standard compression settings."""
    df.to_parquet(
        parquet_path,
        index=False,
        compression=PARQUET_COMPRESSION,
        compression_level=PARQUET_COMPRESSION_LEVEL,
    )
    return parquet_path
```

**flatten_events pattern** (`pipeline.py:81-98`):
```python
def flatten_events(days, src_path=None):
    """Flatten nested days/events structure into individual event dicts."""
    for d in days:
        for ev in d.get("events", []):
            currency = (ev.get("currency") or "").upper()
            impact = norm_impact(ev.get("impactName") or ev.get("impactTitle") or "")
            title = ev.get("prefixedName") or ev.get("name") or ev.get("soloTitle") or ""
            dateline = ev.get("dateline")
            date_iso, time_utc = to_iso(dateline)
            yield {
                "date": date_iso,
                "time_utc": time_utc,
                "currency": currency,
                "impact": impact,
                "title": title,
                "id": ev.get("id", ""),
                "leaked": ev.get("leaked"),
            }
```

---

### `src/forexfactory/_cache.py` (utility, file-I/O + CRUD)

**Analog:** No single close analog. Build from file I/O patterns across both scripts.

**Path construction pattern** (`scrape.py:368`):
```python
out_path = os.path.join(out_dir, f"days_{page.anchor.strftime('%Y_%m')}.json")
```

**Directory creation pattern** (`scrape.py:360`):
```python
os.makedirs(out_dir, exist_ok=True)
```

**JSON read pattern** (`pipeline.py:38-48`):
```python
def load_days_files(in_dir: str):
    """Yield (path, days_list) for each days_*.json file."""
    paths = sorted(glob.glob(os.path.join(in_dir, "days_*.json")))
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            try:
                days = json.load(f)
                if isinstance(days, list):
                    yield p, days
            except json.JSONDecodeError:
                print(f"[warn] bad JSON: {p}")
```

**What to implement:**
- `DEFAULT_CACHE_DIR: Path` — resolves `~/.cache/forexfactory` via `pathlib.Path.home() / ".cache" / "forexfactory"`; overridable via env var `FOREXFACTORY_CACHE_DIR` (CACHE-01)
- `raw_dir(cache_dir: Path) -> Path` — returns `cache_dir / "raw"`
- `queries_dir(cache_dir: Path) -> Path` — returns `cache_dir / "queries"`
- `month_parquet_path(cache_dir: Path, anchor: date) -> Path` — e.g. `cache_dir / "2024-03.parquet"`
- `raw_json_path(cache_dir: Path, anchor: date) -> Path` — e.g. `cache_dir / "raw" / "days_2024_03.json"`
- `manifest_path(cache_dir: Path) -> Path` — `cache_dir / "manifest.json"`
- `read_manifest(cache_dir: Path) -> dict` — loads JSON; returns `{}` if missing
- `write_manifest(cache_dir: Path, manifest: dict) -> None` — atomic write with `os.replace`
- `ensure_dirs(cache_dir: Path) -> None` — `os.makedirs` for cache_dir, raw/, queries/

**Manifest schema (D-02, Claude's Discretion):**
```json
{
  "scope": {
    "currencies": ["USD"],
    "impacts": ["high", "holiday"]
  },
  "months": {
    "2024-03": {
      "scraped_at": "2026-06-08T12:00:00Z",
      "settled": true
    }
  }
}
```

---

### `src/forexfactory/_populate.py` (service, batch + file-I/O)

**Analog:** `pipeline.py:202-233` (`run_pipeline`)

**Core pattern from run_pipeline** (`pipeline.py:202-233`):
```python
def run_pipeline(out_parquet: str = OUT_PARQUET):
    rows = []
    for path, days in load_days_files(IN_DIR):
        for r in flatten_events(days, path):
            if KEEP_CURRENCIES and r["currency"] not in KEEP_CURRENCIES:
                continue
            if KEEP_IMPACTS and r["impact"] not in KEEP_IMPACTS:
                continue
            rows.append(r)

    # De-duplicate
    dedup = {}
    for r in rows:
        key = (r["id"], r["date"], r["time_utc"]) if r["id"] else ...
        dedup[key] = r
    rows = list(dedup.values())
    rows.sort(key=lambda x: (x["date"], x["time_utc"], x["title"]))

    rows = [r for r in rows if should_keep_row(r)]

    df = pd.DataFrame(rows)
    if "date" in df.columns and "time_utc" in df.columns:
        df["datetime_utc"] = pd.to_datetime(df["date"] + " " + df["time_utc"], utc=True)
        df = df.drop(columns=["date", "time_utc"])
        df = df[["datetime_utc"] + [c for c in df.columns if c != "datetime_utc"]]

    write_parquet(df, out_parquet)
    print(f"[done] {len(df)} rows -> {out_parquet}")
```

**What populate does differently from run_pipeline:**
- Iterates over months individually (not all-at-once) so it can write per-month parquet (D-01)
- Uses `_cache.py` for all path resolution
- D-06 skip logic: checks manifest before processing each month; re-processes if missing or narrower scope
- Updates manifest after each month is written (provenance: `scraped_at`, `settled`)
- Default range = all months with raw JSON on disk (D-05 / QUAL-04 replacement for stale hardcoded dates)
- Uses `_deduplicate_rows()` helper from `_pipeline.py` (QUAL-01)

**D-06 skip check pattern to model:**
```python
# Skip only if manifest shows month already cached at this scope
month_key = anchor.strftime("%Y-%m")
cached = manifest.get("months", {}).get(month_key)
if cached and _scope_covers(cached_scope, requested_scope):
    logger.info("[%s/%s] Skip (cached): %s", i, total, month_key)
    skip_count += 1
    continue
```

---

### `src/forexfactory/_refresh.py` (service, request-response HTTP)

**Analog:** `scrape.py:351-392` (`run_scraper`)

**Core run_scraper pattern** (`scrape.py:351-392`):
```python
def run_scraper(
    pages: list[MonthPage],
    *,
    out_dir: str = OUT_DIR,
    session=None,
    between_pages_delay: float = BETWEEN_PAGES_DELAY,
    retry_delay: float = RETRY_DELAY,
) -> ScrapeResult:
    """Scrape pages, skip existing files, write days_YYYY_MM.json files."""
    os.makedirs(out_dir, exist_ok=True)
    session = session or build_session()

    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, page in enumerate(pages, 1):
        out_path = os.path.join(out_dir, f"days_{page.anchor.strftime('%Y_%m')}.json")

        if os.path.isfile(out_path):
            logger.info("[%s/%s] Skip (exists): %s", i, len(pages), page.anchor.strftime("%Y-%m"))
            skip_count += 1
            continue

        logger.info("[%s/%s] Loading: %s", i, len(pages), page.url)
        days = scrape_month(session, page, retry_delay=retry_delay)
        logger.info("  -> Extracted %s days", len(days))

        with open(out_path, "w", encoding="utf-8") as handle:  # <-- QUAL-03: only write if days non-empty
            json.dump(days, handle, ensure_ascii=False, separators=(",", ":"))

        if days:
            logger.info("  Saved: %s", out_path)
            success_count += 1
        else:
            logger.warning("  Saved empty: %s", out_path)  # <-- QUAL-03: becomes a skip, no write
            fail_count += 1

        if between_pages_delay > 0:
            time.sleep(between_pages_delay)

    return ScrapeResult(success_count=success_count, fail_count=fail_count, skip_count=skip_count)
```

**What refresh does differently from run_scraper:**
- Path resolution via `_cache.py.raw_json_path(cache_dir, anchor)` instead of `os.path.join(out_dir, ...)`
- Skip logic: checks raw JSON exists AND is non-empty (D-06; empty file from past QUAL-03 bug is re-fetched)
- QUAL-03: does not write file when `days` is empty (only writes non-empty results)
- QUAL-04: default range = gap-fill from last cached raw JSON month through current month (Claude's Discretion)
- D-11: `BETWEEN_PAGES_DELAY` default changed to `1.0` (polite, per CONCERNS.md security note)
- After successful fetch+write: calls `_cache.py.update_manifest_month(...)` to record provenance
- Uses `_cache.py.raw_json_path()` for all paths; calls `_cache.py.ensure_dirs()` at start

---

### `src/forexfactory/_query.py` (service, batch + file-I/O)

**Analog:** `pipeline.py:187-195` (`write_parquet`) + `pipeline.py:202-233` (`run_pipeline`) for read+filter pattern

**Read parquet pattern (pandas):**
```python
import pandas as pd

df = pd.read_parquet(parquet_path)
```

**Write parquet pattern** (`pipeline.py:187-195`):
```python
def write_parquet(df: pd.DataFrame, parquet_path: str) -> str:
    """Write parquet files with the project's standard compression settings."""
    df.to_parquet(
        parquet_path,
        index=False,
        compression=PARQUET_COMPRESSION,
        compression_level=PARQUET_COMPRESSION_LEVEL,
    )
    return parquet_path
```

**What query does:**
- Checks manifest scope (D-09): if request exceeds populated scope, raise `ValueError` with guidance message — `"EUR/medium not populated — run: forexfactory populate --currency EUR --impact medium"`. Caller (cli.py) catches and calls `sys.exit(1)`.
- Reads per-month parquet files (from `_cache.py.month_parquet_path()`) for the requested date range
- Concatenates with `pd.concat(dfs)`
- Applies filter: `df[df["currency"].isin(currencies) & df["impact"].isin(impacts)]`
- Computes deterministic result path (D-08): `queries_dir / f"{'_'.join(currencies)}_{'_'.join(impacts)}_{start}_{end}.parquet"`
- Writes result parquet via `write_parquet()` from `_pipeline.py`
- Returns `pathlib.Path` (library) or prints path to stdout (CLI via `cli.py`)

**D-10 stdout-only result pattern (in cli.py, not _query.py):**
```python
# stdout = just the path; diagnostics go to stderr or logging
path = query(...)
print(path)  # stdout only — enables: PARQUET=$(forexfactory query ...)
```

---

### `src/forexfactory/cli.py` (controller, request-response)

**Analog:** `scrape.py:395-442` (`parse_args` + `main`) and `pipeline.py:236-281` (`main`)

**argparse pattern from scrape.py** (`scrape.py:395-412`):
```python
def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Forex Factory scraper using curl_cffi")
    parser.add_argument("--start-date", default=START_DATE, help="Start date, YYYY-MM-DD")
    parser.add_argument("--end-date", default=END_DATE, help="End date, YYYY-MM-DD")
    parser.add_argument("--out-dir", default=OUT_DIR, help="Output directory for days_YYYY_MM.json files")
    parser.add_argument(
        "--between-pages-delay",
        type=float,
        default=BETWEEN_PAGES_DELAY,
        help="Seconds to sleep between month requests (default: 0)",
    )
    return parser.parse_args(argv)
```

**main() with date validation and sys.exit(1) pattern** (`scrape.py:415-438`):
```python
def main(argv: list[str] | None = None) -> ScrapeResult:
    args = parse_args(argv)

    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        logger.error("Invalid date format: %s", exc)
        sys.exit(1)

    if start > end:
        logger.error("Start date (%s) is after end date (%s)", start, end)
        sys.exit(1)
    ...
```

**Subcommand dispatch pattern** (`pipeline.py:260-277`):
```python
if args.step == "parse":
    out = args.out or PARSED_CSV
    parse_json_to_csv(in_dir=args.in_dir, out_csv=out)
elif args.step == "sanitize":
    ...
elif args.step == "parquet":
    ...
else:
    out_parquet = args.out or OUT_PARQUET
    run_pipeline(out_parquet=out_parquet)
```

**What cli.py implements:**
- Top-level `argparse` with subparsers: `populate`, `refresh`, `query`
- `main(argv=None)` — accepts optional argv for CLI testing (scrape.py pattern)
- D-12: `--currency`/`--impact` use `action="append"` for repeatable flags
- `populate` subparser: `--currency`, `--impact`, `--start`, `--end`, `--cache-dir`, `--raw-dir`
- `refresh` subparser: `--start`, `--end`, `--cache-dir`, `--between-pages-delay`, `--retry-delay`
- `query` subparser: `--currency`, `--impact`, `--start`, `--end`, `--cache-dir`; prints path to stdout (D-10)
- Validation of dates using `datetime.strptime()`; `sys.exit(1)` on error (scrape.py pattern)
- D-09 scope error: catch `ValueError` from `_query.py`; print message to stderr + `sys.exit(1)`

---

### `tests/test_scrape.py` (test — adapt existing)

**Analog:** `tests/test_scrape.py` (exact; only import path changes)

**Current import** (`tests/test_scrape.py:8`):
```python
import scrape as scraper
```

**Adapted import:**
```python
import forexfactory._scrape as scraper
```

All 8 test methods in `ScrapeTests`, `FakeResponse`, and `FakeSession` carry forward unchanged. The `patch.object(scraper, "run_scraper", ...)` / `patch.object(scraper.time, "sleep")` patterns work without modification.

---

### `tests/test_pipeline.py` (test — adapt existing)

**Analog:** `tests/test_pipeline.py` (exact; only import path changes)

**Current import** (`tests/test_pipeline.py:8`):
```python
import pipeline
```

**Adapted import:**
```python
import forexfactory._pipeline as pipeline
```

Existing `patch.object(pipeline, "IN_DIR", ...)` patches change to pass `in_dir` parameter directly (QUAL-02 fix makes `run_pipeline` accept `in_dir`). The `patch.object(pipeline.pd.DataFrame, "to_parquet", ...)` pattern carries forward.

---

### `tests/test_populate.py` (test, new)

**Analog:** `tests/test_pipeline.py` — tempdir + JSON fixture writing pattern

**Tempdir + fixture pattern** (`tests/test_pipeline.py:42-75`):
```python
def test_run_pipeline_uses_zstd_level_3(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        in_dir = tmp_path / "out"
        in_dir.mkdir()
        out_path = tmp_path / "economic_events.parquet"

        days_path = in_dir / "days_2026_03.json"
        days_path.write_text(
            json.dumps([{"events": [{"currency": "USD", "impactName": "high",
                                     "name": "CPI y/y", "dateline": 1772368200, "id": "cpi-1"}]}]),
            encoding="utf-8",
        )

        with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
            with patch.object(pipeline, "IN_DIR", str(in_dir)):
                pipeline.run_pipeline(out_parquet=str(out_path))
```

**What to test in test_populate.py:**
- `populate` skips months already in manifest at matching scope (D-06)
- `populate` processes months with raw JSON present, not in manifest
- `populate` writes per-month parquet files (D-01)
- `populate` updates manifest after writing
- `populate` default scope is USD + high/holiday (D-04)
- QUAL-01: dedup via `_deduplicate_rows()` produces correct row count

---

### `tests/test_refresh.py` (test, new)

**Analog:** `tests/test_scrape.py` — FakeSession/FakeResponse + patch pattern

**FakeSession/FakeResponse pattern** (`tests/test_scrape.py:11-33`):
```python
class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
```

**What to test in test_refresh.py:**
- QUAL-03: failed scrape (empty days) does NOT write file
- Successful scrape writes raw JSON to `raw/` dir via `_cache.py.raw_json_path()`
- Skip logic: month with existing non-empty raw JSON is skipped
- Manifest updated after successful write

---

### `tests/test_cache.py` (test, new)

**Analog:** `tests/test_pipeline.py` tempdir pattern

**What to test in test_cache.py:**
- `read_manifest()` returns `{}` on missing file (no FileNotFoundError)
- `write_manifest()` + `read_manifest()` round-trip preserves scope and month entries
- `month_parquet_path()` returns expected path pattern
- `raw_json_path()` returns expected path pattern
- `DEFAULT_CACHE_DIR` resolves to `~/.cache/forexfactory`
- `ensure_dirs()` creates `raw/` and `queries/` subdirs

---

### `tests/test_query.py` (test, new)

**Analog:** `tests/test_pipeline.py` (DataFrame + parquet mock pattern)

**What to test in test_query.py:**
- D-09: out-of-scope query raises `ValueError` with actionable guidance message
- Query reads correct per-month parquet files for date range
- Result parquet written to deterministic path (D-08)
- `get()` in `__init__.py` returns `pathlib.Path`
- D-10: CLI `query` command prints path only to stdout

---

### `tests/test_cli.py` (test, new)

**Analog:** `tests/test_scrape.py:116-146` (`test_main_passes_cli_delays_to_run_scraper`)

**CLI test pattern** (`tests/test_scrape.py:116-146`):
```python
def test_main_passes_cli_delays_to_run_scraper(self):
    captured = {}

    def fake_run_scraper(pages, *, out_dir, session=None, between_pages_delay=0.0, retry_delay=0.0):
        captured["pages"] = pages
        captured["out_dir"] = out_dir
        captured["between_pages_delay"] = between_pages_delay
        captured["retry_delay"] = retry_delay
        return scraper.ScrapeResult(success_count=0, fail_count=0, skip_count=0)

    with patch.object(scraper, "run_scraper", side_effect=fake_run_scraper):
        result = scraper.main([
            "--start-date", "2026-03-01",
            "--end-date", "2026-03-31",
            "--out-dir", "out-test",
            "--between-pages-delay", "1.25",
            "--retry-delay", "0.5",
        ])

    self.assertEqual(result, scraper.ScrapeResult(success_count=0, fail_count=0, skip_count=0))
    self.assertEqual(captured["out_dir"], "out-test")
    self.assertEqual(captured["between_pages_delay"], 1.25)
    self.assertEqual(captured["retry_delay"], 0.5)
    self.assertEqual(len(captured["pages"]), 1)
```

**What to test in test_cli.py:**
- `populate` subcommand routes to `_populate` with correct scope args (D-12 append action)
- `refresh` subcommand routes to `_refresh` with delay args
- `query` subcommand routes to `_query`, prints path to stdout
- D-12: `--currency USD --currency EUR` yields `["USD", "EUR"]` list (append action)
- Invalid date → exits with code 1

---

### `tests/test_docs.py` (test — update existing)

**Analog:** `tests/test_docs.py` (exact; update path assertions)

**Current pattern** (`tests/test_docs.py:1-32`):
```python
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"

def test_project_structure_chart_uses_plain_ascii_and_matches_repo_layout():
    text = README.read_text(encoding="utf-8")
    assert "```text\nforexfactory/\n" in text
    assert "|-- scrape.py" in text
    assert "|-- pipeline.py" in text
    ...

def test_readme_schema_documents_current_parquet_columns():
    text = README.read_text(encoding="utf-8")
    assert "| `leaked` | boolean | Whether Forex Factory marked the event as leaked |" in text
```

**Adaptations needed:**
- Update structure chart assertions to reflect new `src/forexfactory/` layout and `pyproject.toml`
- Remove assertions for removed files (e.g. `api.txt` deleted per CONCERNS.md)
- Add assertions for new package files: `|-- src/`, `|   |-- forexfactory/`, `|-- pyproject.toml`
- Schema assertion for `datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked` (DATA-01)

---

## Shared Patterns

### Config constants block
**Source:** `scrape.py:35-61` and `pipeline.py:22-31`
**Apply to:** `_scrape.py`, `_pipeline.py`, `_cache.py`, `_populate.py`, `_refresh.py`, `_query.py`
```python
# ====== CONFIG ======
CONSTANT_NAME = default_value
# ====================
```
All tunable values as `UPPER_SNAKE_CASE` module-level constants. CLI arg defaults derive from matching constant.

### Module docstring
**Source:** `scrape.py:1-9`
**Apply to:** All `src/forexfactory/` modules
```python
"""
Short one-line description.
=============================
Longer explanation.

Usage:
    from forexfactory import get
    path = get(currencies=["USD"], impacts=["high"])
"""
```

### Logging setup
**Source:** `scrape.py:27-33`
**Apply to:** `_scrape.py`, `_refresh.py`, `_populate.py`, `_query.py`, `_cache.py`, `cli.py`
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```
Progress messages use `[N/total]` prefix pattern (`scrape.py:371`):
```python
logger.info("[%s/%s] Skip (exists): %s", i, len(pages), page.anchor.strftime("%Y-%m"))
```

### Frozen dataclass value objects
**Source:** `scrape.py:64-74`
**Apply to:** Any new value objects in `_cache.py` (e.g. `CacheScope`, `MonthStatus`), `_query.py` (e.g. `QueryResult`)
```python
@dataclass(frozen=True)
class MonthPage:
    anchor: date
    url: str
```

### Keyword-only optional parameters
**Source:** `scrape.py:315-321`, `scrape.py:351-358`
**Apply to:** All service functions in `_populate.py`, `_refresh.py`, `_query.py`, `_cache.py`
```python
def run_scraper(
    pages: list[MonthPage],
    *,
    out_dir: str = OUT_DIR,
    session=None,
    between_pages_delay: float = BETWEEN_PAGES_DELAY,
    retry_delay: float = RETRY_DELAY,
) -> ScrapeResult:
```

### Error handling: sys.exit(1) on invalid CLI input
**Source:** `scrape.py:415-427`
**Apply to:** `cli.py` main(), all subcommand handlers
```python
try:
    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
except ValueError as exc:
    logger.error("Invalid date format: %s", exc)
    sys.exit(1)

if start > end:
    logger.error("Start date (%s) is after end date (%s)", start, end)
    sys.exit(1)
```

### Error handling: warn and skip bad JSON, don't raise
**Source:** `pipeline.py:43-48`
**Apply to:** `_cache.py` manifest read, `_populate.py` raw JSON loading
```python
try:
    days = json.load(f)
    if isinstance(days, list):
        yield p, days
except json.JSONDecodeError:
    print(f"[warn] bad JSON: {p}")
```

### Test class naming and structure
**Source:** `tests/test_scrape.py:34`, `tests/test_pipeline.py:11,78`
**Apply to:** All new test files
```python
class PopulateTests(unittest.TestCase):      # PascalCase ending in Tests
    def test_<behavior_under_test>(self):    # snake_case, descriptive
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            ...
```

### patch.object for internal module dependencies
**Source:** `tests/test_pipeline.py:35,69-71`, `tests/test_scrape.py:101,133`
**Apply to:** All new test files
```python
with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
    with patch.object(pipeline, "IN_DIR", str(in_dir)):
        pipeline.run_pipeline(out_parquet=str(out_path))
```

### if __name__ == "__main__" guard
**Source:** `scrape.py:441-442`, `pipeline.py:280-281`
**Apply to:** `cli.py` only (the package entry point); internal modules do not need it
```python
if __name__ == "__main__":
    main()
```

---

## QUAL Fix Summary (Exact Line Pointers)

| Bug | Location | Fix |
|-----|----------|-----|
| QUAL-01: copy-pasted dedup block | `pipeline.py:117-123` and `pipeline.py:214-220` | Extract `_deduplicate_rows(rows)` helper; call from both sites |
| QUAL-02: `--in-dir` no-op | `pipeline.py:202` (no `in_dir` param) and `pipeline.py:277` (not forwarded) | Add `in_dir` keyword param to `run_pipeline()`; forward `args.in_dir` in `main()` |
| QUAL-03: empty JSON written on failure | `scrape.py:379-387` | Guard `open(out_path, "w")` inside `if days:` block; skip write on empty result |
| QUAL-04: stale hardcoded date defaults | `scrape.py:36-37` (`START_DATE`, `END_DATE`) | Remove hardcoded 2021 defaults; in `_refresh.py` default range = gap-fill from last cached month to today |

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `pyproject.toml` | config | N/A | No build system exists yet; project has only `requirements.txt` |
| `src/forexfactory/_cache.py` | utility | file-I/O + CRUD | No equivalent cache-management module exists; built from scattered file I/O patterns across both scripts |

---

## Metadata

**Analog search scope:** `scrape.py`, `pipeline.py`, `tests/test_scrape.py`, `tests/test_pipeline.py`, `tests/test_docs.py`
**Files scanned:** 5 source files + 5 planning documents
**Pattern extraction date:** 2026-06-08
