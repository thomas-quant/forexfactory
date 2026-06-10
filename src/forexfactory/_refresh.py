"""
Network Refresh — Gap-fill the Cache
======================================
Fetches months NOT yet cached over the network (via forexfactory._scrape),
stages raw JSON under the cache ``raw/`` directory, builds per-month parquet
via ``_populate.build_month_parquet``, and records provenance in manifest.json.

Supports force-refresh (CACHE-06 / D-02): force_refresh=True re-scrapes and
overwrites already-cached months on demand.
Implements auto-maturity (CACHE-05, Phase 3): refresh_matured_months() detects
months stored with settled:false that have since fully matured and re-fetches them.

Default range (D-11 / Claude's Discretion): gap-fill from the month following
the latest raw JSON already on disk through the current calendar month.

Usage:
    from forexfactory._refresh import run_refresh

    result = run_refresh(
        currencies=["USD"],
        impacts=["high", "holiday"],
        start="2026-04",       # optional, YYYY-MM
        end="2026-06",         # optional, YYYY-MM
        cache_dir=None,        # resolved via _cache.resolve_cache_dir
    )
    # result == {"fetched": N, "skipped": N, "failed": N}
"""

import glob
import json
import logging
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path

from forexfactory import _cache, _populate, _scrape

# ====== CONFIG ======
DEFAULT_CURRENCIES: list[str] = ["USD"]  # D-04
DEFAULT_IMPACTS: list[str] = ["high", "holiday"]  # D-04
# ====================

logger = logging.getLogger(__name__)


def run_refresh(
    *,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    cache_dir: Path | None = None,
    session=None,
    between_pages_delay: float | None = None,
    retry_delay: float | None = None,
    force_refresh: bool = False,
) -> dict:
    """Fetch months not yet cached over the network; stage raw + build parquet.

    Args:
        currencies: Currency filter list (default: ["USD"] — D-04).
        impacts: Impact filter list (default: ["high", "holiday"] — D-04).
        start: First month to fetch as "YYYY-MM"; defaults to gap-fill start (D-11).
        end: Last month to fetch as "YYYY-MM"; defaults to current month (D-11).
        cache_dir: Cache root directory. Resolved via _cache.resolve_cache_dir.
        session: curl_cffi session to inject (default: build_session() is called).
        between_pages_delay: Seconds between page fetches (default: _scrape.BETWEEN_PAGES_DELAY).
        retry_delay: Seconds before retrying a failed month (default: _scrape.RETRY_DELAY).
        force_refresh: When True, bypass the skip-if-cached check and re-scrape months
                       that already have non-empty raw JSON, overwriting both the staged
                       raw file and the per-month parquet. Distinct from _populate's
                       ``force`` param (which re-processes raw JSON without network) — this
                       issues live network requests (CACHE-06 / D-02). Default False
                       preserves the existing gap-fill skip behavior.

    Returns:
        dict with keys: fetched (int), skipped (int), failed (int).
    """
    # Resolve defaults (D-04)
    if currencies is None:
        currencies = DEFAULT_CURRENCIES
    if impacts is None:
        impacts = DEFAULT_IMPACTS
    if between_pages_delay is None:
        between_pages_delay = _scrape.BETWEEN_PAGES_DELAY
    if retry_delay is None:
        retry_delay = _scrape.RETRY_DELAY

    # Resolve cache dir and ensure layout exists (CACHE-01)
    resolved_cache = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(resolved_cache)

    # CR-01: When force_refresh=True, union the requested scope with the existing
    # manifest scope to prevent silently narrowing previously-cached months' parquets.
    # This mirrors widen_scope_to_cover() and run_populate()'s force_refresh path.
    # The default gap-fill path (force_refresh=False) is unchanged.
    if force_refresh:
        existing_scope = _cache.read_manifest(resolved_cache).get("scope", {})
        currencies = sorted(set(currencies) | set(existing_scope.get("currencies", [])))
        impacts = sorted(set(impacts) | set(existing_scope.get("impacts", [])))

    # Compute date range (D-11 / QUAL-04: no hardcoded defaults)
    start_date, end_date = _compute_date_range(resolved_cache, start, end)

    if start_date > end_date:
        logger.info("[refresh] nothing to do — start %s is after end %s", start_date, end_date)
        return {"fetched": 0, "skipped": 0, "failed": 0}

    pages = _scrape.build_month_pages(start_date, end_date)
    total = len(pages)
    logger.info("[refresh] fetching %d month(s) from %s to %s", total, start_date, end_date)

    # Build or reuse session
    effective_session = session or _scrape.build_session()

    fetched_count = 0
    skipped_count = 0
    failed_count = 0

    for i, page in enumerate(pages, 1):
        anchor = page.anchor
        month_key = f"{anchor:%Y-%m}"
        raw_path = _cache.raw_json_path(resolved_cache, anchor)

        # D-11 skip: month with existing non-empty raw JSON is not re-fetched.
        # An empty file from a previous QUAL-03-violating run is treated as
        # absent (size == 0 → re-fetch).
        # When force_refresh=True the skip is bypassed (CACHE-06 / D-02).
        if not force_refresh and raw_path.exists() and raw_path.stat().st_size > 0:
            logger.info("[%d/%d] Skip (cached): %s", i, total, month_key)
            skipped_count += 1
            continue

        logger.info("[%d/%d] Fetching: %s", i, total, page.url)
        days = _scrape.scrape_month(effective_session, page, retry_delay=retry_delay)
        logger.info("  -> Extracted %d days", len(days))

        # QUAL-03: only write file and record manifest when scrape succeeds.
        if not days:
            logger.warning(
                "  Skipping write for %s — no days extracted (will retry on next run)",
                month_key,
            )
            failed_count += 1
        else:
            # Stage raw JSON
            with open(raw_path, "w", encoding="utf-8") as fh:
                json.dump(days, fh, ensure_ascii=False, separators=(",", ":"))
            logger.info("  Staged: %s", raw_path)

            # Build per-month parquet (reuse _populate ETL, SRC-02)
            _populate.build_month_parquet(
                resolved_cache,
                anchor,
                days,
                currencies=currencies,
                impacts=impacts,
            )

            # Record manifest entry (D-02 / CACHE-04)
            settled = _is_settled(anchor)
            scraped_at = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            _cache.update_manifest_month(
                resolved_cache,
                anchor,
                scraped_at=scraped_at,
                settled=settled,
                currencies=currencies,
                impacts=impacts,
            )

            fetched_count += 1

        # D-11: polite delay between requests (> 0 only to avoid unnecessary sleep)
        if between_pages_delay > 0 and i < total:
            time.sleep(between_pages_delay)

    logger.info(
        "[refresh] done — fetched=%d skipped=%d failed=%d",
        fetched_count,
        skipped_count,
        failed_count,
    )
    return {"fetched": fetched_count, "skipped": skipped_count, "failed": failed_count}


def refresh_matured_months(
    cache_dir,
    *,
    session=None,
    between_pages_delay: float | None = None,
    retry_delay: float | None = None,
) -> dict:
    """Re-fetch all manifest months with settled:false that have since fully matured (CACHE-05).

    Reads the manifest scope once and re-fetches every matured month at that FULL scope so
    the rebuilt parquet retains all previously-cached currencies/impacts.  All matured months
    are refreshed in a single call — there is no per-call cap (D-08).

    On per-month failure (run_refresh reports fetched==0 or failed>0, or raises): emits
    exactly one logger.warning naming the month and continues — the stale parquet (which
    has valid forecast values) is served as-is (D-10 deliberate fail-open).  Never raises.

    Callers gate this helper via auto_fetch; this function itself has no auto_fetch guard.

    Returns:
        dict with keys: matured (int), refreshed (int), failed (int).
    """
    resolved_cache = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(resolved_cache)

    manifest = _cache.read_manifest(resolved_cache)
    scope = manifest.get("scope", {})
    scope_currencies = scope.get("currencies") or DEFAULT_CURRENCIES
    scope_impacts = scope.get("impacts") or DEFAULT_IMPACTS

    # Collect months with settled=False that now pass _is_settled() (D-08 — no cap)
    matured_keys = []
    for month_key, entry in manifest.get("months", {}).items():
        if entry.get("settled"):
            continue  # already settled — skip
        try:
            year_str, month_str = month_key.split("-")
            anchor = date(int(year_str), int(month_str), 1)
        except (ValueError, AttributeError):
            continue
        if _is_settled(anchor):
            matured_keys.append(month_key)

    if not matured_keys:
        return {"matured": 0, "refreshed": 0, "failed": 0}

    matured_count = len(matured_keys)
    refreshed_count = 0
    failed_count = 0

    for month_key in matured_keys:
        try:
            result = run_refresh(
                currencies=scope_currencies,
                impacts=scope_impacts,
                start=month_key,
                end=month_key,
                cache_dir=resolved_cache,
                session=session,
                between_pages_delay=between_pages_delay,
                retry_delay=retry_delay,
                force_refresh=True,
            )
            # D-10: fetched==0 or failed>0 means the re-scrape did not succeed
            if result.get("fetched", 0) == 0 or result.get("failed", 0) > 0:
                logger.warning(
                    "[matured] re-fetch failed for %s — serving stale cached parquet",
                    month_key,
                )
                failed_count += 1
            else:
                refreshed_count += 1
        except Exception:  # noqa: BLE001 — D-10: never raise; serve stale
            logger.warning(
                "[matured] re-fetch failed for %s — serving stale cached parquet",
                month_key,
            )
            failed_count += 1

    logger.info(
        "[matured] done — matured=%d refreshed=%d failed=%d",
        matured_count,
        refreshed_count,
        failed_count,
    )
    return {"matured": matured_count, "refreshed": refreshed_count, "failed": failed_count}


def widen_scope_to_cover(
    cache_dir,
    currencies,
    impacts,
    *,
    session=None,
    between_pages_delay: float | None = None,
    retry_delay: float | None = None,
) -> None:
    """Re-fetch the full cached month range at union scope to cover a scope-miss (CACHE-03/D-05).

    Reads the manifest to determine the existing scope and the full cached month range
    (min..max of manifest month keys), then calls run_refresh(force_refresh=True) at the
    UNION of the existing scope with the requested currencies/impacts.  This permanently
    widens the manifest scope so future queries do not re-trigger a fetch (D-05).

    Raises:
        AutoFetchError: if run_refresh raises, or if after run_refresh the manifest scope
                        still does not cover the requested currencies/impacts (D-06 fail-closed).
    """
    from forexfactory._exceptions import AutoFetchError

    resolved_cache = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(resolved_cache)

    manifest = _cache.read_manifest(resolved_cache)
    scope = manifest.get("scope", {})
    month_keys = sorted(manifest.get("months", {}).keys())

    # Compute full range (D-05: full cached range, not just a query window)
    if month_keys:
        start = month_keys[0]
        end = month_keys[-1]
    else:
        # No cached months — fall back to current month
        today = date.today()
        start = end = f"{today:%Y-%m}"

    # Compute union scope (D-05: union preserves existing currency/impact coverage)
    union_currencies = sorted(set(scope.get("currencies", [])) | set(currencies))
    union_impacts = sorted(set(scope.get("impacts", [])) | set(impacts))

    # Call run_refresh with force_refresh=True; wrap any exception as AutoFetchError (D-06)
    try:
        run_refresh(
            currencies=union_currencies,
            impacts=union_impacts,
            start=start,
            end=end,
            cache_dir=resolved_cache,
            session=session,
            between_pages_delay=between_pages_delay,
            retry_delay=retry_delay,
            force_refresh=True,
        )
    except Exception as exc:
        raise AutoFetchError(
            f"auto-fetch failed to widen scope to cover {currencies}/{impacts}: {exc}"
        ) from exc

    # Re-read manifest and confirm scope now covers the request (D-06: fail-closed, no partial data)
    manifest = _cache.read_manifest(resolved_cache)
    updated_scope = manifest.get("scope", {})
    if not _cache._scope_covers(updated_scope, currencies, impacts):
        raise AutoFetchError(f"auto-fetch failed to widen scope to cover {currencies}/{impacts}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_date_range(cache_dir: Path, start: str | None, end: str | None):
    """Return (start_date, end_date) for the refresh run.

    If start/end provided: parse and use them.
    Otherwise (QUAL-04 / D-11 gap-fill): start = month after latest raw JSON;
    end = current month.
    """
    today = date.today()
    current_month = date(today.year, today.month, 1)

    if start is not None and end is not None:
        return _parse_month_str(start), _parse_month_str(end)

    if start is not None:
        return _parse_month_str(start), current_month

    if end is not None:
        last_cached = _latest_raw_month(cache_dir)
        if last_cached is None:
            # No raw data at all; fall back to current month
            return current_month, _parse_month_str(end)
        next_month = _add_month(last_cached)
        return next_month, _parse_month_str(end)

    # Both None: gap-fill from last cached month + 1 through current month
    last_cached = _latest_raw_month(cache_dir)
    if last_cached is None:
        return current_month, current_month
    return _add_month(last_cached), current_month


def _latest_raw_month(cache_dir: Path) -> date | None:
    """Return the latest anchor date found in cache_dir/raw/, or None."""
    raw_directory = _cache.raw_dir(cache_dir)
    pattern = str(raw_directory / "days_*.json")
    paths = sorted(glob.glob(pattern))
    if not paths:
        return None
    # Parse the last (largest) path
    for p in reversed(paths):
        basename = os.path.basename(p)
        stem = basename[len("days_") : -len(".json")]  # "YYYY_MM"
        try:
            year_str, month_str = stem.split("_")
            return date(int(year_str), int(month_str), 1)
        except (ValueError, TypeError):
            continue
    return None


def _add_month(d: date) -> date:
    """Return the first day of the month following d."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _is_settled(anchor: date) -> bool:
    """Return True iff the whole calendar month is strictly before today."""
    today = date.today()
    next_month_start = _add_month(anchor)
    return next_month_start <= today


def _parse_month_str(s: str) -> date:
    """Parse a 'YYYY-MM' string into a date(year, month, 1)."""
    try:
        year_str, month_str = s.split("-")
        return date(int(year_str), int(month_str), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid month string {s!r} — expected 'YYYY-MM'") from exc
