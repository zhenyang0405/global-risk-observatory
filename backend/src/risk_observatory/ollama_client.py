"""Thin Ollama wrapper. Lifted from Global-Resilience, adapted for Gemma 4.

Key adaptations vs. the source:
- `OPTIONS_INGEST` / `OPTIONS_REASON` honour the Gemma 4 model card sampler
  recommendations (temp=1.0, top_p=0.95, top_k=64 for reasoning; temp=0 for
  schema-enforced extraction).
- `_strip_think` removes <|think|>...<|/think|> blocks before re-sending history
  on multi-turn (Gemma 4 model card explicit requirement).
- `num_ctx` clamped per role to leave KV-cache headroom when both models are
  resident.
"""

from __future__ import annotations

import os
import re
import time
from typing import Type, TypeVar

import ollama
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

_THINK_RE = re.compile(r"<\|think\|>.*?<\|/think\|>", re.DOTALL)


def strip_think(text: str) -> str:
    """Strip <|think|>...<|/think|> blocks from a model response.

    Gemma 4 multi-turn requirement: assistant turns kept in history must NOT
    include the think block. Use this before appending a prior reply to a
    subsequent turn.
    """
    return _THINK_RE.sub("", text).strip()


OPTIONS_INGEST = {
    "temperature": 0.0,
    "num_ctx": 8192,
}

OPTIONS_REASON = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "num_ctx": 32768,
}


class LLMCall(BaseModel):
    """What every chat_* helper returns: the parsed value + telemetry."""

    parsed: object  # actually T at the call site
    latency_ms: int
    model: str


def chat_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    options: dict | None = None,
    think: bool = False,
) -> tuple[T, int]:
    """Single-turn chat with JSON-schema-constrained output. Returns (parsed, latency_ms)."""
    t0 = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format=schema.model_json_schema(),
        options=options or OPTIONS_INGEST,
        think=think,
        stream=False,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    content = response.message.content or ""
    # In case the model leaks the think block into content despite think=True
    # consuming it, scrub before parsing.
    content = strip_think(content)
    return schema.model_validate_json(content), latency_ms


def warmup(model: str) -> None:
    """Fire a tiny generation to load weights into memory. Best-effort."""
    try:
        ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "."}],
            options={"num_predict": 1, "temperature": 0.0},
            stream=False,
        )
    except Exception:
        # warmup is fire-and-forget; if Ollama isn't up yet we'll retry on first real call.
        pass
