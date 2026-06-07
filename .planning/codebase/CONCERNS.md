# Codebase Concerns

**Analysis Date:** 2026-06-07

## Tech Debt

**Stale hardcoded default date range in scrape.py:**
- Issue: `START_DATE = "2021-01-01"` and `END_DATE = "2021-06-30"` are hardcoded constants used as argparse defaults. Running `python scrape.py` with no arguments silently scrapes a historical range from over five years ago, which is rarely the intended behavior for new runs.
- Files: `scrape.py` lines 36–37
- Impact: Users who forget to pass `--start-date` / `--end-date` re-scrape stale months (which are then skipped because the files exist) or, on a fresh checkout, download the wrong date window entirely.
- Fix approach: Change defaults to today's date or require explicit flags; at minimum, add a visible warning in `main()` when the hardcoded fallback range is used.

**Duplicated deduplication logic in pipeline.py:**
- Issue: The deduplication block (building a `dedup` dict keyed on `(id, date, time_utc)` or the 4-tuple fallback) is copy-pasted verbatim in both `parse_json_to_csv()` (lines 117–122) and `run_pipeline()` (lines 214–219).
- Files: `pipeline.py` lines 117–122 and 214–219
- Impact: Any fix to dedup logic (e.g., changing the fallback key) must be applied twice; the two paths can silently diverge.
- Fix approach: Extract a `_deduplicate_rows(rows)` helper and call it from both functions.

**`run_pipeline()` ignores module-level filter constants at call sites:**
- Issue: `run_pipeline()` accepts only `out_parquet` as a parameter; it reads `IN_DIR`, `KEEP_CURRENCIES`, and `KEEP_IMPACTS` directly as module globals. The `--in-dir` CLI flag is correctly threaded through to `parse_json_to_csv()` when `--step parse` is used, but is **silently ignored** when no `--step` is given — `main()` calls `run_pipeline(out_parquet=out_parquet)` without forwarding `args.in_dir`.
- Files: `pipeline.py` lines 202–233 (`run_pipeline`), line 277 (`main()` full-pipeline path)
- Impact: `python pipeline.py --in-dir /custom/path` does nothing; users will assume the flag worked and get wrong output sourced from the default `out/` directory.
- Fix approach: Add `in_dir`, `keep_currencies`, and `keep_impacts` parameters to `run_pipeline()` and forward `args.in_dir` in `main()`.

**`api.txt` is an uncommitted scratch note:**
- Issue: `api.txt` contains a raw URL and a speculative comment ("possibly can send post requests?") with no code consuming it. It is tracked in git but appears to be a personal research note.
- Files: `api.txt`
- Impact: Low, but adds noise and may mislead future contributors into thinking a POST API integration exists.
- Fix approach: Remove the file or convert to a proper comment in the relevant code.

## Known Bugs

**`--in-dir` flag silently no-ops in full pipeline mode:**
- Symptoms: `python pipeline.py --in-dir /other/dir` reads from the hardcoded `IN_DIR = "out"` instead of `/other/dir`.
- Files: `pipeline.py` line 277
- Trigger: Run `python pipeline.py --in-dir /some/other/path` (no `--step`).
- Workaround: Use `--step parse --in-dir /other/dir` followed by `--step sanitize` and `--step parquet` individually.

**Empty JSON files written on failed scrapes create permanent skip entries:**
- Symptoms: When `scrape_month()` returns `[]` after all retry attempts (e.g., bot detection or network failure), `run_scraper()` still writes an empty `days_YYYY_MM.json` file (line 380). On subsequent runs that month is permanently skipped because the file exists.
- Files: `scrape.py` lines 379–387
- Trigger: Any month that fails all `MAX_ATTEMPTS` retries will have an empty JSON file committed to `out/`, preventing any future retry.
- Workaround: Manually delete the empty `out/days_YYYY_MM.json` files before re-running.

## Security Considerations

**No rate-limiting enforced by default:**
- Risk: `BETWEEN_PAGES_DELAY = 0.0` and `RETRY_DELAY = 0.0` are the defaults. Scraping with zero delays could violate Forex Factory's terms of service or trigger IP bans, especially for full historical runs (2010–2026 = ~195 months).
- Files: `scrape.py` lines 44–45
- Current mitigation: CLI flags (`--between-pages-delay`, `--retry-delay`) allow users to add delays, and the README mentions respecting rate limits. The skipping logic prevents redundant re-fetches.
- Recommendations: Set non-zero default delays (e.g., 1.0s between pages) to avoid being an aggressive scraper by default; the defaults are the path of least resistance for users.

**User-Agent header is pinned to a specific Chrome version:**
- Risk: `user-agent` in `HEADERS` is hardcoded to `Chrome/131.0.0.0`. If Forex Factory adds version-based bot checks, this static string may trigger detection before `curl_cffi`'s TLS impersonation helps.
- Files: `scrape.py` lines 56–59
- Current mitigation: `curl_cffi` impersonates the full TLS fingerprint of Chrome (`impersonate="chrome"`), which is the primary anti-bot measure. The User-Agent mismatch is a secondary risk.
- Recommendations: Rotate or update the pinned User-Agent string periodically, or derive it from the `curl_cffi` impersonation target.

## Performance Bottlenecks

**Full in-memory load for large historical ranges:**
- Problem: `run_pipeline()` reads all `days_*.json` files into a single `rows` list before deduplication, sorting, and DataFrame construction. For the full 2010–2026 dataset (~195 files), this may accumulate tens of thousands of rows in memory simultaneously.
- Files: `pipeline.py` lines 205–232
- Cause: No streaming or chunked processing; all rows are held in memory until the DataFrame is written.
- Improvement path: For typical usage (USD high/holiday only) the row count is modest and this is not critical. If filtering is widened to all currencies/impacts, a chunked approach would help.

## Fragile Areas

**HTML-to-JSON parser for `calendarComponentStates`:**
- Files: `scrape.py` lines 95–305 (`_find_matching_brace`, `_find_matching_bracket`, `_quote_js_object_keys`, `_replace_single_quoted_strings`, `_extract_state_json`, `_extract_assigned_state_objects`, `_extract_days_array_from_state_object`, `extract_days`)
- Why fragile: The parser manually walks character-by-character through embedded JavaScript to locate a nested object, convert unquoted JS keys to JSON keys, and convert single-quoted strings to double-quoted JSON. This is sensitive to any change in Forex Factory's HTML/JS bundle structure — a new JS variable name, a change in whitespace, or a nested template literal would silently cause `extract_days()` to return `[]`.
- Safe modification: Always run the full test suite after changes; add fixture-based tests using real or realistic saved HTML fragments. Currently `tests/fixtures/` exists but is empty.
- Test coverage: Unit tests cover the bracket-assignment and whole-object assignment paths with synthetic HTML, but no test uses a real or realistically-complex HTML fixture.

**`sanitize_csv()` can crash when input CSV has no rows:**
- Files: `pipeline.py` lines 146–162
- Why fragile: `reader.fieldnames` is `None` if the CSV is empty (no header row). Passing `None` to `csv.DictWriter(f_out, fieldnames=None)` raises `TypeError: 'NoneType' object is not iterable`.
- Safe modification: Guard with `if fieldnames is None: raise ValueError(...)` before writing.

**`to_iso()` silently swallows all exceptions:**
- Files: `pipeline.py` lines 67–78
- Why fragile: The bare `except Exception: return "", ""` masks any bug in timestamp conversion (overflow, invalid type, etc.) and produces silent empty strings in the output. There is no test for the malformed-timestamp path.
- Safe modification: Catch only `(ValueError, OSError, OverflowError)` and log the bad value.

## Test Coverage Gaps

**`run_pipeline()` full-pipeline path is only tested for compression and `leaked` column:**
- What's not tested: filtering by currency/impact, correct deduplication, the `should_keep_row` sanitize step, datetime_utc column construction, empty-input behavior.
- Files: `pipeline.py` lines 202–233; `tests/test_pipeline.py`
- Risk: A regression in filtering or sanitize logic inside `run_pipeline()` would not be caught.
- Priority: Medium

**`norm_impact()` has no dedicated tests:**
- What's not tested: The fuzzy matching branches (`"non-economic"`, `"bank"`, `"red"`, `"orange"`, `"yellow"` substrings) have no unit tests.
- Files: `pipeline.py` lines 51–64
- Risk: A future change to normalization strings would pass CI silently.
- Priority: Medium

**`sanitize_csv()` step has no unit tests:**
- What's not tested: The step function itself, including the `should_keep_row` logic when called through `sanitize_csv()`, empty-file behavior, and field passthrough.
- Files: `pipeline.py` lines 140–162; `tests/test_pipeline.py`
- Risk: Changes to the sanitize step would not be caught.
- Priority: Medium

**`tests/fixtures/` directory is empty:**
- What's not tested: No HTML fixture files exist to test the `extract_days()` parser against real or realistic Forex Factory page structure.
- Files: `tests/fixtures/` (empty), `scrape.py` lines 295–305
- Risk: A site-side change to the JS state embedding would not be caught until a live scrape fails.
- Priority: High — the parser is the most fragile component and has no fixture-based regression coverage.

**`main()` CLI dispatch in `pipeline.py` has no tests:**
- What's not tested: The `--step parse`, `--step sanitize`, `--step parquet`, and no-step paths in `main()` are not tested. In particular the `--in-dir` silent-ignore bug is not caught.
- Files: `pipeline.py` lines 236–281; `tests/test_pipeline.py`
- Risk: CLI argument wiring bugs (like the `--in-dir` issue) go undetected.
- Priority: Low–Medium

## Missing Critical Features

**No mechanism to force re-scrape of a month:**
- Problem: The skip-if-exists logic in `run_scraper()` means corrupted, empty, or stale JSON files cannot be refreshed without manual deletion. There is no `--force` or `--overwrite` flag.
- Blocks: Recovering from bot-detection failures or re-fetching months where Forex Factory updated historical data.

**No validation that scraped JSON is non-trivially correct:**
- Problem: `run_scraper()` considers a scrape successful if `days` is non-empty, but does not check that `days` contains the expected number of events or that dates match the requested month. A partially-blocked response returning one day with no events would pass as a "success".
- Files: `scrape.py` lines 334–336
- Blocks: Silent data quality issues in the `out/` archive.

---

*Concerns audit: 2026-06-07*
