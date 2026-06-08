"""
Cache Filesystem Layout
========================
Owns all path resolution and manifest read/write for the forexfactory cache.
No other module hard-codes cache paths — they all go through here.

Usage:
    from forexfactory import _cache
    from pathlib import Path

    cache_dir = _cache.resolve_cache_dir()
    _cache.ensure_dirs(cache_dir)
    manifest = _cache.read_manifest(cache_dir)
"""
import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path

# ====== CONFIG ======
DEFAULT_CACHE_DIR: Path = Path.home() / ".cache" / "forexfactory"
CACHE_DIR_ENV: str = "FOREXFACTORY_CACHE_DIR"
# ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache-dir resolution (CACHE-01)
# ---------------------------------------------------------------------------

def resolve_cache_dir(cache_dir: Path | None = None) -> Path:
    """Return the cache directory as a Path.

    Precedence: explicit cache_dir arg > FOREXFACTORY_CACHE_DIR env var >
    DEFAULT_CACHE_DIR (~/.cache/forexfactory).
    """
    if cache_dir is not None:
        return Path(cache_dir)
    env_val = os.environ.get(CACHE_DIR_ENV)
    if env_val:
        return Path(env_val)
    return DEFAULT_CACHE_DIR


# ---------------------------------------------------------------------------
# Sub-directory and file path helpers
# ---------------------------------------------------------------------------

def raw_dir(cache_dir: Path) -> Path:
    """Return the raw JSON staging directory (D-03)."""
    return cache_dir / "raw"


def queries_dir(cache_dir: Path) -> Path:
    """Return the query result directory (D-08)."""
    return cache_dir / "queries"


def month_parquet_path(cache_dir: Path, anchor: date) -> Path:
    """Return the per-month parquet path for the given anchor date (D-01)."""
    return cache_dir / f"{anchor:%Y-%m}.parquet"


def raw_json_path(cache_dir: Path, anchor: date) -> Path:
    """Return the raw JSON staging path for the given anchor date (D-03)."""
    return raw_dir(cache_dir) / f"days_{anchor:%Y_%m}.json"


def manifest_path(cache_dir: Path) -> Path:
    """Return the manifest sidecar path."""
    return cache_dir / "manifest.json"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def ensure_dirs(cache_dir: Path) -> None:
    """Create cache_dir, raw/, and queries/ with exist_ok=True."""
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(raw_dir(cache_dir), exist_ok=True)
    os.makedirs(queries_dir(cache_dir), exist_ok=True)


# ---------------------------------------------------------------------------
# Manifest read / write (D-02)
# ---------------------------------------------------------------------------

def read_manifest(cache_dir: Path) -> dict:
    """Load manifest.json; return {} if missing or invalid JSON (warn-and-skip pattern)."""
    path = manifest_path(cache_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.warning("[manifest] bad JSON in %s — resetting to {}", path)
        return {}


def write_manifest(cache_dir: Path, manifest: dict) -> None:
    """Write manifest.json atomically using os.replace."""
    ensure_dirs(cache_dir)
    path = manifest_path(cache_dir)
    # Write to a temp file in the same directory then atomically rename.
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, prefix=".manifest.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if rename failed.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Manifest helpers (D-02 scope + provenance)
# ---------------------------------------------------------------------------

def update_manifest_month(
    cache_dir: Path,
    anchor: date,
    *,
    scraped_at: str,
    settled: bool,
    currencies: list,
    impacts: list,
) -> dict:
    """Read manifest, record scope + per-month provenance, write back, return manifest.

    Union-merges currencies/impacts into the existing scope (sorted set union) so
    that a second batch at a different scope doesn't erase the first batch's
    coverage.  Records manifest["months"][YYYY-MM] = {"scraped_at": ..., "settled": ...}.
    """
    manifest = read_manifest(cache_dir)
    # WR-01: union-merge so multiple populate batches accumulate coverage.
    existing_scope = manifest.get("scope", {})
    merged_currencies = sorted(
        set(existing_scope.get("currencies", [])) | set(currencies)
    )
    merged_impacts = sorted(
        set(existing_scope.get("impacts", [])) | set(impacts)
    )
    manifest["scope"] = {
        "currencies": merged_currencies,
        "impacts": merged_impacts,
    }
    manifest.setdefault("months", {})[f"{anchor:%Y-%m}"] = {
        "scraped_at": scraped_at,
        "settled": settled,
    }
    write_manifest(cache_dir, manifest)
    return manifest


def _scope_covers(scope: dict, currencies: list, impacts: list) -> bool:
    """Return True iff every requested currency and impact is in the manifest scope."""
    cached_currencies = scope.get("currencies", [])
    cached_impacts = scope.get("impacts", [])
    return all(c in cached_currencies for c in currencies) and all(
        i in cached_impacts for i in impacts
    )
