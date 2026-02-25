"""
ClawFounder — Chat Agent (JSONL streaming)

Reads a JSON request from stdin, runs an agentic loop with the chosen LLM,
and outputs JSONL events to stdout for the dashboard to consume via SSE.

Events emitted:
  {"type": "thinking",    "text": "..."}
  {"type": "tool_call",   "tool": "...", "connector": "...", "args": {...}}
  {"type": "tool_result", "tool": "...", "result": "...", "truncated": bool}
  {"type": "text",        "text": "..."}
  {"type": "error",       "error": "..."}
  {"type": "done"}
"""

import sys
import os
import json
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def emit(event):
    """Write a JSONL event to stdout."""
    print(json.dumps(event, default=str), flush=True)


# ── Load connectors ─────────────────────────────────────────────

def load_all_connectors():
    """Load all connectors that have their deps available."""
    connectors_dir = PROJECT_ROOT / "connectors"
    loaded = {}

    for folder in sorted(connectors_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_") or folder.name.startswith("."):
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"connectors.{folder.name}.connector",
                folder / "connector.py",
                submodule_search_locations=[str(folder)],
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "TOOLS") and hasattr(module, "handle"):
                loaded[folder.name] = module
        except Exception:
            pass  # Skip connectors with missing deps

    return loaded


# ── Gemini via Python SDK (gemini-3-flash-preview + thinking) ────

GEMINI_MODEL = "gemini-3-flash-preview"


def run_gemini(message, history, connectors):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_CLOUD_API_KEY", "")
    if not api_key:
        emit({"type": "error", "error": "GEMINI_API_KEY not set."})
        return

    client = genai.Client(vertexai=True, api_key=api_key)
    emit({"type": "thinking", "text": f"Using {GEMINI_MODEL} with thinking..."})

    # Build tool declarations from connectors
    all_tools = []
    tool_map = {}  # tool_name -> (connector_name, module)
    for conn_name, module in connectors.items():
        for tool in module.TOOLS:
            all_tools.append(types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool.get("parameters", {}),
            ))
            tool_map[tool["name"]] = (conn_name, module)

    gemini_tools = types.Tool(function_declarations=all_tools) if all_tools else None

    system = (
        "You are ClawFounder 🦀 — a personal AI agent that can take real actions "
        "using connected services. Use the available tools to help the user. "
        "Be concise and helpful. When you use tools, explain what you're doing."
    )

    # Build conversation history
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(
            role=role,
            parts=[types.Part(text=msg["text"])],
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=message)],
    ))

    # Generation config with thinking
    config = types.GenerateContentConfig(
        tools=[gemini_tools] if gemini_tools else [],
        system_instruction=system,
        temperature=1,
        top_p=0.95,
        max_output_tokens=65535,
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
    )

    # Agentic loop
    max_turns = 20
    for turn in range(max_turns):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
        except Exception as e:
            emit({"type": "error", "error": str(e)[:300]})
            return

        if not response.candidates or not response.candidates[0].content:
            emit({"type": "error", "error": "Empty response from Gemini"})
            return

        # Process parts
        has_function_calls = False
        function_response_parts = []

        for part in response.candidates[0].content.parts:
            # Skip thinking parts (internal reasoning)
            if hasattr(part, 'thought') and part.thought:
                continue

            if part.function_call:
                has_function_calls = True
                fc = part.function_call
                tool_name = fc.name
                args = dict(fc.args) if fc.args else {}
                conn_name, module = tool_map.get(tool_name, ("unknown", None))

                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

                # Execute tool
                if module:
                    try:
                        result = module.handle(tool_name, args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                else:
                    result = f"Unknown tool: {tool_name}"

                truncated = len(result) > 500 if isinstance(result, str) else False
                emit({
                    "type": "tool_result",
                    "tool": tool_name,
                    "connector": conn_name,
                    "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                    "truncated": truncated,
                })

                function_response_parts.append(
                    types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    ))
                )

            elif part.text:
                if not has_function_calls:
                    emit({"type": "text", "text": part.text})

        if not has_function_calls:
            break

        # Continue the loop with tool results
        contents.append(response.candidates[0].content)
        contents.append(types.Content(
            role="user",
            parts=function_response_parts,
        ))

    emit({"type": "done"})


# ── Provider: OpenAI ─────────────────────────────────────────────

def run_openai(message, history, connectors):
    import requests

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "OPENAI_API_KEY not set"})
        return

    emit({"type": "thinking", "text": "Connecting to OpenAI..."})

    # Build tool definitions
    tool_defs = []
    tool_map = {}
    for conn_name, module in connectors.items():
        for tool in module.TOOLS:
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            })
            tool_map[tool["name"]] = (conn_name, module)

    messages = [{"role": "system", "content": "You are ClawFounder 🦀 — a personal AI agent. Be concise and helpful."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["text"]})
    messages.append({"role": "user", "content": message})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    max_turns = 20
    for turn in range(max_turns):
        body = {"model": "gpt-4o-mini", "messages": messages}
        if tool_defs:
            body["tools"] = tool_defs

        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=60)
        except Exception as e:
            emit({"type": "error", "error": f"Network error: {e}"})
            return

        if resp.status_code != 200:
            emit({"type": "error", "error": f"OpenAI error ({resp.status_code}): {resp.text[:200]}"})
            return

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]

        if msg.get("tool_calls"):
            messages.append(msg)

            for tc in msg["tool_calls"]:
                tool_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {}
                conn_name, module = tool_map.get(tool_name, ("unknown", None))

                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

                if module:
                    try:
                        result = module.handle(tool_name, args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                else:
                    result = f"Unknown tool: {tool_name}"

                emit({
                    "type": "tool_result", "tool": tool_name, "connector": conn_name,
                    "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                    "truncated": len(result) > 500 if isinstance(result, str) else False,
                })

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        else:
            if msg.get("content"):
                emit({"type": "text", "text": msg["content"]})
            break

    emit({"type": "done"})


# ── Provider: Claude ─────────────────────────────────────────────

def run_claude(message, history, connectors):
    import requests

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "ANTHROPIC_API_KEY not set"})
        return

    emit({"type": "thinking", "text": "Connecting to Claude..."})

    # Build tool definitions
    tool_defs = []
    tool_map = {}
    for conn_name, module in connectors.items():
        for tool in module.TOOLS:
            tool_defs.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            })
            tool_map[tool["name"]] = (conn_name, module)

    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["text"]})
    messages.append({"role": "user", "content": message})

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    max_turns = 20
    for turn in range(max_turns):
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": "You are ClawFounder 🦀 — a personal AI agent. Be concise and helpful.",
            "messages": messages,
        }
        if tool_defs:
            body["tools"] = tool_defs

        try:
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=60)
        except Exception as e:
            emit({"type": "error", "error": f"Network error: {e}"})
            return

        if resp.status_code != 200:
            emit({"type": "error", "error": f"Claude error ({resp.status_code}): {resp.text[:200]}"})
            return

        data = resp.json()
        has_tool_use = False
        tool_results = []

        for block in data.get("content", []):
            if block["type"] == "text":
                if not has_tool_use:
                    emit({"type": "text", "text": block["text"]})

            elif block["type"] == "tool_use":
                has_tool_use = True
                tool_name = block["name"]
                args = block.get("input", {})
                conn_name, module = tool_map.get(tool_name, ("unknown", None))

                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

                if module:
                    try:
                        result = module.handle(tool_name, args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                else:
                    result = f"Unknown tool: {tool_name}"

                emit({
                    "type": "tool_result", "tool": tool_name, "connector": conn_name,
                    "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                    "truncated": len(result) > 500 if isinstance(result, str) else False,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

        if not has_tool_use or data.get("stop_reason") != "tool_use":
            break

        messages.append({"role": "assistant", "content": data["content"]})
        messages.append({"role": "user", "content": tool_results})

    emit({"type": "done"})


# ── Main ─────────────────────────────────────────────────────────

def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception as e:
        emit({"type": "error", "error": f"Invalid input: {e}"})
        emit({"type": "done"})
        return

    message = input_data.get("message", "")
    provider = input_data.get("provider", "gemini")
    chat_history = input_data.get("history", [])

    if not message.strip():
        emit({"type": "error", "error": "Empty message"})
        emit({"type": "done"})
        return

    # Load connectors
    connectors = load_all_connectors()
    emit({"type": "thinking", "text": f"Loaded {len(connectors)} connector(s): {', '.join(connectors.keys())}"})

    # Route to provider
    providers = {
        "gemini": run_gemini,
        "openai": run_openai,
        "claude": run_claude,
    }

    run_fn = providers.get(provider)
    if not run_fn:
        emit({"type": "error", "error": f"Unknown provider: {provider}"})
        emit({"type": "done"})
        return

    try:
        run_fn(message, chat_history, connectors)
    except Exception as e:
        emit({"type": "error", "error": f"Agent error: {e}"})
        emit({"type": "done"})


if __name__ == "__main__":
    main()
