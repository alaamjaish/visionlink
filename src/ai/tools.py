"""Tool implementations for Gemini Live function calling.

Each handler is async, takes a dict of args from the model, and returns a
JSON-serializable dict that gets sent back to Gemini as the tool result.

Add a new tool by:
  1. Writing an async `handle_*` function
  2. Adding its declaration to TOOL_DECLS
  3. Registering it in TOOL_HANDLERS
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from google.genai import types as genai_types
from supabase import Client, create_client


_sb: Client | None = None


def _get_sb() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL or SUPABASE_SERVICE_KEY missing in .env"
            )
        _sb = create_client(url, key)
    return _sb


COMPONENT_COLS = (
    "name, part_code, description, "
    "torque_spec, maintenance_interval, safety_notes"
)


async def handle_lookup_component(args: dict[str, Any]) -> dict[str, Any]:
    """Search the components table by part_code (exact) then name (fuzzy)."""
    q = (args.get("query") or "").strip()
    if not q:
        return {"rows": []}

    sb = _get_sb()

    def _query() -> list[dict[str, Any]]:
        r = (sb.table("components")
               .select(COMPONENT_COLS)
               .ilike("part_code", q)
               .limit(3)
               .execute())
        if r.data:
            return r.data
        r = (sb.table("components")
               .select(COMPONENT_COLS)
               .ilike("name", f"%{q}%")
               .limit(3)
               .execute())
        return r.data or []

    rows = await asyncio.to_thread(_query)
    return {"rows": rows}


TOOL_DECLS: list[dict[str, Any]] = [
    {
        "name": "lookup_component",
        "description": (
            "Search the factory components database by name or part code. "
            "Use this for ANY question about a part, torque spec, "
            "maintenance interval, or safety note. Returns up to 3 rows "
            "with name, part_code, description, torque_spec, "
            "maintenance_interval, and safety_notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Component name (e.g. 'pump A3') or part code "
                        "(e.g. 'PMP-A3-IMP')."
                    ),
                },
            },
            "required": ["query"],
        },
    },
]


TOOL_HANDLERS = {
    "lookup_component": handle_lookup_component,
}


_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _schema_from_dict(d: dict[str, Any]) -> genai_types.Schema:
    """Convert an OpenAPI-ish dict into a typed genai Schema (uppercase enums)."""
    kwargs: dict[str, Any] = {}
    if "type" in d:
        kwargs["type"] = _TYPE_MAP.get(d["type"].lower(), d["type"].upper())
    if "description" in d:
        kwargs["description"] = d["description"]
    if "properties" in d:
        kwargs["properties"] = {
            k: _schema_from_dict(v) for k, v in d["properties"].items()
        }
    if "required" in d:
        kwargs["required"] = list(d["required"])
    if "items" in d:
        kwargs["items"] = _schema_from_dict(d["items"])
    return genai_types.Schema(**kwargs)


def build_tools() -> list[genai_types.Tool]:
    """Build the typed Tool list to plug into LiveConnectConfig(tools=...)."""
    decls = []
    for t in TOOL_DECLS:
        decls.append(genai_types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=_schema_from_dict(t["parameters"]),
        ))
    return [genai_types.Tool(function_declarations=decls)]
