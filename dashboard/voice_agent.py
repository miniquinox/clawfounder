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
    setup_env, emit, load_all_connectors, call_tool as _call_tool,
    get_briefing as _get_briefing, get_gemini_client,
)
setup_env()


# ── Session Memory ───────────────────────────────────────────────
# Lightweight conversation memory that survives Gemini session reconnects.
# Tracks contacts, key facts, and recent conversation turns so the model
# doesn't lose context when sessions timeout and reconnect.

class SessionMemory:
    """Tracks key info discovered during a voice session."""

    def __init__(self):
        self.contacts = {}        # name -> email
        self.facts = []           # key facts/decisions (max 20)
        self.turns = []           # recent conversation turns (max 10)
        self.pending_task = None  # what user is currently trying to do
        self.draft_context = {}   # tracks email drafts in progress

    def add_contact(self, name, email):
        self.contacts[name.lower()] = {"name": name, "email": email}

    def add_fact(self, fact):
        if len(self.facts) >= 20:
            self.facts.pop(0)
        if fact not in self.facts:
            self.facts.append(fact)

    def add_turn(self, role, text):
        """Accumulate transcription fragments into the current turn."""
        if self.turns and self.turns[-1]["role"] == role:
            # Same speaker — append to current turn
            self.turns[-1]["text"] = (self.turns[-1]["text"] + " " + text)[:500]
        else:
            # New speaker — finalize previous turn extraction, start new
            if self.turns:
                prev = self.turns[-1]
                self._extract_from_speech(prev["role"], prev["text"])
            if len(self.turns) >= 15:
                self.turns.pop(0)
            self.turns.append({"role": role, "text": text[:500]})

    def set_task(self, task):
        self.pending_task = task

    def clear_draft(self):
        """Clear draft context when user moves on to a different task."""
        self.draft_context = {}
        self.pending_task = None

    def extract_from_tool_result(self, tool_name, args, result_str):
        """Auto-extract useful info from tool results."""
        action = args.get("action", "")

        # If user is doing something unrelated to email drafting, clear draft
        if tool_name in ("finance", "calendar", "github", "get_briefing", "messaging"):
            self.clear_draft()

        # Extract contacts from email results
        if tool_name == "email" and action in ("get_unread", "search", "read_email"):
            self._extract_emails(result_str)
            # Store email content for context (so model can draft replies after reconnect)
            if action in ("get_unread", "read_email"):
                try:
                    data = json.loads(result_str)
                    if isinstance(data, dict) and "subject" in data:
                        self.add_fact(f"Email read: '{data.get('subject','')}' from {data.get('from','')} — {str(data.get('body',''))[:200]}")
                    elif isinstance(data, list):
                        for e in data[:3]:
                            subj = e.get("subject", "")
                            frm = e.get("from", "")
                            snippet = e.get("snippet", e.get("body", ""))[:100]
                            if subj:
                                self.add_fact(f"Email: '{subj}' from {frm} — {snippet}")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Track what user is doing
        if tool_name == "email" and action == "search":
            query = args.get("query", "")
            if query:
                self.add_fact(f"Searched emails for: {query}")

        if tool_name == "email" and action in ("send", "reply", "forward"):
            to = args.get("to", "")
            if to:
                self.add_fact(f"Sent email to {to}")
                self.clear_draft()  # Draft was sent, clear it

    def _extract_emails(self, result_str):
        """Pull name+email pairs from email results."""
        try:
            data = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            return

        entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        for entry in entries[:10]:
            for field_name in ("from", "to"):
                field_val = entry.get(field_name, "")
                if not field_val:
                    continue
                # Handle comma-separated recipients
                for part in str(field_val).split(","):
                    match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>', part.strip())
                    if match:
                        name = match.group(1).strip()
                        email = match.group(2).strip()
                        if name and email and "@" in email:
                            self.add_contact(name, email)
                            self.add_fact(f"Contact found: {name} = {email}")

    def flush_current_turn(self):
        """Extract info from the last accumulated turn (call on turn_complete)."""
        if self.turns:
            last = self.turns[-1]
            self._extract_from_speech(last["role"], last["text"])

    def _extract_from_speech(self, role, text):
        """Extract emails, names, and key info from spoken transcriptions."""
        if not text:
            return
        # Extract any email addresses mentioned in speech
        email_matches = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', text, re.IGNORECASE)
        for email in email_matches:
            email = email.lower().rstrip(".")
            # Try to find a name near the email in the text
            # Look for "Name <email>" or "Name at email" patterns
            name = ""
            # Pattern: "to/for Name at email" or "Name's email"
            for pattern in [
                rf'(?:to|for|from)\s+(\w[\w\s]{{1,30}}?)\s+(?:at\s+)?{re.escape(email)}',
                rf'(\w[\w\s]{{1,30}}?)\s+(?:at\s+|<){re.escape(email)}',
                rf'(\w+(?:\s+\w+)?)\s*(?:\'s?\s+)?(?:email|gmail|address).*?{re.escape(email)}',
            ]:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    name = m.group(1).strip()
                    break
            if not name:
                # Derive from email: "shubanranganath@gmail.com" -> "shubanranganath"
                name = email.split("@")[0]
            self.add_contact(name, email)
            self.add_fact(f"Email mentioned: {name} = {email}")

        # Track email drafting intent from speech
        if role == "user":
            lower = text.lower()
            if any(w in lower for w in ("send an email", "send email", "write an email", "email to")):
                # Extract who they want to email
                name_match = re.search(r'(?:email|send)\s+(?:an?\s+email\s+)?to\s+(\w+)', lower)
                if name_match:
                    target = name_match.group(1)
                    self.set_task(f"User wants to send an email to {target}")
            if any(w in lower for w in ("send it", "go ahead", "yes send", "send that")):
                self.add_fact("User approved sending the current draft")

        # Track when assistant mentions drafting/composing
        if role == "assistant":
            lower = text.lower()
            if "subject" in lower and ("body" in lower or "draft" in lower):
                self.add_fact(f"Assistant discussed email draft: {text[:100]}")

    def set_draft(self, to=None, subject=None, style=None, content_hint=None):
        """Track an email draft in progress."""
        if to:
            self.draft_context["to"] = to
        if subject:
            self.draft_context["subject"] = subject
        if style:
            self.draft_context["style"] = style
        if content_hint:
            self.draft_context["content_hint"] = content_hint

    def format_for_prompt(self):
        """Format session memory as a concise context block for the system prompt."""
        parts = []

        if self.contacts:
            contact_lines = [f"  {v['name']}: {v['email']}" for v in self.contacts.values()]
            parts.append("Known contacts:\n" + "\n".join(contact_lines[:10]))

        if self.pending_task:
            parts.append(f"Current task: {self.pending_task}")

        if self.draft_context:
            draft_parts = [f"  {k}: {v}" for k, v in self.draft_context.items()]
            parts.append("Draft in progress:\n" + "\n".join(draft_parts))

        if self.facts:
            parts.append("Key facts:\n  " + "\n  ".join(self.facts[-8:]))

        if self.turns:
            convo_lines = [f"  {t['role']}: {t['text'][:150]}" for t in self.turns[-8:]]
            parts.append("Recent conversation:\n" + "\n".join(convo_lines))

        if not parts:
            return ""
        return "\n".join(parts)


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
                "action": {"type": "string", "enum": sorted(_EMAIL_ACTIONS), "description": "The email action to perform."},
                "account": {"type": "string", "description": "Which email account: 'personal' or 'work'. Defaults to personal."},
                "query": {"type": "string", "description": "Search query (for 'search' action)."},
                "message_id": {"type": "string", "description": "Email message ID (for read_email, reply, forward, mark_read, trash)."},
                "to": {"type": "string", "description": "Recipient email (for send, forward)."},
                "subject": {"type": "string", "description": "Email subject (for send, create_draft)."},
                "body": {"type": "string", "description": "Email body text (for send, reply, forward, create_draft)."},
                "max_results": {"type": "integer", "description": "Max results to return (default: 10)."},
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
                "action": {"type": "string", "enum": sorted(_GITHUB_ACTIONS), "description": "The GitHub action."},
                "repo": {"type": "string", "description": "Repository in 'owner/repo' format."},
                "number": {"type": "integer", "description": "PR or issue number."},
                "state": {"type": "string", "description": "Filter: open, closed, all."},
                "max_results": {"type": "integer", "description": "Max results (default: 10)."},
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
                "action": {"type": "string", "enum": sorted(_CALENDAR_ACTIONS), "description": "The calendar action."},
                "event_id": {"type": "string", "description": "Event ID (for get_event)."},
                "summary": {"type": "string", "description": "Event title (for create_event)."},
                "start": {"type": "string", "description": "Start time ISO 8601 (for create_event)."},
                "end": {"type": "string", "description": "End time ISO 8601 (for create_event)."},
                "text": {"type": "string", "description": "Natural language event (for quick_add)."},
                "time_min": {"type": "string", "description": "Start of time range (for list_events)."},
                "time_max": {"type": "string", "description": "End of time range (for list_events)."},
                "max_results": {"type": "integer", "description": "Max results (default: 10)."},
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
                "action": {"type": "string", "enum": sorted(_MESSAGING_ACTIONS), "description": "The messaging action."},
                "channel": {"type": "string", "description": "Slack channel or Telegram chat ID."},
                "text": {"type": "string", "description": "Message text to send."},
                "max_results": {"type": "integer", "description": "Max messages to fetch."},
            },
            "required": ["action"],
        },
    },
    {
        "name": "show_draft",
        "description": "Show an email draft to the user visually in the UI for review. Call this BEFORE sending. User sees the draft as a card and can approve or reject verbally.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "to_name": {"type": "string", "description": "Recipient name."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Full email body text."},
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
                "symbol": {"type": "string", "description": "Stock ticker symbol."},
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
        "description": "Search the knowledge base for past context, emails, notes.",
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
        "description": "Save a note to the knowledge base for future reference — contacts, project info, decisions, anything worth remembering.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The information to save."},
                "title": {"type": "string", "description": "Short title (e.g. 'Shuban contact info')."},
                "tags": {"type": "string", "description": "Comma-separated tags (e.g. 'contact, email')."},
            },
            "required": ["content"],
        },
    },
]


def _build_connector_map(connectors):
    """Build a flat map of tool_name -> (conn_name, module, accounts)."""
    tool_map = {}
    for conn_name, info in connectors.items():
        module = info["module"]
        accounts = info["accounts"]
        for tool in module.TOOLS:
            tool_map[tool["name"]] = (conn_name, module, accounts)
    return tool_map


def _route_combined_tool(tool_name, args, tool_map, connectors):
    """Route a combined voice tool call to the underlying connector."""
    if tool_name == "get_briefing":
        return _get_briefing(connectors)

    if tool_name == "search_knowledge":
        import knowledge_base
        return knowledge_base.search(
            args.get("query", ""),
            connector=args.get("connector"),
            max_results=args.get("max_results", 10),
        )

    if tool_name == "show_draft":
        # This doesn't actually send anything — just returns the draft data
        # so the UI can display it as a card. The model then asks user to approve.
        return json.dumps({
            "draft": True,
            "to": args.get("to", ""),
            "to_name": args.get("to_name", ""),
            "subject": args.get("subject", ""),
            "body": args.get("body", ""),
        })

    if tool_name == "save_knowledge":
        import knowledge_base
        tags = [t.strip() for t in args.get("tags", "").split(",") if t.strip()] if args.get("tags") else []
        note = knowledge_base.add_note(
            content=args.get("content", ""),
            title=args.get("title", ""),
            tags=tags,
        )
        return f"Saved to knowledge base: {note.get('title', 'note')} (id: {note.get('id')})"

    if tool_name == "finance":
        lookup = tool_map.get("yahoo_finance_quote")
        if lookup:
            _, module, accounts = lookup
            return _call_tool(module, "yahoo_finance_quote", {"symbol": args.get("symbol", "")}, accounts)
        return "Finance service not connected."

    if tool_name == "email":
        action = args.get("action", "get_unread")
        account = args.get("account", "personal")
        prefix = "work_email" if "work" in account.lower() else "gmail"
        real_tool = f"{prefix}_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"Email action '{action}' not available."
        _, module, accounts_list = lookup
        call_args = {k: v for k, v in args.items() if k not in ("action", "account") and v is not None}
        return _call_tool(module, real_tool, call_args, accounts_list)

    if tool_name == "github":
        action = args.get("action", "notifications")
        real_tool = f"github_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"GitHub action '{action}' not available."
        _, module, accounts_list = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return _call_tool(module, real_tool, call_args, accounts_list)

    if tool_name == "calendar":
        action = args.get("action", "list_events")
        real_tool = f"calendar_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"Calendar action '{action}' not available."
        _, module, accounts_list = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return _call_tool(module, real_tool, call_args, accounts_list)

    if tool_name == "messaging":
        action = args.get("action", "")
        lookup = tool_map.get(action)
        if not lookup:
            return f"Messaging action '{action}' not available."
        _, module, accounts_list = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return _call_tool(module, action, call_args, accounts_list)

    return f"Unknown tool: {tool_name}"


def _build_action_card(tool_name, args, result_str):
    """Build a structured UI card from a tool result for rich previews."""
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
                    "to": data.get("to", ""), "date": data.get("date", ""), "body": data.get("body", "")[:500], "id": data.get("id", "")}
        if action in ("get_unread", "search") and isinstance(data, list):
            return {"type": "email_list", "emails": [{"id": e.get("id", ""), "from": e.get("from", ""),
                    "subject": e.get("subject", ""), "snippet": e.get("snippet", ""), "date": e.get("date", "")} for e in data[:5]], "total": len(data)}
        if action in ("send", "reply", "forward") and isinstance(data, str):
            return {"type": "email_sent", "message": data}

    if tool_name == "calendar" and action == "list_events" and isinstance(data, list):
        return {"type": "event_list", "events": [{"summary": e.get("summary", ""), "start": e.get("start", ""),
                "end": e.get("end", ""), "location": e.get("location", "")} for e in data[:5]]}

    if tool_name == "github" and action in ("list_prs", "list_issues") and isinstance(data, list):
        return {"type": "github_list", "items": [{"number": item.get("number", ""), "title": item.get("title", ""),
                "state": item.get("state", ""), "author": item.get("user", {}).get("login", "") if isinstance(item.get("user"), dict) else ""} for item in data[:5]]}

    return None


# ── System prompt ────────────────────────────────────────────────

def build_system_prompt(connectors, cached_briefing="", session_memory=None):
    """Build a conversational system prompt with session memory at the TOP."""
    lines = [
        "You are ClawFounder, a voice PM assistant. You ACT, you don't deliberate.",
    ]

    # Session memory FIRST — this is the most important context on reconnect
    if session_memory:
        memory_str = session_memory.format_for_prompt()
        if memory_str:
            lines.append("")
            lines.append("=== YOUR MEMORY (HIGHEST PRIORITY — USE THIS) ===")
            lines.append("You ALREADY know the following from this conversation. DO NOT re-search or re-ask for ANY of this information.")
            lines.append(memory_str)
            lines.append("=== END MEMORY ===")

    lines += [
        "",
        "ACTION RULES:",
        "- When the user tells you what to write, WRITE IT immediately.",
        "- When user says 'reply to him' or 'reply to that email', YOU compose an appropriate reply. Do NOT ask 'what should it say?'",
        "- BEFORE drafting a reply that requires specific info (API keys, credentials, project details, dates), ALWAYS search_knowledge first to find it. Include the actual info in the reply — don't say 'I'll send it shortly' if you can find it now.",
        "- NEVER search for something you already know from session memory above.",
        "- When user says 'send it' or 'yes', EXECUTE immediately.",
        "- If you have an email address in your memory, USE IT. Never ask for it again.",
        "- NAMES: Speech-to-text garbles names. Match closest name from memory. Don't ask.",
        "",
        "BEHAVIOR:",
        "1. After drafting an email, ask: 'Want me to show you the draft or read it aloud?' Then use show_draft or read it.",
        "2. Reading emails, calendar, searching — just do it, no need to ask.",
        "3. When user says 'send to him/her/them', use the person you were just discussing.",
        "4. Keep responses to 1-2 sentences. No markdown.",
        "5. Ghostwrite emails as the USER — their voice, their style. Never mention AI.",
        "6. Use save_knowledge to save contacts and key info when discovered.",
        "",
        "PROACTIVE PM:",
        "- When you see an URGENT email (caps, exclamation marks, 'ASAP', 'urgent', 'need'), FLAG it and suggest: 'This looks urgent — want me to draft a reply?'",
        "- When drafting replies, search_knowledge for any relevant info the user has stored (API keys, credentials, project context). A good PM finds the answer, not just acknowledges the question.",
        "- When listing emails, highlight the most important ones first. Call out what needs attention.",
        "- Think like a chief of staff: prioritize, flag, suggest next actions. Don't wait to be told — take initiative.",
    ]

    service_names = sorted(connectors.keys())
    if service_names:
        lines.append(f"\nConnected: {', '.join(service_names)}.")

    if cached_briefing:
        lines.append(f"\nBriefing:\n{cached_briefing[:800]}")

    return "\n".join(lines)


# ── Gemini Live API session ──────────────────────────────────────

def _get_live_model():
    """Prefer AI Studio (API key) — that's where the credits are."""
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


async def run_voice_session():
    """Main async loop: bridge stdin/stdout to Gemini Live API."""
    from google import genai
    from google.genai import types

    loop = asyncio.get_event_loop()
    setup_line = await loop.run_in_executor(None, sys.stdin.readline)
    if not setup_line.strip():
        emit({"type": "error", "error": "No setup message received"})
        return

    # Build client — prefer AI Studio for Live API
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        _log("Auth: Gemini client ready (AI Studio)")
    else:
        try:
            client = get_gemini_client()
            _log("Auth: Gemini client ready (Vertex)")
        except RuntimeError as e:
            emit({"type": "error", "error": str(e)})
            return

    # Load connectors and build tool routing map
    connectors = load_all_connectors()
    tool_map = _build_connector_map(connectors)

    connected_names = sorted(connectors.keys())
    emit({"type": "text", "text": f"Connected services: {', '.join(connected_names) or 'none'}"})

    # Pre-cache briefing
    cached_briefing = ""
    try:
        _log("Pre-caching briefing...")
        cached_briefing = _get_briefing(connectors)
        _log(f"Briefing cached ({len(cached_briefing)} chars)")
    except Exception as e:
        _log(f"Briefing pre-cache failed: {e}")

    # Session memory — persists across reconnects
    memory = SessionMemory()

    # Build function declarations
    function_declarations = []
    for tool in COMBINED_TOOL_DEFS:
        fd_kwargs = {"name": tool["name"], "description": tool.get("description", "")}
        params = tool.get("parameters", {})
        if params.get("properties"):
            fd_kwargs["parameters"] = params
        function_declarations.append(types.FunctionDeclaration(**fd_kwargs))

    _log(f"Model: {LIVE_MODEL} | Tools: {len(function_declarations)}")

    def _build_config(resume_handle=None):
        """Build Live API config, injecting session memory into system prompt."""
        prompt = build_system_prompt(connectors, cached_briefing, memory)
        config_kwargs = dict(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=prompt)]),
            tools=[
                types.Tool(function_declarations=function_declarations),
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
        # Only set session resumption if we have a handle — passing None can cause issues
        if resume_handle:
            config_kwargs["session_resumption"] = types.SessionResumptionConfig(
                handle=resume_handle,
            )
        return types.LiveConnectConfig(**config_kwargs)

    # Auto-reconnect loop
    MAX_RECONNECTS = 50
    resume_handle = None
    for attempt in range(MAX_RECONNECTS + 1):
        config = _build_config(resume_handle)

        if resume_handle and attempt > 0:
            _log(f"Reconnecting WITH resume handle (context preserved)")
        elif attempt > 0:
            _log(f"Reconnecting WITHOUT resume handle — injecting session memory ({len(memory.contacts)} contacts, {len(memory.facts)} facts, {len(memory.turns)} turns)")
            if memory.contacts:
                contacts_str = ", ".join(f"{v['name']}={v['email']}" for v in memory.contacts.values())
                _log(f"  Contacts: {contacts_str}")
            if memory.pending_task:
                _log(f"  Task: {memory.pending_task}")
            if memory.draft_context:
                _log(f"  Draft: {memory.draft_context}")

        try:
            new_handle = await _run_live_session(
                client, config, loop, tool_map, connectors, memory,
            )
            if new_handle:
                resume_handle = new_handle
            _log(f"Session ended, reconnecting (attempt {attempt + 1})")
            await asyncio.sleep(0.5)
            continue
        except _UserStoppedError:
            _log("User stopped the session")
            break
        except Exception as e:
            _log(f"Session error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RECONNECTS:
                await asyncio.sleep(1)
                continue
            emit({"type": "error", "error": f"Session error: {e}"})
            break


class _UserStoppedError(Exception):
    pass


async def _run_live_session(client, config, loop, tool_map, connectors, memory):
    """Run a single Gemini Live session. Returns resume handle or None."""
    from google.genai import types

    resume_handle = None

    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        _log("Connected successfully")
        emit({"type": "ready"})

        stop_event = asyncio.Event()
        user_stopped = False

        async def send_audio():
            """Read audio from stdin, forward to Gemini Live."""
            nonlocal user_stopped
            while not stop_event.is_set():
                try:
                    try:
                        line = await asyncio.wait_for(
                            loop.run_in_executor(None, sys.stdin.readline),
                            timeout=2.0,
                        )
                    except asyncio.TimeoutError:
                        continue
                    if not line:
                        _log("stdin EOF")
                        user_stopped = True
                        stop_event.set()
                        break
                    msg = json.loads(line)
                    if msg["type"] == "audio":
                        audio_bytes = base64.b64decode(msg["data"])
                        await session.send_realtime_input(
                            audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                        )
                    elif msg["type"] == "end":
                        _log("Received end message")
                        user_stopped = True
                        stop_event.set()
                        break
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    _log(f"Send error: {e}")
                    stop_event.set()
                    break

        async def receive_responses():
            """Read Gemini Live responses, forward to stdout."""
            nonlocal resume_handle
            _log("receive_responses started")
            audio_chunks = 0
            while not stop_event.is_set():
                try:
                    async for response in session.receive():
                        if stop_event.is_set():
                            break

                        # Session resumption handle
                        if (response.session_resumption_update
                                and response.session_resumption_update.new_handle):
                            resume_handle = response.session_resumption_update.new_handle
                            _log(f"Got resume handle ({len(resume_handle)} chars)")

                        # Go-away: server is about to disconnect
                        if response.go_away:
                            time_left = getattr(response.go_away, "time_left", "?")
                            _log(f"Go-away received, time_left={time_left} — will reconnect gracefully")
                            # Don't break — let the session finish naturally,
                            # the receive() generator will end soon

                        # Audio / text responses
                        if response.server_content:
                            sc = response.server_content

                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        audio_b64 = base64.b64encode(part.inline_data.data).decode()
                                        emit({"type": "audio", "data": audio_b64})
                                        audio_chunks += 1
                                    # Native audio thinking — log only, don't show
                                    if part.text:
                                        _log(f"[thinking] {part.text[:120]}")

                            if sc.interrupted:
                                emit({"type": "interrupted"})
                            if sc.turn_complete:
                                memory.flush_current_turn()
                                emit({"type": "turn_complete"})

                            # Transcriptions — feed into session memory
                            if sc.output_transcription and sc.output_transcription.text:
                                text = sc.output_transcription.text
                                emit({"type": "transcript", "role": "assistant", "text": text})
                                memory.add_turn("assistant", text)
                            if sc.input_transcription and sc.input_transcription.text:
                                text = sc.input_transcription.text
                                emit({"type": "transcript", "role": "user", "text": text})
                                memory.add_turn("user", text)

                        # Tool calls
                        if response.tool_call:
                            for fc in response.tool_call.function_calls:
                                tool_name = fc.name
                                args = dict(fc.args) if fc.args else {}

                                emit({"type": "tool_call", "id": fc.id, "name": tool_name, "args": args})

                                # Track what's being done in memory
                                if tool_name == "email":
                                    action = args.get("action", "")
                                    if action in ("send", "create_draft"):
                                        memory.set_task(f"Sending email to {args.get('to', '?')}")
                                        memory.set_draft(to=args.get("to"), subject=args.get("subject"))
                                    elif action == "search":
                                        memory.add_fact(f"Searched emails for: {args.get('query', '?')}")
                                elif tool_name == "show_draft":
                                    memory.set_draft(
                                        to=args.get("to"),
                                        subject=args.get("subject"),
                                        content_hint=args.get("body", "")[:100],
                                    )
                                    memory.set_task(f"Draft shown to user: email to {args.get('to', '?')} — waiting for approval")

                                def _exec_tool(tn, a):
                                    try:
                                        return _route_combined_tool(tn, a, tool_map, connectors)
                                    except Exception as e:
                                        _log(f"Tool {tn} failed: {e}")
                                        try:
                                            import knowledge_base
                                            query = " ".join(str(v) for v in a.values() if v)[:100]
                                            return f"Tool error: {e}. KB: {knowledge_base.search(query or tn, max_results=3)}"
                                        except Exception:
                                            return f"Tool error: {e}"

                                result = await loop.run_in_executor(None, _exec_tool, tool_name, args)
                                result_str = str(result)[:3000]

                                # Auto-extract useful info into session memory
                                memory.extract_from_tool_result(tool_name, args, result_str)

                                card = _build_action_card(tool_name, args, result_str)
                                emit({"type": "tool_result", "id": fc.id, "name": tool_name,
                                      "action": args.get("action", ""), "result": result_str, "card": card})

                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(id=fc.id, name=tool_name, response={"result": result_str})
                                    ]
                                )

                    _log(f"session.receive() ended ({audio_chunks} audio chunks sent)")
                    stop_event.set()
                    break

                except Exception as e:
                    if not stop_event.is_set():
                        _log(f"Receive error: {e}")
                    stop_event.set()
                    break

        results = await asyncio.gather(send_audio(), receive_responses(), return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                _log(f"Task {i} raised: {r}")

        if user_stopped:
            raise _UserStoppedError()

        return resume_handle


if __name__ == "__main__":
    asyncio.run(run_voice_session())
