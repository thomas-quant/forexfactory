# Testing Patterns

**Analysis Date:** 2026-06-07

## Test Framework

**Runner:**
- pytest (invoked as `python3 -m pytest -q`)
- No config file — no `pytest.ini`, `pyproject.toml`, `setup.cfg`, or `tox.ini`

**Test Style:**
- `tests/test_scrape.py` and `tests/test_pipeline.py`: `unittest.TestCase` subclasses (discovered and run by pytest)
- `tests/test_docs.py`: plain pytest functions (no class)

**Assertion Library:**
- `unittest.TestCase` methods (`assertEqual`, `assertIn`) in class-based tests
- Plain `assert` statements in `test_docs.py`

**Run Commands:**
```bash
python3 -m pytest -q          # Run all tests (quiet output)
python3 -m pytest -v          # Verbose with test names
python3 -m pytest tests/test_scrape.py   # Single file
```

## Test File Organization

**Location:** Separate `tests/` directory at repo root — not co-located with source modules

**Naming:**
- Test files: `test_<module>.py` — `test_scrape.py`, `test_pipeline.py`, `test_docs.py`
- Test classes: `<Subject>Tests` (PascalCase) grouped by theme — e.g. `ScrapeTests`, `PipelineParquetCompressionTests`, `PipelineLeakedFieldTests`
- Test methods/functions: `test_<what_is_being_verified>` in full descriptive snake_case — e.g. `test_extract_days_from_bracket_assignment_with_unquoted_days_key`

**Structure:**
```
tests/
├── fixtures/         # Present but empty — no fixture files used
├── test_docs.py      # Documentation regression tests (plain pytest functions)
├── test_pipeline.py  # Pipeline unit tests (unittest.TestCase classes)
└── test_scrape.py    # Scraper unit tests (unittest.TestCase classes)
```

## Test Structure

**Class-based suite organization (`test_scrape.py`, `test_pipeline.py`):**
```python
class ScrapeTests(unittest.TestCase):
    def test_<descriptive_name>(self):
        # Arrange
        ...
        # Act
        result = scraper.some_function(...)
        # Assert
        self.assertEqual(result, expected)
```

**Plain pytest function organization (`test_docs.py`):**
```python
def test_<descriptive_name>():
    text = README.read_text(encoding="utf-8")
    assert "expected string" in text
```

**Patterns:**
- No `setUp` / `tearDown` methods used — each test is self-contained
- `tempfile.TemporaryDirectory()` used as context manager for filesystem isolation
- `pathlib.Path` used for all temp-file construction (`.write_text()`, `.read_text()`, `/` path joining)
- Tests import source modules at the top of the file by name (`import scrape as scraper`, `import pipeline`)

## Mocking

**Framework:** `unittest.mock` — `patch` and `patch.object`

**Patterns:**

Patching a module-level attribute (constant):
```python
with patch.object(pipeline, "IN_DIR", str(in_dir)):
    pipeline.run_pipeline(out_parquet=str(out_path))
```

Patching a method on an imported library class with `autospec`:
```python
with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
    pipeline.csv_to_parquet(str(csv_path), str(parquet_path))
_, kwargs = to_parquet.call_args
self.assertEqual(kwargs["compression"], "zstd")
```

Patching a module function called inside the unit under test:
```python
with patch.object(scraper, "run_scraper", side_effect=fake_run_scraper):
    result = scraper.main([...])
```

Patching `time.sleep` to suppress delays:
```python
with patch.object(scraper.time, "sleep"):
    result = scraper.scrape_month(session, page, max_attempts=2)
```

**Hand-rolled fakes (preferred over MagicMock for HTTP layer):**
- `FakeResponse` — mimics a `curl_cffi` response with `.text` and `.raise_for_status()`
- `FakeSession` — queue-based fake that pops pre-loaded responses or raises exceptions per call, records all `(url, kwargs)` call tuples for assertion

```python
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

**What to Mock:**
- `time.sleep` — always suppress in tests to avoid delays
- `pandas.DataFrame.to_parquet` — avoid writing real Parquet files; use `call_args` to assert compression settings
- Module-level config constants (`IN_DIR`) when tests need a different input directory
- `run_scraper` when testing `main()` end-to-end behavior without filesystem side effects

**What NOT to Mock:**
- Pure parsing/transformation logic (`extract_days`, `flatten_events`, `norm_impact`, `to_iso`) — test with real inputs
- Filesystem reads/writes — use `tempfile.TemporaryDirectory()` for real isolation instead

## Fixtures and Factories

**Test Data:**
- JSON event payloads constructed inline within each test using `json.dumps()`:
```python
days = [{"events": [{"id": "nfp-1"}, {"id": "cpi-1"}]}]
html = f'<script>window.calendarComponentStates = {{"month": {{"days": {json.dumps(days)}}}}};</script>'
```

- CSV files written directly to temp directories:
```python
writer = csv.DictWriter(handle, fieldnames=[...])
writer.writeheader()
writer.writerow({"date": "2026-03-01", "time_utc": "12:30:00", ...})
```

- JSON data files written to temp directories:
```python
(in_dir / "days_2026_03.json").write_text(json.dumps([{...}]), encoding="utf-8")
```

**Location:** No separate fixture files — all test data is defined inline. `tests/fixtures/` directory exists but is empty.

## Coverage

**Requirements:** None enforced — no coverage config or threshold
**Coverage exclusions:** `# pragma: no cover` used on the `except ImportError` branch for the optional `curl_cffi` import in `scrape.py:24`

**View Coverage (manual):**
```bash
python3 -m pytest --cov=scrape --cov=pipeline --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- All tests are unit tests
- Scope: individual functions and methods in `scrape.py` and `pipeline.py`
- Filesystem is isolated via `tempfile.TemporaryDirectory()`
- HTTP is isolated via `FakeSession` / `FakeResponse`

**Documentation Regression Tests (`tests/test_docs.py`):**
- Assert that `README.md` contains expected strings for project structure chart and schema table
- Enforced via `test_docs.py` and documented in `AGENTS.md` as part of the change checklist
- Must be updated whenever pipeline columns, file names, or repo layout changes

**Integration Tests:** Not present

**E2E Tests:** Not present — live network calls to forexfactory.com are never made in the test suite

## Common Patterns

**Async Testing:** Not applicable — codebase is fully synchronous

**Verifying call arguments after a mock:**
```python
with patch.object(pipeline.pd.DataFrame, "to_parquet", autospec=True) as to_parquet:
    pipeline.csv_to_parquet(str(csv_path), str(parquet_path))
_, kwargs = to_parquet.call_args
self.assertEqual(kwargs["compression"], "zstd")
self.assertEqual(kwargs["compression_level"], 3)
```

**Testing retry behavior:**
```python
session = FakeSession([RuntimeError("temporary"), FakeResponse(html)])
with patch.object(scraper.time, "sleep"):
    result = scraper.scrape_month(session, page, max_attempts=2)
self.assertEqual(result, days)
self.assertEqual(len(session.calls), 2)
```

**Testing file skip logic:**
```python
(out_dir / "days_2026_01.json").write_text("[]", encoding="utf-8")  # pre-existing
pages = [MonthPage(date(2026, 1, 1), "..."), MonthPage(date(2026, 2, 1), "...")]
result = scraper.run_scraper(pages, out_dir=str(out_dir), session=session)
self.assertEqual(result.skip_count, 1)
self.assertEqual(result.success_count, 1)
```

**Testing CLI wiring with a captured side effect:**
```python
captured = {}
def fake_run_scraper(pages, *, out_dir, ...):
    captured["out_dir"] = out_dir
    ...
    return scraper.ScrapeResult(...)

with patch.object(scraper, "run_scraper", side_effect=fake_run_scraper):
    scraper.main(["--start-date", "2026-03-01", "--out-dir", "out-test", ...])
self.assertEqual(captured["out_dir"], "out-test")
```

---

*Testing analysis: 2026-06-07*
