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


# Voice-appropriate tools — keeps the Live API under its tool limit
# Excludes advanced/destructive GitHub ops that don't make sense in voice
VOICE_TOOL_WHITELIST = {
    # Gmail essentials
    "gmail_get_unread", "gmail_search", "gmail_read_email", "gmail_send", "gmail_reply",
    "gmail_mark_read", "gmail_trash",
    # Work email essentials
    "work_email_get_unread", "work_email_search", "work_email_read_email",
    "work_email_send", "work_email_reply", "work_email_mark_read",
    # GitHub — high-level only
    "github_notifications", "github_list_repos", "github_search",
    "github_list_prs", "github_get_pr", "github_list_issues", "github_get_issue",
    "github_create_issue", "github_get_me",
    # Yahoo Finance
    "yahoo_finance_quote", "yahoo_finance_search",
    # Telegram
    "telegram_get_updates", "telegram_send_message",
    # WhatsApp
    "whatsapp_send_message",
    # Firebase
    "firebase_list_collections", "firebase_query",
    # Supabase
    "supabase_query",
    # Knowledge base
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
    """Build a concise voice-appropriate system prompt."""
    connectors_dir = PROJECT_ROOT / "connectors"

    lines = [
        "You are ClawFounder — a sharp, proactive project manager who knows everything about "
        "the user's work. You take real actions using connected services. You are speaking "
        "to the user via voice — be punchy, direct, and useful.",
        "",
        "## Voice Behavior",
        "- Keep responses SHORT and conversational — 2-3 sentences max. You are speaking, not writing.",
        "- Don't use markdown, bullet points, or formatting — just speak naturally.",
        "- When using tools, briefly say what you're doing (e.g., 'Checking your emails now...' or 'Let me look that up...').",
        "- For read-only actions, just do them. For actions that send/modify/delete, confirm first.",
        "- Summarize results verbally — don't read out raw data. Give the highlights.",
        "- After completing a task, suggest a natural next step. For example: after reading emails, say 'Want me to reply to any of these?'",
        "",
        "## Proactive Behavior",
        "- When the user asks for a summary, briefing, or 'what's going on', use the get_briefing tool.",
        "- When the user mentions a person, project, or topic, use search_knowledge FIRST to check for relevant context.",
        "- If the user mentions being blocked, frustrated, or waiting on something, proactively search your knowledge to see if you can help unblock them.",
        "- Connect dots across services — if an email mentions a PR, and the user asks about that PR, mention the email context too.",
        "",
        "## Error Recovery",
        "- If a tool fails, say something natural like 'I couldn't reach GitHub right now' and offer to check what you know from earlier.",
        "- Never go silent — always give a verbal response, even if it's 'I ran into an issue, let me try another way.'",
        "",
    ]

    if connectors:
        lines.append("## Connected Services")
        lines.append("")
        for conn_name in sorted(connectors.keys()):
            instructions_file = connectors_dir / conn_name / "instructions.md"
            if instructions_file.exists():
                try:
                    content = instructions_file.read_text().strip()
                    lines.append(f"### {conn_name}")
                    lines.append(content)
                    lines.append("")
                except Exception:
                    pass

            info = connectors[conn_name]
            accounts = info.get("accounts", []) if isinstance(info, dict) else []
            if len(accounts) > 1:
                lines.append(f"#### {conn_name} — Accounts")
                for acct in accounts:
                    lines.append(f"- `{acct['id']}`: {acct.get('label', acct['id'])}")
                lines.append("")

    # Add knowledge base summary (what the agent already knows)
    try:
        import knowledge_base
        kb_summary = knowledge_base.get_summary()
        if kb_summary:
            lines.append("## Memory")
            lines.append(f"You have context from past interactions. {kb_summary}")
            lines.append("Use search_knowledge to look up details about any person or topic.")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


# ── Gemini Live API session ──────────────────────────────────────

LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-native-audio")


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
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    if not line:
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
                        stop_event.set()
                        break
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    emit({"type": "error", "error": f"Send error: {e}"})
                    stop_event.set()
                    break

        async def receive_responses():
            """Read Gemini Live responses, forward to stdout."""
            while not stop_event.is_set():
                try:
                    async for response in session.receive():
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

                except Exception as e:
                    if not stop_event.is_set():
                        emit({"type": "error", "error": f"Receive error: {e}"})
                    break

        # Run send and receive concurrently
        await asyncio.gather(
            send_audio(),
            receive_responses(),
            return_exceptions=True,
        )


if __name__ == "__main__":
    asyncio.run(run_voice_session())
