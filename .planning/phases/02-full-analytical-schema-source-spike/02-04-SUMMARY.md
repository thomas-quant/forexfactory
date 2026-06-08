---
phase: 02-full-analytical-schema-source-spike
plan: 04
subsystem: data-source
tags: [curl_cffi, forexfactory, apply-settings, calendar-api, parquet, scraping]

# Dependency graph
requires:
  - phase: 02-full-analytical-schema-source-spike
    provides: "_scrape.build_session() reusable session builder; existing HTML ?month= scraper hardened by fixture tests in 02-03"

provides:
  - "Documented SRC-01 decision (SC5): NOT ADOPTED — apply-settings is settings-save only; HTML ?month= GET remains bulk primary"
  - "Full endpoint inventory for FF calendar JSON API: /calendar/more (validated fallback), /calendar/graph (future enhancement), /calendar?range= (arbitrary-date GET)"
  - "Corrected D-06 four-part evaluation for /calendar/more (all four PASS with bounded-probe caveat)"
  - "Filed SRC-GRAPH-01 (/calendar/graph numeric time-series) and SRC-MORE-01 (/calendar/more fallback) in STATE.md Deferred Items"

affects:
  - "02-05-PLAN.md (cache rebuild / raw-JSON drop)"
  - "02-02-PLAN.md (query filter)"
  - "Phase 3 cache-lifecycle work"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SRC-01 spike pattern: automated curl_cffi recon via build_session() + window.FF globals + JS bundle inspection; no browser tooling shipped (D-07)"
    - "Append-paginated endpoint documentation: /calendar/more returns fixed ~1-week chunk AFTER requested window, not the window itself"

key-files:
  created: []
  modified:
    - ".planning/phases/02-full-analytical-schema-source-spike/02-SRC01-SPIKE.md"
    - ".planning/PROJECT.md"
    - ".planning/STATE.md"

key-decisions:
  - "SRC-01 NOT ADOPTED (SC5): apply-settings is a settings-save endpoint, cannot target arbitrary historical months"
  - "/calendar/more validated as clean-JSON fallback (all 4 D-06 criteria pass) but rejected as bulk primary due to append-pagination (4-5 requests/month vs 1 for HTML ?month=)"
  - "/calendar/graph filed as SRC-GRAPH-01 future enhancement: numeric per-event time-series directly serves expected-vs-surprise core value"
  - "HTML ?month= GET + calendarComponentStates parser remains the unchanged bulk primary source"
  - "Task-1 forecast ('no clean endpoint exists') was wrong — corrected in Part 3 of spike notes"

patterns-established:
  - "Spike documentation pattern: Task-1 automated recon, Task-2 checkpoint resolution with deeper findings, corrective note that supersedes earlier forecast"

requirements-completed: [SRC-01]

# Metrics
duration: 25min
completed: 2026-06-08
---

# Phase 2 Plan 04: SRC-01 apply-settings Spike Summary

**SRC-01 NOT ADOPTED (SC5): apply-settings is settings-save only; /calendar/more is a validated clean-JSON fallback (all 4 D-06 criteria pass) but append-paginated; HTML ?month= GET remains the bulk primary; /calendar/graph filed as high-value future enhancement**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-08
- **Completed:** 2026-06-08
- **Tasks:** 3 (Task 1 from prior session, Tasks 2 + 3 in this session)
- **Files modified:** 3

## Accomplishments

- Completed the deeper curl_cffi network recon that supersedes the Task-1 "no clean endpoint" forecast — a clean JSON path DOES exist via `/calendar/more` and `/calendar/graph`, but neither is ergonomically better than the existing HTML `?month=` GET for per-month bulk extraction
- Documented the full FF calendar JSON API endpoint inventory (apply-settings, /calendar/more, /calendar/graph, /calendar?range=, wss) in `02-SRC01-SPIKE.md`
- Evaluated `/calendar/more` against the full D-06 four-part adopt-bar: all four PASS (50-field parity, arbitrary history to 2010, curl_cffi/no-auth, polite-rate stable at bounded probe scale)
- Resolved SRC-01 to NOT ADOPTED (SC5) in PROJECT.md Key Decisions with one-line evidence summary; updated active requirements
- Filed `/calendar/graph` as SRC-GRAPH-01 (high-value future enhancement: numeric per-event time-series) and `/calendar/more` as SRC-MORE-01 (documented validated fallback) in STATE.md Deferred Items
- D-07 holds: no recon tooling shipped; curl_cffi remains the sole network dependency; 119 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: Automated curl_cffi reconnaissance of the apply-settings endpoint** - `375ee29` (docs) — from prior session
2. **Task 2: Network-request recon findings + corrected D-06 evaluation** - `6815c43` (docs)
3. **Task 3: SRC-01 documented decision (SC5) + future enhancements filed** - `3bd0b5d` (docs)

**Plan metadata:** see final commit below

## Files Created/Modified

- `.planning/phases/02-full-analytical-schema-source-spike/02-SRC01-SPIKE.md` — Part 3 appended: endpoint inventory, corrected D-06 four-part result for /calendar/more, Cloudflare probe result + caveat, final NOT-ADOPTED rationale
- `.planning/PROJECT.md` — Key Decisions row resolved (NOT ADOPTED SC5); SRC-01 active requirement marked complete; Context api.txt reference updated to past tense
- `.planning/STATE.md` — Deferred Items: added SRC-GRAPH-01 and SRC-MORE-01; Blockers: resolved SRC-01 entry

## Decisions Made

**SRC-01 NOT ADOPTED (SC5):** `/calendar/more` clears all four D-06 adopt-bar criteria on data fidelity — 50-field parity with HTML extract_days, arbitrary history to 2010, curl_cffi/no-auth, polite-rate stable. It is nonetheless rejected as bulk primary because it is **append-paginated**: it returns the ~1-week chunk AFTER the requested window, requiring 4–5 sequential weekly POSTs to reconstruct one calendar month. The existing HTML `?month=` GET retrieves a clean 31-day / 350-event month in a single request. The ergonomic advantage is decisive.

**Task-1 forecast correction:** Task 1 concluded "no clean endpoint exists." This was wrong in the narrow claim. A clean JSON path does exist (via `/calendar/more` and `/calendar/graph`). Part 3 of the spike notes records the corrected picture and makes the supersession explicit.

**Future enhancement filing:** `/calendar/graph/{eventId}?limit=100&site_id={siteId}` carries per-event numeric historical time-series (actual/forecast/revision + is_most_recent, meta.is_more). This directly serves the expected-vs-surprise core value and lets a consumer pull a full event history in a few calls. Filed as SRC-GRAPH-01 in STATE.md Deferred Items for a future phase.

## Deviations from Plan

### Scope expansion (resolved in Task 2)

**[Rule 2 - Auto-add missing critical functionality] Deeper endpoint recon corrects Task-1 partial findings**

- **Found during:** Task 2 (checkpoint resolution)
- **Issue:** Task-1 automated recon did not load the `calendar-production.js` bundle (the main JS bundle) and missed three additional JSON endpoints. The original Task-1 conclusion "no clean endpoint exists" was incorrect.
- **Fix:** The orchestrator performed deeper curl_cffi recon (loading `/calendar?month=jan.2015` and analysing network requests) that discovered `/calendar/more`, `/calendar/graph`, and `/calendar?range=`. Part 3 appended to spike notes supersedes the Task-1 forecast. The final decision (NOT ADOPTED) is the same — but for the correct reason (append-pagination ergonomics, not absence of a clean endpoint).
- **Files modified:** `.planning/phases/02-full-analytical-schema-source-spike/02-SRC01-SPIKE.md`
- **Committed in:** 6815c43

---

**Total deviations:** 1 (informational correction — same outcome, improved evidence)
**Impact on plan:** The corrected recon strengthens the documented decision with accurate evidence. The NOT-ADOPTED outcome and SC5 satisfaction are unchanged.

## Issues Encountered

None beyond the Task-1 partial-findings correction addressed above. Tests stayed green throughout (119 passed, no regressions). No `_api.py` was ever created; `_refresh.py` is unchanged.

## User Setup Required

None — no external service configuration required. The spike performed network recon using the existing `curl_cffi` session infrastructure, adding no dependencies.

## Next Phase Readiness

- SRC-01 decision is documented; SC5 satisfied; Phase 2 Wave 1 unblocked for 02-02 (query no-data filter)
- `/calendar/more` is a documented fallback if the HTML parser ever fails at scale
- `/calendar/graph` is filed for a future phase to surface per-event numeric time-series
- HTML `?month=` GET + `calendarComponentStates` parser remains primary and is now protected by the fixture matrix added in 02-03

---
*Phase: 02-full-analytical-schema-source-spike*
*Completed: 2026-06-08*
