"""
ClawFounder — Voice Agent (Gemini Live API)

Long-running async process that bridges stdin/stdout JSONL to the Gemini Live API
for real-time voice interaction. Spawned by server.js for each voice session.

Protocol (stdin ← server.js):
  {"type": "setup", "api_key": "..."}
  {"type": "audio", "data": "<base64 PCM 16kHz 16-bit mono>"}
  {"type": "end"}

Protocol (stdout → server.js):
  {"type": "ready"}
  {"type": "audio", "data": "<base64 PCM 24kHz 16-bit mono>"}
  {"type": "text", "text": "..."}
  {"type": "tool_call", "id": "...", "name": "...", "args": {...}}
  {"type": "tool_result", "id": "...", "result": "..."}
  {"type": "turn_complete"}
  {"type": "interrupted"}
  {"type": "error", "error": "..."}
"""

import sys
import os
import json
import asyncio
import base64
import copy
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent_shared import (
    setup_env, emit, load_all_connectors, call_tool as _call_tool, get_briefing as _get_briefing,
)
setup_env()


# Voice-appropriate tools — kept minimal for Gemini Live API stability.
# Each tool declaration adds to the session config size.
VOICE_TOOL_WHITELIST = {
    # Email (read + reply + forward — the voice essentials)
    "gmail_get_unread", "gmail_search", "gmail_read_email",
    "gmail_send", "gmail_reply", "gmail_forward",
    "work_email_get_unread", "work_email_search", "work_email_read_email",
    "work_email_send", "work_email_reply", "work_email_forward",
    # GitHub (read-only summaries)
    "github_notifications", "github_list_prs", "github_get_pr",
    "github_list_issues", "github_get_issue",
    # Quick lookups
    "yahoo_finance_quote",
    "telegram_get_updates", "telegram_send_message",
    # Knowledge
    "search_knowledge",
}


def build_tools_and_map(connectors):
    """Build tool definitions and routing map (voice-filtered)."""
    all_tools = []
    tool_map = {}

    for conn_name, info in connectors.items():
        module = info["module"]
        accounts = info["accounts"]
        supports_multi = info["supports_multi"]

        for tool in module.TOOLS:
            # Skip tools not in the voice whitelist
            if tool["name"] not in VOICE_TOOL_WHITELIST:
                continue

            if supports_multi and len(accounts) > 1:
                tool_def = copy.deepcopy(tool)
                params = tool_def.setdefault("parameters", {"type": "object", "properties": {}})
                props = params.setdefault("properties", {})
                required = params.setdefault("required", [])
                account_ids = [a["id"] for a in accounts]
                account_labels = {a["id"]: a.get("label", a["id"]) for a in accounts}
                desc_parts = ", ".join(f'"{aid}" ({account_labels[aid]})' for aid in account_ids)
                props["account"] = {
                    "type": "string",
                    "enum": account_ids,
                    "description": f"Which account to use: {desc_parts}",
                }
                if "account" not in required:
                    required.append("account")
                all_tools.append(tool_def)
            else:
                all_tools.append(tool)

            tool_map[tool["name"]] = (conn_name, module, accounts)

    return all_tools, tool_map


# Briefing tool definition for Gemini
BRIEFING_TOOL_DEF = {
    "name": "get_briefing",
    "description": "Get a summary of everything happening across the user's connected services — emails, GitHub notifications, stock prices, messages, etc. Use this when the user asks for a summary, briefing, or update on what's going on.",
    "parameters": {"type": "object", "properties": {}},
}


def build_system_prompt(connectors):
    """Build a lean voice-appropriate system prompt.

    IMPORTANT: Keep this small — Gemini Live counts system instructions + tool
    definitions toward context. Tool descriptions are already in function
    declarations, so we do NOT load connector instructions.md files here.
    """
    lines = [
        "You are ClawFounder, a predictive PM speaking via voice. Be punchy — 2-3 sentences max.",
        "",
        "How you work:",
        "- React to what you see. Email needs reply? Draft it: 'I'd say [draft]. Send it?'",
        "- Cross-reference everything. Email asks about X? Check GitHub/knowledge first.",
        "- Propose actions, let the user approve or deny. Minimize user thinking.",
        "- Read-only actions: just do them. Send/modify/delete: confirm first.",
        "- If a tool fails, say so naturally and check knowledge base for context.",
        "- Speak naturally — no markdown, no bullet points, no formatting.",
    ]

    # List connected services and accounts (compact, no full instruction files)
    service_parts = []
    for conn_name in sorted(connectors.keys()):
        info = connectors[conn_name]
        accounts = info.get("accounts", []) if isinstance(info, dict) else []
        if len(accounts) > 1:
            labels = ", ".join(a.get("label", a["id"]) for a in accounts)
            service_parts.append(f"{conn_name} ({labels})")
        else:
            service_parts.append(conn_name)
    if service_parts:
        lines.append(f"\nConnected: {', '.join(service_parts)}.")

    try:
        import knowledge_base
        kb_summary = knowledge_base.get_summary()
        if kb_summary:
            lines.append(f"Memory: {kb_summary}")
    except Exception:
        pass

    return "\n".join(lines)


# ── Gemini Live API session ──────────────────────────────────────

LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")


def _log(msg):
    """Log to stderr (visible in server.js but not in JSONL stdout)."""
    print(f"[voice] {msg}", file=sys.stderr, flush=True)


async def run_voice_session():
    """Main async loop: bridge stdin/stdout to Gemini Live API."""
    from google import genai
    from google.genai import types

    # Read setup message from stdin
    loop = asyncio.get_event_loop()
    setup_line = await loop.run_in_executor(None, sys.stdin.readline)
    if not setup_line.strip():
        emit({"type": "error", "error": "No setup message received"})
        return

    setup = json.loads(setup_line)

    # Gemini uses AI Studio API key only (no Vertex AI / ADC)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "GEMINI_API_KEY not set. Get one from aistudio.google.com/apikey"})
        return

    _log(f"Auth: using API key ({api_key[:6]}...)")
    client = genai.Client(api_key=api_key)

    # Load connectors and build tools
    connectors = load_all_connectors()
    all_tool_defs, tool_map = build_tools_and_map(connectors)
    system_prompt = build_system_prompt(connectors)

    # Add the briefing + knowledge tools
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    import knowledge_base
    all_tool_defs.append(knowledge_base.KNOWLEDGE_TOOL_DEF)
    tool_map["search_knowledge"] = ("_knowledge", None, [])

    connected_names = sorted(connectors.keys())
    emit({"type": "text", "text": f"Connected services: {', '.join(connected_names) or 'none'}"})

    # Build function declarations for Gemini Live
    function_declarations = []
    for tool in all_tool_defs:
        fd_kwargs = {
            "name": tool["name"],
            "description": tool.get("description", ""),
        }
        # Only include parameters if there are actual properties
        params = tool.get("parameters", {})
        if params.get("properties"):
            fd_kwargs["parameters"] = params
        function_declarations.append(types.FunctionDeclaration(**fd_kwargs))

    # Live API config
    config = types.LiveConnectConfig(
        responseModalities=["AUDIO"],
        systemInstruction=types.Content(
            parts=[types.Part(text=system_prompt)]
        ),
        tools=[types.Tool(functionDeclarations=function_declarations)] if function_declarations else [],
        speechConfig=types.SpeechConfig(
            voiceConfig=types.VoiceConfig(
                prebuiltVoiceConfig=types.PrebuiltVoiceConfig(voiceName="Puck")
            )
        ),
    )

    _log(f"Model: {LIVE_MODEL} | Tools: {len(function_declarations)}")

    try:
        await _run_live_session(client, config, loop, tool_map, connectors)
    except Exception as e:
        emit({"type": "error", "error": f"Session error: {e}"})


async def _run_live_session(client, config, loop, tool_map, connectors):
    """Run a Gemini Live session with the given client. Raises on failure."""
    from google.genai import types

    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        _log("Connected successfully")
        emit({"type": "ready"})

        stop_event = asyncio.Event()

        async def send_audio():
            """Read audio from stdin, forward to Gemini Live."""
            while not stop_event.is_set():
                try:
                    # Use timeout so we can check stop_event periodically
                    # (stdin.readline blocks in executor and can't be cancelled)
                    try:
                        line = await asyncio.wait_for(
                            loop.run_in_executor(None, sys.stdin.readline),
                            timeout=2.0,
                        )
                    except asyncio.TimeoutError:
                        continue  # Check stop_event and loop
                    if not line:
                        _log("stdin EOF — ending send_audio")
                        stop_event.set()
                        break
                    msg = json.loads(line)
                    if msg["type"] == "audio":
                        audio_bytes = base64.b64decode(msg["data"])
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                    elif msg["type"] == "end":
                        _log("Received end message — stopping")
                        stop_event.set()
                        break
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    _log(f"Send error: {e}")
                    emit({"type": "error", "error": f"Send error: {e}"})
                    stop_event.set()
                    break

        async def receive_responses():
            """Read Gemini Live responses, forward to stdout."""
            _log("receive_responses started")
            while not stop_event.is_set():
                try:
                    response_count = 0
                    async for response in session.receive():
                        response_count += 1
                        if stop_event.is_set():
                            break

                        # Audio / text responses
                        if response.server_content:
                            sc = response.server_content
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        audio_b64 = base64.b64encode(
                                            part.inline_data.data
                                        ).decode()
                                        emit({"type": "audio", "data": audio_b64})
                                    if part.text:
                                        emit({"type": "text", "text": part.text})

                            if sc.interrupted:
                                emit({"type": "interrupted"})
                            if sc.turn_complete:
                                emit({"type": "turn_complete"})

                            # Output transcription (what Gemini said as text)
                            if sc.output_transcription and sc.output_transcription.text:
                                emit({"type": "transcript", "role": "assistant",
                                      "text": sc.output_transcription.text})
                            # Input transcription (what user said as text)
                            if sc.input_transcription and sc.input_transcription.text:
                                emit({"type": "transcript", "role": "user",
                                      "text": sc.input_transcription.text})

                        # Tool calls from Gemini
                        if response.tool_call:
                            for fc in response.tool_call.function_calls:
                                tool_name = fc.name
                                args = dict(fc.args) if fc.args else {}

                                emit({
                                    "type": "tool_call",
                                    "id": fc.id,
                                    "name": tool_name,
                                    "args": args,
                                })

                                # Execute tool in thread to avoid blocking the event loop
                                def _exec_tool(tn, a):
                                    if tn == "get_briefing":
                                        try:
                                            return _get_briefing(connectors)
                                        except Exception as e:
                                            return f"Briefing error: {e}"
                                    if tn == "search_knowledge":
                                        try:
                                            import knowledge_base
                                            return knowledge_base.search(
                                                a.get("query", ""),
                                                connector=a.get("connector"),
                                                max_results=a.get("max_results", 10),
                                            )
                                        except Exception as e:
                                            return f"Knowledge search error: {e}"
                                    lookup = tool_map.get(tn)
                                    if lookup:
                                        conn_name, module, accounts = lookup
                                        try:
                                            return _call_tool(module, tn, dict(a), accounts)
                                        except Exception as e:
                                            # Fallback: search knowledge base for relevant context
                                            _log(f"Tool {tn} failed: {e}, trying KB fallback")
                                            try:
                                                import knowledge_base
                                                query = " ".join(str(v) for v in a.values() if v)[:100]
                                                kb_result = knowledge_base.search(query or tn, max_results=3)
                                                return (
                                                    f"The {conn_name} service returned an error: {e}. "
                                                    f"However, here's what I found from earlier interactions: {kb_result}"
                                                )
                                            except Exception:
                                                return f"Tool error: {e}. The service might be temporarily unavailable."
                                    return f"Unknown tool: {tn}"

                                result = await loop.run_in_executor(
                                    None, _exec_tool, tool_name, args
                                )

                                # Truncate large results for voice
                                result_str = str(result)[:3000]
                                emit({
                                    "type": "tool_result",
                                    "id": fc.id,
                                    "result": result_str,
                                })

                                # Send result back to Gemini Live
                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            id=fc.id,
                                            name=tool_name,
                                            response={"result": result_str},
                                        )
                                    ]
                                )

                    # Iterator completed — Gemini closed the session
                    _log(f"session.receive() ended after {response_count} responses")
                    stop_event.set()
                    break

                except Exception as e:
                    if not stop_event.is_set():
                        _log(f"Receive error: {e}")
                        emit({"type": "error", "error": f"Receive error: {e}"})
                    stop_event.set()
                    break

        # Run send and receive concurrently
        results = await asyncio.gather(
            send_audio(),
            receive_responses(),
            return_exceptions=True,
        )
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                _log(f"Task {i} raised: {r}")
        _log("Session ended — both tasks complete")


if __name__ == "__main__":
    asyncio.run(run_voice_session())
