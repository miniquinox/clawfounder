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

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── Shared helpers (same as chat_agent.py) ───────────────────────

def emit(event):
    """Write a JSONL event to stdout."""
    print(json.dumps(event, default=str), flush=True)


def _read_accounts_registry():
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            return json.loads(accounts_file.read_text())
        except Exception:
            pass
    return {"version": 1, "accounts": {}}


def load_all_connectors():
    """Load all connectors that have their deps available."""
    connectors_dir = PROJECT_ROOT / "connectors"
    registry = _read_accounts_registry()
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

            if not (hasattr(module, "TOOLS") and hasattr(module, "handle")):
                continue

            supports_multi = getattr(module, "SUPPORTS_MULTI_ACCOUNT", False)
            reg_accounts = registry.get("accounts", {}).get(folder.name, [])
            enabled_accounts = [a for a in reg_accounts if a.get("enabled", True)]

            if enabled_accounts:
                loaded[folder.name] = {
                    "module": module,
                    "accounts": enabled_accounts,
                    "supports_multi": supports_multi,
                }
            else:
                if hasattr(module, "is_connected") and callable(module.is_connected):
                    if not module.is_connected():
                        continue
                loaded[folder.name] = {
                    "module": module,
                    "accounts": [],
                    "supports_multi": supports_multi,
                }
        except Exception:
            pass

    return loaded


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


_CACHEABLE_PREFIXES = (
    "gmail_get_unread", "gmail_search", "gmail_read_email", "gmail_list_labels",
    "work_email_get_unread", "work_email_search", "work_email_read_email",
    "github_list_repos", "github_get_repo", "github_notifications", "github_list_prs",
    "github_list_issues", "github_get_issue", "github_get_pr", "github_search",
    "github_get_commits", "github_list_branches", "github_list_releases",
    "github_get_file", "github_get_me", "github_list_tags", "github_list_gists",
    "yahoo_finance_quote", "yahoo_finance_history", "yahoo_finance_search",
    "telegram_get_updates",
)


def _call_tool(module, tool_name, args, accounts):
    """Call a connector's handle() with optional account_id routing + caching."""
    import tool_cache

    account_id = args.pop("account", None)
    if account_id is None and len(accounts) == 1:
        account_id = accounts[0]["id"]

    connector = tool_name.split("_")[0]
    if tool_name in _CACHEABLE_PREFIXES:
        cached = tool_cache.get(tool_name, args, account_id=account_id, connector=connector)
        if cached is not None:
            return cached

    supports_multi = getattr(module, "SUPPORTS_MULTI_ACCOUNT", False)
    if supports_multi and account_id:
        result = module.handle(tool_name, args, account_id=account_id)
    else:
        result = module.handle(tool_name, args)

    if tool_name in _CACHEABLE_PREFIXES and isinstance(result, str):
        tool_cache.put(tool_name, args, result, account_id=account_id)

    return result


def _get_briefing(connectors):
    """Gather data from all connected services and return a summary."""
    # Import briefing helpers
    briefing_path = Path(__file__).parent / "briefing_agent.py"
    spec = importlib.util.spec_from_file_location("briefing_agent", briefing_path)
    briefing_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(briefing_mod)

    # Load briefing config (user's watchlist, repos, etc.)
    config_file = Path.home() / ".clawfounder" / "briefing_config.json"
    connector_configs = {}
    if config_file.exists():
        try:
            connector_configs = json.loads(config_file.read_text()).get("connectors", {})
        except Exception:
            pass

    # Gather raw data from all connectors
    gathered = briefing_mod.gather_data(connectors, connector_configs)

    # Format as a readable summary for the voice model
    parts = []
    for conn_name, data in gathered.items():
        for item in data:
            result = item.get("result", item.get("error", ""))
            label = item.get("account", conn_name)
            # Truncate per-connector results for voice
            result_str = str(result)[:2000]
            parts.append(f"[{conn_name}] {item.get('tool', '')} ({label}):\n{result_str}")

    return "\n\n".join(parts) if parts else "No data available from connected services."


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
        "You are ClawFounder — a personal AI voice assistant that takes real actions "
        "using connected services. You are speaking to the user via voice.",
        "",
        "## Voice Behavior",
        "- Keep responses SHORT and conversational — you are speaking, not writing.",
        "- Don't use markdown, bullet points, or formatting — just speak naturally.",
        "- When using tools, briefly say what you're doing (e.g., 'Let me check your emails...').",
        "- For read-only actions, just do them. For actions that send/modify/delete, confirm first.",
        "- Summarize results verbally — don't read out raw data.",
        "- When the user asks for a summary, briefing, or 'what's going on', use the get_briefing tool to fetch everything at once rather than calling individual tools.",
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

    # Add the briefing tool
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    connected_names = sorted(connectors.keys())
    emit({"type": "text", "text": f"Connected services: {', '.join(connected_names) or 'none'}"})

    # Build function declarations for Gemini Live
    function_declarations = []
    for tool in all_tool_defs:
        fd_kwargs = {
            "name": tool["name"],
            "description": tool.get("description", ""),
        }
        if "parameters" in tool:
            fd_kwargs["parameters"] = tool["parameters"]
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
                                    lookup = tool_map.get(tn)
                                    if lookup:
                                        conn_name, module, accounts = lookup
                                        try:
                                            return _call_tool(module, tn, dict(a), accounts)
                                        except Exception as e:
                                            return f"Tool error: {e}"
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
