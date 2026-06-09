"""
forexfactory — Cached Economic Calendar Data Provider
======================================================
Install once, fetch once, and read the Forex Factory economic calendar from
any project via a shared local cache.

Usage:
    from forexfactory import get, populate
    path = get(currencies=["USD"], impacts=["high"])
    # path is a pathlib.Path to a filtered Parquet file

    result = populate(force_refresh=True, start="2025-01")
    # result == {"fetched": N, "skipped": N, "failed": N}
"""

from pathlib import Path

__version__ = "0.1.0"


def get(
    *,
    currencies=None,
    impacts=None,
    start=None,
    end=None,
    include_no_data=False,
    cache_dir=None,
) -> Path:
    """Return a Path to a filtered Parquet file from the local cache.

    Lazily imports _query so that `import forexfactory` works before
    _query.py exists (it is implemented in plan 04).
    """
    from . import _query  # noqa: PLC0415 — intentional lazy import
    return _query.run_query(
        currencies=currencies,
        impacts=impacts,
        start=start,
        end=end,
        include_no_data=include_no_data,
        cache_dir=cache_dir,
    )


def populate(
    *,
    currencies=None,
    impacts=None,
    start=None,
    end=None,
    raw_dir=None,
    cache_dir=None,
    force=False,
    force_refresh=False,
) -> dict:
    """Populate or refresh the local cache; library mirror of the populate CLI command.

    With force_refresh=False (default): reads on-disk raw JSON and builds parquet
    (zero network calls). Returns {"populated": N, "skipped": N, "empty": N}.

    With force_refresh=True: re-scrapes the requested range over the network and
    overwrites existing cached parquets (CACHE-06 / D-03). Returns
    {"fetched": N, "skipped": N, "failed": N}.
    """
    from . import _populate  # noqa: PLC0415 — intentional lazy import
    kwargs = dict(
        currencies=currencies,
        impacts=impacts,
        start=start,
        end=end,
        cache_dir=cache_dir,
        force=force,
        force_refresh=force_refresh,
    )
    if raw_dir is not None:
        kwargs["raw_dir"] = raw_dir
    return _populate.run_populate(**kwargs)
