"""
Quant helpers for Forex Factory economic event data.
=====================================================
Provides row-aligned, NaN-safe surprise metrics over a DataFrame returned by
forexfactory.read() (or equivalent parquet-sourced DataFrame with the Phase-2
analytical schema columns: actual, forecast, ebaseId).

Usage:
    import forexfactory
    df = forexfactory.read(currencies=["USD"], impacts=["high"])
    df["surprise"] = forexfactory.surprise(df)
    df["surprise_z"] = forexfactory.surprise_z(df)
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def surprise(df: pd.DataFrame) -> pd.Series:
    """Return raw actual − forecast for every row, row-aligned to df.index.

    Satisfies D-01 (raw arithmetic, no polarity adjustment) and D-03 (NaN-propagate,
    never raise, output index equals input index).  When 'actual' or 'forecast' columns
    are absent the entire Series is NaN; pandas column subtraction is otherwise
    inherently row-aligned and NaN-propagating.
    """
    if "actual" not in df.columns or "forecast" not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return df["actual"] - df["forecast"]


def surprise_z(df: pd.DataFrame) -> pd.Series:
    """Return z-scored surprise per ebaseId group, row-aligned to df.index.

    Computes z = (surprise − group_mean) / group_std over each ebaseId's full
    history present in df (D-02 — single groupby over all rows, look-ahead accepted
    for v1.1).  NaN rules (D-03):
      - NaN actual or forecast => NaN surprise => NaN z (excluded from group stats).
      - Groups with <2 non-NaN releases => NaN (pandas ddof=1 std yields NaN for
        size-1 groups).
      - Groups with std == 0 (constant surprise) => NaN (explicit guard to avoid
        divide-by-zero / inf).
    Output Series is reindexed to df.index so row count and order are preserved even
    when the groupby transform drops or reorders anything.
    """
    if "ebaseId" not in df.columns:
        return pd.Series(float("nan"), index=df.index)

    if df.empty:
        return pd.Series(dtype=float)

    s = surprise(df)

    def _standardize(group: pd.Series) -> pd.Series:
        """Standardize a group's surprise values; return NaN if std==0 or <2 valid."""
        std = group.std()  # ddof=1 — NaN for size-1 groups
        if pd.isna(std) or std == 0:
            return pd.Series(float("nan"), index=group.index)
        mean = group.mean()
        return (group - mean) / std

    result = s.groupby(df["ebaseId"], dropna=False).transform(_standardize)

    # Reindex to df.index so row-alignment is guaranteed even after groupby transform.
    return result.reindex(df.index)
