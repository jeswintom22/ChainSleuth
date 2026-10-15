"""Thin LLM wrapper (LiteLLM, the same provider layer the GraphRAG SDK uses)."""
from __future__ import annotations

import os
from typing import Any

from app.config import settings


def llm_available() -> bool:
    return bool(settings.openai_api_key) and os.getenv("CHAINSLEUTH_DISABLE_LLM") != "1"


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict[str, Any]:
    import litellm  # imported lazily: slow import, and optional at runtime

    litellm.suppress_debug_info = True
    kwargs: dict[str, Any] = {"model": settings.llm_model, "messages": messages, "temperature": 0, "timeout": 60,
                              "api_key": settings.openai_api_key}
    if tools:
        kwargs.update(tools=tools, tool_choice="auto")
    msg = litellm.completion(**kwargs).choices[0].message
    calls = [{"id": c.id, "name": c.function.name, "arguments": c.function.arguments} for c in (msg.tool_calls or [])]
    return {"content": msg.content or "", "tool_calls": calls}
