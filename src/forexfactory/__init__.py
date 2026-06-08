"""
forexfactory — Cached Economic Calendar Data Provider
======================================================
Install once, fetch once, and read the Forex Factory economic calendar from
any project via a shared local cache.

Usage:
    from forexfactory import get
    path = get(currencies=["USD"], impacts=["high"])
    # path is a pathlib.Path to a filtered Parquet file
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
