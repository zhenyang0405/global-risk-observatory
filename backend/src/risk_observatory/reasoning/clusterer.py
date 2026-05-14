"""Cluster recent events with gemma4:26b-a4b."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Iterable

from ..models import model_for
from ..ollama_client import OPTIONS_REASON, chat_structured
from ..schemas import ClusterSet, PersistedEvent

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "cluster.md"


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _serialise(events: Iterable[PersistedEvent]) -> str:
    payload = [
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
        for e in events
    ]
    return json.dumps(payload, separators=(",", ":"))


async def cluster(events: list[PersistedEvent]) -> ClusterSet:
    if not events:
        return ClusterSet(clusters=[])
    model = model_for("reason")
    cs, _ = await asyncio.to_thread(
        chat_structured,
        model=model,
        system=_system_prompt(),
        user=f"EVENTS:\n{_serialise(events)}",
        schema=ClusterSet,
        options=OPTIONS_REASON,
        think=True,
    )
    return cs
