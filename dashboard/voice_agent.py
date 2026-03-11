"""
ClawFounder — Voice Agent (Gemini Live API)

Long-running async process that bridges stdin/stdout JSONL to the Gemini Live API
for real-time voice interaction. Spawned by server.js for each voice session.

Protocol (stdin <- server.js):
  {"type": "setup", "api_key": "..."}
  {"type": "audio", "data": "<base64 PCM 16kHz 16-bit mono>"}
  {"type": "end"}

Protocol (stdout -> server.js):
  {"type": "ready"}
  {"type": "audio", "data": "<base64 PCM 24kHz 16-bit mono>"}
  {"type": "text", "text": "..."}
  {"type": "tool_call", "id": "...", "name": "...", "args": {...}}
  {"type": "tool_result", "id": "...", "result": "...", "card": {...}}
  {"type": "turn_complete"}
  {"type": "interrupted"}
  {"type": "error", "error": "..."}
"""

import sys
import os
import json
import asyncio
import base64
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent_shared import (
    setup_env, emit, load_all_connectors, get_gemini_client,
    build_connector_map, route_voice_tool, build_voice_system_prompt,
)
setup_env()


# ── Session Memory ───────────────────────────────────────────────
# Survives Gemini session reconnects. Keeps it simple:
# contacts from tool results, conversation turns, and one active task.

class SessionMemory:
    def __init__(self):
        self.contacts = {}   # name_lower -> {name, email}
        self.facts = []      # max 15
        self.turns = []      # max 12, accumulated (not fragments)

    def add_contact(self, name, email):
        self.contacts[name.lower()] = {"name": name, "email": email}

    def add_fact(self, fact):
        if fact not in self.facts:
            if len(self.facts) >= 15:
                self.facts.pop(0)
            self.facts.append(fact)

    def add_turn(self, role, text):
        """Accumulate transcription fragments into full turns."""
        if self.turns and self.turns[-1]["role"] == role:
            self.turns[-1]["text"] = (self.turns[-1]["text"] + " " + text)[:400]
        else:
            if len(self.turns) >= 12:
                self.turns.pop(0)
            self.turns.append({"role": role, "text": text[:400]})

    def extract_from_tool(self, tool_name, args, result_str):
        """Extract contacts and facts from structured tool results (reliable)."""
        action = args.get("action", "")

        # Contacts from email results (structured JSON — reliable)
        if tool_name == "email" and action in ("get_unread", "search", "read_email"):
            self._extract_contacts(result_str)

        # Store email subjects/content as facts
        if tool_name == "email" and action in ("get_unread", "read_email"):
            try:
                data = json.loads(result_str)
                entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                for e in entries[:3]:
                    subj = e.get("subject", "")
                    frm = e.get("from", "")
                    body = e.get("body", e.get("snippet", ""))[:150]
                    if subj:
                        self.add_fact(f"Email: '{subj}' from {frm} — {body}")
            except (json.JSONDecodeError, TypeError):
                pass

        if tool_name == "email" and action in ("send", "reply", "forward"):
            self.add_fact(f"Sent email to {args.get('to', '?')}: {args.get('subject', '?')}")

        if tool_name == "show_draft":
            self.add_fact(f"Draft shown: to={args.get('to','')} subj={args.get('subject','')}")

        if tool_name == "email" and action == "search":
            self.add_fact(f"Searched emails: {args.get('query', '?')}")

    def _extract_contacts(self, result_str):
        """Pull name+email from structured email JSON."""
        try:
            data = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            return
        entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        for entry in entries[:10]:
            for field in ("from", "to"):
                val = entry.get(field, "")
                if not val:
                    continue
                for part in str(val).split(","):
                    m = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>', part.strip())
                    if m:
                        name, email = m.group(1).strip(), m.group(2).strip()
                        if name and "@" in email:
                            self.add_contact(name, email)

    def flush_turn(self):
        """Extract emails mentioned in the last turn's text (simple regex)."""
        if not self.turns:
            return
        text = self.turns[-1]["text"]
        for email in re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,}', text):
            email = email.lower().rstrip(".")
            name = email.split("@")[0]
            self.add_contact(name, email)

    def format_for_prompt(self):
        parts = []
        if self.contacts:
            lines = [f"  {v['name']}: {v['email']}" for v in self.contacts.values()]
            parts.append("CONTACTS:\n" + "\n".join(lines[:10]))
        if self.facts:
            parts.append("FACTS:\n  " + "\n  ".join(self.facts[-10:]))
        if self.turns:
            lines = [f"  {t['role']}: {t['text'][:120]}" for t in self.turns[-8:]]
            parts.append("CONVERSATION:\n" + "\n".join(lines))
        return "\n\n".join(parts)


# ── Combined voice tools ─────────────────────────────────────────

_EMAIL_ACTIONS = {
    "get_unread", "search", "read_email", "send", "reply", "forward",
    "create_draft", "mark_read", "trash",
}
_GITHUB_ACTIONS = {
    "notifications", "list_prs", "get_pr", "list_issues", "get_issue",
}
_CALENDAR_ACTIONS = {
    "list_events", "get_event", "create_event", "quick_add", "list_calendars",
}
_MESSAGING_ACTIONS = {
    "slack_get_messages", "slack_send_message",
    "telegram_get_updates", "telegram_send_message",
}

COMBINED_TOOL_DEFS = [
    {
        "name": "email",
        "description": (
            "Manage emails across all connected accounts (personal Gmail, work email). "
            "Actions: get_unread, search, read_email, send, reply, forward, create_draft, mark_read, trash."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(_EMAIL_ACTIONS)},
                "account": {"type": "string", "description": "'personal' or 'work'. Defaults to personal."},
                "query": {"type": "string", "description": "Search query (for search)."},
                "message_id": {"type": "string", "description": "Email ID (for read_email, reply, forward, mark_read, trash)."},
                "to": {"type": "string", "description": "Recipient email (for send, forward)."},
                "subject": {"type": "string", "description": "Email subject (for send, create_draft)."},
                "body": {"type": "string", "description": "Email body (for send, reply, forward, create_draft)."},
                "max_results": {"type": "integer", "description": "Max results (default 10)."},
            },
            "required": ["action"],
        },
    },
    {
        "name": "github",
        "description": "Check GitHub activity. Actions: notifications, list_prs, get_pr, list_issues, get_issue.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(_GITHUB_ACTIONS)},
                "repo": {"type": "string", "description": "Repository 'owner/repo'."},
                "number": {"type": "integer", "description": "PR or issue number."},
                "state": {"type": "string", "description": "open, closed, or all."},
                "max_results": {"type": "integer"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "calendar",
        "description": "Manage Google Calendar. Actions: list_events, get_event, create_event, quick_add, list_calendars.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(_CALENDAR_ACTIONS)},
                "event_id": {"type": "string"},
                "summary": {"type": "string", "description": "Event title."},
                "start": {"type": "string", "description": "Start ISO 8601."},
                "end": {"type": "string", "description": "End ISO 8601."},
                "text": {"type": "string", "description": "Natural language event (quick_add)."},
                "time_min": {"type": "string"},
                "time_max": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "messaging",
        "description": "Send and read messages on Slack and Telegram.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(_MESSAGING_ACTIONS)},
                "channel": {"type": "string"},
                "text": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "show_draft",
        "description": "Show an email draft visually in the UI for user review before sending. User can approve or reject verbally.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email."},
                "to_name": {"type": "string", "description": "Recipient name."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Full email body."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "finance",
        "description": "Get stock quotes. Provide a ticker like AAPL, TSLA.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker."},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_briefing",
        "description": "Get a summary across all services — emails, GitHub, calendar, stocks, messages.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_knowledge",
        "description": "Search the user's knowledge base for saved notes, API keys, project details, contacts, credentials. User notes appear first in results — look for 'user_notes' entries.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_knowledge",
        "description": "Save a note to the knowledge base — contacts, project info, decisions, API keys.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "title": {"type": "string", "description": "Short title."},
                "tags": {"type": "string", "description": "Comma-separated tags."},
            },
            "required": ["content"],
        },
    },
]


# ── Tool routing ─────────────────────────────────────────────────
# (Moved to agent_shared.py — using build_connector_map and route_voice_tool)


def _build_card(tool_name, args, result_str):
    """Build a UI card from a tool result."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return None

    action = args.get("action", "")

    if tool_name == "show_draft" and isinstance(data, dict) and data.get("draft"):
        return {
            "type": "email_draft",
            "to": data.get("to", ""),
            "to_name": data.get("to_name", ""),
            "subject": data.get("subject", ""),
            "body": data.get("body", ""),
        }

    if tool_name == "email":
        if action == "read_email" and isinstance(data, dict) and "subject" in data:
            return {"type": "email", "subject": data.get("subject", ""), "from": data.get("from", ""),
                    "to": data.get("to", ""), "date": data.get("date", ""), "body": data.get("body", "")[:500]}
        if action in ("get_unread", "search") and isinstance(data, list):
            return {"type": "email_list", "total": len(data),
                    "emails": [{"from": e.get("from", ""), "subject": e.get("subject", ""),
                                "snippet": e.get("snippet", ""), "date": e.get("date", "")} for e in data[:5]]}
        if action in ("send", "reply", "forward"):
            return {"type": "email_sent", "message": str(data)[:200]}

    if tool_name == "calendar" and action == "list_events" and isinstance(data, list):
        return {"type": "event_list", "events": [{"summary": e.get("summary", ""), "start": e.get("start", ""),
                "end": e.get("end", ""), "location": e.get("location", "")} for e in data[:5]]}

    if tool_name == "github" and action in ("list_prs", "list_issues") and isinstance(data, list):
        return {"type": "github_list", "items": [{"number": it.get("number", ""), "title": it.get("title", ""),
                "state": it.get("state", ""), "author": it.get("user", {}).get("login", "") if isinstance(it.get("user"), dict) else ""} for it in data[:5]]}

    return None


# ── System prompt ────────────────────────────────────────────────

SYSTEM_PROMPT_BASE = """\
You are ClawFounder, a voice PM assistant. Act like a sharp chief of staff.

SESSION MEMORY — you already know this, do NOT re-ask or re-search:
{memory}

RULES:
1. ACT, don't deliberate. When user says do something, DO IT.
2. When replying to an email, search_knowledge for relevant info (API keys, credentials, context) \
and include it in the reply. Don't say "I'll send it later" — find and include it now.
3. After composing an email, use show_draft to display it. Then ask "want me to send it?"
4. When user says "send it" / "yes" / "go ahead" — send immediately. No re-verification.
5. Use contacts from memory. Speech-to-text garbles names — match closest known contact.
6. Ghostwrite emails as the USER, not as AI. Their tone, their style.
7. Keep voice responses to 1-2 sentences.
8. When you see urgent emails (caps, ASAP, urgent), flag them and suggest action.
9. When user says "reply to that", compose an appropriate reply yourself — never ask "what should it say?"

Connected: {services}

Briefing:
{briefing}\
"""


# build_system_prompt moved to agent_shared.py as build_voice_system_prompt


# ── Gemini Live API ──────────────────────────────────────────────

def _get_live_model():
    override = os.environ.get("GEMINI_LIVE_MODEL")
    if override:
        return override
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini-2.5-flash-native-audio-preview-12-2025"
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return "gemini-live-2.5-flash-native-audio"
    return "gemini-2.5-flash-native-audio-preview-12-2025"


LIVE_MODEL = _get_live_model()


def _log(msg):
    print(f"[voice] {msg}", file=sys.stderr, flush=True)


class _UserStoppedError(Exception):
    pass


async def run_voice_session():
    from google import genai
    from google.genai import types

    loop = asyncio.get_event_loop()
    setup_line = await loop.run_in_executor(None, sys.stdin.readline)
    if not setup_line.strip():
        emit({"type": "error", "error": "No setup message received"})
        return

    # Client — prefer AI Studio (that's where credits are)
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        _log("Auth: AI Studio")
    else:
        try:
            client = get_gemini_client()
            _log("Auth: Vertex")
        except RuntimeError as e:
            emit({"type": "error", "error": str(e)})
            return

    # Load connectors
    connectors = load_all_connectors()
    tool_map = build_connector_map(connectors)
    emit({"type": "text", "text": f"Connected services: {', '.join(sorted(connectors.keys())) or 'none'}"})

    # Pre-cache briefing
    from agent_shared import get_briefing
    briefing = ""
    try:
        _log("Caching briefing...")
        briefing = get_briefing(connectors)
        _log(f"Briefing ready ({len(briefing)} chars)")
    except Exception as e:
        _log(f"Briefing failed: {e}")

    # Session memory — persists across Gemini reconnects
    memory = SessionMemory()

    # Build function declarations
    func_decls = []
    for tool in COMBINED_TOOL_DEFS:
        kwargs = {"name": tool["name"], "description": tool.get("description", "")}
        params = tool.get("parameters", {})
        if params.get("properties"):
            kwargs["parameters"] = params
        func_decls.append(types.FunctionDeclaration(**kwargs))

    _log(f"Model: {LIVE_MODEL} | Tools: {len(func_decls)}")

    def _build_config(resume_handle=None):
        prompt = build_voice_system_prompt(connectors, briefing, memory, SYSTEM_PROMPT_BASE)
        kw = dict(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=prompt)]),
            tools=[
                types.Tool(function_declarations=func_decls),
                types.Tool(google_search=types.GoogleSearch()),
            ],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                )
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        if resume_handle:
            kw["session_resumption"] = types.SessionResumptionConfig(handle=resume_handle)
        return types.LiveConnectConfig(**kw)

    # Reconnect loop — Gemini sessions timeout every few minutes
    MAX_RECONNECTS = 50
    resume_handle = None

    for attempt in range(MAX_RECONNECTS + 1):
        config = _build_config(resume_handle)

        if attempt > 0:
            if resume_handle:
                _log("Reconnecting with resume handle")
            else:
                _log(f"Reconnecting — memory: {len(memory.contacts)} contacts, {len(memory.facts)} facts, {len(memory.turns)} turns")

        try:
            new_handle = await _run_session(client, config, loop, tool_map, connectors, memory)
            if new_handle:
                resume_handle = new_handle
            _log(f"Session ended (attempt {attempt + 1})")
            await asyncio.sleep(0.5)
        except _UserStoppedError:
            _log("User stopped")
            break
        except Exception as e:
            _log(f"Session error: {e}")
            if attempt >= MAX_RECONNECTS:
                emit({"type": "error", "error": str(e)})
                break
            await asyncio.sleep(1)


async def _run_session(client, config, loop, tool_map, connectors, memory):
    """Run one Gemini Live session. Returns resume handle or None."""
    from google.genai import types

    resume_handle = None

    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        _log("Connected")
        emit({"type": "ready"})

        stop = asyncio.Event()
        user_stopped = False

        async def send_audio():
            nonlocal user_stopped
            while not stop.is_set():
                try:
                    line = await asyncio.wait_for(
                        loop.run_in_executor(None, sys.stdin.readline), timeout=2.0
                    )
                except asyncio.TimeoutError:
                    continue
                if not line:
                    user_stopped = True
                    stop.set()
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg["type"] == "audio":
                    await session.send_realtime_input(
                        audio=types.Blob(data=base64.b64decode(msg["data"]), mime_type="audio/pcm;rate=16000")
                    )
                elif msg["type"] == "end":
                    user_stopped = True
                    stop.set()
                    break

        async def receive():
            nonlocal resume_handle
            audio_chunks = 0
            try:
                async for resp in session.receive():
                    if stop.is_set():
                        break

                    # Resume handle
                    if resp.session_resumption_update and resp.session_resumption_update.new_handle:
                        resume_handle = resp.session_resumption_update.new_handle

                    # Go-away warning
                    if resp.go_away:
                        _log(f"Go-away: {getattr(resp.go_away, 'time_left', '?')}")

                    # Server content (audio, transcriptions, turn signals)
                    if resp.server_content:
                        sc = resp.server_content

                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    emit({"type": "audio", "data": base64.b64encode(part.inline_data.data).decode()})
                                    audio_chunks += 1
                                if part.text:
                                    _log(f"[thinking] {part.text[:100]}")

                        if sc.interrupted:
                            emit({"type": "interrupted"})
                        if sc.turn_complete:
                            memory.flush_turn()
                            emit({"type": "turn_complete"})

                        if sc.output_transcription and sc.output_transcription.text:
                            text = sc.output_transcription.text
                            emit({"type": "transcript", "role": "assistant", "text": text})
                            memory.add_turn("assistant", text)
                        if sc.input_transcription and sc.input_transcription.text:
                            text = sc.input_transcription.text
                            emit({"type": "transcript", "role": "user", "text": text})
                            memory.add_turn("user", text)

                    # Tool calls
                    if resp.tool_call:
                        for fc in resp.tool_call.function_calls:
                            tn = fc.name
                            ta = dict(fc.args) if fc.args else {}

                            emit({"type": "tool_call", "id": fc.id, "name": tn, "args": ta})

                            # Execute in thread pool (connectors are sync)
                            def _exec(name=tn, args=ta):
                                try:
                                    return route_voice_tool(name, args, tool_map, connectors)
                                except Exception as e:
                                    _log(f"Tool {name} error: {e}")
                                    return f"Error: {e}"

                            result = await loop.run_in_executor(None, _exec)
                            result_str = str(result)[:3000]

                            memory.extract_from_tool(tn, ta, result_str)

                            card = _build_card(tn, ta, result_str)
                            emit({"type": "tool_result", "id": fc.id, "name": tn,
                                  "action": ta.get("action", ""), "result": result_str, "card": card})

                            await session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(id=fc.id, name=tn, response={"result": result_str})
                                ]
                            )

            except Exception as e:
                if not stop.is_set():
                    _log(f"Receive error: {e}")
            finally:
                _log(f"Session done ({audio_chunks} audio chunks)")
                stop.set()

        await asyncio.gather(send_audio(), receive(), return_exceptions=True)

        if user_stopped:
            raise _UserStoppedError()
        return resume_handle


if __name__ == "__main__":
    asyncio.run(run_voice_session())
