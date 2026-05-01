"""Isolated test: does Gemini Live actually call our tool?

Bypasses all dashboard / audio machinery. Sends a text turn directly,
prints every message attribute, and reports whether tool_call ever fires.
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ai.tools import build_tools, TOOL_HANDLERS


async def run(model_name: str) -> None:
    print(f"\n{'='*60}\nTesting model: {model_name}\n{'='*60}")
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options={"api_version": "v1alpha"},
    )

    # Try the dict-form tools per Google's published examples
    tools_dict = [{
        "function_declarations": [{
            "name": "lookup_component",
            "description": (
                "Look up a factory component in the database. Returns "
                "rows with name, part_code, torque_spec, etc."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {
                        "type": "STRING",
                        "description": "Component name or part code",
                    },
                },
                "required": ["query"],
            },
        }]
    }]
    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
        tools=tools_dict,
        system_instruction=types.Content(parts=[types.Part.from_text(text=(
            "You are a factory assistant. You MUST call lookup_component "
            "for any question about a part. NEVER answer from memory."
        ))]),
    )

    saw_tool_call = False
    text_chunks: list[str] = []
    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            await session.send_client_content(turns=types.Content(
                role="user",
                parts=[types.Part.from_text(text="What's the torque spec on pump A3?")],
            ))
            n = 0
            async for message in session.receive():
                n += 1
                attrs = []
                for a in dir(message):
                    if a.startswith("_"):
                        continue
                    try:
                        v = getattr(message, a)
                    except Exception:
                        continue
                    if v is None or callable(v):
                        continue
                    attrs.append(a)
                print(f"[{n}] attrs={attrs}")

                tc = getattr(message, "tool_call", None)
                if tc and getattr(tc, "function_calls", None):
                    saw_tool_call = True
                    for fc in tc.function_calls:
                        args = dict(fc.args or {})
                        print(f"    TOOL CALL: {fc.name}({args})")
                        h = TOOL_HANDLERS.get(fc.name)
                        result = await h(args) if h else {"error": "no handler"}
                        print(f"    HANDLER RESULT: {str(result)[:300]}")
                        await session.send_tool_response(function_responses=[
                            types.FunctionResponse(
                                id=fc.id, name=fc.name,
                                response={"result": result},
                            )
                        ])
                sc = getattr(message, "server_content", None)
                if sc is not None:
                    parts = getattr(getattr(sc, "model_turn", None), "parts", None) or []
                    for p in parts:
                        t = getattr(p, "text", None)
                        if t:
                            text_chunks.append(t)
                            print(f"    TEXT: {t!r}")
                    if getattr(sc, "turn_complete", False):
                        print(f"    turn_complete after {n} msgs")
                        break
                if n > 80:
                    print("    [stopping after 80 msgs]")
                    break
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return

    print(f"\nRESULT: saw_tool_call={saw_tool_call}, "
          f"final_text={''.join(text_chunks)!r}")


async def main() -> None:
    for m in [
        "gemini-2.0-flash-live-001",
        "gemini-2.5-flash-preview-native-audio-dialog",
        "gemini-live-2.5-flash-preview",
    ]:
        try:
            await run(m)
        except Exception as e:
            print(f"  {m}: outer exception {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
