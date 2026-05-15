"""Serve cached source images.

The on-disk cache lives at SETTINGS.image_cache_path keyed by sha256(url).jpg.
This route exposes those files to the frontend so the browser doesn't have to
hot-link the publisher's CDN (which often blocks referer or sets aggressive
CORS).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import SETTINGS

router = APIRouter()

# sha256 hex digest is exactly 64 hex chars. The strict guard is also a
# path-traversal defence.
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@router.get("/images/{name}.jpg")
def get_image(name: str) -> FileResponse:
    if not _HASH_RE.match(name):
        raise HTTPException(status_code=400, detail="bad image name")
    path = SETTINGS.image_cache_path / f"{name}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
