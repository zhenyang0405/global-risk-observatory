"""NASA EONET (Earth Observatory Natural Event Tracker) feed.

EONET API v3: https://eonet.gsfc.nasa.gov/docs/v3
Open natural events (wildfires, severe storms, volcanoes, floods, icebergs,
landslides, sea/lake ice). Each event has a category and one or more
timestamped geometries (lat/lng or polygon). No API key, no auth.

We emit one StructuredEvent per EONET event, using the most-recent geometry
as the marker position. Bypasses the LLM extractor.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from ..schemas import StructuredEvent

EONET_EVENTS_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

_USER_AGENT = "Global-Risk-Observatory/0.1 (Kaggle Gemma 4 hackathon)"

# Map EONET category id -> our Severity. Defaults to "medium".
_SEVERITY_BY_CATEGORY: dict[str, str] = {
    "wildfires": "high",
    "severeStorms": "high",
    "floods": "high",
    "volcanoes": "high",
    "landslides": "medium",
    "drought": "medium",
    "dustHaze": "medium",
    "earthquakes": "high",          # EONET rarely uses this; USGS dominates.
    "manmade": "medium",
    "seaLakeIce": "low",
    "snow": "low",
    "tempExtremes": "medium",
    "waterColor": "low",
}


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    # EONET timestamps look like "2026-05-13T20:00:00Z"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coords_from_geometry(geom: dict) -> tuple[float, float] | None:
    """Extract (lat, lng) from an EONET geometry dict.

    Point geometries arrive as {"type": "Point", "coordinates": [lng, lat]}.
    Polygon geometries arrive as
    {"type": "Polygon", "coordinates": [[[lng, lat], ...]]} — use the centroid
    of the first ring as a rough pin.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Point":
        if len(coords) < 2:
            return None
        return float(coords[1]), float(coords[0])
    if gtype == "Polygon" and coords:
        ring = coords[0]
        if not ring:
            return None
        lats = [p[1] for p in ring if len(p) >= 2]
        lngs = [p[0] for p in ring if len(p) >= 2]
        if not lats or not lngs:
            return None
        return sum(lats) / len(lats), sum(lngs) / len(lngs)
    return None


async def fetch_events(
    *,
    days: int = 20,
    limit: int = 200,
    client: httpx.AsyncClient | None = None,
) -> list[StructuredEvent]:
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    params = {"status": "open", "days": str(days), "limit": str(limit)}
    headers = {"User-Agent": _USER_AGENT}
    try:
        r = await c.get(EONET_EVENTS_URL, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
    finally:
        if own_client:
            await c.aclose()

    raw_events = data.get("events", []) if isinstance(data, dict) else []
    out: list[StructuredEvent] = []
    for ev in raw_events:
        eid = ev.get("id")
        title = (ev.get("title") or "").strip()
        if not eid or not title:
            continue
        # EONET events can carry multiple categories; pick the first.
        categories = ev.get("categories") or []
        cat_id = (categories[0].get("id") if categories else "") or "other"
        cat_title = (categories[0].get("title") if categories else "") or cat_id

        # Most-recent geometry wins as the marker pin.
        geometries = ev.get("geometry") or []
        if not geometries:
            continue
        latest = max(
            geometries,
            key=lambda g: _parse_iso(g.get("date")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        latlng = _coords_from_geometry(latest)
        if latlng is None:
            continue
        lat, lng = latlng
        published_at = _parse_iso(latest.get("date")) or datetime.now(timezone.utc)

        # EONET 'sources' often points back to the underlying agency.
        sources_list = ev.get("sources") or []
        src_url = (sources_list[0].get("url") if sources_list else "") or ev.get("link") or ""
        url = src_url or f"https://eonet.gsfc.nasa.gov/api/v3/events/{eid}"

        summary = f"NASA EONET · {cat_title} · {published_at.date().isoformat()}"[:240]
        primary_location = title[:80]

        severity = _SEVERITY_BY_CATEGORY.get(cat_id, "medium")
        key_entities = [cat_title][:8]

        out.append(
            StructuredEvent(
                url=url,
                source="eonet",
                title=title[:120],
                summary=summary,
                primary_location=primary_location,
                country_iso=None,
                lat=lat,
                lng=lng,
                category="disaster",
                severity=severity,
                key_entities=key_entities,
                sentiment=-0.2,
                published_at=published_at,
            )
        )
    return out


# ---- CLI for the verification step ----


async def _main_once() -> None:
    events = await fetch_events()
    print(f"EONET returned {len(events)} events")
    for e in events[:6]:
        print(f"  - [{e.severity}] {e.title[:60]:<60}  ({e.lat:.2f}, {e.lng:.2f})")


if __name__ == "__main__":
    asyncio.run(_main_once())
