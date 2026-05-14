"""Generate the World Risk Brief with gemma4:26b-a4b."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from ..models import model_for
from ..ollama_client import OPTIONS_REASON, chat_structured
from ..schemas import ClusterSet, PersistedEvent, WorldBrief

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "brief.md"


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _serialise(clusters: ClusterSet, tail: list[PersistedEvent]) -> str:
    return json.dumps(
        {
            "clusters": [c.model_dump() for c in clusters.clusters],
            "tail": [
                {
                    "id": e.id,
                    "title": e.title,
                    "summary": e.summary,
                    "location": e.primary_location,
                    "country_iso": e.country_iso,
                    "category": e.category,
                    "severity": e.severity,
                    "published_at": e.published_at.isoformat(),
                }
                for e in tail
            ],
        },
        separators=(",", ":"),
    )


async def write(
    clusters: ClusterSet, tail: list[PersistedEvent]
) -> tuple[WorldBrief, int, str]:
    """Returns (brief, latency_ms, model)."""
    model = model_for("reason")
    brief, latency_ms = await asyncio.to_thread(
        chat_structured,
        model=model,
        system=_system_prompt(),
        user=_serialise(clusters, tail),
        schema=WorldBrief,
        options=OPTIONS_REASON,
        think=True,
    )
    return brief, latency_ms, model
