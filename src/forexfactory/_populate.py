"""
Populate Cache from On-Disk Raw JSON
=====================================
Ingests the existing per-month days_*.json files from the raw input directory
into per-month parquet files under the cache, recording scope + provenance in
manifest.json.

With auto_fetch=True (default): auto-refreshes matured months over the network
before the disk-ingest loop (CACHE-05 / D-08).  Use auto_fetch=False for strict
cache-only behavior with zero network calls.

Usage:
    from forexfactory._populate import run_populate
    result = run_populate(cache_dir="/path/to/cache", raw_dir="out")
    # result == {"populated": N, "skipped": N, "empty": N}
"""
import glob
import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from forexfactory import _cache, _pipeline

# ====== CONFIG ======
RAW_INPUT_DIR: str = "out"                    # legacy on-disk asset location (D-05 / SC2)
DEFAULT_CURRENCIES: list[str] = ["USD"]       # D-04
DEFAULT_IMPACTS: list[str] = ["high", "holiday"]  # D-04
# Nullable-int columns: cast after DataFrame construction to guarantee Int64 parquet
# dtype even when some rows have None (T-02-02 / RESEARCH Pattern 4).
INT_NULLABLE_COLS: list[str] = ["id", "ebaseId", "actualBetterWorse", "revisionBetterWorse"]
# ====================

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-month builder (D-01 / DATA-01)
# ---------------------------------------------------------------------------

def build_month_parquet(
    cache_dir: Path,
    anchor: date,
    days: list,
    *,
    currencies: list[str],
    impacts: list[str],
) -> int:
    """Build a per-month parquet from raw days list, write to cache, return row count.

    Reuses _pipeline.flatten_events, _deduplicate_rows, and write_parquet so the
    ETL logic stays in one place (QUAL-01 reuse). Speech events are retained in cache
    and filtered at query time per D-09 — the populate path does NOT apply the
    legacy 'speaks' drop (that filter lives only in the _pipeline.run_pipeline() legacy path).
    """
    # Flatten + filter
    rows = []
    for r in _pipeline.flatten_events(days):
        if currencies and r["currency"] not in currencies:
            continue
        if impacts and r["impact"] not in impacts:
            continue
        rows.append(r)

    # Deduplicate (QUAL-01)
    rows = _pipeline._deduplicate_rows(rows)

    # Speech-event filter intentionally absent — retained per D-09; query layer filters.

    # Build DataFrame with datetime_utc column (DATA-01 / Phase-2 wide schema)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=_pipeline.PHASE2_COLUMNS
    )
    if rows and "date" in df.columns and "time_utc" in df.columns:
        # WR-02: use errors="coerce" so holiday-class events with null/empty
        # datelines become NaT instead of raising a ParserError mid-run.
        df["datetime_utc"] = pd.to_datetime(
            df["date"] + " " + df["time_utc"], utc=True, errors="coerce"
        )
        null_count = int(df["datetime_utc"].isna().sum())
        if null_count:
            logger.warning(
                "[populate] %d row(s) have no parseable dateline — stored as NaT",
                null_count,
            )
        df = df.drop(columns=["date", "time_utc"])
        df = df[["datetime_utc"] + [c for c in df.columns if c != "datetime_utc"]]

    # Enforce nullable-int dtype for integer columns that may have None values.
    # Int64 (capital I) is the pandas nullable extension type; it round-trips
    # through pyarrow as int64 with nullability (T-02-02 / RESEARCH Pattern 4).
    # pd.to_numeric(errors='coerce') runs first to handle any non-numeric values
    # (e.g. string IDs from legacy fixture data) gracefully — they become <NA>
    # instead of raising ValueError (RESEARCH "fallback dtype normalizer").
    for col in INT_NULLABLE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    parquet_path = _cache.month_parquet_path(cache_dir, anchor)
    _pipeline.write_parquet(df, str(parquet_path))

    logger.debug("[populate] wrote %d rows -> %s", len(df), parquet_path)
    return len(df)


# ---------------------------------------------------------------------------
# Main populate entry point
# ---------------------------------------------------------------------------

def run_populate(
    *,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    raw_dir: str = RAW_INPUT_DIR,
    cache_dir: Path | None = None,
    force: bool = False,
    force_refresh: bool = False,
    auto_fetch: bool = True,
    session=None,
) -> dict:
    """Populate the cache from on-disk raw JSON files.

    With auto_fetch=True (default), auto-refreshes matured months over the network
    before the disk-ingest loop (CACHE-05 / D-08).  Pass auto_fetch=False for strict
    cache-only behavior (no automatic network activity).

    Args:
        currencies: Currency filter list (default: ["USD"] — D-04).
        impacts: Impact filter list (default: ["high", "holiday"] — D-04).
        start: First month to process as "YYYY-MM" (default: all on disk — D-05).
        end: Last month to process as "YYYY-MM" (default: all on disk — D-05).
        raw_dir: Directory containing days_YYYY_MM.json files (default: "out").
        cache_dir: Cache root directory. Resolved via _cache.resolve_cache_dir.
        force: When True, rebuild every month unconditionally from on-disk raw JSON,
               bypassing the manifest skip-check. Used for Phase-2 schema migration
               (RESEARCH Pattern 6). Makes zero network calls. CLI --force flag is
               in plan 02-02 (cli.py ownership). Distinct from force_refresh (D-01).
        force_refresh: When True, short-circuit the disk-ingest loop and delegate
                       to run_refresh(force_refresh=True) to re-scrape the requested
                       range over the network and overwrite cached parquets. Returns
                       run_refresh's {"fetched","skipped","failed"} dict instead of
                       the normal {"populated","skipped","empty"} dict (D-04). The
                       effective scope is unioned with the existing manifest scope to
                       avoid silently narrowing previously-cached months' parquets
                       (D-01/D-03/D-04). Default False preserves disk-ingest behavior.
        auto_fetch: When True (default), auto-refresh matured months before the
                    disk-ingest loop (CACHE-05 / D-08).  When False, strict cache-only
                    mode — no automatic network activity (D-09).  Suppressed automatically
                    when force_refresh=True (that path handles its own network activity).
        session: HTTP session to inject into the matured re-fetch (default: built lazily).

    Returns:
        If force_refresh=True: dict with keys fetched (int), skipped (int), failed (int).
        Otherwise: dict with keys populated (int), skipped (int), empty (int).
    """
    # Resolve defaults (D-04)
    if currencies is None:
        currencies = DEFAULT_CURRENCIES
    if impacts is None:
        impacts = DEFAULT_IMPACTS

    # Resolve cache dir and ensure layout exists
    resolved_cache = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(resolved_cache)

    # CACHE-05: auto-refresh matured months before disk-ingest (D-08/D-09).
    # Skipped when force_refresh=True because that path delegates to run_refresh
    # which handles freshness via its own force_refresh=True skip-bypass (D-08).
    # No stdout output here — D-11 reserves banners for the CLI query command.
    if auto_fetch and not force_refresh:
        from forexfactory import _refresh  # noqa: PLC0415 — lazy to avoid circular import
        _refresh.refresh_matured_months(resolved_cache, session=session)

    # CACHE-06 / D-01: force_refresh short-circuits the disk-ingest loop and
    # delegates to run_refresh(force_refresh=True) for the requested range.
    # The effective scope is unioned with the existing manifest scope to avoid
    # silently narrowing previously-cached months' parquets.
    if force_refresh:
        from forexfactory import _refresh  # noqa: PLC0415 — lazy to avoid circular import
        manifest = _cache.read_manifest(resolved_cache)
        existing_scope = manifest.get("scope", {})
        effective_currencies = sorted(
            set(currencies) | set(existing_scope.get("currencies", []))
        )
        effective_impacts = sorted(
            set(impacts) | set(existing_scope.get("impacts", []))
        )
        # WR-01: When start/end are unset, derive the full range from cached manifest
        # months (min..max of months keys) so force-refresh re-scrapes the entire
        # cached span rather than collapsing to the current month via gap-fill.
        # If the manifest has no months, keep start/end as-is (current-month fallback
        # inside _compute_date_range is still appropriate for a fresh cache).
        if start is None and end is None:
            month_keys = sorted(manifest.get("months", {}).keys())
            if month_keys:
                start, end = month_keys[0], month_keys[-1]

        return _refresh.run_refresh(
            currencies=effective_currencies,
            impacts=effective_impacts,
            start=start,
            end=end,
            cache_dir=resolved_cache,
            force_refresh=True,
            session=session,  # WR-03: forward injected session so build_session() is not called
        )

    # Discover month anchors from raw dir (D-05 — all on-disk months)
    pattern = os.path.join(raw_dir, "days_*.json")
    raw_paths = sorted(glob.glob(pattern))

    # Parse YYYY_MM from filename → date(year, month, 1)
    anchors: list[tuple[date, str]] = []
    for p in raw_paths:
        basename = os.path.basename(p)
        # filename: days_YYYY_MM.json
        stem = basename[len("days_"):-len(".json")]  # "YYYY_MM"
        try:
            year_str, month_str = stem.split("_")
            anchor = date(int(year_str), int(month_str), 1)
        except (ValueError, TypeError):
            logger.warning("[populate] unrecognized filename: %s — skipping", basename)
            continue
        anchors.append((anchor, p))

    # Narrow to [start, end] window if given (D-05)
    if start is not None:
        start_anchor = _parse_month_str(start)
        anchors = [(a, p) for a, p in anchors if a >= start_anchor]
    if end is not None:
        end_anchor = _parse_month_str(end)
        anchors = [(a, p) for a, p in anchors if a <= end_anchor]

    total = len(anchors)
    populated_count = 0
    skipped_count = 0
    empty_count = 0

    # Read manifest once outside the loop (updated after each write)
    manifest = _cache.read_manifest(resolved_cache)
    # BL-01: snapshot the scope that was in force at the start of this run.
    # The in-memory `manifest` is mutated by update_manifest_month after each
    # successful write, so we must NOT read manifest.get("scope") inside the
    # loop — doing so causes subsequent months to be skipped because the scope
    # already contains the wider currencies/impacts that were just written.
    original_scope = manifest.get("scope", {})
    today = date.today()

    for i, (anchor, raw_path) in enumerate(anchors, 1):
        month_key = f"{anchor:%Y-%m}"

        # Load raw JSON — warn-and-skip on bad JSON (T-01-01)
        try:
            with open(raw_path, "r", encoding="utf-8") as fh:
                days = json.load(fh)
            if not isinstance(days, list):
                logger.warning("[%d/%d] bad structure in %s — skipping", i, total, raw_path)
                empty_count += 1
                continue
        except json.JSONDecodeError:
            logger.warning("[%d/%d] bad JSON in %s — skipping", i, total, raw_path)
            empty_count += 1
            continue

        # Empty raw → never record as cached; retry on next run (QUAL-03 / SC5)
        if not days:
            logger.warning("[%d/%d] empty raw: %s — not cached (will retry)", i, total, month_key)
            empty_count += 1
            continue

        # D-06 incremental skip-check: skip only if manifest shows this month
        # already cached at a covering scope — bypassed entirely when force=True.
        if not force:
            cached_entry = manifest.get("months", {}).get(month_key)
            if cached_entry and _cache._scope_covers(original_scope, currencies, impacts):
                logger.info("[%d/%d] Skip (cached at scope): %s", i, total, month_key)
                skipped_count += 1
                continue

        # Build per-month parquet
        logger.info("[%d/%d] Populating: %s", i, total, month_key)
        row_count = build_month_parquet(
            resolved_cache, anchor, days, currencies=currencies, impacts=impacts
        )

        # Record manifest entry (D-02 / CACHE-04)
        # settled = whole month is strictly before today
        settled = (date(anchor.year, anchor.month + 1, 1) if anchor.month < 12
                   else date(anchor.year + 1, 1, 1)) <= today
        scraped_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        manifest = _cache.update_manifest_month(
            resolved_cache,
            anchor,
            scraped_at=scraped_at,
            settled=settled,
            currencies=currencies,
            impacts=impacts,
        )

        logger.info("[%d/%d] Populated %s: %d rows", i, total, month_key, row_count)
        populated_count += 1

    logger.info(
        "[populate] done — populated=%d skipped=%d empty=%d",
        populated_count, skipped_count, empty_count,
    )

    # Stamp schema_version after any successful activity so callers can detect
    # Phase-2 cache without inspecting parquet dtypes (Open Question 3 / RESEARCH Pattern 6).
    if populated_count or skipped_count:
        current_manifest = _cache.read_manifest(resolved_cache)
        current_manifest["schema_version"] = _cache.SCHEMA_VERSION
        _cache.write_manifest(resolved_cache, current_manifest)

    return {"populated": populated_count, "skipped": skipped_count, "empty": empty_count}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_month_str(s: str) -> date:
    """Parse a 'YYYY-MM' string into a date(year, month, 1)."""
    try:
        year_str, month_str = s.split("-")
        return date(int(year_str), int(month_str), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid month string {s!r} — expected 'YYYY-MM'") from exc
