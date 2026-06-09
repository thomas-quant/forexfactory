# Phase 3: Cache Lifecycle - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 5 (all existing files modified — no new files)
**Analogs found:** 5 / 5 (all analogs drawn from within the same modified files)

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/forexfactory/_refresh.py` | service | request-response (network fetch) | `_populate.run_populate()` `force` param (same file's skip-check block) | exact |
| `src/forexfactory/_query.py` | service | request-response (cache read) | `_query._raise_scope_error()` call site; `_populate.run_populate()` manifest loop | exact |
| `src/forexfactory/_populate.py` | service | CRUD (disk ETL) | `_populate.run_populate()` existing `force` param | exact |
| `src/forexfactory/__init__.py` | library entry point | request-response (delegation) | `get()` existing keyword-only signature | exact |
| `src/forexfactory/cli.py` | CLI | request-response | `--force` flag pattern; `print(path)` vs `logger.info` split | exact |

---

## Pattern Assignments

### `src/forexfactory/_refresh.py` (service, request-response) — CACHE-06

**Change:** Add `force_refresh: bool = False` kwarg. When `True`, bypass the "existing non-empty raw JSON" skip check so already-cached months are re-scraped and their parquets overwritten.

**Analog for new param signature** — `_populate.run_populate()` lines 117–118 and 210–215:
```python
# _populate.py lines 109-118: existing force param signature and docstring pattern
def run_populate(
    *,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    raw_dir: str = RAW_INPUT_DIR,
    cache_dir: Path | None = None,
    force: bool = False,
) -> dict:
```

**Analog for skip-check bypass** — `_populate.py` lines 210–215 (`if not force:` guards the skip):
```python
# _populate.py lines 210-215
if not force:
    cached_entry = manifest.get("months", {}).get(month_key)
    if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
        logger.info("[%d/%d] Skip (cached at scope): %s", i, total, month_key)
        skipped_count += 1
        continue
```

**Existing skip-check to bypass in `_refresh.py`** — lines 110–113 (the block that `force_refresh=True` must skip):
```python
# _refresh.py lines 110-113
if raw_path.exists() and raw_path.stat().st_size > 0:
    logger.info("[%d/%d] Skip (cached): %s", i, total, month_key)
    skipped_count += 1
    continue
```

**Result dict shape** (unchanged — D-04 reuses this) — `_refresh.py` line 161:
```python
return {"fetched": fetched_count, "skipped": skipped_count, "failed": failed_count}
```

**Progress log format** — `_refresh.py` lines 111–115 (`[N/total]` prefix, logger not print):
```python
logger.info("[%d/%d] Skip (cached): %s", i, total, month_key)
# ...
logger.info("[%d/%d] Fetching: %s", i, total, page.url)
```

**Summary log pattern** — `_refresh.py` lines 157–160:
```python
logger.info(
    "[refresh] done — fetched=%d skipped=%d failed=%d",
    fetched_count, skipped_count, failed_count,
)
```

---

### `src/forexfactory/_query.py` (service, request-response) — CACHE-03 + CACHE-05

**Changes:**
- Add `auto_fetch: bool = True` kwarg.
- CACHE-05 (before scope check): iterate manifest months, collect entries where `settled: false` and `_is_settled()` is now `True`; call `run_refresh()` for them. On failure: `logger.warning`, serve stale (do not raise).
- CACHE-03 (replaces unconditional `_raise_scope_error` call): if `auto_fetch=True`, call `run_refresh()` to widen scope; on failure: raise. If `auto_fetch=False`: call `_raise_scope_error()` as before.

**Existing scope-miss intercept point** — `_query.py` lines 137–139 (the block CACHE-03 converts to a conditional):
```python
# _query.py lines 137-139
if not scope or not _cache._scope_covers(scope, currencies, impacts):
    _raise_scope_error(currencies, impacts, scope)
```

**`_raise_scope_error` kept as the `auto_fetch=False` fallback** — `_query.py` lines 74–100:
```python
def _raise_scope_error(
    currencies: list,
    impacts: list,
    scope: dict,
) -> None:
    """Raise ValueError with actionable populate guidance for each uncovered pair (D-09)."""
    cached_currencies: set = set(scope.get("currencies", []))
    cached_impacts: set = set(scope.get("impacts", []))
    messages = []
    for c in currencies:
        for i in impacts:
            if c not in cached_currencies or i not in cached_impacts:
                messages.append(
                    f"{c}/{i} not populated — run: forexfactory populate"
                    f" --currency {c} --impact {i}"
                )
    if not messages:
        messages = ["cache not populated — run: forexfactory populate"]
    raise ValueError("\n".join(messages))
```

**Analog for manifest months iteration (CACHE-05)** — `_populate.run_populate()` lines 177–183:
```python
# _populate.py lines 177-183: read manifest once; iterate months dict
manifest = _cache.read_manifest(resolved_cache)
original_scope = manifest.get("scope", {})
# ...
for i, (anchor, raw_path) in enumerate(anchors, 1):
    month_key = f"{anchor:%Y-%m}"
    # ...
    cached_entry = manifest.get("months", {}).get(month_key)
```

**`settled` field in manifest months** — `_cache.py` lines 157–160:
```python
manifest.setdefault("months", {})[f"{anchor:%Y-%m}"] = {
    "scraped_at": scraped_at,
    "settled": settled,
}
```

**`_is_settled()` predicate (already implemented in `_refresh.py`)** — lines 225–229:
```python
def _is_settled(anchor: date) -> bool:
    """Return True iff the whole calendar month is strictly before today."""
    today = date.today()
    next_month_start = _add_month(anchor)
    return next_month_start <= today
```

**Warn-and-serve-stale pattern (CACHE-05 failure)** — `_populate.py` lines 195–200 (warn + skip, do not raise):
```python
# _populate.py lines 196-200: warning + skip without raise — analog for D-10 stale-serve
except json.JSONDecodeError:
    logger.warning("[%d/%d] bad JSON in %s — skipping", i, total, raw_path)
    empty_count += 1
    continue
```

**Resolved cache + ensure_dirs preamble** — `_query.py` lines 131–132 (copy for any new call site that needs a resolved cache):
```python
cache_dir = _cache.resolve_cache_dir(cache_dir)
_cache.ensure_dirs(cache_dir)
```

---

### `src/forexfactory/_populate.py` (service, CRUD) — CACHE-06 + CACHE-05

**Changes:**
- Add `force_refresh: bool = False` kwarg. Routes to `run_refresh(force_refresh=True)` for the months in range rather than re-processing raw JSON. Distinct from existing `force` (which reprocesses raw JSON without network).
- CACHE-05: iterate manifest months; re-fetch any with `settled: false` that now pass `_is_settled()`.

**Existing `force` param — direct analog for `force_refresh`** — `_populate.py` lines 117–130 (signature + docstring pattern to copy):
```python
def run_populate(
    *,
    # ...
    force: bool = False,
) -> dict:
    """...
    Args:
        force: When True, rebuild every month unconditionally, bypassing the
               manifest skip-check. Used for Phase-2 schema migration (RESEARCH
               Pattern 6). CLI --force flag is in plan 02-02 (cli.py ownership).
    ...
    """
```

**Existing `force` skip-bypass block** — `_populate.py` lines 210–215 (exact analog for `force_refresh` bypass structure):
```python
if not force:
    cached_entry = manifest.get("months", {}).get(month_key)
    if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
        logger.info("[%d/%d] Skip (cached at scope): %s", i, total, month_key)
        skipped_count += 1
        continue
```

**Manifest-months iteration for CACHE-05** — `_populate.py` lines 177–183 (same pattern reused):
```python
manifest = _cache.read_manifest(resolved_cache)
original_scope = manifest.get("scope", {})
today = date.today()
for i, (anchor, raw_path) in enumerate(anchors, 1):
    month_key = f"{anchor:%Y-%m}"
    # ...
    cached_entry = manifest.get("months", {}).get(month_key)
```

**Result dict return** — `_populate.py` lines 241–252:
```python
logger.info(
    "[populate] done — populated=%d skipped=%d empty=%d",
    populated_count, skipped_count, empty_count,
)
# ...
return {"populated": populated_count, "skipped": skipped_count, "empty": empty_count}
```

---

### `src/forexfactory/__init__.py` (library entry point) — CACHE-03 + CACHE-05 + CACHE-06

**Change:** Add `auto_fetch: bool = True` and `force_refresh: bool = False` keyword-only params to `get()`; thread both through to `_query.run_query()`.

**Existing `get()` signature — exact pattern to extend** — `__init__.py` lines 18–26:
```python
def get(
    *,
    currencies=None,
    impacts=None,
    start=None,
    end=None,
    include_no_data=False,
    cache_dir=None,
) -> Path:
```

**Existing kwarg threading — pass-through pattern** — `__init__.py` lines 33–40:
```python
from . import _query  # noqa: PLC0415 — intentional lazy import
return _query.run_query(
    currencies=currencies,
    impacts=impacts,
    start=start,
    end=end,
    include_no_data=include_no_data,
    cache_dir=cache_dir,
)
```

The new params `auto_fetch` and `force_refresh` follow identical pass-through to `run_query(auto_fetch=auto_fetch, force_refresh=force_refresh)`.

---

### `src/forexfactory/cli.py` (CLI) — CACHE-06 on populate + refresh; CACHE-03/05 progress printing on query

**Changes:**
- `populate` subparser: add `--force-refresh` flag; thread to `run_populate(force_refresh=args.force_refresh)`.
- `refresh` subparser: add `--force-refresh` flag; thread to `run_refresh(force_refresh=args.force_refresh)`.
- `query` dispatch: before calling `run_query()`, check scope coverage and matured months; print D-12 preamble banners to stdout; thread `auto_fetch=True` (default).

**`--force` flag — exact analog for `--force-refresh`** — `cli.py` lines 107–111 (argparse definition):
```python
pop.add_argument(
    "--force",
    action="store_true",
    default=False,
    help="Force rebuild all months even if already cached [Phase-2 migration]",
)
```

**`force` threading in populate dispatch** — `cli.py` lines 219–233:
```python
if args.command == "populate":
    cache_dir = Path(args.cache_dir) if args.cache_dir is not None else None
    result = _populate.run_populate(
        currencies=args.currency,
        impacts=args.impact,
        start=args.start,
        end=args.end,
        raw_dir=args.raw_dir,
        cache_dir=cache_dir,
        force=args.force,
    )
    logger.info(
        "[populate] done — populated=%d skipped=%d empty=%d",
        result["populated"], result["skipped"], result["empty"],
    )
    return 0
```

**`print` vs `logger` split for query** — `cli.py` lines 236–254:
```python
if args.command == "query":
    cache_dir = Path(args.cache_dir) if args.cache_dir is not None else None
    try:
        path = _query.run_query(
            currencies=args.currency,
            impacts=args.impact,
            start=args.start,
            end=args.end,
            include_no_data=args.include_no_data,
            cache_dir=cache_dir,
        )
    except ValueError as exc:
        # D-09: out-of-scope query — print guidance to stderr, exit non-zero
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    # D-10: stdout = ONLY the absolute path; all diagnostics go to logger (stderr)
    print(path)
    return 0
```

**D-12 preamble banners (new, by convention):** The scope-miss banner and matured-month banner are `print()` calls — one to stdout before the auto-fetch begins. They follow the `print(path)` convention (user-facing stdout), NOT `logger.info`. The `[N/total]` per-month progress during auto-fetch continues to live in `logger.info` inside `run_refresh()` (visible on stderr via `logging.basicConfig`). The two distinct preamble strings from D-12:
```
"{currency}/{impact} not in cache — fetching now..."
"{N} months matured since last run — refreshing actuals..."
```

**`_validate_month` pattern for new args** — `cli.py` lines 44–59 (applies to `--start`/`--end` on all subcommands; `--force-refresh` needs no validation since it is `store_true`):
```python
def _validate_month(value: str | None, name: str) -> None:
    """Validate that a --start or --end value has YYYY-MM shape; sys.exit(1) if not."""
    if value is None:
        return
    try:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError("expected exactly two dash-separated parts")
        year, month = int(parts[0]), int(parts[1])
        if not (1 <= month <= 12):
            raise ValueError(f"month {month} out of range 1–12")
    except (ValueError, AttributeError):
        logger.error("Invalid %s %r — expected YYYY-MM (e.g. 2024-03)", name, value)
        sys.exit(1)
```

---

## Shared Patterns

### Keyword-only function signatures (project-wide convention)
**Source:** `_populate.py` line 110, `_refresh.py` line 44, `_query.py` line 107 — all public engine functions use `*` to enforce keyword-only call sites. Every new param (`force_refresh`, `auto_fetch`) must appear after `*` in the signature.

### `[module] done — key=val key=val` summary log
**Source:** `_refresh.py` lines 157–160; `_populate.py` lines 240–243
**Apply to:** All engine function return points
```python
logger.info(
    "[refresh] done — fetched=%d skipped=%d failed=%d",
    fetched_count, skipped_count, failed_count,
)
```

### `[N/total]` per-item progress log
**Source:** `_refresh.py` lines 111, 115; `_populate.py` lines 194, 203, 218, 237
**Apply to:** Any new loop over month anchors
```python
logger.info("[%d/%d] Skip (cached): %s", i, total, month_key)
logger.info("[%d/%d] Fetching: %s", i, total, page.url)
```

### `print()` for CLI user output; `logger.*` for diagnostics
**Source:** `cli.py` lines 248–253
**Apply to:** `cli.py` query command auto-fetch preamble (D-11). `run_refresh()` and `run_query()` must never call `print()`.

### `_cache.resolve_cache_dir` + `_cache.ensure_dirs` preamble
**Source:** `_refresh.py` lines 81–82; `_query.py` lines 131–132; `_populate.py` lines 142–143
**Apply to:** Any new function or code path that resolves a cache directory
```python
resolved_cache = _cache.resolve_cache_dir(cache_dir)
_cache.ensure_dirs(resolved_cache)
```

### Atomic manifest write via `update_manifest_month`
**Source:** `_refresh.py` lines 140–149; `_populate.py` lines 228–235
**Apply to:** Any code path that re-fetches a month and records provenance. Call `update_manifest_month` with the full `scraped_at`, `settled`, `currencies`, `impacts` kwargs — do not call `write_manifest` directly from engine functions.

### `_is_settled()` import boundary
**Source:** `_refresh.py` lines 225–229 — `_is_settled` lives in `_refresh.py`, not `_cache.py`
**Apply to:** `_query.py` and `_populate.py` must import it as `from forexfactory._refresh import _is_settled` (or via `_refresh._is_settled`) rather than reimplementing it.

### Exception type for CACHE-03 network failure (discretionary — to be decided by planner)
**Context:** D-06 says scope-miss auto-widen failure must raise with a descriptive error. No custom exception class exists yet.
- Option A: raise `RuntimeError(f"auto-fetch failed for {c}/{i}: ...")` — zero new files, consistent with stdlib-only error approach
- Option B: add `src/forexfactory/_exceptions.py` with a `NetworkError(RuntimeError)` class — allows callers to catch specifically
- Recommendation pattern: the codebase currently uses `ValueError` for user input errors (`_raise_scope_error`, `_parse_month_str`) and `FileNotFoundError` for missing inputs (`_populate`). A distinct `RuntimeError` subclass (either inline or in `_exceptions.py`) cleanly separates network failures from schema/input errors. Either is valid; planner decides.

---

## No Analog Found

All five modified files have strong analogs within the same file set. No file is without a pattern.

---

## Metadata

**Analog search scope:** `src/forexfactory/` (all five files listed in the phase context)
**Files read:** 7 (`03-CONTEXT.md`, `_cache.py`, `_query.py`, `_refresh.py`, `_populate.py`, `__init__.py`, `cli.py`)
**Pattern extraction date:** 2026-06-09
