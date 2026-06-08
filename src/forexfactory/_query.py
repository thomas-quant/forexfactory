"""
Cache Query Engine
==================
Reads per-month parquet files from the local cache, applies currency/impact/date
filters, writes ONE consolidated result parquet at a deterministic path, and
returns its absolute Path.

Usage:
    from forexfactory import _query
    path = _query.run_query(currencies=["USD"], impacts=["high"])
    # path is a pathlib.Path to a filtered Parquet file
"""
import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

from forexfactory import _cache, _pipeline

# ====== CONFIG ======
DEFAULT_CURRENCIES = ["USD"]
DEFAULT_IMPACTS = ["high", "holiday"]
# ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# DATA-01 columns — used to create an empty DataFrame when no months match.
_DATA01_COLUMNS = ["datetime_utc", "currency", "impact", "title", "id", "leaked"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_token(token: str) -> str:
    """Strip characters that are not alphanumeric or hyphen (T-01-03 path-traversal guard)."""
    return re.sub(r"[^a-zA-Z0-9-]", "", str(token))


def _result_filename(
    currencies: list,
    impacts: list,
    start: str | None,
    end: str | None,
) -> str:
    """Compute a deterministic, filesystem-safe result parquet filename (D-08).

    Example: 'USD__high-holiday__all_all.parquet'
    """
    cur_part = "-".join(sorted(_safe_token(c) for c in currencies))
    imp_part = "-".join(sorted(_safe_token(i) for i in impacts))
    start_part = _safe_token(start) if start else "all"
    end_part = _safe_token(end) if end else "all"
    return f"{cur_part}__{imp_part}__{start_part}_{end_part}.parquet"


def _filter_months_by_range(
    month_keys: list,
    start: str | None,
    end: str | None,
) -> list:
    """Return month_keys (YYYY-MM strings) narrowed to [start, end], inclusive."""
    if start is None and end is None:
        return month_keys
    result = []
    for k in month_keys:
        if start is not None and k < start:
            continue
        if end is not None and k > end:
            continue
        result.append(k)
    return result


def _raise_scope_error(
    currencies: list,
    impacts: list,
    scope: dict,
) -> None:
    """Raise ValueError with actionable populate guidance for each uncovered pair (D-09).

    Example message:
        EUR/medium not populated — run: forexfactory populate --currency EUR --impact medium
    """
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
        # Defensive fallback — should not be reached if _scope_covers is consistent.
        messages = ["cache not populated — run: forexfactory populate"]

    raise ValueError("\n".join(messages))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_query(
    *,
    currencies: list | None = None,
    impacts: list | None = None,
    start: str | None = None,
    end: str | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Read per-month cache parquets, filter, write and return a consolidated result parquet.

    Returns an absolute pathlib.Path to the result parquet under
    <cache_dir>/queries/.  The path is deterministic (keyed by filter
    parameters) and overwritten on every call (D-07 / D-08).

    Raises ValueError when the manifest scope does not cover the request (D-09).
    All diagnostics go to logging, never to stdout (D-10).
    """
    # Apply defaults (D-04 — consistent with populate defaults)
    if currencies is None:
        currencies = list(DEFAULT_CURRENCIES)
    if impacts is None:
        impacts = list(DEFAULT_IMPACTS)

    cache_dir = _cache.resolve_cache_dir(cache_dir)
    _cache.ensure_dirs(cache_dir)

    manifest = _cache.read_manifest(cache_dir)
    scope = manifest.get("scope", {})

    # D-09: scope check — raise before any parquet reads if the request is not covered.
    if not scope or not _cache._scope_covers(scope, currencies, impacts):
        _raise_scope_error(currencies, impacts, scope)

    # Candidate months from the manifest, optionally narrowed by start/end (D-07).
    all_month_keys = sorted(manifest.get("months", {}).keys())
    candidate_keys = _filter_months_by_range(all_month_keys, start, end)

    logger.info(
        "[query] %d candidate months | currencies=%s impacts=%s",
        len(candidate_keys),
        currencies,
        impacts,
    )

    # Read per-month parquets; silently skip absent files.
    dfs = []
    for month_key in candidate_keys:
        try:
            year, month_num = map(int, month_key.split("-"))
            anchor = date(year, month_num, 1)
        except (ValueError, AttributeError):
            logger.warning("[query] cannot parse month key '%s' — skipping", month_key)
            continue

        p = _cache.month_parquet_path(cache_dir, anchor)
        if not p.exists():
            logger.debug("[query] month parquet absent, skipping: %s", p)
            continue

        dfs.append(pd.read_parquet(p))

    # Concatenate (or produce an empty DATA-01 DataFrame when nothing matched).
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
    else:
        df = pd.DataFrame(columns=_DATA01_COLUMNS)

    # Apply currency + impact filter.
    df = df[df["currency"].isin(currencies) & df["impact"].isin(impacts)]

    logger.info("[query] %d rows after filter", len(df))

    # Compute deterministic result path (D-08) and write (overwrite) it.
    result_filename = _result_filename(currencies, impacts, start, end)
    result_path = _cache.queries_dir(cache_dir) / result_filename
    _pipeline.write_parquet(df, str(result_path))

    resolved = Path(result_path).resolve()
    logger.info("[query] result -> %s", resolved)
    return resolved
