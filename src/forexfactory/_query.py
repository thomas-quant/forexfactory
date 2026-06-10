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
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from forexfactory import _cache, _pipeline

# ====== CONFIG ======
DEFAULT_CURRENCIES = ["USD"]
DEFAULT_IMPACTS = ["high", "holiday"]
# ====================

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_token(token: str) -> str:
    """Strip characters that are not alphanumeric or hyphen (T-01-03 path-traversal guard)."""
    return re.sub(r"[^a-zA-Z0-9-]", "", str(token))


def _result_filename(
    currencies: list[str],
    impacts: list[str],
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
    month_keys: list[str],
    start: str | None,
    end: str | None,
) -> list[str]:
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
    currencies: list[str],
    impacts: list[str],
    scope: dict[str, Any],
) -> None:
    """Raise ValueError with actionable populate guidance for each uncovered pair (D-09).

    Example message:
        EUR/medium not populated — run: forexfactory populate --currency EUR --impact medium
    """
    cached_currencies: set[str] = set(scope.get("currencies", []))
    cached_impacts: set[str] = set(scope.get("impacts", []))

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
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    include_no_data: bool = False,
    cache_dir: Path | None = None,
    auto_fetch: bool = True,
    session: Any = None,
    progress: Callable[..., None] | None = None,
) -> Path:
    """Read per-month cache parquets, filter, write and return a consolidated result parquet.

    Returns an absolute pathlib.Path to the result parquet under
    <cache_dir>/queries/.  The path is deterministic (keyed by filter
    parameters) and overwritten on every call (D-07 / D-08).

    Args:
        auto_fetch: When True (default), auto-refresh matured months before reading
                    (CACHE-05 / D-08). When False, strict cache-only read (D-07/D-09).
        session: curl_cffi session to inject into the matured re-fetch (default: built lazily).
        progress: Optional callable(event, **kwargs) invoked when an auto-fetch is about
                  to occur, so the CLI can print a D-12 banner before fetch progress lines.

    Raises ValueError when the manifest scope does not cover the request (D-09).
    All diagnostics go to logging, never to stdout (D-10/D-11).
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

    # CACHE-05: auto-refresh matured months BEFORE the scope check (D-08/D-09).
    # Runs only when auto_fetch=True; suppressed by auto_fetch=False (D-07/D-09).
    if auto_fetch:
        from forexfactory import _refresh  # noqa: PLC0415 — lazy to avoid circular import

        # Count matured months to drive the D-12 progress banner (must fire BEFORE fetch)
        matured_count = 0
        for mk, entry in manifest.get("months", {}).items():
            if not entry.get("settled"):
                try:
                    year_str, mon_str = mk.split("-")
                    anchor = date(int(year_str), int(mon_str), 1)
                    if _refresh._is_settled(anchor):
                        matured_count += 1
                except (ValueError, AttributeError):
                    pass

        if matured_count > 0:
            # D-12: CLI banner fires before the [N/total] per-month log lines
            if progress is not None:
                progress("matured", count=matured_count)
            _refresh.refresh_matured_months(cache_dir, session=session)
            # Re-read so subsequent scope check and parquet loop see refreshed state
            manifest = _cache.read_manifest(cache_dir)
            scope = manifest.get("scope", {})

    # D-09/CACHE-03: scope check — either raise (auto_fetch=False) or auto-widen (auto_fetch=True).
    if not scope or not _cache._scope_covers(scope, currencies, impacts):
        if not auto_fetch:
            # D-07: strict cache-only — raise with guidance, zero network calls
            _raise_scope_error(currencies, impacts, scope)
        else:
            from forexfactory import _refresh  # noqa: PLC0415 — lazy; avoids circular import

            # D-12: fire progress("scope_miss", ...) for each uncovered pair BEFORE fetching
            if progress is not None:
                cached_currencies: set[str] = set(scope.get("currencies", []))
                cached_impacts: set[str] = set(scope.get("impacts", []))
                for c in currencies:
                    for i in impacts:
                        if c not in cached_currencies or i not in cached_impacts:
                            progress("scope_miss", currency=c, impact=i)
            # Widen: re-fetches full cached range at union scope (D-05).
            # AutoFetchError propagates as-is (D-06 fail-closed — no partial data).
            _refresh.widen_scope_to_cover(cache_dir, currencies, impacts, session=session)
            # Re-read so the parquet read loop sees the widened cache
            manifest = _cache.read_manifest(cache_dir)
            scope = manifest.get("scope", {})

    # Candidate months from the manifest, optionally narrowed by start/end (D-07).
    # Always computed after any scope refresh so the read loop sees up-to-date state.
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

    # Concatenate (or produce an empty Phase-2 DataFrame when nothing matched).
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
    else:
        df = pd.DataFrame(columns=_pipeline.PHASE2_COLUMNS)

    # D-15 / DATA-06: ensure siteId is always present in the result (mirrors hasDataValues guard).
    # Stale pre-bump parquets lack the siteId column; add it as all-null so consumers never
    # branch on column existence (nullable object — not coerced to Int64).
    if "siteId" not in df.columns:
        df = df.copy()
        df["siteId"] = None

    # D-08: default filter hides no-data events (speeches) but keeps holidays.
    # Guard handles pre-Phase-2 parquets that lack the hasDataValues column (RESEARCH Pitfall 4).
    if not include_no_data:
        if "hasDataValues" in df.columns:
            df = df[df["hasDataValues"] | (df["impact"] == "holiday")]
        else:
            logger.warning(
                "[query] hasDataValues column absent — stale cache; run populate --force"
            )

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
