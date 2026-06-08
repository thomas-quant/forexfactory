# SRC-01 Spike Notes: FF `apply-settings` POST Endpoint Investigation

**Spike date:** 2026-06-08
**Status:** Task 1 (automated curl_cffi recon) COMPLETE — awaiting Task 2 (human DevTools capture)

---

## Part 1: Automated curl_cffi Reconnaissance (Task 1)

### Environment

- curl_cffi: available (imported from installed environment)
- Network access: available (confirmed via socket test)
- Recon approach: `_scrape.build_session()` + Chrome impersonation (D-07)
- No new dependencies added to pyproject.toml (D-07 constraint respected)

### Step 1: GET /calendar — Session Establishment

```
GET https://www.forexfactory.com/calendar
  → HTTP 200 (text/html; charset=ISO-8859-1, ~380 KB)
```

**Cookies set by server:**

| Cookie name | Shape | Notes |
|---|---|---|
| `fflastvisit` | `<10-char>` (epoch seconds) | Last visit timestamp |
| `fflastactivity` | `<1-char>` | Activity flag |
| `ffsettingshash` | `<32-char>` (hex hash) | Settings fingerprint |
| `fftab-history` | `<8-char>` | Tab navigation history |
| `__cf_bm` | `<221-char>` | Cloudflare Bot Management token |

Cookie values REDACTED — only shape and presence recorded.

**No CSRF token found** in response headers or HTML body. No `X-CSRF-Token` header.

**Key JS globals in `window.FF` object:**
```
calendar_feed_endpoint: 'wss://calendar-feed.forexfactory.com:2087'
npd_api_endpoint: 'https://npd-api.forexfactory.com/api.php'
mds_api_endpoint: 'https://mds-api.forexfactory.com'
bds_api_endpoint: 'https://bds-api.forexfactory.com'
explorer_api_endpoint: 'https://explorer-api.forexfactory.com/api.php/'
```

None of these are `apply-settings`. The `apply-settings` URL does **not** appear anywhere in the HTML response body or in any of the JS files loaded by the calendar page (`flex.js`, `site.js`, `ffsettings.js`, `common-production.js`, `ff_util.js`, `data_store.js`).

**`calendarComponentStates` embedding:** The current week's data is embedded inline in a `<script>` block as `window.calendarComponentStates[1] = { days: [...] }` (form 2 assignment). The current session returned data for the week of Jun 7-13, 2026.

### Step 2: Apply-Settings POST Reconnaissance

**Endpoint tested:** `https://www.forexfactory.com/calendar/apply-settings/100000`
(Note: `100000` from `api.txt`/PROJECT.md lead; the actual `calendarComponentStates` index is `1` not `100000`.)

**Headers used for POST:**
```
Accept: application/json, text/javascript, */*; q=0.01
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: https://www.forexfactory.com/calendar
Origin: https://www.forexfactory.com
```
Plus all standard HEADERS from `_scrape.py` (accept, accept-language, cache-control, user-agent, etc.).

**POST tests and results:**

| Test | params | body | HTTP status | begin_date | days returned |
|---|---|---|---|---|---|
| navigation=0 | `?navigation=0` | — | 200 | June 7, 2026 | 7 |
| navigation=1 | `?navigation=1` | — | 200 | June 7, 2026 | 7 |
| navigation=-1 | `?navigation=-1` | — | 200 | June 7, 2026 | 7 |
| month=jan.2015 (body) | — | `month=jan.2015` | 200 | June 7, 2026 | 7 |
| month=mar.2018 (body) | — | `month=mar.2018` | 200 | June 7, 2026 | 7 |
| month=jan.2015 (params) | `?month=jan.2015` | — | 200 | June 7, 2026 | 7 |
| week=jan4.2015 (body) | — | `week=jan4.2015` | 200 | June 7, 2026 | 7 |
| default_view + month (body) | — | `default_view=monthly&month=jan.2015` | 200 | June 7, 2026 | 7 |

**Critical observation:** All POST requests returned *identical* `begin_date='June 7, 2026'` (the current week). Neither `navigation`, `month`, nor `week` parameters changed the returned date range.

**Also tested:** alternate calendarId `1` (the actual `calendarComponentStates` index):
- `POST apply-settings/1?navigation=0` → HTTP 200, `begin_date='June 7, 2026'`, 7 days
- Same result as `apply-settings/100000` — calendarId value makes no difference.

**Also tested:** GET to `?month=jan.2015` followed by POST with different navigation values:
- After navigating to January 2015 via GET, all `POST apply-settings?navigation=N` still returned `begin_date='June 7, 2026'`
- The server's "current" position is pinned to the wall clock, not the session's navigated position.

### Step 3: Inspecting the Response Structure

**Full response JSON shape** (HTTP 200, application/json):

```json
{
  "settings": {
    "default_view": "this_week",
    "impacts": [3, 2, 1, 0],
    "event_types": [1, 2, 3, 4, 5, 7, 8, 9, 10, 11],
    "currencies": [1, 2, 3, 4, 5, 6, 7, 8, 9],
    "begin_date": "June 7, 2026",
    "end_date": "June 13, 2026"
  },
  "navigation": {
    "last": {"url": "\\/calendar?week=may31.2026", ...},
    "current": {"url": "\\/calendar?week=jun7.2026", ...},
    "next": {"url": "\\/calendar?week=jun14.2026", ...}
  },
  "days": [ ... 7 day objects ... ],
  "more": ...,
  "append": ...,
  "upnext": ...,
  "mini": ...
}
```

**Event field set** (full inventory from first event):
```
actual, actualBetterWorse, checkedIn, checker, country, currency, date,
dateline, ebaseId, editUrl, enableActualComponent, enableDetailComponent,
enableExpandComponent, firstInDay, forecast, greyed, hasDataValues,
hasGraph, hasLinkedThreads, hasNotice, hideHistory, hideSoloPage, id,
impactClass, impactName, impactTitle, isMasterList, isSubscribable,
isSubscribed, leaked, name, notice, prefixedName, previous, releaser,
revision, revisionBetterWorse, showDetails, showExpanded, showGraph,
showGridLine, siteId, soloTitle, soloTitleFull, soloTitleShort, soloUrl,
timeLabel, timeMasked, trimmedPrefixedName, upNext, url
```

This is the **same field set** as the HTML `calendarComponentStates` embedded object.

**All D-01 target fields are present:**
`forecast`, `actual`, `previous`, `revision`, `actualBetterWorse`,
`revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`, `id`, `leaked`,
`currency`, `impactName`, `dateline`, `prefixedName`.

### Step 4: GET-based Historical Month Navigation (Baseline Comparison)

To confirm what *does* work for historical months:

| Request | HTTP | days | events | Data values present? |
|---|---|---|---|---|
| `GET /calendar?month=jan.2015` | 200 | 31 | 350 | Yes (actual='-21.2%', forecast='') |
| `GET /calendar?month=mar.2018` | 200 | 31 | 407 | Yes (actual='0.6%', forecast='0.6%') |
| `GET /calendar?week=jan4.2015` | 200 | 7 | 86 | Yes (actual='46.9') |

The **existing HTML scraper approach** (GET `?month=`) retrieves arbitrary historical months, with all 50+ event fields embedded in `calendarComponentStates` JS.

### Step 5: Where `apply-settings` Actually Appears

`apply-settings` was searched for in:
- The `text/html` response body (~380 KB): **0 occurrences**
- `ffsettings.js` (1,268 B), `site.js` (1,181 B), `ff_util.js` (5,310 B): **0 occurrences**
- `data_store.js` (83 B): **0 occurrences**
- `common-production.js` (196 KB TypeScript bundle): **0 occurrences**
- `flex.js` (24 KB): **0 occurrences** (no calendar URL patterns at all)

The `apply-settings` URL is never referenced in the static JS bundles served during the session.
The URL `https://www.forexfactory.com/calendar/apply-settings/100000?navigation=1` in the original `api.txt` lead is likely:
- Captured during a browser session where the FF calendar JavaScript (dynamically loaded) made a POST to save/apply the user's filter settings (currencies, impact levels)
- The `/100000` may be a session-specific or A/B-test-specific calendar component ID that was active when it was captured, and is now replaced by `1` as the `calendarComponentStates` index

---

## D-06 Four-Part Adopt-Bar: Automated Recon Assessment

### Criterion 1: No field regression (all target fields present)

**Result: PASS (conditional)**

The `apply-settings` response event dict contains all D-01 target fields:
`forecast`, `actual`, `previous`, `revision`, `actualBetterWorse`,
`revisionBetterWorse`, `ebaseId`, `country`, `hasDataValues`, `id`, `leaked`.

However: the current-week response had `forecast=''`, `actual=''` (no-data events), so no
live data was compared against the HTML parse. The field schema matches — actual value
populations would require a data-bearing week.

### Criterion 2: Arbitrary historical months back to 2010

**Result: FAIL (definitive)**

Every POST to `apply-settings` returned the current week (Jun 7-13, 2026), regardless of:
- `navigation` parameter value (-1, 0, 1)
- `month=` or `week=` in body or query params
- Prior GET navigation to a historical month
- Different calendarId values (100000 vs 1)

The endpoint is **server-state-pinned to the current week**. It does not support targeting
arbitrary historical months via any parameter combination tested.

### Criterion 3: Works via curl_cffi, no auth

**Result: PARTIAL (moot given Criterion 2 failure)**

The basic 5-cookie session from a prior GET is sufficient for the POST to return HTTP 200.
No CSRF token is required. curl_cffi Chrome impersonation works without login.

However, the endpoint can only return the current week, making it unsuitable as a historical
data source regardless of curl_cffi compatibility.

### Criterion 4: Stable at polite rate

**Result: UNDETERMINED (moot given Criterion 2 failure)**

Rate testing was not performed since Criterion 2 fails definitively.

---

## Overall D-06 Result: NOT ADOPTED

The `apply-settings` endpoint fails the adopt-bar at Criterion 2 (arbitrary historical months).

- It is a **settings-save endpoint** (stores user filter preferences: currencies, impacts,
  event types) that also returns the current week's structured data as a side effect.
- It is NOT a historical data retrieval endpoint.
- The correct interpretation of the `api.txt` lead is that clicking the navigation arrows
  in a browser fires a POST that combines "save settings + return current view data" rather
  than "navigate to a specific month".

**The existing HTML-scrape-and-parse approach (`GET /calendar?month=`) remains primary.**
It is confirmed to reach arbitrary historical months back to at least 2010 (195 months already
cached). All 50+ event fields — including all D-01 analytical targets — are embedded in the
inline `calendarComponentStates` JS object in every HTML response.

---

## Part 2: Live DevTools Capture (Task 2 — PENDING HUMAN INPUT)

The automated recon above confirms the automated findings but cannot substitute for an
actual browser DevTools capture. The human checkpoint (Task 2) asks:

1. Open https://www.forexfactory.com/calendar in a browser with DevTools → Network tab
2. Click prev/next navigation arrows; find any POST to `/calendar/apply-settings/...`
3. Note the full URL, request headers, body/params, and response JSON shape
4. If possible, confirm whether any navigation mechanism reaches arbitrary historical months

The human can also confirm the automated finding by observing that navigation uses
`data-endpoint="?week=jun7.2026&date=may1.2026"` (a GET pattern, not a POST).

**Expected outcome from human recon:** confirm that:
- Navigation clicks fire GET requests (not POSTs) to `/calendar?week=...&date=...`
- `apply-settings` POSTs are only fired when the user changes filter settings (currencies, impacts)
- No POST mechanism exists for fetching arbitrary historical months

---

## Pending: Task 3 (Post-human-checkpoint)

Task 3 will:
1. Append the human DevTools capture findings
2. Write the formal D-06 four-criteria decision
3. Update `.planning/PROJECT.md` Key Decisions with the SRC-01 outcome (SC5)

Current forecast: NOT ADOPTED (HTML parse stays primary; apply-settings is a settings-save
endpoint only). SC5 will be satisfied with a "not adopted" decision backed by this evidence.
