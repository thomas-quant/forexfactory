"""
Forex Factory Economic Events Pipeline
=======================================
Consolidates: parse.py, sanitize.py, to_parquet.py

Usage:
  python pipeline.py                    # full pipeline -> parquet only (no CSV)
  python pipeline.py --step parse       # JSON -> CSV
  python pipeline.py --step sanitize    # sanitize CSV -> CSV
  python pipeline.py --step parquet     # CSV -> Parquet
"""

import argparse
import csv
import glob
import json
import os
import re
from collections.abc import Generator, Iterator
from datetime import UTC, datetime
from typing import Any, Literal

import pandas as pd

# ========= CONFIG =========
IN_DIR = "out"  # where days_YYYY_MM.json live
PARSED_CSV = "ff_usd_high_holiday.csv"  # output from parse step
CLEAN_CSV = "ff_usd_high_holiday_clean.csv"  # output from sanitize step
OUT_PARQUET = "economic_events.parquet"  # final parquet output
KEEP_CURRENCIES = {"USD"}  # only USD
KEEP_IMPACTS = {"high", "holiday"}  # red folder + bank holidays
PARQUET_COMPRESSION: Literal["zstd"] = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
# Phase-2 full analytical schema — final parquet column order (D-01, DATA-02/03/04).
# Imported by _populate.py and _query.py to prevent stale-column-list drift (RESEARCH Pitfall 3).
PHASE2_COLUMNS: list[str] = [
    "datetime_utc",
    "currency",
    "impact",
    "title",
    "id",
    "leaked",
    "forecast_raw",
    "actual_raw",
    "previous_raw",
    "revision_raw",
    "forecast",
    "actual",
    "previous",
    "revision",
    "actualBetterWorse",
    "revisionBetterWorse",
    "ebaseId",
    "country",
    "hasDataValues",
]
# ==========================

# Numeric parsing helpers for _parse_value() (D-02).
# Regex matches an optional sign, digits, optional decimal, and an optional
# magnitude suffix or percent. Pipe-separated bond auction values ('1.34|2.6'),
# angle-bracket sub-threshold values ('<0.10%'), and any other format that
# contains characters outside this set produce no match -> NaN.
_NUMERIC_RE = re.compile(r"^([+-]?\d*\.?\d+)([KMBTkmbt%]?)$")
_SUFFIX_MAP: dict[str, float] = {
    "K": 1e3,
    "M": 1e6,
    "B": 1e9,
    "T": 1e12,
    "%": 1e-2,
}


# ─────────────────────────────────────────────────────────────────────────────
# PARSE: JSON -> CSV
# ─────────────────────────────────────────────────────────────────────────────


def load_days_files(in_dir: str) -> Iterator[tuple[str, list[Any]]]:
    """Yield (path, days_list) for each days_*.json file."""
    paths = sorted(glob.glob(os.path.join(in_dir, "days_*.json")))
    for p in paths:
        with open(p, encoding="utf-8") as f:
            try:
                days = json.load(f)
                if isinstance(days, list):
                    yield p, days
            except json.JSONDecodeError:
                print(f"[warn] bad JSON: {p}")


def norm_impact(s: str) -> str:
    """Normalize impact string to one of: high, holiday, medium, low."""
    s = (s or "").strip().lower()
    if s in {"high", "holiday", "medium", "low"}:
        return s
    if "non-economic" in s or "holiday" in s or "bank" in s:
        return "holiday"
    if "high" in s or "red" in s:
        return "high"
    if "medium" in s or "orange" in s:
        return "medium"
    if "low" in s or "yellow" in s:
        return "low"
    return s


def to_iso(dt_epoch: int | float | None) -> tuple[str, str]:
    """Convert epoch seconds (UTC) to (date_iso, time_utc)."""
    if not dt_epoch:
        return "", ""
    try:
        ts = float(dt_epoch)
        if ts > 10_000_000_000:  # milliseconds -> seconds
            ts = ts / 1000.0
        dt = datetime.fromtimestamp(ts, tz=UTC)
        return dt.date().isoformat(), dt.strftime("%H:%M:%S")
    except Exception:
        return "", ""


def _parse_value(s: str) -> float:
    """Parse a FF value string to float, returning float('nan') for unparseable input.

    Magnitude suffixes: K=1e3, M=1e6, B=1e9, T=1e12. Percent divides by 100 so
    ratio-ready columns need no re-dividing downstream (D-02). Pipe-separated bond
    auction values ('1.34|2.6'), angle-bracket sub-threshold values ('<0.10%'),
    non-numeric strings ('Pass', 'Yes'), and empty strings all become NaN.
    Suffix matching is case-insensitive (the regex captures [KMBTkmbt%]).
    NEVER raises; any unparseable or hostile input -> float('nan') (T-02-01).
    """
    if not s or not s.strip():
        return float("nan")
    s = s.strip()
    m = _NUMERIC_RE.match(s)
    if not m:
        return float("nan")
    num = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix:
        num *= _SUFFIX_MAP[suffix]
    return num


def flatten_events(
    days: list[Any], src_path: str | None = None
) -> Generator[dict[str, Any], None, None]:
    """Flatten nested days/events structure into individual event dicts.

    Phase 2: yields 20 source keys — the 19 PHASE2_COLUMNS fields (with date +
    time_utc standing in for the derived datetime_utc) plus the analytical schema:
    raw value strings, parsed numerics, surprise flags, identity, and hasDataValues.
    FF UI/internal fields (checker, releaser, siteId, show*/enable*, soloTitle,
    notice, etc.) are silently dropped (DATA-04).
    """
    for d in days:
        for ev in d.get("events", []):
            currency = (ev.get("currency") or "").upper()
            impact = norm_impact(ev.get("impactName") or ev.get("impactTitle") or "")
            # soloTitle is in the DATA-04 drop list — do NOT add it as a fallback.
            title = ev.get("prefixedName") or ev.get("name") or ""
            dateline = ev.get("dateline")
            date_iso, time_utc = to_iso(dateline)

            # Raw value strings (verbatim from FF — D-01)
            forecast_raw = ev.get("forecast") or ""
            actual_raw = ev.get("actual") or ""
            previous_raw = ev.get("previous") or ""
            revision_raw = ev.get("revision") or ""

            yield {
                "date": date_iso,
                "time_utc": time_utc,
                "currency": currency,
                "impact": impact,
                "title": title,
                # id: None when absent (enables Int64 nullable casting downstream; D-01)
                "id": ev.get("id"),
                "leaked": ev.get("leaked"),
                # Phase-2 analytical schema (D-01, DATA-02/03/04):
                "forecast_raw": forecast_raw,
                "actual_raw": actual_raw,
                "previous_raw": previous_raw,
                "revision_raw": revision_raw,
                "forecast": _parse_value(forecast_raw),
                "actual": _parse_value(actual_raw),
                "previous": _parse_value(previous_raw),
                "revision": _parse_value(revision_raw),
                # actualBetterWorse: 0 can mean "no comparison performed" (speeches/holidays)
                # or "inline with forecast" (data releases) — store raw int per D-03.
                "actualBetterWorse": ev.get("actualBetterWorse"),
                "revisionBetterWorse": ev.get("revisionBetterWorse"),
                "ebaseId": ev.get("ebaseId"),
                "country": ev.get("country") or "",
                "hasDataValues": ev.get("hasDataValues", False),
            }


def _deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate event rows and return them sorted by (date, time_utc, title).

    Keyed by (id, date, time_utc) when id is truthy; falls back to
    (date, time_utc, currency, title) for anonymous events.
    """
    dedup = {}
    for r in rows:
        key = (
            (r["id"], r["date"], r["time_utc"])
            if r["id"]
            else (r["date"], r["time_utc"], r["currency"], r["title"])
        )
        dedup[key] = r
    result = list(dedup.values())
    result.sort(key=lambda x: (x["date"], x["time_utc"], x["title"]))
    return result


def parse_json_to_csv(
    in_dir: str = IN_DIR,
    out_csv: str = PARSED_CSV,
    keep_currencies: set[str] = KEEP_CURRENCIES,
    keep_impacts: set[str] = KEEP_IMPACTS,
) -> str:
    """Parse all days_*.json files and write filtered events to CSV."""
    rows = []
    for path, days in load_days_files(in_dir):
        for r in flatten_events(days, path):
            if keep_currencies and r["currency"] not in keep_currencies:
                continue
            if keep_impacts and r["impact"] not in keep_impacts:
                continue
            rows.append(r)

    rows = _deduplicate_rows(rows)

    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    cols = ["date", "time_utc", "currency", "impact", "title", "id", "leaked"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        # extrasaction="ignore": flatten_events now yields the full 20-field Phase-2 dict;
        # the legacy 7-column CSV only writes the narrow fieldnames and silently ignores
        # the new analytical fields — preserves backward compatibility (RESEARCH Pitfall 3).
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"[parse] wrote {len(rows)} rows -> {out_csv}")
    return out_csv


# ─────────────────────────────────────────────────────────────────────────────
# SANITIZE: Remove unwanted rows from CSV
# ─────────────────────────────────────────────────────────────────────────────


def should_keep_row(row: dict[str, Any]) -> bool:
    """Return True if the row should be kept (no 'speaks' in title)."""
    title = (row.get("title") or "").lower()
    return "speaks" not in title


def sanitize_csv(in_csv: str = PARSED_CSV, out_csv: str = CLEAN_CSV) -> str:
    """Remove rows with 'speaks' in the title."""
    if not os.path.isfile(in_csv):
        raise FileNotFoundError(f"Input CSV not found: {in_csv}")

    with open(in_csv, encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        rows = [r for r in reader if should_keep_row(r)]
        fieldnames = reader.fieldnames or []

    with open(out_csv, "w", encoding="utf-8", newline="") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"[sanitize] kept {len(rows)} rows -> {out_csv}")
    return out_csv


# ─────────────────────────────────────────────────────────────────────────────
# PARQUET: Convert CSV to Parquet
# ─────────────────────────────────────────────────────────────────────────────


def csv_to_parquet(csv_path: str, parquet_path: str | None = None) -> str:
    """Convert CSV to Parquet, combining date+time into datetime_utc column."""
    if parquet_path is None:
        parquet_path = os.path.splitext(csv_path)[0] + ".parquet"

    df = pd.read_csv(csv_path)

    # Combine date + time into a single datetime column (UTC)
    if "date" in df.columns and "time_utc" in df.columns:
        # WR-02: errors="coerce" so rows with empty/null datelines become NaT
        # instead of raising a ParserError and aborting the run.
        df["datetime_utc"] = pd.to_datetime(
            df["date"] + " " + df["time_utc"], utc=True, errors="coerce"
        )
        null_count = int(df["datetime_utc"].isna().sum())
        if null_count:
            print(f"[warn] {null_count} row(s) have no parseable dateline — stored as NaT")
        df = df.drop(columns=["date", "time_utc"])
        df = df[["datetime_utc"] + [c for c in df.columns if c != "datetime_utc"]]

    write_parquet(df, parquet_path)
    print(f"[parquet] converted -> {parquet_path}")
    return parquet_path


def write_parquet(df: pd.DataFrame, parquet_path: str) -> str:
    """Write parquet files with the project's standard compression settings."""
    df.to_parquet(
        parquet_path,
        index=False,
        compression=PARQUET_COMPRESSION,
        compression_level=PARQUET_COMPRESSION_LEVEL,
    )
    return parquet_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN: Run full pipeline or individual steps
# ─────────────────────────────────────────────────────────────────────────────


def run_pipeline(
    out_parquet: str = OUT_PARQUET,
    *,
    in_dir: str = IN_DIR,
    keep_currencies: set[str] = KEEP_CURRENCIES,
    keep_impacts: set[str] = KEEP_IMPACTS,
) -> None:
    """Run full pipeline in memory: JSON -> filtered -> sanitized -> Parquet.

    No intermediate CSVs are written.
    """
    # Parse JSON files
    rows = []
    for path, days in load_days_files(in_dir):
        for r in flatten_events(days, path):
            if keep_currencies and r["currency"] not in keep_currencies:
                continue
            if keep_impacts and r["impact"] not in keep_impacts:
                continue
            rows.append(r)

    rows = _deduplicate_rows(rows)

    # Sanitize (remove 'speaks')
    rows = [r for r in rows if should_keep_row(r)]

    # Convert to DataFrame and output parquet
    df = pd.DataFrame(rows)
    if "date" in df.columns and "time_utc" in df.columns:
        # WR-02: errors="coerce" so rows with empty/null datelines become NaT
        # instead of raising a ParserError and aborting the run.
        df["datetime_utc"] = pd.to_datetime(
            df["date"] + " " + df["time_utc"], utc=True, errors="coerce"
        )
        null_count = int(df["datetime_utc"].isna().sum())
        if null_count:
            print(f"[warn] {null_count} row(s) have no parseable dateline — stored as NaT")
        df = df.drop(columns=["date", "time_utc"])
        df = df[["datetime_utc"] + [c for c in df.columns if c != "datetime_utc"]]

    write_parquet(df, out_parquet)
    print(f"[done] {len(df)} rows -> {out_parquet}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forex Factory Economic Events Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  parse     - Parse JSON files to CSV (filtered by currency/impact)
  sanitize  - Remove 'speaks' events from CSV
  parquet   - Convert CSV to Parquet format
  
Without --step, runs full pipeline directly to Parquet (no intermediate CSVs).
        """,
    )
    parser.add_argument(
        "--step",
        choices=["parse", "sanitize", "parquet"],
        help="Run a specific step only",
    )
    parser.add_argument("--in-dir", default=IN_DIR, help="Input directory for JSON files")
    parser.add_argument("--csv", help="Input CSV for sanitize/parquet steps")
    parser.add_argument("--out", help="Output file path")

    args = parser.parse_args()

    if args.step == "parse":
        out = args.out or PARSED_CSV
        parse_json_to_csv(in_dir=args.in_dir, out_csv=out)

    elif args.step == "sanitize":
        in_csv = args.csv or PARSED_CSV
        out_csv = args.out or CLEAN_CSV
        sanitize_csv(in_csv=in_csv, out_csv=out_csv)

    elif args.step == "parquet":
        in_csv = args.csv or CLEAN_CSV
        out_parquet = args.out or OUT_PARQUET
        csv_to_parquet(csv_path=in_csv, parquet_path=out_parquet)

    else:
        # No step specified -> run full pipeline (parquet only, no intermediate CSVs)
        out_parquet = args.out or OUT_PARQUET
        run_pipeline(out_parquet=out_parquet, in_dir=args.in_dir)


if __name__ == "__main__":
    main()
