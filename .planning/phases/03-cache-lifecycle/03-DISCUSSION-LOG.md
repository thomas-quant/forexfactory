# Phase 3: Cache Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 3-Cache Lifecycle
**Areas discussed:** Force-refresh CLI shape, Auto-widen failure mode, Matured-month check placement, Auto-fetch progress visibility

---

## Force-refresh CLI shape

### Q1: What should '--force-refresh' do on 'populate'?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-scrape + overwrite cache | `populate --force-refresh` re-scrapes via network and overwrites existing cached parquets. Existing `--force` (raw-JSON reprocess) stays unchanged. | ✓ |
| Merge --force into --force-refresh | Rename/replace `--force` with `--force-refresh` as "re-scrape and overwrite". Simpler surface, but breaks the schema-migration use case. | |

**User's choice:** Re-scrape + overwrite cache (recommended)

---

### Q2: Does 'refresh --force-refresh' also need to exist?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — refresh --force-refresh overwrites cached months | `run_refresh()` currently skips already-cached months. Adding `--force-refresh` makes it overwrite them. Consistent: both `populate` and `refresh` get the flag. | ✓ |
| No — populate --force-refresh is enough | Force-refresh on `populate` covers CACHE-06. `refresh` stays gap-fill only. | |

**User's choice:** Yes — refresh --force-refresh overwrites cached months (recommended)

---

### Q3: Library arg — should force_refresh=True be a kwarg on both populate() and get()/refresh()?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, mirror CLI flag as library kwarg | `forexfactory.populate(force_refresh=True)` and `run_refresh(force_refresh=True)`. Consistent with Phase 1 D-12 flag↔kwarg convention. | ✓ |
| CLI only | Expose `--force-refresh` on CLI; library callers use `run_refresh()` directly with an `overwrite=True` param. | |

**User's choice:** Yes, mirror CLI flag as library kwarg (recommended)

---

### Q4: What does 'populate --force-refresh' do when re-scrape succeeds but some months fail?

| Option | Description | Selected |
|--------|-------------|----------|
| Partial overwrite: write what succeeded, skip failed months | Same retry/skip contract as `run_refresh()` today. Failed months keep their old cached parquet. Result dict reports fetched/skipped/failed counts. | ✓ |
| All-or-nothing: roll back on any failure | If any month fails, leave entire range unchanged. Safer but complex — requires temp files + atomic swap per month. | |

**User's choice:** Partial overwrite (recommended)

---

## Auto-widen failure mode

### Q1: If the auto-widen fetch fails, what should query()/get() return?

| Option | Description | Selected |
|--------|-------------|----------|
| Raise with a NetworkError | `query()` raises an exception describing what was attempted and what failed. No silent partial data. Caller knows the cache is incomplete. | ✓ |
| Return partial cache + warn | Return whatever matching data exists in cache and emit `logger.warning`. Caller gets a possibly-empty parquet silently. | |

**User's choice:** Raise with a NetworkError (recommended)

---

### Q2: Auto-widen: fetch all missing months, or only what's needed for the query's date range?

| Option | Description | Selected |
|--------|-------------|----------|
| Full scope widen | Fetch the full configured range for the missing currency/impact. Cache is permanently widened; subsequent queries don't re-trigger. | ✓ |
| Query-range only | Only fetch months that overlap the query's `--start/--end` window. Faster for narrow queries but partially widens scope. | |

**User's choice:** Full scope widen (recommended)

---

### Q3: When auto-widen triggers multiple missing scope combinations, abort after first failure or best-effort?

| Option | Description | Selected |
|--------|-------------|----------|
| Abort on first failure | If EUR/medium fetch fails, stop and raise immediately. Don't silently partially populate GBP/medium while EUR/medium is incomplete. | ✓ |
| Best-effort: fetch all, collect failures | Attempt all missing combinations. Report failures at the end. Cache is partially widened for successful combos. | |

**User's choice:** Abort on first failure (recommended)

---

### Q4: Should auto-widen be suppressible via a library kwarg (e.g. auto_fetch=False)?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — auto_fetch=True default, opt-out via False | `get(..., auto_fetch=False)` reverts to the current raise-on-scope-miss behavior. Useful for callers who want strict cache-only reads. | ✓ |
| No — auto-widen always on | The old error path is gone. Any scope miss auto-fetches. Simpler API, but callers can't opt out. | |

**User's choice:** Yes — auto_fetch=True default, opt-out via False (recommended)

---

## Matured-month check placement

### Q1: When should the unsettled→settled check + re-fetch run?

| Option | Description | Selected |
|--------|-------------|----------|
| Both populate and query paths | Consistent with SC2 ("on next populate or query call"). Any cache-touching call triggers the re-fetch. | ✓ |
| Populate-only | Maturity check runs only on explicit `forexfactory populate`. `query`/`get()` never triggers a scrape for this reason. | |

**User's choice:** Both populate and query paths (recommended)

---

### Q2: How many matured months can a single call auto-refresh at once?

| Option | Description | Selected |
|--------|-------------|----------|
| All unsettled-but-now-mature months | If 3 months matured since last run, all 3 are re-fetched. Complete correctness; one call suffices. | ✓ |
| Cap at N months per call (e.g. 6) | Limits worst-case latency for long-dormant caches. Adds complexity and a config constant. | |

**User's choice:** All unsettled-but-now-mature months (recommended)

---

### Q3: Should matured-month auto-refresh be suppressible?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — same opt-out as auto_fetch=False | `get(..., auto_fetch=False)` disables both scope-miss auto-widen AND matured-month auto-refresh. One knob, clear semantics. | ✓ |
| Separate flag: auto_refresh=False | Two independent flags: `auto_fetch` controls scope-miss; `auto_refresh` controls maturity. More granular but doubles the opt-out surface. | |

**User's choice:** Same opt-out as auto_fetch=False (recommended)

---

### Q4: What happens if a matured-month re-fetch fails mid-query?

| Option | Description | Selected |
|--------|-------------|----------|
| Serve stale cached data + warn in log | Existing parquet is still valid (has forecast values, missing actuals). Return it with `logger.warning`. | ✓ |
| Raise — same contract as auto-widen failure | Consistent error contract but crashing loses data the user already has. | |

**User's choice:** Serve stale cached data + warn in log (recommended)

---

## Auto-fetch progress visibility

### Q1: What should the CLI show when a query triggers a live scrape?

| Option | Description | Selected |
|--------|-------------|----------|
| Print progress to stdout | e.g. "Auto-fetching EUR/medium (6 months)... [1/6] 2025-01 ..." — consistent with existing `[N/total]` progress. User knows why the query is slow. | ✓ |
| Logging only (INFO level, no print) | No stdout output. Progress only visible if logging configured at INFO. | |

**User's choice:** Print progress to stdout (recommended)

---

### Q2: Should the library call (forexfactory.get()) also print progress, or print only from the CLI?

| Option | Description | Selected |
|--------|-------------|----------|
| Print from both library and CLI | Print calls live in `run_refresh()`. Any caller — CLI or library — sees progress. | |
| CLI prints, library is silent | Print logic lives in `cli.py`'s `query` command. `get()` callers get no stdout side-effects. | ✓ |

**User's choice:** CLI prints, library is silent

---

### Q3: Should the CLI announce the auto-fetch trigger with a preamble?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — one-line preamble | e.g. "EUR/medium not in cache — fetching now..." then the `[N/total]` lines. User understands WHY before seeing the progress. | ✓ |
| No preamble, just the progress lines | Jump straight to `[1/6] 2025-01`. Fewer lines. | |

**User's choice:** Yes — one-line preamble (recommended)

---

### Q4: Same progress/preamble output for matured-month auto-refresh, or different messaging?

| Option | Description | Selected |
|--------|-------------|----------|
| Different preamble, same [N/total] lines | Auto-widen: "EUR/medium not in cache — fetching now..." \| Matured: "2 months matured since last run — refreshing actuals..." then `[N/total]` lines. Clear distinction. | ✓ |
| Same output for both triggers | Generic "Fetching N months..." regardless of trigger. Simpler. | |

**User's choice:** Different preamble, same [N/total] lines (recommended)

---

## Claude's Discretion

- Exact Python exception type for CACHE-03 network failures (`NetworkError`, `RuntimeError`, or custom class in `_exceptions.py`)
- Whether matured-month check in `query()` runs before or after the scope check
- Internal routing for `populate --force-refresh` (via `run_refresh(force_refresh=True)` or direct CLI dispatch)
- Whether `auto_fetch=False` also suppresses the CLI progress print
- How `cli.py` `query` command detects auto-fetch is about to happen

## Deferred Ideas

None — discussion stayed within phase scope.
