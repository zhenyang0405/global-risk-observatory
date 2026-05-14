"""Tool dispatch table for Gemma 4 tool-calling extraction.

Each tool is a pure function: dict -> JSON-serialisable dict. Tools must open
their own DB connection inside the body and close it before returning.

The TOOL_DEFS list mirrors Ollama's OpenAI-compatible tool-call schema; it is
passed verbatim to the `tools=` parameter of ollama.chat(). The DISPATCH map
is consumed by ollama_client.chat_tools() to route a tool_call by name.
"""

from __future__ import annotations

import logging
from typing import Any

from ..geocoding.gazetteer import get_gazetteer
from ..store import repository as repo
from ..store.connection import connect

log = logging.getLogger(__name__)


# ---- Tool 1: lookup_location -------------------------------------------------


def lookup_location(args: dict) -> dict:
    """Resolve a place name to canonical lat/lng/country via the GeoNames gazetteer.

    Args:
      name: city/region name as written in the article.
      country_hint: optional ISO-3166 alpha-2 code to disambiguate.
    """
    name = (args.get("name") or "").strip()
    hint = (args.get("country_hint") or "").strip() or None
    if not name:
        return {"error": "missing 'name'"}
    city = get_gazetteer().resolve_full(name, hint)
    if city is None:
        return {"error": "not_found", "name": name}
    return {
        "name": city.name,
        "lat": city.lat,
        "lng": city.lng,
        "country_iso": city.country or None,
    }


# ---- Tool 2: classify_severity_by_metric ------------------------------------

# Each rule is a sorted list of (threshold, severity). The first threshold the
# value is strictly LESS than wins. Values >= the last threshold are critical.
_RULES: dict[str, list[tuple[float, str]]] = {
    "earthquake_magnitude": [
        (4.0, "low"),
        (5.0, "medium"),
        (7.0, "high"),        # USGS calls M7+ "major"
        (10.0, "critical"),
    ],
    "fatalities": [
        (1, "low"),
        (10, "medium"),
        (100, "high"),
        (10**9, "critical"),
    ],
    "displaced": [
        (1000, "low"),
        (10_000, "medium"),
        (100_000, "high"),
        (10**9, "critical"),
    ],
    "wind_speed_kmh": [
        (60, "low"),
        (120, "medium"),
        (180, "high"),
        (10**6, "critical"),
    ],
}


def classify_severity_by_metric(args: dict) -> dict:
    """Map a quantitative anchor to a deterministic severity bucket.

    Args:
      metric: one of {earthquake_magnitude, fatalities, displaced, wind_speed_kmh}.
      value:  number.
    """
    metric = args.get("metric")
    value = args.get("value")
    rules = _RULES.get(metric) if isinstance(metric, str) else None
    if rules is None:
        return {"error": f"unsupported metric: {metric!r}"}
    if not isinstance(value, (int, float)):
        return {"error": f"value must be numeric, got {type(value).__name__}"}

    for threshold, sev in rules:
        if value < threshold:
            return {
                "severity": sev,
                "rationale": f"{metric}={value} < {threshold} -> {sev}",
            }
    # Above all thresholds (the table's last entry is intentionally astronomical).
    return {
        "severity": "critical",
        "rationale": f"{metric}={value} above all thresholds",
    }


# ---- Tool 3: find_similar_recent_events --------------------------------------


def find_similar_recent_events(args: dict) -> dict:
    """Search the last 12 hours of events for similar reports.

    Args:
      query: short search phrase ('earthquake turkey', 'flood manila', ...).
      k:     max results; default 3, capped at 5.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"matches": []}
    try:
        k = int(args.get("k", 3))
    except (TypeError, ValueError):
        k = 3
    k = max(1, min(k, 5))

    conn = connect()
    try:
        rows = repo.search_recent(conn, query=query, hours=12, limit=k)
    except Exception as e:  # noqa: BLE001
        log.warning("find_similar_recent_events failed: %s", e)
        return {"matches": [], "error": str(e)}
    finally:
        conn.close()

    return {
        "matches": [
            {
                "id": r.id,
                "title": r.title,
                "primary_location": r.primary_location,
                "country_iso": r.country_iso,
                "category": r.category,
                "severity": r.severity,
                "published_at": r.published_at.isoformat(),
            }
            for r in rows
        ]
    }


# ---- Registry exported to the extractor -------------------------------------


TOOL_DEFS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_location",
            "description": (
                "Resolve a place name to canonical lat/lng/country via the local "
                "GeoNames gazetteer. Always prefer this over guessing coordinates. "
                "Returns {name, lat, lng, country_iso} or {error: 'not_found'}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "City or region as written in the article.",
                    },
                    "country_hint": {
                        "type": "string",
                        "description": "ISO-3166 alpha-2 country code if known (e.g. 'TR').",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_severity_by_metric",
            "description": (
                "Map a quantitative anchor (magnitude, fatalities, displaced, wind "
                "speed) to a severity bucket. Use whenever the article gives a "
                "number; do not guess severity yourself in that case."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": [
                            "earthquake_magnitude",
                            "fatalities",
                            "displaced",
                            "wind_speed_kmh",
                        ],
                    },
                    "value": {"type": "number"},
                },
                "required": ["metric", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_recent_events",
            "description": (
                "Search the last 12 hours of stored events for similar reports. "
                "Use to ground titles/summaries against known recent context; do NOT "
                "use to skip extraction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Short search phrase, e.g. 'earthquake turkey'.",
                    },
                    "k": {
                        "type": "integer",
                        "description": "Max results (1-5). Default 3.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# Dispatch table: name -> function. Consumed by ollama_client.chat_tools().
DISPATCH: dict[str, Any] = {
    "lookup_location": lookup_location,
    "classify_severity_by_metric": classify_severity_by_metric,
    "find_similar_recent_events": find_similar_recent_events,
}
