# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — Cached Economic Calendar Data Provider

**Shipped:** 2026-06-09
**Phases:** 3 | **Plans:** 15 | **Timeline:** 3 days (2026-06-07 → 2026-06-09)

### What Was Built

- pip-installable `forexfactory` package (src layout, `pyproject.toml`); unified CLI (populate/query/refresh) + `forexfactory.get() -> pathlib.Path`
- 195-month parquet cache rebuilt to `schema_version "2"` with full analytical schema: forecast/actual/previous/revision (raw strings + parsed floats), surprise flags (`actualBetterWorse`, `revisionBetterWorse`), identity fields (`ebaseId`, `country`), `hasDataValues` — zero re-scrape
- Self-managing cache lifecycle: scope-miss auto-widen (fail-closed via `AutoFetchError`), matured-month auto-refresh (serve-stale-on-failure), force-refresh on demand (`--force-refresh` + `force_refresh=` kwarg)
- Fixture-based regression protection for the fragile `calendarComponentStates` JS parser (4 golden HTML fixtures); 169 tests total, 0 failures
- SRC-01 spike: `apply-settings` NOT ADOPTED; HTML `?month=` GET stays primary; `/calendar/more` documented as validated clean-JSON fallback; `/calendar/graph` filed as high-value future enhancement

### What Worked

- **Coarse 3-phase roadmap** held cleanly through execution with no re-planning: packaging first → schema second → lifecycle third was the right sequencing
- **TDD red-green discipline** on Phase 3 (all 3 plans used test-first): caught integration gaps that would have been runtime surprises, especially the scope-union edge cases in `widen_scope_to_cover`
- **Code review after each phase** (quick depth): CR-01 in Phase 3 caught a critical data-loss bug (force-refresh silently narrowing cached parquets to subset scope) that would have been very hard to detect in production
- **Human-verify checkpoint at D-03 (raw JSON drop)**: gating irreversible deletion behind a blocking checkpoint with explicit spot-verification worked exactly as intended; user approved confidently after seeing the verified column/dtype counts
- **Existing scrape logic reused directly** (SRC-02): relocating `scrape.py`/`pipeline.py` under `src/forexfactory/` rather than rewriting avoided a high-risk parser rewrite; the SRC-01 spike confirmed this was correct
- **`manifest.json` sidecar pattern**: per-month parquets + a single manifest for scope/maturity tracking turned out to be the right cache contract; all three cache lifecycle features (scope-miss, matured, force-refresh) built cleanly on it

### What Was Inefficient

- **SRC-01 spike planning**: the spike was planned in Phase 2 Wave 1 alongside schema work; in hindsight it could have been done earlier (or even pre-planning) since the outcome (`apply-settings` is settings-save only) was architecturally load-bearing — if the API had worked, Phase 1's scrape relocation would have been unnecessary
- **STATE.md decision log format**: decisions were accumulated with `[Phase ?]` markers (unresolved phase references) because the log was updated incrementally; cleaner to batch-update after each phase transition
- **AGENTS.md + v1.0-MILESTONE-AUDIT.md untracked files at close**: these were left as untracked in git status at the start of the milestone close, suggesting the audit workflow doesn't auto-stage its output file

### Patterns Established

- **Fail-closed auto-fetch**: any automatic network operation raises a typed exception (`AutoFetchError`) on failure rather than silently serving partial/stale data; callers get a clean non-zero exit
- **Serve-stale-on-failure for matured months**: auto-refresh failure returns the existing (forecast-only) parquet with a warning rather than crashing; only the D-12 banner count is under-reported in pathological cases (IN-02)
- **`progress=` callback to separate CLI output from library silence**: `run_query`/`run_populate` accept a callable so the library API stays stdout-silent while the CLI prints structured progress banners
- **Doc-regression gate**: `tests/test_docs.py` asserts README structure chart and schema table stay honest after each code change; caught stale claims twice during Phase 1 and 2

### Key Lessons

1. **Code review after each phase, not just at milestone end** — CR-01 (critical data-loss bug) was found in Phase 3 code review, not the milestone audit. Quick-depth review after each phase is cheap and catches regressions while context is fresh.
2. **Irreversible data operations need explicit human gates** — the D-03 raw JSON deletion was gated on a human-verify checkpoint that required spot-verification before approval; the pattern should be applied to any future operation that destroys source data.
3. **Scope-union correctness is subtle** — the first implementation of `run_refresh` in force-refresh mode narrowed the manifest scope to the requested subset instead of unioning with existing scope (CR-01); any future code that rewrites a manifest entry needs an explicit union step and a test for it.
4. **`calendarComponentStates` parser is the highest ongoing risk** — it walks raw JS character-by-character and breaks silently on FF bundle changes; the 4 golden fixtures provide regression coverage but the right long-term mitigation is to adopt `/calendar/more` (validated clean-JSON fallback) if parsing fails in production.
5. **SRC-GRAPH-01 is the right next investment** — `/calendar/graph/{eventId}?limit=100&site_id={siteId}` returns clean numeric per-event historical time-series directly serving the expected-vs-surprise core value; this is higher priority than the DIST-01 PyPI publish.

### Cost Observations

- Sessions: ~3 planning + ~15 execution (one per plan) + 1 audit + 1 milestone close
- Notable: 3-day end-to-end from codebase map to shipped milestone; coarse 3-phase structure kept total planning overhead low relative to execution work

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 15 | First structured GSD milestone; established manifest-sidecar cache pattern and fail-closed auto-fetch convention |

### Cumulative Quality

| Milestone | Tests | Notes |
|-----------|-------|-------|
| v1.0 | 169 | 0 failures; fixture-based parser regression coverage added in Phase 2 |

### Top Lessons (Verified Across Milestones)

1. Quick code review after each phase catches critical bugs while context is warm — don't defer to milestone close
2. Irreversible data operations (deletion, schema rebuild) need explicit human-verify checkpoints with spot-verification evidence
