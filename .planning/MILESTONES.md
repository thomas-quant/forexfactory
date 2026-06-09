# Milestones: forexfactory

---

## v1.0 — Cached Economic Calendar Data Provider

**Shipped:** 2026-06-09
**Phases:** 3 (Phases 1–3)
**Plans:** 15
**Timeline:** 2026-06-07 → 2026-06-09 (3 days)
**Commits:** ~101 | **LOC:** ~6,884 Python (2,440 src + 4,444 tests)

**Delivered:**
Turned two loose scripts and ~195 months of scraped data into a pip-installable `forexfactory` package with a shared parquet cache, unified CLI (populate/query/refresh), library API (`get() -> Path`), full analytical schema (forecast/actual/previous/revision raw+parsed, surprise flags, identity fields), and a self-managing cache lifecycle (scope-miss auto-widen, matured-month auto-refresh, force-refresh on demand).

**Key Accomplishments:**
1. pip-installable `forexfactory` package (src layout, `pyproject.toml`); CLI + `import forexfactory` + `get() -> Path`
2. 195-month parquet cache rebuilt at `schema_version "2"` with full analytical schema — zero re-scrape
3. Fixture-based regression tests protecting the fragile `calendarComponentStates` parser; 169 tests total
4. Self-managing cache: scope-miss auto-widen (`AutoFetchError` fail-closed), matured-month auto-refresh (serve-stale-on-failure), force-refresh on demand
5. FF `/calendar/more` and `/calendar/graph` documented as validated fallback / future enhancement; HTML parse stays primary (SRC-01 spike)
6. CR-01: critical force-refresh scope-narrowing data-loss bug caught in code review and fixed (union manifest scope before rebuild)

**Test suite:** 169 tests, 0 failures

**Tech Debt Deferred:**
- IN-01, IN-02: low-severity refactors (scope-union extraction, silent except pass in matured loop)
- DIST-01: PyPI publish (v2)
- CACHE-V2-01: chunked/streaming for wide scopes (v2)
- SRC-GRAPH-01: `/calendar/graph` numeric per-event time-series (future enhancement)
- SRC-MORE-01: `/calendar/more` clean-JSON fallback (documented, not adopted as primary)

**Archives:**
- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
- [v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md)

---
