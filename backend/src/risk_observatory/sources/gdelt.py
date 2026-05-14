"""GDELT 2.0 DOC API client.

GDELT DOC API: https://api.gdeltproject.org/api/v2/doc/doc
- No API key, no daily cap. Self-throttle to ~1 req / 5s.
- ArtList format returns up to 250 articles per call.
- We filter at the query level (theme: filter) to pre-narrow to risk-relevant
  CAMEO themes. Each call returns ~recent articles ordered by date desc.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable

import httpx

from ..schemas import RawArticle

# CAMEO-aligned GDELT themes that map to our risk categories.
# Pulled from GDELT theme list (https://www.gdeltproject.org/data/lookups/CAMEO.txtcountrycode.txt
# and related). Curated for high signal.
DEFAULT_THEMES: tuple[str, ...] = (
    "ARMEDCONFLICT",
    "TERROR",
    "PROTEST",
    "NATURAL_DISASTER",
    "EPIDEMIC",
    "ECON_BANKRUPTCY",
    "FORCED_DISPLACEMENT",
    "REFUGEES",
    "WB_2487_KILLINGS",
    "CRISISLEX_CRISISLEXREC",
)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

_USER_AGENT = "Global-Risk-Observatory/0.1 (Kaggle Gemma 4 hackathon)"


def _theme_query(themes: Iterable[str]) -> str:
    return "(" + " OR ".join(f"theme:{t}" for t in themes) + ")"


def _parse_seendate(s: str) -> datetime:
    # GDELT format: YYYYMMDDTHHMMSSZ
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


async def fetch_articles(
    *,
    themes: Iterable[str] = DEFAULT_THEMES,
    max_records: int = 75,
    timespan: str = "30min",
    client: httpx.AsyncClient | None = None,
) -> list[RawArticle]:
    """Query GDELT DOC API and return a list of RawArticles.

    timespan accepts strings like "15min", "30min", "1h", "24h".
    """
    query = _theme_query(themes) + " sourcelang:eng"
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(min(max_records, 250)),
        "timespan": timespan,
        "sort": "DateDesc",
    }
    headers = {"User-Agent": _USER_AGENT}

    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    try:
        r = await c.get(GDELT_DOC_URL, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
    finally:
        if own_client:
            await c.aclose()

    articles_raw = data.get("articles", []) if isinstance(data, dict) else []
    out: list[RawArticle] = []
    for a in articles_raw:
        url = a.get("url")
        title = (a.get("title") or "").strip()
        seendate = a.get("seendate")
        if not url or not title or not seendate:
            continue
        try:
            published = _parse_seendate(seendate)
        except ValueError:
            continue

        lat = a.get("sourcelat")
        lng = a.get("sourcelng")
        # GDELT sometimes returns 0/0 for "unknown"; treat (0,0) as missing.
        if lat == 0 and lng == 0:
            lat = lng = None

        out.append(
            RawArticle(
                url=url,
                source="gdelt",
                title=title,
                body=None,  # DOC API does not return body
                published_at=published,
                gdelt_country=a.get("sourcecountry"),
                gdelt_lat=lat,
                gdelt_lng=lng,
            )
        )
    return out


# ---- CLI for the verification step ----


async def _main_once() -> None:
    articles = await fetch_articles()
    print(f"GDELT returned {len(articles)} articles")
    geocoded = sum(1 for a in articles if a.gdelt_lat is not None)
    print(f"  with pre-geocoded coords: {geocoded}")
    for a in articles[:5]:
        print(f"  - [{a.gdelt_country}] {a.title[:80]}")


if __name__ == "__main__":
    asyncio.run(_main_once())
