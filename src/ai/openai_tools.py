"""Adapter that converts the provider-agnostic TOOL_DECLS into OpenAI's
Realtime function-tool format, and translates tool-call event payloads
back into the dict shape that TOOL_HANDLERS already accepts.

This is intentionally a thin layer — all the actual tool *logic* still
lives in src/ai/tools.py and is shared with the Gemini path.
"""
from __future__ import annotations

from typing import Any

from src.ai.tools import TOOL_DECLS


def build_openai_tools() -> list[dict[str, Any]]:
    """Convert TOOL_DECLS into the list shape expected by Realtime
    session.update -> tools.

    OpenAI Realtime expects each tool to be:
        {
          "type": "function",
          "name": "...",
          "description": "...",
          "parameters": { JSON Schema },
        }

    Our TOOL_DECLS already store name/description/parameters as a
    JSON-Schema-ish dict (lowercase types). No type re-mapping is needed
    because OpenAI accepts standard JSON Schema directly.
    """
    out: list[dict[str, Any]] = []
    for t in TOOL_DECLS:
        out.append({
            "type": "function",
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        })
    return out


def describe_openai_tools() -> list[dict[str, Any]]:
    """Read-only schema view of every tool the OpenAI agent sees.

    Mirrors dashboard.server._describe_tools() so the AGENT SETTINGS
    panel can render the same tool cards regardless of provider.
    """
    out = []
    for t in build_openai_tools():
        out.append({
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        })
    return out
