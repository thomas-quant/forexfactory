# Phase 2: Full Analytical Schema + Source Spike — Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 12 (8 modified, 1 new module, 3 extended test files + 1 new fixture directory)
**Analogs found:** 12 / 12 (all files have at least a role-match analog in the codebase)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/forexfactory/_pipeline.py` | utility/transform | batch/transform | `src/forexfactory/_pipeline.py` (self) | exact — in-place widening |
| `src/forexfactory/_populate.py` | service/ETL | batch | `src/forexfactory/_populate.py` (self) | exact — targeted edits |
| `src/forexfactory/_query.py` | service/query | request-response | `src/forexfactory/_query.py` (self) | exact — targeted edits |
| `src/forexfactory/cli.py` | CLI/dispatcher | request-response | `src/forexfactory/cli.py` (self) | exact — additive only |
| `src/forexfactory/_cache.py` | utility/filesystem | file-I/O | `src/forexfactory/_cache.py` (self) | exact — constant addition |
| `src/forexfactory/__init__.py` | public API/facade | request-response | `src/forexfactory/__init__.py` (self) | exact — signature mirroring |
| `src/forexfactory/_api.py` (NEW) | service/network | request-response | `src/forexfactory/_scrape.py` | role-match (same curl_cffi + session pattern) |
| `tests/test_pipeline.py` | test | transform | `tests/test_pipeline.py` (self) | exact — new classes appended |
| `tests/test_scrape.py` | test | file-I/O + parser | `tests/test_scrape.py` (self) | exact — new class appended |
| `tests/test_query.py` | test | request-response | `tests/test_query.py` (self) | exact — new class appended |
| `tests/test_populate.py` | test | batch | `tests/test_populate.py` (self) | exact — new tests appended |
| `tests/fixtures/*.html` (NEW) | test fixture | file-I/O | inline HTML in `tests/test_scrape.py` | partial — real HTML replaces synthetic strings |

---

## Pattern Assignments

### `src/forexfactory/_pipeline.py` — add `_NUMERIC_RE`, `_SUFFIX_MAP`, `_parse_value()`, widen `flatten_events()`

**Analog:** `src/forexfactory/_pipeline.py` (self) + private-helper style from `src/forexfactory/_scrape.py`

**New module-level constants pattern** — copy placement after `# ========= CONFIG =========` block (lines 22–31 of `_pipeline.py`):
```python
# ========= CONFIG =========
IN_DIR = "out"
PARSED_CSV = "ff_usd_high_holiday.csv"
...
PARQUET_COMPRESSION_LEVEL = 3
# ==========================
```
Add `PHASE2_COLUMNS` constant here (or just below the config block). It must be importable by `_populate.py` and `_query.py` to avoid the three-way staleness pitfall.

**Private helper naming convention** — copy from `_pipeline.py` lines 101–113 (`_deduplicate_rows`) and `_scrape.py` lines 88–115 (`_find_matching_brace`):
- No docstring on private helpers; leading underscore; called only by one or two public functions.
- Module-level compiled regex constant in `UPPER_SNAKE_CASE`:

```python
# _scrape.py lines 148–150 (exact pattern to replicate for _parse_value's regex)
def _quote_js_object_keys(value: str) -> str:
    """Quote simple JavaScript object keys so JSON can parse them."""
    return re.sub(r'([,{]\s*)([A-Za-z_$][\w$]*)(\s*:)', r'\1"\2"\3', value)
```

**`_parse_value` placement** — insert above `flatten_events()` (currently line 81). Module-level constants `_NUMERIC_RE` and `_SUFFIX_MAP` go in the CONFIG section or just below it. Return type annotation is `float` (since `float('nan')` is a float):
```python
_NUMERIC_RE = re.compile(r'^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$')
_SUFFIX_MAP = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12, '%': 1e-2}

def _parse_value(s: str) -> float:
    """Parse a FF value string to float, returning float('nan') for unparseable input."""
    ...
```

**`flatten_events()` current yield** (lines 88–98 of `_pipeline.py`) — the 7-field dict to replace:
```python
yield {
    "date": date_iso,
    "time_utc": time_utc,
    "currency": currency,
    "impact": impact,
    "title": title,
    "id": ev.get("id", ""),   # NOTE: Phase 2 changes "" fallback to None
    "leaked": ev.get("leaked"),
}
```
Phase 2 replaces this yield with the 19-field dict from RESEARCH.md Pattern 2. The `id` fallback changes from `""` to `None` to enable clean `Int64` dtype casting downstream.

**`title` field source order** (line 87) — keep existing fallback chain; do NOT use `soloTitle` as Phase 2 drops it (DATA-04):
```python
# Current (line 87) — trim soloTitle since it is in the DATA-04 drop list
title = ev.get("prefixedName") or ev.get("name") or ""
```

---

### `src/forexfactory/_populate.py` — remove `should_keep_row` call, widen empty-df fallback, add `force=` kwarg

**Analog:** `src/forexfactory/_populate.py` (self)

**`should_keep_row` call to remove** (lines 62–63):
```python
# DROP these two lines from build_month_parquet() — D-09
# Drop 'speaks' events
rows = [r for r in rows if _pipeline.should_keep_row(r)]
```
The `should_keep_row` function definition in `_pipeline.py` stays intact (legacy `run_pipeline()` path still calls it, per RESEARCH.md Pitfall 6).

**Empty-df fallback to update** (lines 66–68):
```python
# Current — replace the column list with PHASE2_COLUMNS (imported from _pipeline)
df = pd.DataFrame(rows) if rows else pd.DataFrame(
    columns=["datetime_utc", "currency", "impact", "title", "id", "leaked"]
)
```
Replace with `pd.DataFrame(columns=_pipeline.PHASE2_COLUMNS)`.

**`Int64` cast to insert** — add after `pd.DataFrame(rows)` construction and before `write_parquet` call, following the `df.drop(columns=...)` block (around line 82):
```python
# After df = pd.DataFrame(rows) and before write_parquet:
# Pattern: _populate.py already does post-construction column manipulation at lines 69-83
INT_NULLABLE_COLS = ["id", "ebaseId", "actualBetterWorse", "revisionBetterWorse"]
for col in INT_NULLABLE_COLS:
    if col in df.columns:
        df[col] = df[col].astype("Int64")
```

**`force=False` kwarg pattern** — copy keyword-only arg convention from `run_populate()` signature (lines 95–103):
```python
def run_populate(
    *,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    raw_dir: str = RAW_INPUT_DIR,
    cache_dir: Path | None = None,
) -> dict:
```
Add `force: bool = False` after `cache_dir`. The skip-check to wrap (lines 192–196):
```python
# Current skip-check (lines 192-196) — wrap the whole block in if not force:
cached_entry = manifest.get("months", {}).get(month_key)
if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
    logger.info("[%d/%d] Skip (cached at scope): %s", i, total, month_key)
    skipped_count += 1
    continue
```

---

### `src/forexfactory/_query.py` — widen `_DATA01_COLUMNS`, add `include_no_data` kwarg and default filter

**Analog:** `src/forexfactory/_query.py` (self)

**`_DATA01_COLUMNS` to replace** (line 30):
```python
# Current — replace with PHASE2_COLUMNS imported from _pipeline
_DATA01_COLUMNS = ["datetime_utc", "currency", "impact", "title", "id", "leaked"]
```
Import `PHASE2_COLUMNS` from `_pipeline` and rename or alias it for the empty-df fallback (line 175):
```python
# Current empty-df fallback (line 175)
df = pd.DataFrame(columns=_DATA01_COLUMNS)
# Replace with:
df = pd.DataFrame(columns=_pipeline.PHASE2_COLUMNS)
```

**`include_no_data=False` kwarg pattern** — add to `run_query()` signature (lines 110–117), following the exact keyword-only arg style used throughout the file:
```python
def run_query(
    *,
    currencies: list | None = None,
    impacts: list | None = None,
    start: str | None = None,
    end: str | None = None,
    cache_dir: Path | None = None,
) -> Path:
```
Add `include_no_data: bool = False` before `cache_dir`. The filter insert point is after the `pd.concat` / empty-df branch (around line 173) and before the currency+impact filter (line 178):
```python
# Current currency+impact filter (line 178):
df = df[df["currency"].isin(currencies) & df["impact"].isin(impacts)]
# Insert the include_no_data filter BEFORE the above line:
if not include_no_data:
    if "hasDataValues" in df.columns:
        df = df[df["hasDataValues"] | (df["impact"] == "holiday")]
    else:
        logger.warning("[query] hasDataValues column absent — stale cache; run populate --force")
```
The `"hasDataValues" in df.columns` guard is required (RESEARCH.md Pitfall 4) — queries against pre-Phase-2 parquets must degrade gracefully.

---

### `src/forexfactory/cli.py` — add `--include-no-data` to query subparser, add `--force` to populate subparser

**Analog:** `src/forexfactory/cli.py` (self)

**`store_true` flag pattern** — there is no existing `store_true` flag in the file yet; copy argparse convention from an adjacent bool-like flag. The closest pattern is the `--raw-dir` argument (lines 99–105) for placement. The `store_true` form is:
```python
# Insert in the query subparser block (after --cache-dir, around line 177):
qry.add_argument(
    "--include-no-data",
    action="store_true",
    default=False,
    help="Include speech/no-data events (default: data-bearing + holidays only) [D-09]",
)
```

**Flag-to-kwarg mirroring at dispatch** (lines 223–239) — copy the existing pattern where `args.currency` (None → service default) is passed directly:
```python
# Current query dispatch (lines 223-239):
path = _query.run_query(
    currencies=args.currency,
    impacts=args.impact,
    start=args.start,
    end=args.end,
    cache_dir=cache_dir,
)
# Add:
    include_no_data=args.include_no_data,
```

**`--force` flag for populate subparser** — insert after `--raw-dir` argument (lines 99–105):
```python
pop.add_argument(
    "--force",
    action="store_true",
    default=False,
    help="Force rebuild all months even if already cached [Phase-2 migration]",
)
```
Dispatch at lines 207–221 — add `force=args.force` to the `run_populate(...)` call.

---

### `src/forexfactory/_cache.py` — add `SCHEMA_VERSION` constant

**Analog:** `src/forexfactory/_cache.py` (self)

**CONFIG section** (lines 22–25):
```python
# ====== CONFIG ======
DEFAULT_CACHE_DIR: Path = Path.home() / ".cache" / "forexfactory"
CACHE_DIR_ENV: str = "FOREXFACTORY_CACHE_DIR"
# ====================
```
Add `SCHEMA_VERSION: str = "2"` inside this block. Used by `run_populate()` after a force rebuild to stamp `manifest["schema_version"] = _cache.SCHEMA_VERSION`.

---

### `src/forexfactory/__init__.py` — add `include_no_data=False` kwarg to `get()`

**Analog:** `src/forexfactory/__init__.py` (self)

**Current `get()` signature** (lines 18–25):
```python
def get(
    *,
    currencies=None,
    impacts=None,
    start=None,
    end=None,
    cache_dir=None,
) -> Path:
```
Add `include_no_data=False` after `end=None`. Pass through to `_query.run_query()` (line 32):
```python
return _query.run_query(
    currencies=currencies,
    impacts=impacts,
    start=start,
    end=end,
    cache_dir=cache_dir,
    include_no_data=include_no_data,
)
```
The lazy-import pattern (line 31 `from . import _query`) stays unchanged.

---

### `src/forexfactory/_api.py` (NEW) — spike fetcher for `apply-settings` POST endpoint

**Analog:** `src/forexfactory/_scrape.py`

**Module structure pattern** (copy from `_scrape.py` lines 1–55):
- Module docstring with purpose + usage example
- `try/except ImportError` guard for `curl_cffi` (lines 23–26):
```python
try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover
    curl_requests = None
```
- `logger = logging.getLogger(__name__)` after imports (line 28)
- CONFIG section with `UPPER_SNAKE_CASE` constants (lines 31–53):
```python
# ====== CONFIG ======
APPLY_SETTINGS_URL = "https://www.forexfactory.com/calendar/apply-settings/100000"
IMPERSONATE = "chrome"           # same as _scrape.IMPERSONATE
REQUEST_TIMEOUT = 30             # same as _scrape.REQUEST_TIMEOUT
# ====================
```

**`build_session()` — reuse, do not duplicate** (lines 301–305 of `_scrape.py`):
```python
def build_session():
    """Create a curl_cffi session."""
    if curl_requests is None:
        raise RuntimeError("curl_cffi is required. Install it with: pip install curl_cffi")
    return curl_requests.Session()
```
`_api.py` should import and reuse `_scrape.build_session()` rather than define its own.

**`scrape_month()` as the template** (lines 308–340 of `_scrape.py`):
```python
def scrape_month(
    session,
    page: MonthPage,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    retry_delay: float = RETRY_DELAY,
) -> list:
    """Fetch a month page and return extracted days."""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            ...
            response = session.get(
                page.url,
                headers=HEADERS,
                impersonate=IMPERSONATE,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
```
`_api.fetch_month_api()` mirrors this structure with `session.post(...)` instead of `session.get(...)`. Retry loop, `last_error`, `raise_for_status()` all carry over.

**HEADERS constant pattern** (lines 43–53 of `_scrape.py`):
```python
HEADERS = {
    "accept": "text/html,...",
    "accept-language": "en-US,en;q=0.9",
    ...
}
```
`_api.py` will need a separate `API_HEADERS` dict derived from DevTools capture (Content-Type will differ for a POST). The dict-literal style is the same.

---

### `tests/test_pipeline.py` — extend with `ParseValueTests` and `FlattenEventsWidenedTests`

**Analog:** `tests/test_pipeline.py` (self)

**Existing test class pattern** (lines 11–74) — copy `PipelineParquetCompressionTests`:
```python
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import forexfactory._pipeline as pipeline


class PipelineParquetCompressionTests(unittest.TestCase):
    def test_csv_to_parquet_uses_zstd_level_3(self):
        ...
```
New classes follow identical structure. `ParseValueTests` is a pure-function unit test class (no temp dirs needed):
```python
class ParseValueTests(unittest.TestCase):
    """Unit tests for _pipeline._parse_value() — D-02 numeric parsing."""

    def test_percent_becomes_fraction(self):
        self.assertAlmostEqual(pipeline._parse_value("4.3%"), 0.043)

    def test_magnitude_suffix_K(self):
        self.assertAlmostEqual(pipeline._parse_value("-27.4K"), -27400.0)

    def test_empty_string_returns_nan(self):
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("")))

    def test_unparseable_returns_nan(self):
        import math
        self.assertTrue(math.isnan(pipeline._parse_value("<0.10%")))
        self.assertTrue(math.isnan(pipeline._parse_value("Pass")))
        self.assertTrue(math.isnan(pipeline._parse_value("1.34|2.6")))
```

**`FlattenEventsWidenedTests`** pattern — use inline JSON dict (copy style from `PipelineDedupTests` at lines 147–204 which passes dicts directly, no temp file):
```python
class FlattenEventsWidenedTests(unittest.TestCase):
    """Phase-2 schema fields present in flatten_events output (D-01/DATA-02/03/04)."""

    _EVENT = {
        "currency": "USD", "impactName": "High Impact Expected",
        "prefixedName": "US CPI y/y", "dateline": 1772368200,
        "id": 12345, "leaked": False,
        "forecast": "4.3%", "actual": "4.5%", "previous": "4.1%", "revision": "",
        "actualBetterWorse": 1, "revisionBetterWorse": 0,
        "ebaseId": 999, "country": "US", "hasDataValues": True,
    }

    def _flatten_one(self):
        days = [{"events": [self._EVENT]}]
        return list(pipeline.flatten_events(days))[0]

    def test_forecast_raw_is_verbatim_string(self):
        r = self._flatten_one()
        self.assertEqual(r["forecast_raw"], "4.3%")

    def test_forecast_parsed_is_fraction(self):
        import math
        r = self._flatten_one()
        self.assertAlmostEqual(r["forecast"], 0.043)
```

---

### `tests/test_scrape.py` — extend with `ExtractDaysFixtureTests`

**Analog:** `tests/test_scrape.py` (self)

**Import block to copy** (lines 1–8):
```python
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import forexfactory._scrape as scraper
```
Add `from pathlib import Path` (already present); add no new imports for the fixture class.

**Existing inline-HTML test pattern** (lines 42–57) — shows HTML → `extract_days()` → assertEqual:
```python
def test_extract_days_from_calendar_component_states_selects_most_complete_state(self):
    sparse_days = [{"events": []}]
    rich_days = [...]
    html = f"""
    <script>
      window.calendarComponentStates = {{
        "short": {{"days": {json.dumps(sparse_days)}}},
        "month": {{"days": {json.dumps(rich_days)}}}
      }};
    </script>
    """
    self.assertEqual(scraper.extract_days(html), rich_days)
```
`ExtractDaysFixtureTests` replaces inline HTML with file loads. The fixture load helper:
```python
class ExtractDaysFixtureTests(unittest.TestCase):
    """QUAL-05: Parser regression against real-HTML fixtures. D-10/D-11."""

    def _fixture(self, name: str) -> str:
        return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")
```
`Path(__file__).parent` resolves to the `tests/` directory at test runtime. This is the correct pattern for fixture loading — no `os.path` manipulation needed.

---

### `tests/test_query.py` — extend with `QueryIncludeNoDataTests`

**Analog:** `tests/test_query.py` (self)

**`_setup_cache()` helper pattern** (lines 56–79) — reuse directly; the helper already accepts arbitrary `rows` and `scope`:
```python
def _setup_cache(
    self,
    cache_dir: Path,
    months: list,
    rows_per_month: list,
    scope: dict | None = None,
) -> None:
    """Write per-month parquets + manifest under cache_dir."""
    ...
```

**`_usd_high_row()` helper** (lines 28–36) — extend with a `_speech_row()` helper that has `hasDataValues=False`:
```python
def _speech_row(dt: str = "2026-03-01 09:00:00") -> dict:
    return {
        "datetime_utc": pd.Timestamp(dt, tz="UTC"),
        "currency": "USD",
        "impact": "high",        # speeches can be any impact
        "title": "Fed Chair Powell Speaks",
        "id": "powell-1",
        "leaked": False,
        "hasDataValues": False,
    }
```

**New test class structure** — mirrors `QueryHappyPathTests` (lines 54–220):
```python
class QueryIncludeNoDataTests(unittest.TestCase):
    """D-08/D-09: include_no_data filter — speeches hidden by default, holidays visible."""

    def test_default_hides_speeches(self):
        """hasDataValues=False + non-holiday rows absent from default query result."""
        ...

    def test_include_no_data_surfaces_speeches(self):
        """include_no_data=True returns all rows including speeches."""
        ...

    def test_holiday_visible_by_default(self):
        """impact='holiday' + hasDataValues=False still appears in default result (D-08)."""
        ...
```

---

### `tests/test_populate.py` — extend with no-speaks-filter and `force=True` tests

**Analog:** `tests/test_populate.py` (self)

**`_write_raw()` helper** (lines 20–27) — the standard fixture-writer to reuse:
```python
def _write_raw(self, raw_dir: Path, year: int, month: int, events: list) -> Path:
    """Write a days_YYYY_MM.json fixture to raw_dir and return its path."""
    path = raw_dir / f"days_{year:04d}_{month:02d}.json"
    path.write_text(
        json.dumps([{"events": events}]),
        encoding="utf-8",
    )
    return path
```

**`_usd_high_event()` helper** (lines 29–37) — extend with a `_speaks_event()` helper:
```python
def _speaks_event(self, dateline: int = 1772368200) -> dict:
    return {
        "currency": "USD",
        "impactName": "High Impact Expected",
        "name": "Fed Chair Powell Speaks",
        "dateline": dateline,
        "id": "powell-1",
        "leaked": False,
        "hasDataValues": False,
    }
```

**`force=True` test pattern** — reads parquet before and after; uses same `tempfile.TemporaryDirectory` pattern as `test_writes_per_month_parquet` (lines 49–69):
```python
def test_force_true_overwrites_cached_month(self):
    """force=True re-populates a month that the manifest marks as cached."""
    ...
    # First populate — month is cached
    result1 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
    self.assertEqual(result1["populated"], 1)
    # Second populate without force — should skip
    result2 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir))
    self.assertEqual(result2["skipped"], 1)
    # Third populate with force — should re-populate
    result3 = _populate.run_populate(cache_dir=cache_dir, raw_dir=str(raw_dir), force=True)
    self.assertEqual(result3["populated"], 1)
    self.assertEqual(result3["skipped"], 0)
```

---

### `tests/fixtures/` (NEW) — HTML fixture files for QUAL-05

**Analog:** inline HTML in `tests/test_scrape.py` lines 46–55 (synthetic) + `_write_raw()` in `tests/test_populate.py` lines 20–27 (real file writing pattern)

**Fixture naming convention** — copy `days_YYYY_MM.json` snake_case naming pattern from `_populate.py`:
```
tests/fixtures/
    form1_rich_month.html          # = {...} assignment, data-bearing events
    form2_bracket_assignment.html  # [n]={...} form (may be synthetic fragment)
    no_data_events.html            # speech + holiday events; hasDataValues=False
    empty_month.html               # zero events page
    multi_candidate.html           # multiple state objects for _select_best_days
```

**File load pattern** — `(Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")` (the `_fixture()` helper defined in `ExtractDaysFixtureTests`, described above).

**Trimming convention** — real captured HTML trimmed to a representative slice (1–3 days of events per file). The full calendar page HTML is 200–400 KB; trim to the `<script>` blocks containing `calendarComponentStates` and minimal surrounding HTML to keep the repository lightweight (D-11).

---

## Shared Patterns

### Keyword-Only Function Arguments
**Source:** `src/forexfactory/_populate.py` lines 95–103, `src/forexfactory/_query.py` lines 110–117, `src/forexfactory/_refresh.py` lines 44–54
**Apply to:** All new/modified service function signatures (`run_populate`, `run_query`, `build_month_parquet`, `fetch_month_api`)
```python
# Copy this exact pattern — positional-required params first, then * to start keyword-only:
def run_populate(
    *,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    raw_dir: str = RAW_INPUT_DIR,
    cache_dir: Path | None = None,
    force: bool = False,           # Phase-2 addition
) -> dict:
```

### argparse Flag-to-Kwarg Mirroring (D-12)
**Source:** `src/forexfactory/cli.py` lines 79–91 (flag definition) + lines 207–221 (dispatch)
**Apply to:** `--include-no-data` in query subparser → `include_no_data=args.include_no_data` at dispatch; `--force` in populate subparser → `force=args.force` at dispatch
```python
# Flag definition pattern (lines 79-87):
pop.add_argument(
    "--currency", dest="currency", action="append", metavar="CURRENCY",
    help="Currency to include (repeatable; default: USD) [D-12]",
)
# Dispatch pattern (lines 208-213) — pass directly; None → service applies its own default:
result = _populate.run_populate(
    currencies=args.currency,   # None → service applies D-04 default (USD)
    impacts=args.impact,
    ...
)
```

### Logger Setup
**Source:** `src/forexfactory/_populate.py` line 30, `src/forexfactory/_query.py` line 27, `src/forexfactory/_refresh.py` line 41
**Apply to:** `src/forexfactory/_api.py`
```python
logger = logging.getLogger(__name__)
```
No `logging.basicConfig` in service modules — only `cli.py` configures the root logger (lines 32–36).

### Warn-and-Continue on Bad Data
**Source:** `src/forexfactory/_pipeline.py` line 48 (`print("[warn] bad JSON: {p}")`), `src/forexfactory/_populate.py` lines 179–181 (`logger.warning(...)`), `src/forexfactory/_query.py` lines 161–162 (`logger.warning(...)`)
**Apply to:** `_query.run_query()` stale-cache guard for missing `hasDataValues` column
```python
# Warn pattern (from _populate.py lines 179-181):
logger.warning("[%d/%d] bad JSON in %s — skipping", i, total, raw_path)
empty_count += 1
continue
# Apply same style to stale-cache warning in _query:
logger.warning("[query] hasDataValues column absent — stale cache; run populate --force")
```

### UPPER_SNAKE_CASE Config Constants with Section Delimiter
**Source:** `src/forexfactory/_populate.py` lines 24–28, `src/forexfactory/_scrape.py` lines 31–53, `src/forexfactory/_cache.py` lines 22–25
**Apply to:** All new constants (`PHASE2_COLUMNS`, `SCHEMA_VERSION`, `APPLY_SETTINGS_URL`, `INT_NULLABLE_COLS`)
```python
# ====== CONFIG ======
RAW_INPUT_DIR: str = "out"
DEFAULT_CURRENCIES: list[str] = ["USD"]
DEFAULT_IMPACTS: list[str] = ["high", "holiday"]
# ====================
```

### `float('nan')` for Nullable Float Columns (critical)
**Source:** RESEARCH.md Pattern 1 (verified in-process; no existing codebase analog)
**Apply to:** `_parse_value()` return value on all unparseable inputs
```python
# CORRECT — pandas infers float64 even for all-null columns:
return float('nan')
# WRONG — pandas infers object dtype for all-None columns:
return None
```

### `Int64` for Nullable Integer Columns (critical)
**Source:** RESEARCH.md Pattern 4 (verified in-process; no existing codebase analog)
**Apply to:** `build_month_parquet()` after `pd.DataFrame(rows)` construction
```python
INT_NULLABLE_COLS = ["id", "ebaseId", "actualBetterWorse", "revisionBetterWorse"]
for col in INT_NULLABLE_COLS:
    if col in df.columns:
        df[col] = df[col].astype("Int64")
```

### `WR-02: errors="coerce"` DateTime Pattern
**Source:** `src/forexfactory/_populate.py` lines 73–80, `src/forexfactory/_pipeline.py` lines 186–195
**Apply to:** `build_month_parquet()` — unchanged, carry forward as-is
```python
df["datetime_utc"] = pd.to_datetime(
    df["date"] + " " + df["time_utc"], utc=True, errors="coerce"
)
null_count = int(df["datetime_utc"].isna().sum())
if null_count:
    logger.warning(
        "[populate] %d row(s) have no parseable dateline — stored as NaT",
        null_count,
    )
```

---

## No Analog Found

All Phase-2 files have analogs. The following are genuinely new patterns not yet in the codebase:

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `_parse_value()` inside `_pipeline.py` | private helper | transform | No numeric-string-to-float helper exists; regex pattern is new |
| `_api.py` POST endpoint | service/network | request-response | All existing network code uses `session.get()`; `session.post()` is new |
| `tests/fixtures/*.html` | test fixture | file-I/O | `tests/fixtures/` directory exists but is empty; file-based fixture loading pattern is new to this project |
| `include_no_data` DataFrame filter | query logic | transform | No boolean column filter exists in `_query.py`; only currency/impact string filters |

For these, use the RESEARCH.md pattern excerpts directly (Patterns 1–8 in that document are all verified against real data and can be copied verbatim).

---

## Metadata

**Analog search scope:** `src/forexfactory/`, `tests/`
**Files read:** 10 source files + 5 test files
**Pattern extraction date:** 2026-06-08
**All analogs confirmed by direct file read** — no inferred patterns.

---

## PATTERN MAPPING COMPLETE
