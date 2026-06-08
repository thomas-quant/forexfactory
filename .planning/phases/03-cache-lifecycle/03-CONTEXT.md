# Phase 3: Cache Lifecycle - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Three self-management capabilities layered on top of the packaged cache built in
Phases 1–2:

1. **Auto-widen on scope miss** (CACHE-03): when `query()` / `get()` detects that
   the requested currency/impact combination is absent from the manifest scope, it
   automatically calls `run_refresh()` to fetch the full missing scope and widens the
   cache before returning. No manual `populate` step required.
2. **Matured-month auto-refresh** (CACHE-05): months stored with `settled: false`
   (scraped while future-dated) are automatically re-fetched once the whole calendar
   month has passed (`_is_settled()` is already implemented in `_refresh.py`). Both
   `populate` and `query`/`get()` trigger this check.
3. **Force-refresh on demand** (CACHE-06): a new `--force-refresh` CLI flag (and
   matching library kwarg) on both `populate` and `refresh` re-scrapes a specified
   range and overwrites existing cached parquets, bypassing the skip-if-cached logic.

**In scope (Phase 3):** CACHE-03, CACHE-05, CACHE-06.

**Explicitly NOT this phase:** any new analytical fields, CLI commands other than
the additions listed above, or changes to the parquet schema (locked at schema
version 2 from Phase 2).

</domain>

<decisions>
## Implementation Decisions

### Force-refresh CLI + library surface (CACHE-06)

- **D-01: `populate --force-refresh` is a NEW flag, separate from existing `--force`.**
  `--force-refresh` re-scrapes the specified range via the network and overwrites
  existing cached parquets. The existing `--force` flag (re-process raw JSON without
  network) stays unchanged as a legacy/migration tool — the two flags are different
  operations.

- **D-02: `refresh --force-refresh` also gets the flag.** `run_refresh()` currently
  skips already-cached months unconditionally. With `force_refresh=True` it overwrites
  them. Consistent: both `populate` and `refresh` support force-refresh semantics.

- **D-03: Library kwargs mirror CLI — Phase-1 D-12 convention.**
  `forexfactory.populate(force_refresh=True, start="2025-01")` and
  `run_refresh(force_refresh=True, ...)`. The parameter name is `force_refresh` (not
  `force`) to distinguish from the existing `force` (raw-JSON reprocess) parameter on
  `run_populate()`.

- **D-04: Partial overwrite on failure.** If some months succeed and some fail during
  a `--force-refresh` run: write what succeeded, keep the prior cached parquet for
  failed months, report `fetched/skipped/failed` counts in the result dict. No
  all-or-nothing rollback.

### Auto-widen on scope miss (CACHE-03)

- **D-05: `query()` / `get()` auto-call `run_refresh()` on scope miss.** Full scope
  widen — fetch the full configured populate range for the missing currency/impact
  combination (not just the query's `--start/--end` window). Manifest scope is
  permanently widened after a successful auto-widen so future queries don't re-trigger
  a fetch.

- **D-06: Scope-miss auto-widen failure raises.** If `run_refresh()` fails during
  auto-widen (network error, bot detection, offline): raise with a descriptive error.
  No silent partial data. Multiple missing scope combos: abort on the first failure.

- **D-07: Suppressible via `auto_fetch=False` kwarg on `get()`.** Default is
  `auto_fetch=True`. Passing `auto_fetch=False` reverts to the current
  raise-on-scope-miss behavior (error message with `forexfactory populate ...`
  guidance). Intended for callers who want strict cache-only reads.

### Matured-month auto-refresh (CACHE-05)

- **D-08: Both `populate` and `query`/`get()` check for matured months.** Any manifest
  entry with `settled: false` that now passes `_is_settled()` is auto-re-fetched.
  All mature months are refreshed in one call — no per-call cap.

- **D-09: Same `auto_fetch=False` kwarg suppresses CACHE-05 as well as CACHE-03.**
  `auto_fetch=False` means "strict cache-only" for both scope-miss auto-widen and
  matured-month auto-refresh. One knob, clear semantics.

- **D-10: Matured-month re-fetch failure → serve stale + warn.** Unlike CACHE-03
  (always raise on failure), a failed matured-month re-fetch falls back to the
  existing cached parquet (which has forecast values — valid data, just missing
  actuals) and emits `logger.warning`. This is intentionally different from D-06:
  there is always a valid prior cache entry for a matured month, so crashing is
  worse than serving stale forecast-only data.

### Auto-fetch progress visibility

- **D-11: CLI prints progress; library is silent.** Print logic lives in `cli.py`'s
  `query` command, NOT in `run_refresh()` itself. This keeps the library clean —
  `get()` callers get no stdout side-effects. The `run_refresh()` engine continues to
  use `logger.info` / `logger.warning` only.

- **D-12: Two distinct preambles, shared `[N/total]` progress format.** Before the
  per-month `[N/total] YYYY-MM` lines the CLI prints one of:
  - Scope miss: `"{currency}/{impact} not in cache — fetching now..."`
  - Matured months: `"{N} months matured since last run — refreshing actuals..."`

### Claude's Discretion

The planner/researcher decides these (no user constraint beyond the decisions above):
- Exact Python exception type for CACHE-03 network failures (`NetworkError`,
  `RuntimeError`, or a custom exception class in `_exceptions.py`).
- Whether the matured-month check in `query()` runs before or after the scope check.
- How `populate --force-refresh` is internally routed — whether `run_populate()` calls
  `run_refresh(force_refresh=True)` internally or the CLI dispatches to `run_refresh()`
  directly.
- Whether `auto_fetch=False` also suppresses the CLI progress print.
- How the `cli.py` `query` command detects that an auto-fetch is about to happen (check
  scope coverage before calling `run_query`, or via a callback/return value from
  `run_query`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements
- `.planning/ROADMAP.md` §"Phase 3: Cache Lifecycle" — goal and the 3 success
  criteria (SC1/SC2/SC3 are the acceptance tests for this phase).
- `.planning/REQUIREMENTS.md` — Phase 3 owns CACHE-03, CACHE-05, CACHE-06
  (traceability table at the bottom).
- `.planning/PROJECT.md` — Key Decisions table (especially the partial
  "Cache scope auto-widen → Phase 3" entry and the "Freshness: matured-month
  auto-refresh → Phase 3" note).

### Prior context carrying forward
- `.planning/phases/02-full-analytical-schema-source-spike/02-CONTEXT.md` — for
  Phase-1 D-12 (flag↔kwarg convention) restated there; the `force` param history.
- `.planning/phases/01-installable-data-provider/01-CONTEXT.md` — D-03 (JSON-drop
  exit condition, now complete), D-12 (CLI flag↔library kwarg mirroring).

### Cache engine (key files to extend — do NOT rewrite from scratch)
- `src/forexfactory/_cache.py` — `_scope_covers()`, `update_manifest_month()`,
  `read_manifest()`, `write_manifest()`; the `settled` field in manifest months.
- `src/forexfactory/_query.py` — `run_query()` and `_raise_scope_error()` (the
  scope-miss path that CACHE-03 converts to auto-fetch); `_filter_months_by_range()`.
- `src/forexfactory/_refresh.py` — `run_refresh()`, `_is_settled()`, `_add_month()`
  (the network fetch engine; gains `force_refresh` param for CACHE-06).
- `src/forexfactory/_populate.py` — `run_populate()` with existing `force` param
  (unchanged); gains `force_refresh` param that routes to `run_refresh()`.
- `src/forexfactory/__init__.py` — `get()` library entry point that gains
  `auto_fetch=True` and `force_refresh=False` kwargs.
- `src/forexfactory/cli.py` — `query` command (gains auto-fetch progress printing,
  D-11/D-12); `populate` and `refresh` commands gain `--force-refresh` flag.

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — module responsibilities and data-flow diagram.
- `.planning/codebase/CONCERNS.md` — rate-limiting security note (non-zero delays
  remain important for any auto-triggered network calls).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_refresh.run_refresh()` — the network fetch engine; already handles
  per-month retry/skip/fail logic, delay config, and progress logging. CACHE-03 and
  CACHE-05 call it; CACHE-06 adds `force_refresh=True` to it.
- `_cache._scope_covers()` — scope check used in both `_query.run_query()` (the
  intercept point for CACHE-03) and `_populate.run_populate()`.
- `_cache._is_settled()` — already implemented in `_refresh.py`; the maturity
  predicate for CACHE-05.
- `_cache.update_manifest_month()` — union-merges scope on write; the permanent
  manifest widen after auto-fetch.
- `_query._raise_scope_error()` — current failure path for scope miss; converted to
  auto-fetch trigger by CACHE-03 (kept as a fallback when `auto_fetch=False`).

### Established Patterns
- Phase-1 D-12 flag↔kwarg convention: CLI `--force-refresh` mirrors library
  `force_refresh=True`; `--auto-fetch / auto_fetch` follows the same pattern.
- `print()` for user-facing CLI output; `logger.info` / `logger.warning` for library
  diagnostics. This split is the reason D-11 puts progress prints in `cli.py`, not
  `run_refresh()`.
- `run_refresh()` result dict (`fetched`, `skipped`, `failed`) — D-04 reuses this
  same structure for force-refresh reporting.

### Integration Points
- `_query.run_query()`: insert matured-month check and scope-miss auto-widen before
  the existing parquet-read loop. The `auto_fetch` kwarg threads down from `get()`.
- `cli.py` `query` command: add progress print banner (D-11/D-12) between the
  auto-fetch call and the final path print.
- `cli.py` `populate` / `refresh` commands: add `--force-refresh` argparse argument,
  thread to `run_populate(force_refresh=...)` / `run_refresh(force_refresh=...)`.

</code_context>

<specifics>
## Specific Ideas

- **Asymmetric failure contracts** (D-06 vs D-10): scope-miss auto-widen always raises
  on failure (no prior data); matured-month re-fetch failure serves the stale parquet
  and warns (prior data is valid — just missing actuals). The planner should implement
  these as separate code paths even if they share the same `run_refresh()` call site.
- **`auto_fetch=False` is a strict cache-only guard**: it must suppress BOTH triggers
  (CACHE-03 scope miss + CACHE-05 matured month) — user chose a single flag with clear
  semantics over two separate flags.
- **Rate-limit note**: any auto-triggered `run_refresh()` call inherits the existing
  `between_pages_delay` and `retry_delay` config. The CONCERNS.md note about non-zero
  delays applies equally here.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-Cache Lifecycle*
*Context gathered: 2026-06-08*
