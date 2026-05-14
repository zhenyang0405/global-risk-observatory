"""Download GeoNames cities15000 gazetteer to data/cities15000.txt.

cities15000 = all cities with population > 15,000 (~25k rows, ~3 MB unzipped).
Tab-delimited per https://download.geonames.org/export/dump/readme.txt
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import httpx

URL = "https://download.geonames.org/export/dump/cities15000.zip"
OUT = Path(__file__).resolve().parents[2] / "data" / "cities15000.txt"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL} ...")
    with httpx.Client(timeout=120.0, follow_redirects=True) as c:
        r = c.get(URL)
        r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    inner = "cities15000.txt"
    if inner not in zf.namelist():
        print(f"expected {inner} in zip; got {zf.namelist()}", file=sys.stderr)
        return 1
    OUT.write_bytes(zf.read(inner))
    n = sum(1 for _ in OUT.open())
    print(f"wrote {OUT} ({n} rows, {OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
