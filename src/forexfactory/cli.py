"""
forexfactory CLI
================
Unified console script ``forexfactory`` exposing ``populate``, ``refresh``,
and ``query`` subcommands.

Usage::

    # Populate the cache from on-disk raw JSON (zero network calls, SC2):
    forexfactory populate --raw-dir out [--cache-dir DIR]

    # Refresh: fetch months not yet cached over the network (D-11, SRC-02):
    forexfactory refresh [--currency USD] [--start 2026-04] [--cache-dir DIR]

    # Query the cache; prints the result parquet path to stdout (D-10, SC3):
    forexfactory query --currency USD --impact high [--cache-dir DIR]

    # Path-only stdout enables shell capture (D-10):
    PARQUET=$(forexfactory query --currency USD --impact high)
"""
import argparse
import logging
import sys
from pathlib import Path

from forexfactory import _populate, _query, _refresh, _scrape

# ====== CONFIG ======
# No standalone constants — CLI arg defaults derive from the service modules.
# ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_month(value: str | None, name: str) -> None:
    """Validate that a --start or --end value has YYYY-MM shape; sys.exit(1) if not."""
    if value is None:
        return
    try:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError("expected exactly two dash-separated parts")
        year, month = int(parts[0]), int(parts[1])
        # WR-05: range-check month so "2024-99" / "2024-00" produce a clean
        # argparse error instead of an unhandled ValueError traceback later.
        if not (1 <= month <= 12):
            raise ValueError(f"month {month} out of range 1–12")
    except (ValueError, AttributeError):
        logger.error("Invalid %s %r — expected YYYY-MM (e.g. 2024-03)", name, value)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``forexfactory`` console script."""
    parser = argparse.ArgumentParser(
        prog="forexfactory",
        description="Forex Factory economic calendar cache provider",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── populate ─────────────────────────────────────────────────────────────
    pop = subparsers.add_parser(
        "populate",
        help="Build the parquet cache from on-disk raw JSON files (zero network calls)",
    )
    pop.add_argument(
        "--currency", dest="currency", action="append", metavar="CURRENCY",
        help="Currency to include (repeatable; default: USD) [D-12]",
    )
    pop.add_argument(
        "--impact", dest="impact", action="append", metavar="IMPACT",
        help="Impact level to include (repeatable; default: high holiday) [D-12]",
    )
    pop.add_argument(
        "--start", default=None, metavar="YYYY-MM",
        help="First month to process (default: all on disk — D-05)",
    )
    pop.add_argument(
        "--end", default=None, metavar="YYYY-MM",
        help="Last month to process (default: all on disk — D-05)",
    )
    pop.add_argument(
        "--cache-dir", default=None, metavar="DIR",
        help="Override cache directory (default: ~/.cache/forexfactory) [CACHE-01]",
    )
    pop.add_argument(
        "--raw-dir", default=_populate.RAW_INPUT_DIR, metavar="DIR",
        help=(
            "Directory containing days_YYYY_MM.json files "
            f"(default: {_populate.RAW_INPUT_DIR})"
        ),
    )
    pop.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force rebuild all months even if already cached [Phase-2 migration]",
    )

    # ── refresh ───────────────────────────────────────────────────────────────
    rfr = subparsers.add_parser(
        "refresh",
        help="Fetch months not yet cached over the network (D-11, SRC-02)",
    )
    rfr.add_argument(
        "--currency", dest="currency", action="append", metavar="CURRENCY",
        help="Currency to fetch (repeatable; default: USD) [D-12]",
    )
    rfr.add_argument(
        "--impact", dest="impact", action="append", metavar="IMPACT",
        help="Impact level to fetch (repeatable; default: high holiday) [D-12]",
    )
    rfr.add_argument(
        "--start", default=None, metavar="YYYY-MM",
        help="First month to fetch (default: gap-fill from last cached — D-11)",
    )
    rfr.add_argument(
        "--end", default=None, metavar="YYYY-MM",
        help="Last month to fetch (default: current month — D-11)",
    )
    rfr.add_argument(
        "--cache-dir", default=None, metavar="DIR",
        help="Override cache directory (default: ~/.cache/forexfactory) [CACHE-01]",
    )
    rfr.add_argument(
        "--between-pages-delay",
        type=float,
        default=_scrape.BETWEEN_PAGES_DELAY,
        metavar="SECONDS",
        help=(
            "Seconds to sleep between month requests "
            f"(default: {_scrape.BETWEEN_PAGES_DELAY}) [D-11]"
        ),
    )
    rfr.add_argument(
        "--retry-delay",
        type=float,
        default=_scrape.RETRY_DELAY,
        metavar="SECONDS",
        help=(
            "Seconds to sleep before retrying a failed month "
            f"(default: {_scrape.RETRY_DELAY}) [D-11]"
        ),
    )

    # ── query ─────────────────────────────────────────────────────────────────
    qry = subparsers.add_parser(
        "query",
        help="Query the cache; prints the result parquet path to stdout (D-10)",
    )
    qry.add_argument(
        "--currency", dest="currency", action="append", metavar="CURRENCY",
        help="Currency to query (repeatable; default: USD) [D-12]",
    )
    qry.add_argument(
        "--impact", dest="impact", action="append", metavar="IMPACT",
        help="Impact level to query (repeatable; default: high holiday) [D-12]",
    )
    qry.add_argument(
        "--start", default=None, metavar="YYYY-MM",
        help="First month to query (default: all cached)",
    )
    qry.add_argument(
        "--end", default=None, metavar="YYYY-MM",
        help="Last month to query (default: all cached)",
    )
    qry.add_argument(
        "--cache-dir", default=None, metavar="DIR",
        help="Override cache directory (default: ~/.cache/forexfactory) [CACHE-01]",
    )
    qry.add_argument(
        "--include-no-data",
        action="store_true",
        default=False,
        help="Include speech/no-data events (default: data-bearing + holidays only) [D-09]",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Validate optional YYYY-MM month strings
    _validate_month(args.start, "--start")
    _validate_month(args.end, "--end")

    # ── dispatch ──────────────────────────────────────────────────────────────
    if args.command == "refresh":
        cache_dir = Path(args.cache_dir) if args.cache_dir is not None else None
        result = _refresh.run_refresh(
            currencies=args.currency,   # None → service applies D-04 default
            impacts=args.impact,        # None → service applies D-04 default
            start=args.start,
            end=args.end,
            cache_dir=cache_dir,
            between_pages_delay=args.between_pages_delay,
            retry_delay=args.retry_delay,
        )
        logger.info(
            "[refresh] done — fetched=%d skipped=%d failed=%d",
            result["fetched"], result["skipped"], result["failed"],
        )
        return 0

    if args.command == "populate":
        cache_dir = Path(args.cache_dir) if args.cache_dir is not None else None
        result = _populate.run_populate(
            currencies=args.currency,   # None → service applies D-04 default (USD)
            impacts=args.impact,        # None → service applies D-04 default (high, holiday)
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
