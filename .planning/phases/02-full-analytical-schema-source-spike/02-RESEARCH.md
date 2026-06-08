# Phase 2: Full Analytical Schema + Source Spike — Research

**Researched:** 2026-06-08
**Domain:** Python ETL schema widening, pyarrow/pandas dtypes, numeric string parsing, fixture-based parser testing, AJAX endpoint spike
**Confidence:** HIGH (schema/parsing/dtypes verified in-process; SRC-01 spike by definition requires live investigation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Full analytical column set.**
Each event row carries, in addition to the Phase-1 core (`datetime_utc`, `currency`, `impact`, `title`, `id`, `leaked`):
- **Raw value strings** (verbatim from FF): `forecast_raw`, `actual_raw`, `previous_raw`, `revision_raw`.
- **Parsed numerics** (float or null): `forecast`, `actual`, `previous`, `revision`.
- **Surprise flags:** `actualBetterWorse`, `revisionBetterWorse`.
- **Identity:** `ebaseId`, `country`.
- **Data presence:** `hasDataValues`.
- FF UI/internal fields (`checker`, `releaser`, `siteId`, `show*`/`enable*`, `notice`, naming duplicates, etc.) are **dropped** (DATA-04).
- Exact column names/ordering/dtypes are Claude's discretion (keep `datetime_utc` first; SC1/SC2 names above are the contract).

**D-02: Numeric parsing = faithful, percent-as-fraction.**
- Expand magnitude suffixes: `'1.5K'`→1500, `'2.3M'`→2300000, `'113B'`→113000000000, trailing `T`→×1e12.
- **Percent → decimal fraction:** `'4.3%'`→0.043.
- Sign preserved (`'-0.2'`→-0.2); plain numbers pass through.
- Unparseable/empty (`''`, `'<0.1%'`, `'~'`, `'Tentative'`, etc.) → **null (NaN)**. Never raise.
- A value with **no `%`** is taken at face value.

**D-03: No derived surprise column.** Store raw + parsed + FF flags only. `actualBetterWorse`/`revisionBetterWorse` carried as their **raw integer** value.

**D-04: Prototype & compare, adopt-if-it-wins.** Build a minimal fetcher against the `apply-settings` endpoint, diff output vs HTML parser. If it reliably returns full structured data, wire in as PRIMARY with HTML-parse as fallback (SRC-02). Otherwise keep HTML primary, document why. SC5 satisfied either way.

**D-05: Spike runs independent of schema extraction.** Schema extraction is driven by on-disk raw JSON (no network). Event-dict boundary is source-agnostic. Swapping fetcher does not redo schema work.

**D-06: Adopt-bar = ALL FOUR must-haves.** (1) No field regression, (2) arbitrary historical months back to 2010, (3) works via `curl_cffi` no auth, (4) stable at polite rate.

**D-07: Live reconnaissance is part of the spike.** Load live FF calendar in browser/devtools tool; capture the `apply-settings` POST — full URL, method, headers, cookies, body, response shape, and the JS that assembles `window.calendarComponentStates`. Recon is spike-only scaffolding — MUST NOT ship in the package. Synergy: save the recon page as the realistic HTML fixture for QUAL-05 (D-11).

**D-08: Default query returns data-bearing events + holidays.** All events retained in cache; query hides no-data ones by default except holidays. Practical default predicate: `hasDataValues == True OR impact == 'holiday'`.

**D-09: `--include-no-data` toggle.** `store_true` CLI flag + matching `include_no_data=False` library kwarg on `get()`. The old hard `'speaks'` sanitize step is **removed** — speeches retained in cache, filtered out by default at query time.

**D-10: Small fixture matrix (~3–5).** Cover both assignment forms, a rich data-values month, a no-data case (speech/holiday), an empty/no-events month, and the multi-candidate `_select_best_days` case.

**D-11: Real captured HTML + targeted field assertions.** Capture real FF pages (including from D-07 spike recon), trim to representative day slices, assert on meaningful fields: `currency`, `impact`, `title`, `id`, parsed `forecast`/`actual`/`previous`/`revision`, `hasDataValues`, `leaked`. Hand-crafted fragments are acceptable only to supplement hard-to-capture edge cases (e.g., the `[n]={...}` branch).

**JSON-drop exit condition (Phase-1 D-03, carried forward):** Phase 2 MUST extract every field of lasting value into parquet, re-populate the existing cache to the wider schema, then drop the raw JSON staging layer. After that, obtaining a new field requires a re-scrape.

### Claude's Discretion
- Exact new parquet column names, ordering, and dtypes (SC1/SC2 names are the contract; `datetime_utc` stays first).
- Where the parsing helper lives and its implementation.
- Whether `actualBetterWorse`/`revisionBetterWorse` also get a categorical mapping (raw int is the floor).
- How the cache is rebuilt (force-flag vs wipe-and-rebuild; whether to bump a schema version).
- The spike fetcher module location and the recon tooling choice.
- Fixture file layout, naming, and aggressiveness of page trimming.

### Deferred Ideas (OUT OF SCOPE)
- Computed surprise/expected-vs-surprise metrics (e.g. `actual − forecast`, z-scores).
- Categorical encoding of `actualBetterWorse`/`revisionBetterWorse` (optional extension).
- Adopting `apply-settings` as primary only if it clears the D-06 bar; if promising-but-not-ready, full adoption is a follow-up.
- Phase 3 items: CACHE-03, CACHE-05, CACHE-06.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-02 | Each event carries `forecast`, `actual`, `previous`, `revision`, `hasDataValues` as raw strings + parsed numerics | Verified: all fields present in every raw JSON event; flatten_events() widening is the implementation path |
| DATA-03 | Each event carries `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country` | Verified: all fields present; int types confirmed; value range 0/1/2 for flags |
| DATA-04 | FF UI/internal fields dropped (`checker`, `releaser`, `siteId`, `show*`/`enable*`, `notice`, duplicates) | Verified: complete drop list documented; 35 fields drop, 17 analytical fields kept |
| DATA-05 | Speech/holiday/no-data events retained in cache; dropping becomes optional query-time filter | Implementation path: remove `should_keep_row` from `_populate.build_month_parquet()`; add `include_no_data` kwarg to `run_query()` |
| QUAL-05 | Fixture-based regression tests cover `calendarComponentStates` parser against realistic saved HTML | Implementation path: `tests/fixtures/` directory exists (empty); test class pattern established in existing suite |
| SRC-01 | FF `apply-settings` endpoint investigated; adopted as primary if it clears D-06 bar | Requires live spike — cannot be pre-researched; research documents the spike approach and decision criteria |
</phase_requirements>

---

## Summary

Phase 2 has three independent threads that share no blocking dependency: schema widening (DATA-02/03/04 + cache rebuild), query filter change (DATA-05), and the SRC-01 spike + QUAL-05 fixture tests. The schema work is entirely driven by the 195 on-disk raw JSON files with no network — confirmed that every target field (`forecast`, `actual`, `previous`, `revision`, `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`) is present in all events in the raw JSON, all with the expected types.

The numeric parsing helper is a solved problem: a single regex `^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$` correctly handles all real value string patterns found in the 195-month dataset (K/M/B/T suffixes, percent, signed values, empty string, and all unparseable edge cases including `'<0.10%'`, `'Pass'`, `'Yes'`, and pipe-separated bond auction values like `'1.34|2.6'`). The critical dtype decision is to return `float('nan')` (not Python `None`) from the helper, so pandas infers `float64` rather than `object` for all-null columns.

The SRC-01 spike is the phase's only genuine unknown — it requires live browser DevTools reconnaissance against the live FF site, a `curl_cffi` POST prototype, and a documented comparison against the HTML parser. The D-07/QUAL-05 synergy note is load-bearing: the HTML page captured during spike recon is the highest-quality fixture source for QUAL-05, so those two tracks should run together.

**Primary recommendation:** Sequence the work in three waves: (1) widen `flatten_events()` + numeric parsing helper + dtype enforcement + update `_populate`/`_query`/`cli` + force-rebuild cache; (2) QUAL-05 fixtures and parser tests, ideally using recon HTML from the spike; (3) SRC-01 spike prototype and documented decision.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Numeric string parsing | `_pipeline._parse_value()` | — | Single helper called inside `flatten_events()`; no duplication |
| Schema widening | `_pipeline.flatten_events()` | `_populate.build_month_parquet()` (empty-df fallback) | flatten_events is the single ETL choke point; _populate controls filtering |
| `should_keep_row` removal | `_populate.build_month_parquet()` | — | Remove the call there; `_pipeline.run_pipeline()` legacy path left unchanged |
| Cache rebuild (force) | `_populate.run_populate(force=True)` | `_cache.py` schema_version stamp | Force kwarg bypasses manifest skip check; schema_version enables future detection |
| Query default filter | `_query.run_query(include_no_data=False)` | `forexfactory.get()`, `cli.query` | Filter lives in query layer; cache retains everything |
| `--include-no-data` CLI flag | `cli.query` subparser | `forexfactory.get()` kwarg | Mirrors D-12 flag↔kwarg convention |
| QUAL-05 fixture tests | `tests/test_scrape.py` extended | `tests/fixtures/*.html` | Extends existing test class; fixtures loaded by path |
| SRC-01 spike fetcher | New `_api.py` (throwaway or adopted) | `_refresh.run_refresh()` if adopted | Isolated module; slots into `_refresh.py` at D-04 adoption point |
| SRC-01 recon tooling | Playwright or manual browser devtools | — | Spike-only, not shipped; output = captured HTTP transaction |

---

## Standard Stack

### Core (existing — all confirmed present, no new packages)

| Library | Version on Host | Purpose | Notes |
|---------|-----------------|---------|-------|
| Python | 3.12.3 | All source code | No change |
| `pandas` | 2.1.4 | DataFrame construction, parquet I/O, dtype enforcement | `pd.to_numeric(errors='coerce')` as fallback dtype normalizer |
| `pyarrow` | 23.0.1 | Parquet write engine (zstd level 3) | Handles nullable float64 and Int64 natively |
| `curl_cffi` | ≥0.13.0 | Chrome TLS impersonation for SRC-01 spike fetcher | Session.post() for the `apply-settings` endpoint |
| `pytest` | existing | Test runner for QUAL-05 fixture tests | `unittest.TestCase` with pytest runner (existing pattern) |
| `re` (stdlib) | — | Numeric parsing regex | Single compiled pattern; no third-party parser |

[VERIFIED: pyarrow version confirmed `pa.__version__ == '23.0.1'` on this machine]
[VERIFIED: pandas version confirmed `pd.__version__ == '2.1.4'` on this machine]

### No New Packages

Phase 2 introduces no new pip dependencies. All required functionality is covered by the existing stack:
- Numeric parsing: stdlib `re`
- Schema enforcement: `pandas` type system + `pyarrow`
- Fixture loading: stdlib `pathlib`
- Spike recon: Playwright (if chosen) is spike-only throwaway — not added to `pyproject.toml`

**Package Legitimacy Audit:** N/A — no new packages introduced in this phase.

---

## Architecture Patterns

### System Architecture Diagram

```
Raw JSON (out/days_YYYY_MM.json, 195 months)
        |
        v  (no network; zero HTTP)
_pipeline.flatten_events()          <-- Phase-2 change: yields 19 fields not 7
        |  - ev.get("forecast") -> forecast_raw (verbatim string)
        |  - _parse_value(forecast_raw) -> forecast (float | NaN)
        |  - ev.get("actualBetterWorse") -> actualBetterWorse (int)
        |  - ev.get("ebaseId") -> ebaseId (int)
        |  - ev.get("hasDataValues") -> hasDataValues (bool)
        |  - [35 UI/internal fields silently dropped]
        v
_populate.build_month_parquet()     <-- Phase-2 change: removes should_keep_row call
        |  - filter by currency/impact
        |  - _deduplicate_rows (unchanged)
        |  - [NO should_keep_row -- speeches now kept]
        |  - DataFrame with explicit dtypes + write_parquet (zstd/3)
        v
~/.cache/forexfactory/YYYY-MM.parquet  (wider schema, ~19 columns)
        |
        v  (query time)
_query.run_query(include_no_data=False)   <-- Phase-2 change: adds filter
        |  - if not include_no_data:
        |      df = df[(df.hasDataValues) | (df.impact == 'holiday')]
        v
~/.cache/forexfactory/queries/result.parquet

--- SRC-01 Spike (parallel, independent) ---

Browser DevTools recon
        |  capture: POST /calendar/apply-settings/100000?navigation=1
        |           headers, cookies, body, response JSON shape
        v
_api.py (throwaway or adopted)   <-- spike-only if rejected; wired into _refresh if adopted
        |  session.post(url, params=..., data=..., impersonate="chrome")
        |  compare field set vs HTML parse for 3-5 months
        v
Decision: adopt (slot into _refresh.run_refresh) or reject (document in PROJECT.md)
```

### Recommended Project Structure (additions only)

```
src/forexfactory/
├── _pipeline.py     # add _parse_value(), widen flatten_events()
├── _populate.py     # remove should_keep_row call, update empty-df columns, add force= kwarg
├── _query.py        # add include_no_data kwarg + default filter, update _DATA01_COLUMNS
├── _cache.py        # add SCHEMA_VERSION constant, stamp manifest on rebuild
├── _refresh.py      # unchanged unless SRC-01 adopted (then: slot in _api fetcher)
├── cli.py           # add --include-no-data to query subparser
├── __init__.py      # add include_no_data= kwarg to get()
└── _api.py          # NEW (spike only): apply-settings POST fetcher; keep if adopted
tests/
├── test_scrape.py   # extend with ExtractDaysFixtureTests class
├── test_pipeline.py # extend with parse_value tests + widen_schema tests
├── test_query.py    # extend with include_no_data filter tests
├── test_populate.py # extend with no-should_keep_row + force= tests
└── fixtures/
    ├── form1_rich_month.html         # = {...} assignment, data-bearing month
    ├── form2_bracket_assignment.html # [n]={...} assignment (may be synthetic fragment)
    ├── no_data_events.html           # speech + holiday month
    ├── empty_month.html              # zero events
    └── multi_candidate.html          # multiple state objects; _select_best_days chooses best
```

### Pattern 1: Numeric Parsing Helper

**What:** Single private function in `_pipeline.py` using one compiled regex to parse FF value strings to float | float('nan'). Returns `float('nan')` on any unparseable input.

**Why `float('nan')` not `None`:** When pandas builds a DataFrame from a list of dicts and ALL values in a column are `None`, the column gets `dtype('O')` (object) instead of `float64`. Using `float('nan')` guarantees `float64` inference, which is the correct type for nullable float parquet columns. Verified by in-process test.

**When to use:** Called inside `flatten_events()` for each of the four raw value fields immediately after extracting the raw string.

```python
# Source: in-process verification against 195 months of real FF data
import re

_NUMERIC_RE = re.compile(r'^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$')
_SUFFIX_MAP = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12, '%': 1e-2}

def _parse_value(s: str) -> float:
    """Parse a FF value string to float, returning float('nan') for unparseable input.

    Magnitude suffixes: K=1e3, M=1e6, B=1e9, T=1e12. Percent divides by 100.
    Pipe-separated values (bond auctions), angle-bracket values (<0.10%),
    non-numeric strings ('Pass', 'Yes'), and empty strings all become NaN.
    """
    if not s or not s.strip():
        return float('nan')
    s = s.strip()
    m = _NUMERIC_RE.match(s)
    if not m:
        return float('nan')
    num = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix:
        num *= _SUFFIX_MAP[suffix]
    return num
```

**Verified against all real edge cases found in 195-month dataset:**
- `'4.3%'` → 0.043 [VERIFIED: in-process test]
- `'-10.7%'` → -0.107 [VERIFIED]
- `'-27.4K'` → -27400.0 [VERIFIED]
- `'8.79M'` → 8790000.0 [VERIFIED]
- `'2.0B'` → 2000000000.0 [VERIFIED]
- `'1.89T'` → 1890000000000.0 [VERIFIED]
- `'-0.41T'` → -410000000000.0 [VERIFIED]
- `'50.8'` → 50.8 [VERIFIED]
- `''` → NaN [VERIFIED]
- `'<0.10%'` → NaN [VERIFIED] (angle bracket prefix; confirmed in real data)
- `'<0.25%'` → NaN [VERIFIED] (same pattern)
- `'Pass'` → NaN [VERIFIED] (Fed Chair Nomination Vote, Greek Gov Debt Crisis Vote)
- `'Yes'` → NaN [VERIFIED] (Irish Stability Treaty Vote)
- `'1.34|2.6'` → NaN [VERIFIED] (bond auction pipe-separated yield|bid-to-cover format)

### Pattern 2: Widened `flatten_events()`

**What:** Replace the 7-field yield with a 19-field yield. Add four raw string fields and their four parsed-float counterparts; add `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`.

**When to use:** This is the single ETL choke point. All downstream consumers (populate, legacy run_pipeline) call this function.

```python
# Source: verified against out/days_2024_01.json field inventory
def flatten_events(days, src_path=None):
    """Flatten nested days/events structure into individual event dicts.

    Phase 2: yields 19 fields including raw value strings, parsed numerics,
    surprise flags, identity fields, and hasDataValues. FF UI/internal fields
    (checker, releaser, siteId, show*/enable*, notice, etc.) are dropped.
    """
    for d in days:
        for ev in d.get("events", []):
            currency = (ev.get("currency") or "").upper()
            impact = norm_impact(ev.get("impactName") or ev.get("impactTitle") or "")
            title = ev.get("prefixedName") or ev.get("name") or ""
            dateline = ev.get("dateline")
            date_iso, time_utc = to_iso(dateline)

            # Raw value strings (verbatim from FF — D-01)
            forecast_raw = ev.get("forecast") or ""
            actual_raw = ev.get("actual") or ""
            previous_raw = ev.get("previous") or ""
            revision_raw = ev.get("revision") or ""

            yield {
                "date": date_iso,
                "time_utc": time_utc,
                "currency": currency,
                "impact": impact,
                "title": title,
                "id": ev.get("id"),
                "leaked": ev.get("leaked"),
                # Phase 2 analytical schema (D-01):
                "forecast_raw": forecast_raw,
                "actual_raw": actual_raw,
                "previous_raw": previous_raw,
                "revision_raw": revision_raw,
                "forecast": _parse_value(forecast_raw),
                "actual": _parse_value(actual_raw),
                "previous": _parse_value(previous_raw),
                "revision": _parse_value(revision_raw),
                "actualBetterWorse": ev.get("actualBetterWorse"),
                "revisionBetterWorse": ev.get("revisionBetterWorse"),
                "ebaseId": ev.get("ebaseId"),
                "country": ev.get("country") or "",
                "hasDataValues": ev.get("hasDataValues", False),
            }
```

### Pattern 3: Empty-DataFrame Fallback (in `_populate.build_month_parquet()`)

The current hard-coded column list must expand to the full Phase-2 schema. The empty-df path is hit when `rows` is empty (month has zero events after filter). Failing to update it means the empty-df will be missing the new columns, and `pd.concat` across months will produce NaN columns for months where the fallback triggered.

```python
# Phase-2 replacement for the fallback in _populate.build_month_parquet()
PHASE2_COLUMNS = [
    "datetime_utc", "currency", "impact", "title", "id", "leaked",
    "forecast_raw", "actual_raw", "previous_raw", "revision_raw",
    "forecast", "actual", "previous", "revision",
    "actualBetterWorse", "revisionBetterWorse",
    "ebaseId", "country", "hasDataValues",
]

df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=PHASE2_COLUMNS)
```

### Pattern 4: Nullable Int Column Enforcement

`actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, and `id` are integers in the raw JSON. When rows is non-empty, pandas infers `int64` naturally (confirmed). But `id` currently uses `ev.get("id", "")` which mixes int and empty string. Phase 2 should use `ev.get("id")` (Python `None` for missing) and explicitly cast with `pd.Int64Dtype()` after DataFrame construction to guarantee nullable int parquet columns.

```python
# After pd.DataFrame(rows) and before write_parquet:
INT_NULLABLE_COLS = ["id", "ebaseId", "actualBetterWorse", "revisionBetterWorse"]
for col in INT_NULLABLE_COLS:
    if col in df.columns:
        df[col] = df[col].astype("Int64")
```

Verified: `Int64Dtype()` round-trips cleanly through pyarrow 23.0.1 / zstd parquet. [VERIFIED: in-process test]

### Pattern 5: Query-Time Default Filter

Add `include_no_data=False` kwarg to `run_query()`. When False (default), apply:

```python
# Source: D-08 decision — default predicate is hasDataValues OR holiday
if not include_no_data:
    if "hasDataValues" in df.columns:
        df = df[df["hasDataValues"] | (df["impact"] == "holiday")]
    # If hasDataValues absent (pre-Phase-2 parquet), log warning but don't crash
```

The `if "hasDataValues" in df.columns` guard handles the edge case where a query is run against a cache built before Phase 2 (pre-rebuild parquets won't have the column). Without the guard, querying a stale cache raises `KeyError` rather than giving a clear error.

### Pattern 6: Cache Force-Rebuild

Add `force: bool = False` to `run_populate()`. When `force=True`, skip the manifest skip check and rebuild all months unconditionally. This is the Phase-2 migration tool.

```python
# In _populate.run_populate():
if not force:
    cached_entry = manifest.get("months", {}).get(month_key)
    if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
        skipped_count += 1
        continue
# (if force=True, fall through and rebuild)
```

CLI: add `--force` flag to the `populate` subcommand.

After successful rebuild, the JSON drop tasks are:
1. Remove `out/*.json` (repo root legacy staging): `find out/ -name 'days_*.json' -delete`
2. Remove `~/.cache/forexfactory/raw/` (cache staging): delete the `raw/` subdirectory

### Pattern 7: QUAL-05 Fixture Test Class

Extend `tests/test_scrape.py` with a new `ExtractDaysFixtureTests` class. Load fixtures from `tests/fixtures/` via `Path(__file__).parent / "fixtures" / name`.

```python
# Pattern for fixture-driven regression tests (extends existing unittest.TestCase pattern)
class ExtractDaysFixtureTests(unittest.TestCase):
    """QUAL-05: Parser regression against real-HTML fixtures. D-10/D-11."""

    def _fixture(self, name: str) -> str:
        return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")

    def test_form1_whole_object_assignment_rich_month(self):
        """= {...} form; month with forecast/actual/previous/revision values."""
        html = self._fixture("form1_rich_month.html")
        days = scraper.extract_days(html)
        self.assertGreater(len(days), 0)
        # Find an event with data values and assert key fields
        events = [ev for d in days for ev in d.get("events", []) if ev.get("hasDataValues")]
        self.assertGreater(len(events), 0)
        ev = events[0]
        self.assertIn("id", ev)
        self.assertIn("currency", ev)
        self.assertIn("forecast", ev)
        self.assertIn("hasDataValues", ev)
        self.assertTrue(ev["hasDataValues"])
        self.assertNotIn("checker", ev)  # dropped field must not leak (DATA-04)

    def test_form2_bracket_assignment_no_data_events(self):
        """[n]={...} form; speech/holiday events (hasDataValues=False)."""
        html = self._fixture("form2_bracket_no_data.html")
        days = scraper.extract_days(html)
        self.assertGreater(len(days), 0)
        no_data = [ev for d in days for ev in d.get("events", [])
                   if not ev.get("hasDataValues")]
        self.assertGreater(len(no_data), 0)

    def test_empty_month_returns_empty_list(self):
        """A month page with zero events returns []."""
        html = self._fixture("empty_month.html")
        days = scraper.extract_days(html)
        event_count = sum(len(d.get("events", [])) for d in days)
        self.assertEqual(event_count, 0)

    def test_multi_candidate_select_best_days(self):
        """Multiple state objects: _select_best_days picks the richest one."""
        html = self._fixture("multi_candidate.html")
        days = scraper.extract_days(html)
        # Best candidate has the most events
        event_count = sum(len(d.get("events", [])) for d in days)
        self.assertGreater(event_count, 1)
```

### Pattern 8: SRC-01 Spike Fetcher Prototype

The spike fetcher is a standalone function (not integrated into the package until adopted). The approach:

1. **Recon step (D-07):** Open `https://www.forexfactory.com/calendar` in a browser with DevTools Network tab open. Click the month navigation arrows (prev/next). Capture the POST to `/calendar/apply-settings/100000?navigation=1`. Note: exact URL, all request headers (especially `Cookie`, `X-Csrf-Token` if present, `Content-Type`), the POST body/params, and the full response JSON.

2. **Prototype (curl_cffi):**
```python
# spike-only prototype — _api.py, not shipped unless adopted
def fetch_month_api(session, *, month_token: str, between_delay: float = 1.0) -> list:
    """Fetch calendar events via the apply-settings POST endpoint.

    month_token: e.g. 'jan.2024' (same format as ?month= param).
    Returns a days list (same shape as extract_days output) or [].
    """
    response = session.post(
        "https://www.forexfactory.com/calendar/apply-settings/100000",
        params={"navigation": "1"},
        data={"month": month_token},   # ASSUMPTION: body format TBD from recon
        headers=HEADERS,
        impersonate="chrome",
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    # Extract days list from response — shape TBD from recon
    return data.get("days", [])
```

3. **Comparison test:** Call both `scrape_month` (HTML) and `fetch_month_api` for the same 3-5 months. Diff the resulting event dicts field-by-field. Document any field present in HTML parse but missing from API response.

4. **Decision criteria (D-06):** If all four must-haves pass → adopt as primary (wire into `_refresh.run_refresh`). Otherwise → reject, document in PROJECT.md Key Decisions.

### Anti-Patterns to Avoid

- **Never call `None` from `_parse_value`** — use `float('nan')`. Python `None` in all-null float columns causes `dtype('O')` inference, breaking the typed parquet schema.
- **Never cast `actualBetterWorse` as plain `int64`** — use `Int64` (nullable) so future data with missing flag survives without an uncatchable TypeError.
- **Never update `_DATA01_COLUMNS` in `_query.py` without also updating the empty-df fallback in `_populate.build_month_parquet()`** — a mismatch causes `pd.concat` to introduce spurious NaN columns.
- **Never ship Playwright or browser-automation code in the package** — recon is spike-only scaffolding (D-07). If adopted, the shipped fetcher is `curl_cffi`-only.
- **Never drop `should_keep_row` from `_pipeline.run_pipeline()`** — the legacy `_pipeline` full-pipeline path (used by `pipeline.py` root script, if still invoked directly) still uses it. Remove it only from `_populate.build_month_parquet()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Nullable float parquet columns | Custom NaN-sentinel encoding | `float('nan')` + pandas `float64` → pyarrow `pa.float64()` | Verified to round-trip cleanly; NaN is the standard null for float64 in parquet |
| Nullable int parquet columns | `None` in plain `int64` (raises on to_parquet) | `pd.Int64Dtype()` via `.astype("Int64")` | Verified: `Int64Dtype()` round-trips through pyarrow 23.x with `<NA>` semantics |
| Value string parser | Hand-rolled tokenizer | Single compiled `re.compile(r'^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$')` | All 20 real edge cases pass with this one pattern; no tokenizer needed |
| Column type enforcement | Hand-written pyarrow schema | Post-construction `.astype("Int64")` + natural pandas inference | Simpler than explicit `pa.schema()`; produces the same result |
| Fixture HTML generation | Hand-written synthetic HTML | Real trimmed FF pages (captured during D-07 recon) | Synthetic fragments miss real quirks (whitespace, nested objects, real field values) |

**Key insight:** The FF value string format is narrow enough for a regex — no magnitude suffix stacks (no `'1.5KM'`), no parenthesis-negative format, no currency symbols in the string itself. The regex handles the entire observed space.

---

## Real Data Field Inventory

Verified against `out/days_2024_01.json` (January 2024, 75,913 total events across 195 months).

### Fields to KEEP (analytical value — D-01)

| JSON field | Type in JSON | Parquet dtype | Notes |
|------------|-------------|---------------|-------|
| `id` | `int` | `Int64` (nullable) | All observed events have non-zero id |
| `ebaseId` | `int` | `Int64` (nullable) | Numeric metric series identifier |
| `name` | `str` | `string` | Used as fallback for `title` |
| `prefixedName` | `str` | — | Primary `title` source (e.g., "US Non-Farm Payrolls") |
| `currency` | `str` | `string` | 2-3 char: "USD", "EUR", "JPY", etc. |
| `country` | `str` | `string` | 2-3 char code: "US", "UK", "JN", "EZ" etc. |
| `dateline` | `int` | — | Epoch seconds → `datetime_utc` via `to_iso()` |
| `impactName` | `str` | — | → `impact` via `norm_impact()` |
| `impactTitle` | `str` | — | Fallback for `impactName` |
| `hasDataValues` | `bool` | `bool` | False for speeches, holidays; True for data releases |
| `actual` | `str` | → `actual_raw` (str) + `actual` (float64) | e.g. `'4.3%'`, `'202K'`, `''` |
| `forecast` | `str` | → `forecast_raw` + `forecast` | Same format as actual |
| `previous` | `str` | → `previous_raw` + `previous` | Same |
| `revision` | `str` | → `revision_raw` + `revision` | Same |
| `actualBetterWorse` | `int` | `Int64` | Observed values: 0 (neutral/n/a), 1 (better), 2 (worse) |
| `revisionBetterWorse` | `int` | `Int64` | Same value range |
| `leaked` | `bool` | `bool` | All observed as `false` in 2024-01; type confirmed |

### Fields to DROP (UI/internal — D-04, DATA-04)

Confirmed 35 fields dropped:
`checkedIn`, `checker`, `date` (text date, redundant), `editUrl`, `enableActualComponent`, `enableDetailComponent`, `enableExpandComponent`, `firstInDay`, `greyed`, `hasGraph`, `hasLinkedThreads`, `hasNotice`, `hideHistory`, `hideSoloPage`, `impactClass`, `isMasterList`, `isSubscribable`, `isSubscribed`, `notice`, `releaser`, `showDetails`, `showExpanded`, `showGraph`, `showGridLine`, `siteId`, `soloTitle`, `soloTitleFull`, `soloTitleShort`, `soloUrl`, `timeLabel`, `timeMasked`, `trimmedPrefixedName`, `upNext`, `url`

### Value String Edge Cases Confirmed in Dataset

| Value string | Interpretation | `_parse_value` result | Source in dataset |
|-------------|----------------|-----------------------|-------------------|
| `'4.3%'` | 4.3 percent → fraction | 0.043 | BRC Shop Price Index |
| `'-10.7%'` | -10.7 percent | -0.107 | Commodity Prices |
| `'-27.4K'` | -27,400 | -27400.0 | Spanish Unemployment |
| `'8.79M'` | 8,790,000 | 8790000.0 | JOLTS Job Openings |
| `'2.0B'` | 2,000,000,000 | 2000000000.0 | Net Lending |
| `'1.89T'` | 1.89 × 10¹² | 1890000000000.0 | Current Account (CNY) |
| `'-0.41T'` | -0.41 × 10¹² | -410000000000.0 | Trade Balance |
| `'<0.10%'` | sub-threshold percent | NaN (unparseable) | Various |
| `'<0.25%'` | sub-threshold percent | NaN | Various |
| `'Pass'` | non-numeric outcome | NaN | Fed/Greek parliamentary votes |
| `'Yes'` | non-numeric outcome | NaN | Irish treaty vote |
| `'1.34|2.6'` | yield|bid-to-cover (bond auction) | NaN (pipe char blocks match) | 10-y bond auctions |
| `''` | no data | NaN | All no-data events |

---

## Common Pitfalls

### Pitfall 1: `None` vs `float('nan')` in Float Columns

**What goes wrong:** `_parse_value` returns Python `None` for unparseable input. If all values in a column happen to be unparseable (e.g., a month where every event has `forecast=''`), pandas constructs a `dtype('O')` (object) column instead of `float64`. This silently breaks pyarrow schema expectations and can cause `pd.concat` type conflicts when merging monthly parquets during query.

**Why it happens:** `pd.DataFrame([{'forecast': None}, {'forecast': None}])` gives `dtype('O')`, but `pd.DataFrame([{'forecast': float('nan')}, {'forecast': float('nan')}])` gives `dtype('float64')`. Verified in-process.

**How to avoid:** `_parse_value` must return `float('nan')` (not `None`). Verified all 20 test cases pass with this return type.

**Warning signs:** `df.dtypes['forecast'] == object` after building the DataFrame.

### Pitfall 2: `Int64` vs `int64` for Integer Columns with Potential Nulls

**What goes wrong:** `ev.get("id")` returns `None` when the key is absent. If you build a DataFrame with a mix of `None` and integer values in a column declared as plain `int64`, pyarrow will raise on write (cannot store null in non-nullable int64). Conversely, if all values are non-None, pandas infers `int64` naturally — which is fine — but a future month with a missing `id` would break.

**How to avoid:** After DataFrame construction, cast nullable integer columns with `.astype("Int64")`. This uses pandas nullable integer extension type, which maps to pyarrow `int64` with nullability. Verified round-trip in-process.

**Warning signs:** `ArrowInvalid` or `TypeError` on `df.to_parquet()`.

### Pitfall 3: `_DATA01_COLUMNS` / Empty-DataFrame Stale Column List

**What goes wrong:** `_query.py` has `_DATA01_COLUMNS` used to construct an empty DataFrame when no months match. `_populate.build_month_parquet()` has a parallel fallback. If either is not updated to Phase-2 columns, `pd.concat` across months will silently introduce NaN for the new columns in the empty-DataFrame case, and the result parquet will have schema drift.

**How to avoid:** Update both lists together. Define a single `PHASE2_COLUMNS` constant in `_pipeline.py` and import it into `_populate.py` and `_query.py`.

**Warning signs:** Empty result parquet missing expected columns, or unexpected NaN columns appearing in concat output.

### Pitfall 4: Cache Query Against Pre-Phase-2 Parquets

**What goes wrong:** If `forexfactory query` is run after the code changes but before the cache rebuild (`populate --force`), the per-month parquets won't have `hasDataValues`. The new `include_no_data` filter will raise `KeyError: 'hasDataValues'`.

**How to avoid:** In `_query.run_query()`, guard the filter with `if "hasDataValues" in df.columns`. Log a warning rather than raising. This makes a stale cache degrade gracefully. The Phase-2 plan must document the rebuild step as mandatory before first use of the new query filter.

**Warning signs:** `KeyError: 'hasDataValues'` in `run_query`.

### Pitfall 5: Bond Auction Pipe-Separated Values

**What goes wrong:** Bond auction events use `'1.34|2.6'` format (yield|bid-to-cover ratio). A naive parser that just strips letters might attempt to parse the full string as a number and either raise or produce garbage. The regex `^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$` correctly returns no-match (NaN) for any string containing `|` because `|` is not in the character class.

**Why it happens:** FF reports bond auctions with two statistics in one value string. The pair has no standard meaning without domain knowledge of which is which, so null is the correct output.

**How to avoid:** The regex approach handles this correctly. Do not add special-case parsing for `|` unless specifically requested.

**Warning signs:** Unexpected float values appearing for bond auction events.

### Pitfall 6: `should_keep_row` Still in `_pipeline.run_pipeline()`

**What goes wrong:** D-09 removes the speaks filter from the populate path. But `_pipeline.run_pipeline()` (the legacy full-pipeline path) still calls `should_keep_row`. If someone updates `_populate.build_month_parquet()` to remove the call but also accidentally removes it from `_pipeline.run_pipeline()`, the legacy `pipeline.py` root script behavior changes unintentionally.

**How to avoid:** The Phase-2 change is targeted: remove `should_keep_row` only from `_populate.build_month_parquet()`. Leave `_pipeline.run_pipeline()` and the `should_keep_row` function definition unchanged. The legacy path is independent.

**Warning signs:** Test failures in `test_pipeline.py` if `should_keep_row` is accidentally deleted.

### Pitfall 7: SRC-01 Spike — `navigation=1` Parameter May Not Navigate Freely

**What goes wrong:** The URL `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` suggests this is a navigation-oriented endpoint. The `navigation=1` parameter likely means "navigate forward one month" relative to the current session context. If so, it may only work for the current ±1-2 months, not arbitrary historical months (adopt-bar criterion 2). A spike that only tests recent months would give a false positive.

**How to avoid:** During the spike, explicitly test fetching a month from 2015 or 2018 to confirm the endpoint supports true historical access. If it returns empty data or an error for historical months, criterion 2 of D-06 fails and the endpoint is rejected.

**Warning signs:** Endpoint returns current month data regardless of the month parameter passed; returns HTTP 404 or 400 for old month tokens.

---

## Cache Re-Population Sequencing

The Phase-2 exit condition (Phase-1 D-03) requires: widen schema → rebuild cache → drop JSON staging. The safe sequencing:

```
Step 1: Widen flatten_events() + add _parse_value() + update empty-df fallbacks
         (no network; no data change — just code)

Step 2: Add force=True to run_populate() + add --force CLI flag

Step 3: Run: forexfactory populate --force
         → rebuilds all 195 months from out/*.json at new schema
         → each month parquet overwrites in place
         → manifest updated with scraped_at timestamps (idempotent)
         Expect: ~60K rows with new columns; 195 parquets rebuilt

Step 4: Verify: spot-check 2-3 months with pd.read_parquet()
         assert 'forecast_raw' in df.columns
         assert df['hasDataValues'].dtype == bool
         assert df['actualBetterWorse'].dtype.name == 'Int64'

Step 5: Drop raw JSON staging:
         (a) rm out/days_*.json         (repo root legacy staging)
         (b) rm -r ~/.cache/forexfactory/raw/   (cache raw/ subdir)

Step 6: Update manifest schema_version to "2" (so future code can detect Phase-2 cache)

Step 7: Update README schema table + test_docs.py assertions
```

**Idempotency:** `populate --force` can be re-run without corruption. Each invocation overwrites the per-month parquet and updates the manifest. If a month fails (bad JSON), it logs a warning and continues — the `empty_count` counter captures failures.

**Rollback:** If the rebuild is interrupted, the already-rebuilt months are at Phase-2 schema, the un-rebuilt ones are at Phase-1 schema. A re-run of `populate --force` will complete the rebuild. Only after Step 4 verification should the JSON files be dropped (Step 5).

---

## SRC-01 Spike Research

### What Can Be Researched Without Live Access

The URL `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` conforms to the pattern of an internal AJAX/SPA endpoint used by FF's calendar widget. Based on the pattern of FF's architecture as observed in the embedded JS: [ASSUMED]

- `apply-settings` is the action the FF calendar widget performs when its settings (date, currencies, impacts) change.
- `100000` is likely the "calendarId" or a widget scope identifier — the calendar page embeds a specific state key and uses it as part of the endpoint path.
- `navigation=1` means forward navigation (next month); `navigation=-1` likely means backward (previous month).
- The response is likely JSON with the same structure as `window.calendarComponentStates` (the object the HTML parser already extracts). [ASSUMED]
- Session cookies from the browser visit (CSRF token, session ID) are likely required in the POST request, obtainable without login since the FF calendar is public. [ASSUMED]

### What Requires Live Spike

All four D-06 criteria require empirical testing:

1. **Field completeness:** Does the JSON response include `forecast`, `actual`, `previous`, `revision`, `actualBetterWorse`, `revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`? — Must compare field-for-field against the HTML parse output.

2. **Historical access:** Does `navigation=-N` (or a month parameter in the POST body) allow fetching 2010-2015 data, or only the current ±few months? — Test by requesting months from 2015, 2018, 2022 in addition to recent months.

3. **curl_cffi compatibility:** Does the endpoint require browser-state cookies (CSRF, session) that `curl_cffi`'s Chrome impersonation can obtain by first fetching the calendar page, or does it require a persistent authenticated session that `curl_cffi` cannot reproduce? — Test by (a) fetching the calendar page GET first to capture cookies, then (b) POST with those cookies.

4. **Rate stability:** Does repeated POST at 1-second intervals trigger 429/403 throttling across 10-20 requests? — Test with a small batch (10 months) at 1-second delay.

### Spike Decision Protocol

The spike produces a `DECISION.md` (or inline comment in `PROJECT.md`) documenting:
- What was captured in devtools (headers, body, response shape)
- The D-06 bar result for each of the four criteria (pass/fail)
- If all pass: the `_api.py` prototype is merged as `_api.py`, wired into `_refresh.run_refresh()` as the primary path (HTML parse becomes fallback)
- If any fail: the endpoint is documented as investigated-and-rejected; `_api.py` is deleted

---

## Open Questions (RESOLVED)

All four open questions are resolved for planning: each is either deferred to the
SRC-01 spike (a spike *deliverable*, not a blocking research gap) or implemented
directly in the Phase-2 plans, as marked below.

1. **`navigation` parameter semantics (SRC-01)**
   - What we know: URL contains `?navigation=1`; FF calendar uses prev/next buttons for pagination; direction and target encoding are unknown without devtools capture.
   - What's unclear: Whether navigation is relative (±N months from server-side session state) or absolute (a month token in the POST body). If relative, replaying a POST request out of context may not work.
   - Recommendation: DevTools capture is the only reliable answer. This is a spike deliverable, not a research deliverable.
   - RESOLVED: deferred to spike plan 02-04 (the D-07 live-recon deliverable). Not a planning blocker — the schema thread (02-01) is source-agnostic per D-05 and does not depend on the answer.

2. **`id` field storage type migration**
   - What we know: `id` in JSON is `int`; the Phase-1 `flatten_events()` uses `ev.get("id", "")` which returns `int` or empty string `""`. The Phase-1 parquets therefore have `id` as `object` dtype in months where all events have int IDs (pandas infers object when the fallback `""` is mixed with ints in some code paths).
   - What's unclear: Whether the Phase-1 per-month parquets actually have `id` as `object` or `int64`. This affects whether the cache rebuild is a schema migration or just a widening.
   - Recommendation: Check one Phase-1 parquet dtype for `id` before writing the migration plan. If `object`, the cast to `Int64` in Phase 2 is a type change (breaking if consumer code does `df['id'].astype(int)`). Planner should note this as a potential downstream incompatibility.
   - RESOLVED: the unconditional `Int64` cast in 02-01 Task 2 handles both starting dtypes (`object` and `int64`); moreover the cache is currently empty, so the rebuild is a fresh build rather than a migration — the question is moot for execution.

3. **Schema version stamping mechanism**
   - What we know: The planner needs to drive a wipe-and-rebuild; a `schema_version` in `manifest.json` enables future automatic detection.
   - What's unclear: Whether Phase 2 should also read the version on populate (to auto-force-rebuild on version mismatch) or only stamp it post-rebuild.
   - Recommendation: For Phase 2, stamp `"schema_version": "2"` in manifest after rebuild and store `SCHEMA_VERSION = "2"` in `_cache.py`. Full auto-rebuild-on-mismatch is a Phase-3 enhancement (CACHE-03 territory).
   - RESOLVED: stamp-only for Phase 2 — `SCHEMA_VERSION = "2"` in `_cache.py`, written to `manifest.json` after rebuild (02-01 Task 2). Auto-rebuild-on-mismatch is explicitly deferred to Phase 3.

4. **`actualBetterWorse` = 0 for no-data events**
   - What we know: Every event (including speeches and holidays) has `actualBetterWorse: 0` in the raw JSON — even when there is no actual/forecast comparison to make.
   - What's unclear: Whether 0 means "neutral/inline" or "no comparison available". The FF UI uses different styling for the three values, and 0 is the default when there's no actual data.
   - Recommendation: Store the raw int as specified by D-03. Add an inline comment in the code noting that 0 can mean "no comparison performed" (speeches/holidays) or "inline with forecast" (data releases). Do not map to categorical in Phase 2.
   - RESOLVED: store the raw int per D-03 (02-01 Task 1), with an inline code comment noting `0` can mean "no comparison performed" (speeches/holidays) vs "inline with forecast" (data releases). No categorical mapping in Phase 2.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All source code | ✓ | 3.12.3 | — |
| pandas | Schema widening, parquet I/O | ✓ | 2.1.4 | — |
| pyarrow | Parquet write engine | ✓ | 23.0.1 | — |
| curl_cffi | SRC-01 spike fetcher | ✓ (in venv) | ≥0.13.0 | — |
| pytest | QUAL-05 test runner | ✓ | — | — |
| out/ raw JSON | Cache rebuild (195 months) | ✓ | 2010-01 → 2026-03 (195 files) | Re-scrape (not acceptable per D-03) |
| Internet access | SRC-01 spike live recon | [unknown] | — | Spike cannot proceed without; document and defer |
| Browser + DevTools | D-07 recon step | [unknown] | — | Manual curl analysis (reduced fidelity) |

**Missing dependencies with no fallback:**
- Internet access and a browser with DevTools are required for the SRC-01 spike. If unavailable in the execution environment, the spike task must be flagged as requiring human execution and the decision documented manually.

**All other dependencies confirmed present.** Test suite baseline: `80 passed in 2.31s` (pre-Phase-2 state). [VERIFIED: in-process]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `apply-settings` response is JSON with the same structure as `window.calendarComponentStates` | SRC-01 Spike Research | Spike prototype would need different parsing logic |
| A2 | Session cookies from a prior GET to the calendar page are sufficient for the POST (no persistent login needed) | SRC-01 Spike Research | May need to find a cookie-acquisition strategy; does not block HTML fallback |
| A3 | `navigation=-N` or a month POST body param allows arbitrary historical access | SRC-01 Spike Research | If false, endpoint fails adopt-bar criterion 2 (HTML fallback stays primary) |
| A4 | `actualBetterWorse = 0` on speech/holiday events is a neutral "no comparison" sentinel, not a meaningful signal | Open Questions | Consumer code using `ABW != 0` as a filter would be correct either way |

---

## Sources

### Primary (HIGH confidence)

- In-process inspection of `out/days_2024_01.json` — field inventory, types, value string shapes, edge cases (confirmed all 50+ raw event fields and their Python types) [VERIFIED]
- In-process pandas 2.1.4 + pyarrow 23.0.1 dtype experiments — nullable float round-trip, Int64 nullable int round-trip, bool round-trip through zstd parquet [VERIFIED]
- In-process regex verification — `_parse_value()` against all 20 edge cases from real data [VERIFIED]
- In-process 195-month scan — value string edge cases (`'<0.10%'`, `'Pass'`, `'Yes'`, `'1.34|2.6'`) confirmed in real data [VERIFIED]
- In-process event counting — 75,913 total events; 60,339 data-bearing; 2,141 holidays; 13,433 no-data non-holiday [VERIFIED]
- `src/forexfactory/_pipeline.py` — `flatten_events()`, `should_keep_row()`, `write_parquet()`, `_deduplicate_rows()` (direct code read) [VERIFIED]
- `src/forexfactory/_populate.py` — `build_month_parquet()`, `run_populate()` (direct code read) [VERIFIED]
- `src/forexfactory/_query.py` — `run_query()`, `_DATA01_COLUMNS`, filter logic (direct code read) [VERIFIED]
- `src/forexfactory/_cache.py` — `manifest.json` layout, `_scope_covers()`, `update_manifest_month()` (direct code read) [VERIFIED]
- Existing test suite — `tests/test_scrape.py`, `tests/test_pipeline.py` patterns for QUAL-05 fixture test class design [VERIFIED]

### Secondary (MEDIUM confidence)

- CONTEXT.md D-01..D-11 decisions — locked design choices; treated as constraints [CITED: .planning/phases/02-full-analytical-schema-source-spike/02-CONTEXT.md]
- Phase-1 D-03 exit condition — JSON-drop sequencing [CITED: .planning/phases/01-installable-data-provider/01-CONTEXT.md]

### Tertiary (LOW confidence)

- `apply-settings` endpoint semantics (response shape, navigation parameter encoding, cookie requirements) — all ASSUMED from training knowledge; must be verified in spike [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Schema widening (DATA-02/03/04): HIGH — every field verified in real data; dtype round-trips confirmed in-process
- Numeric parsing (D-02): HIGH — regex verified against all real edge cases found across 195 months
- Cache rebuild sequencing: HIGH — code read confirms force-flag approach; sequencing is deterministic
- Query filter change (DATA-05): HIGH — pattern is straightforward; `hasDataValues` column presence guard handles stale-cache edge case
- QUAL-05 fixture approach: HIGH — test class pattern established; fixture directory exists; only remaining work is capturing real HTML
- SRC-01 endpoint: LOW — requires live investigation; all claims are ASSUMED

**Research date:** 2026-06-08
**Valid until:** Schema/dtype findings are stable (pyarrow 23.x, pandas 2.x). SRC-01 spike findings depend on FF site behaviour, which changes without notice.
