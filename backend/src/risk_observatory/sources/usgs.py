"""USGS earthquakes feed.

The USGS Earthquake Hazards Program publishes a family of GeoJSON summary
feeds: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/

We use the M2.5+ past-day feed because it gives ~50-200 events that paint the
globe immediately on cold start. Every feature ships lat/lng in the GeoJSON
payload, so this source bypasses the LLM extractor entirely and inserts
straight into the DB via repository.insert_structured_event.

No API key, no auth. Self-throttle is unnecessary at our 5-minute cadence.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from ..schemas import StructuredEvent

USGS_FEED_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
)

_USER_AGENT = "Global-Risk-Observatory/0.1 (Kaggle Gemma 4 hackathon)"


def _severity_for_magnitude(mag: float | None) -> str:
    """Map Richter-scale magnitude to our Severity enum.

    USGS magnitudes are roughly: 2.5 = barely felt, 4 = furniture shakes,
    5 = damage in poorly built structures, 6 = serious damage, 7+ = major.
    Matches the threshold rule used by tools.classify_severity_by_metric so the
    structured-feed severity and tool-derived severity always agree.
    """
    if mag is None:
        return "low"
    if mag < 4.0:
        return "low"
    if mag < 5.0:
        return "medium"
    if mag < 7.0:
        return "high"
    return "critical"


async def fetch_events(
    *,
    client: httpx.AsyncClient | None = None,
) -> list[StructuredEvent]:
    """Fetch the USGS M2.5+ past-day feed and convert features into StructuredEvents."""
    own_client = client is None
    c = client or httpx.AsyncClient(timeout=30.0)
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/geo+json"}
    try:
        r = await c.get(USGS_FEED_URL, headers=headers)
        r.raise_for_status()
        data = r.json()
    finally:
        if own_client:
            await c.aclose()

    features = data.get("features", []) if isinstance(data, dict) else []
    out: list[StructuredEvent] = []
    for f in features:
        props = f.get("properties") or {}
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or []
        # GeoJSON ordering is [lng, lat, depth].
        if len(coords) < 2:
            continue
        lng = coords[0]
        lat = coords[1]
        depth_km = coords[2] if len(coords) > 2 else None
        if lat is None or lng is None:
            continue
        mag = props.get("mag")
        place = (props.get("place") or "").strip() or "Unknown location"

        event_id = f.get("id") or props.get("code")
        if not event_id:
            continue
        url = props.get("url") or f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}"

        time_ms = props.get("time")
        if time_ms is None:
            continue
        try:
            published_at = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc)
        except (OSError, ValueError):
            continue

        # Build the human-readable strings. Keep them short to fit field caps.
        mag_str = f"M{mag:.1f}" if isinstance(mag, (int, float)) else "M?"
        title = f"{mag_str} earthquake — {place}"[:120]
        depth_part = f" · depth {depth_km:.0f} km" if isinstance(depth_km, (int, float)) else ""
        summary = f"USGS-reported {mag_str} earthquake near {place}{depth_part}."[:240]

        # primary_location: prefer the bit after the last "of" (USGS convention
        # like "10km NE of Adıyaman"), otherwise the whole place string.
        primary_location = place.rsplit(" of ", 1)[-1].strip() or place
        # Keyword entities: short tokens for downstream clustering.
        key_entities = ["earthquake"]
        if primary_location and primary_location != "Unknown location":
            key_entities.append(primary_location[:40])

        out.append(
            StructuredEvent(
                url=url,
                source="usgs",
                title=title,
                summary=summary,
                primary_location=primary_location[:80],
                country_iso=None,  # USGS does not provide ISO country code.
                lat=float(lat),
                lng=float(lng),
                category="disaster",
                severity=_severity_for_magnitude(mag if isinstance(mag, (int, float)) else None),
                key_entities=key_entities[:8],
                sentiment=-0.3,  # Mild negative; this is a disaster feed.
                published_at=published_at,
            )
        )
    return out


# ---- CLI for the verification step ----


async def _main_once() -> None:
    events = await fetch_events()
    print(f"USGS returned {len(events)} events")
    crit = sum(1 for e in events if e.severity == "critical")
    high = sum(1 for e in events if e.severity == "high")
    print(f"  critical={crit}  high={high}")
    for e in events[:5]:
        print(f"  - [{e.severity}] {e.title}  ({e.lat:.2f}, {e.lng:.2f})")


if __name__ == "__main__":
    asyncio.run(_main_once())
