"""On-disk cache for source images.

Used by the vision-ingestion path so we (a) avoid re-downloading the same
publisher image on every replay, (b) serve images through our own API to
sidestep hot-link blocks and CORS, and (c) give a future Gemma 4:26b pass
a stable local path to read from.

Filenames are sha256(source_url).jpg under SETTINGS.image_cache_path.
Existing files short-circuit the HTTP fetch.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..config import SETTINGS

log = logging.getLogger(__name__)

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_TIMEOUT_S = 10.0


def _hash_for(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def cache_path_for(url: str) -> Path:
    return SETTINGS.image_cache_path / f"{_hash_for(url)}.jpg"


def _ensure_dir() -> None:
    SETTINGS.image_cache_path.mkdir(parents=True, exist_ok=True)


async def fetch_and_cache(url: str) -> tuple[Path, bytes] | None:
    """Return (local_path, raw_bytes) or None on any failure.

    Handles both http(s) URLs and file:// URLs / bare local paths so the same
    helper backs both the live ingestion path and the CLI demo path.
    Never raises — image fetch is best-effort.
    """
    if not url:
        return None
    _ensure_dir()

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # --- local file path branch -----------------------------------------------
    if scheme in ("", "file"):
        local_src = Path(parsed.path if scheme == "file" else url).expanduser()
        if not local_src.is_file():
            log.warning("image_cache: local file not found: %s", local_src)
            return None
        try:
            data = local_src.read_bytes()
        except OSError as e:
            log.warning("image_cache: read failed for %s: %s", local_src, e)
            return None
        if len(data) > _MAX_BYTES:
            log.warning("image_cache: %s exceeds %d bytes", local_src, _MAX_BYTES)
            return None
        dest = cache_path_for(url)
        if not dest.exists():
            try:
                dest.write_bytes(data)
            except OSError as e:
                log.warning("image_cache: write failed for %s: %s", dest, e)
                return None
        return dest, data

    # --- http(s) branch -------------------------------------------------------
    if scheme not in ("http", "https"):
        log.warning("image_cache: unsupported scheme %r in %s", scheme, url)
        return None

    dest = cache_path_for(url)
    if dest.exists():
        try:
            return dest, dest.read_bytes()
        except OSError as e:
            log.warning("image_cache: re-read cache miss for %s: %s", dest, e)
            # fall through to refetch

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_S, follow_redirects=True
        ) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "global-risk-observatory/0.1 (+hackathon)",
                    "Accept": "image/*",
                },
            )
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        log.warning("image_cache: fetch failed for %s: %s", url, e)
        return None

    if resp.status_code != 200:
        log.warning("image_cache: %s returned HTTP %d", url, resp.status_code)
        return None

    ctype = resp.headers.get("content-type", "").lower()
    if not ctype.startswith("image/"):
        log.warning("image_cache: %s served non-image content-type %r", url, ctype)
        return None

    data = resp.content
    if len(data) > _MAX_BYTES:
        log.warning(
            "image_cache: %s exceeded %d bytes (got %d)", url, _MAX_BYTES, len(data)
        )
        return None

    try:
        dest.write_bytes(data)
    except OSError as e:
        log.warning("image_cache: write failed for %s: %s", dest, e)
        return None

    return dest, data
