"""
Populate Cache from On-Disk Raw JSON
=====================================
Ingests the existing per-month days_*.json files from the raw input directory
into per-month parquet files under the cache, recording scope + provenance in
manifest.json. Makes ZERO network calls (SC2).

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
# ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
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

    Reuses _pipeline.flatten_events, _deduplicate_rows, should_keep_row, and
    write_parquet so the ETL logic stays in one place (QUAL-01 reuse).
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

    # Drop 'speaks' events
    rows = [r for r in rows if _pipeline.should_keep_row(r)]

    # Build DataFrame with datetime_utc column (DATA-01)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["datetime_utc", "currency", "impact", "title", "id", "leaked"]
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
) -> dict:
    """Populate the cache from on-disk raw JSON files. Makes zero network calls.

    Args:
        currencies: Currency filter list (default: ["USD"] — D-04).
        impacts: Impact filter list (default: ["high", "holiday"] — D-04).
        start: First month to process as "YYYY-MM" (default: all on disk — D-05).
        end: Last month to process as "YYYY-MM" (default: all on disk — D-05).
        raw_dir: Directory containing days_YYYY_MM.json files (default: "out").
        cache_dir: Cache root directory. Resolved via _cache.resolve_cache_dir.

    Returns:
        dict with keys: populated (int), skipped (int), empty (int).
    """
    # Resolve defaults (D-04)
    if currencies is None:
        currencies = DEFAULT_CURRENCIES
    if impacts is None:
        impacts = DEFAULT_IMPACTS

    # Resolve cache dir and ensure layout exists
    resolved_cache = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(resolved_cache)

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
        # already cached at a covering scope.
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
