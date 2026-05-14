"""Centralised model role registry. Never hardcode model ids elsewhere."""

from __future__ import annotations

from typing import Literal

from .config import SETTINGS

ModelRole = Literal["ingest", "reason"]


MODELS: dict[ModelRole, str] = {
    "ingest": SETTINGS.model_ingest,
    "reason": SETTINGS.model_reason,
}

ACTIVE_MODELS: tuple[str, ...] = tuple(set(MODELS.values()))


def model_for(role: ModelRole) -> str:
    return MODELS[role]
