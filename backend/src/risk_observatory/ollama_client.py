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

import json
import logging
import os
import re
import time
from typing import Any, Callable, Type, TypeVar

import ollama
from pydantic import BaseModel

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

ToolFn = Callable[[dict], Any]

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


def _tool_call_to_dict(tc: Any) -> dict:
    """Best-effort serialization of an Ollama ToolCall to a plain dict.

    The python `ollama` library returns Pydantic models whose `.model_dump()`
    sometimes drops the `function.arguments` dict when it has non-string values.
    We rebuild explicitly to be safe across library versions.
    """
    fn = getattr(tc, "function", None)
    name = getattr(fn, "name", None) if fn is not None else None
    args = getattr(fn, "arguments", None) if fn is not None else None
    return {
        "type": "function",
        "function": {"name": name, "arguments": args or {}},
    }


def chat_tools(
    *,
    model: str,
    system: str,
    user: str,
    tools: list[dict],
    dispatch: dict[str, ToolFn],
    schema: Type[T],
    options: dict | None = None,
    max_tool_rounds: int = 3,
) -> tuple[T, int, list[dict]]:
    """Multi-turn tool-calling loop ending in a schema-locked final answer.

    Two phases:
      1. Tool loop: call ollama.chat with `tools=`, no `format=`. Whenever the
         model returns tool_calls, execute them via `dispatch` and append the
         results as role="tool" messages. Loop up to `max_tool_rounds` rounds.
      2. Final pass: re-prompt with `format=schema` (no `tools=`) to force a
         JSON-schema-conformant answer.

    Returns (parsed_final, latency_ms, tool_trace). The trace is a list of
    {"round","name","args","result"} dicts useful for debugging / persisting.
    """
    t0 = time.perf_counter()
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    trace: list[dict] = []

    for round_idx in range(max_tool_rounds):
        resp = ollama.chat(
            model=model,
            messages=messages,
            tools=tools,
            options=options or OPTIONS_INGEST,
            think=False,
            stream=False,
        )
        msg = resp.message
        tcs = getattr(msg, "tool_calls", None) or []
        if not tcs:
            # Model is done calling tools. Bail out and let the final pass
            # enforce schema; we ignore msg.content here because it's not
            # schema-constrained yet.
            break

        # Persist the assistant turn that requested the tools (think-stripped,
        # tool_calls in OpenAI-compatible shape).
        messages.append(
            {
                "role": "assistant",
                "content": strip_think(msg.content or ""),
                "tool_calls": [_tool_call_to_dict(tc) for tc in tcs],
            }
        )

        for tc in tcs:
            fn_name = getattr(tc.function, "name", None) or ""
            raw_args = getattr(tc.function, "arguments", None) or {}
            # Some models return arguments as a JSON string instead of a dict.
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}
            fn = dispatch.get(fn_name)
            if fn is None:
                result: Any = {"error": f"unknown tool: {fn_name}"}
            else:
                try:
                    result = fn(raw_args)
                except Exception as e:  # noqa: BLE001
                    log.warning("tool %s raised: %s", fn_name, e)
                    result = {"error": str(e)}
            trace.append(
                {
                    "round": round_idx,
                    "name": fn_name,
                    "args": raw_args,
                    "result": result,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result, default=str),
                }
            )

    # Final schema-locked pass. Some Ollama builds reject `tools` + `format` in
    # the same call, so we drop tools here. Also force think=False to keep the
    # JSON parse clean.
    final = ollama.chat(
        model=model,
        messages=messages
        + [
            {
                "role": "user",
                "content": (
                    "Now emit the final JSON object matching the schema. "
                    "Do not call more tools. "
                    "If any lookup_location call returned country_iso, lat, "
                    "or lng, copy those exact values into the final JSON — "
                    "do not leave them null when a tool already gave them to you."
                ),
            }
        ],
        format=schema.model_json_schema(),
        options=options or OPTIONS_INGEST,
        think=False,
        stream=False,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    content = strip_think(final.message.content or "")
    return schema.model_validate_json(content), latency_ms, trace


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
