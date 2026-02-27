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


def emit(event):
    """Write a JSONL event to stdout."""
    print(json.dumps(event, default=str), flush=True)


def _log(msg):
    """Log to stderr (visible in server.js but not in JSONL stdout)."""
    print(f"[chat] {msg}", file=sys.stderr, flush=True)


# ── Load connectors ─────────────────────────────────────────────

def _read_accounts_registry():
    """Read the accounts registry from ~/.clawfounder/accounts.json."""
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            return json.loads(accounts_file.read_text())
        except Exception:
            pass
    return {"version": 1, "accounts": {}}


def load_all_connectors():
    """Load all connectors that have their deps available.

    Returns a dict of {conn_name: {"module": module, "accounts": [...], "supports_multi": bool}}.
    """
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
            # Filter to only enabled accounts
            enabled_accounts = [a for a in reg_accounts if a.get("enabled", True)]

            if enabled_accounts:
                # At least one enabled account exists in the registry
                loaded[folder.name] = {
                    "module": module,
                    "accounts": enabled_accounts,
                    "supports_multi": supports_multi,
                }
            else:
                # Fall back to legacy is_connected() check when no registry entry
                if hasattr(module, "is_connected") and callable(module.is_connected):
                    if not module.is_connected():
                        continue
                loaded[folder.name] = {
                    "module": module,
                    "accounts": [],
                    "supports_multi": supports_multi,
                }
        except Exception:
            pass  # Skip connectors with missing deps

    return loaded


def build_tools_and_map(connectors, allowed_tools=None):
    """Build tool definitions and a routing map from loaded connectors.

    When a connector has multiple enabled accounts and supports multi-account,
    inject an `account` parameter into each tool's parameters.

    If allowed_tools is provided (a set of tool name strings), only include
    tools whose name is in the set.

    Returns (all_tools, tool_map) where:
      all_tools = list of tool definition dicts
      tool_map = {tool_name: (conn_name, module, accounts)}
    """
    all_tools = []
    tool_map = {}

    for conn_name, info in connectors.items():
        module = info["module"]
        accounts = info["accounts"]
        supports_multi = info["supports_multi"]

        for tool in module.TOOLS:
            if allowed_tools and tool["name"] not in allowed_tools:
                continue

            if supports_multi and len(accounts) > 1:
                # Deep copy and inject `account` parameter
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


def build_system_prompt(connectors):
    """Build a rich system prompt from the loaded connectors and their instructions."""
    connectors_dir = PROJECT_ROOT / "connectors"

    # Detect user identity from connected email accounts & token files
    user_emails = []
    user_name = None
    clawfounder_dir = Path.home() / ".clawfounder"
    for cname in ("gmail", "work_email"):
        info = connectors.get(cname)
        if not info or not isinstance(info, dict):
            continue
        for acct in info.get("accounts", []):
            email = acct.get("label", "")
            if "@" in email:
                user_emails.append(email)
            # Try to read the display name from the token file
            if not user_name:
                cred_file = acct.get("credential_file")
                if cred_file:
                    try:
                        token_data = json.loads((clawfounder_dir / cred_file).read_text())
                        if token_data.get("_name"):
                            user_name = token_data["_name"]
                    except Exception:
                        pass

    lines = [
        "You are ClawFounder 🦀 — a personal AI agent that takes real actions "
        "using connected services. Be concise and helpful.",
        "",
        "## CORE BEHAVIOR — PREDICT, VERIFY, EXECUTE",
        "",
        "You operate in a 3-step loop:",
        "",
        "### Step 1: PREDICT — Do the research silently",
        "When the user gives you a task, IMMEDIATELY use tools to gather everything you need. "
        "Never ask the user for information you can look up yourself. "
        "If the user says 'email Shuban', search all connected email accounts for Shuban's address. "
        "If the user says 'check my emails', read them across all accounts. "
        "Your first response must be tool calls — not questions.",
        "",
        "### Step 2: VERIFY — Show the user what you plan to do and get confirmation",
        "Before executing any action that SENDS, CREATES, MODIFIES, or DELETES something "
        "(sending emails, creating issues, inserting data, etc.), "
        "present a clear summary of what you're about to do and ask for confirmation. Example:",
        "",
        '  "Here\'s what I\'ll send from both accounts to shuban@email.com:"',
        '  "**From kaziabdullah61@gmail.com:**"',
        '  "> Subject: ..."',
        '  "> Body preview..."',
        '  "**From akaziwork61@gmail.com:**"',
        '  "> Subject: ..."',
        '  "> Body preview..."',
        '  "Send both?"',
        "",
        "Keep the preview concise. For short emails show the full body. For long ones, show a summary.",
        "READ-ONLY actions (searching, listing, reading emails) do NOT need confirmation — just do them.",
        "",
        "### Step 3: EXECUTE — Act on confirmation",
        "When the user confirms (yes, yep, send it, go, do it, etc.), execute immediately. "
        "If they want changes, adjust and show the updated plan.",
        "",
        "## Rules",
        "1. ALWAYS use tools to answer questions — never guess or say you can't when a tool exists.",
        "2. When the user asks for a summary, briefing, or 'what's going on', use the get_briefing tool.",
        "3. When the user mentions a person, project, or topic, use search_knowledge FIRST to check for "
        "relevant context across all services before making direct tool calls.",
        "4. When the user asks about emails, files, data, etc. — call the appropriate tool FIRST, then answer.",
        "5. If a tool returns an error, report it honestly and suggest next steps.",
        "6. Be brief. Don't narrate every step — just do it.",
        "7. If multiple email accounts are connected, search ALL of them when looking something up.",
        "8. When the user mentions a person by name, search your emails to find their address. "
        "The search results include `to` and `from` fields — use those.",
        "",
        "## Email Persona — CRITICAL",
        "You are ghostwriting on behalf of the user. Every email you compose, reply to, or draft "
        "must read as if the user typed it themselves.",
        "- Write in first person. You ARE the user.",
        "- Never mention you are an AI, an assistant, or ClawFounder.",
        "- Never say things like 'I've drafted this for you' or 'Here's what I wrote' in the email body itself. "
        "Just write the email directly.",
        "- Match context: professional and polished for work, relaxed and natural for personal.",
        "- Keep it short. Real people write short emails.",
    ]
    if user_name:
        lines.append(f"- The user's name is **{user_name}**. Sign off naturally (e.g. 'Best,\\n{user_name}' or "
                      f"just '{user_name}' or no sign-off for casual quick replies).")
    else:
        lines.append("- If you don't know the user's name, infer it from their email address or skip the sign-off.")
    if user_emails:
        lines.append(f"- Connected email addresses: {', '.join(user_emails)}.")
    lines.append("- Avoid stiff AI-sounding phrases: no 'I hope this finds you well', no 'as per our discussion', "
                  "no 'please do not hesitate', no 'I wanted to reach out'. Write like a real person.")
    lines.append("")

    # Include each connector's instructions.md (the source of truth for tool usage)
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

            # If this connector has multiple enabled accounts, list them
            info = connectors[conn_name]
            accounts = info.get("accounts", []) if isinstance(info, dict) else []
            if len(accounts) > 1:
                lines.append(f"#### {conn_name} — Accounts")
                for acct in accounts:
                    lines.append(f"- `{acct['id']}`: {acct.get('label', acct['id'])}")
                lines.append("")
                lines.append(
                    f"You MUST specify the `account` parameter when calling {conn_name} tools. "
                    "If the user says 'both' or 'all', call the tool once per account. "
                    "If the user doesn't specify, use ALL accounts."
                )
                lines.append("")

        # If both email connectors are active, add disambiguation guidance
        if "gmail" in connectors and "work_email" in connectors:
            lines.append("### Email Disambiguation")
            lines.append(
                "The user has TWO email connector types connected: personal Gmail (`gmail_*` tools) "
                "and work email (`work_email_*` tools). "
                "When they say 'personal', 'Gmail', or 'personal email' → use gmail_* tools. "
                "When they say 'work', 'work email', 'company email', or 'workspace' → use work_email_* tools. "
                "When they say 'both' or 'all my emails' → use BOTH. "
                "When they just say 'my email' without specifying → use ALL connected email accounts."
            )
            lines.append("")

    return "\n".join(lines)


# ── Tool execution helper ────────────────────────────────────────

# Read-only tools that are safe to cache
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
    """Call a connector's handle() with optional account_id routing + caching + knowledge indexing."""
    import tool_cache
    import knowledge_base

    account_id = args.pop("account", None)
    # Auto-select if only 1 account
    if account_id is None and len(accounts) == 1:
        account_id = accounts[0]["id"]

    # Check cache for read-only tools
    connector = tool_name.split("_")[0]
    if tool_name in _CACHEABLE_PREFIXES:
        cached = tool_cache.get(tool_name, args, account_id=account_id, connector=connector)
        if cached is not None:
            knowledge_base.index(connector, tool_name, cached, args, account_id)
            return cached

    supports_multi = getattr(module, "SUPPORTS_MULTI_ACCOUNT", False)
    if supports_multi and account_id:
        result = module.handle(tool_name, args, account_id=account_id)
    else:
        result = module.handle(tool_name, args)

    # Cache the result for read-only tools
    if tool_name in _CACHEABLE_PREFIXES and isinstance(result, str):
        tool_cache.put(tool_name, args, result, account_id=account_id)

    # Index into knowledge base (fire-and-forget)
    if isinstance(result, str):
        knowledge_base.index(connector, tool_name, result, args, account_id)

    return result


# ── Briefing tool ────────────────────────────────────────────────

BRIEFING_TOOL_DEF = {
    "name": "get_briefing",
    "description": (
        "Get a summary of everything happening across the user's connected services — "
        "emails, GitHub notifications, stock prices, messages, etc. "
        "Use this when the user asks for a summary, briefing, or update on what's going on."
    ),
    "parameters": {"type": "object", "properties": {}},
}


def _get_briefing(connectors):
    """Gather data from all connected services and return a summary."""
    briefing_path = Path(__file__).parent / "briefing_agent.py"
    spec = importlib.util.spec_from_file_location("briefing_agent", briefing_path)
    briefing_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(briefing_mod)

    config_file = Path.home() / ".clawfounder" / "briefing_config.json"
    connector_configs = {}
    if config_file.exists():
        try:
            connector_configs = json.loads(config_file.read_text()).get("connectors", {})
        except Exception:
            pass

    gathered = briefing_mod.gather_data(connectors, connector_configs)

    parts = []
    for conn_name, data in gathered.items():
        for item in data:
            result = item.get("result", item.get("error", ""))
            label = item.get("account", conn_name)
            result_str = str(result)[:3000]
            parts.append(f"[{conn_name}] {item.get('tool', '')} ({label}):\n{result_str}")

    return "\n\n".join(parts) if parts else "No data available from connected services."


# ── Tool router (LLM-powered) ────────────────────────────────────


# ── Provider: Gemini ─────────────────────────────────────────────

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def run_gemini(message, history, connectors):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "GEMINI_API_KEY not set. Get one from aistudio.google.com/apikey"})
        return

    client = genai.Client(api_key=api_key)

    # Smart tool routing — LLM picks relevant tools
    import tool_router
    allowed_tools = tool_router.route(message, connectors, api_key)
    if allowed_tools:
        emit({"type": "thinking", "text": f"Routed to {len(allowed_tools)} tools"})

    # Build tool declarations from connectors + briefing + knowledge
    all_tool_defs, tool_map = build_tools_and_map(connectors, allowed_tools=allowed_tools)
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    import knowledge_base
    all_tool_defs.append(knowledge_base.KNOWLEDGE_TOOL_DEF)
    tool_map["search_knowledge"] = ("_knowledge", None, [])

    gemini_fns = []
    for tool in all_tool_defs:
        gemini_fns.append(types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool.get("parameters", {}),
        ))

    gemini_tools = types.Tool(function_declarations=gemini_fns) if gemini_fns else None

    system = build_system_prompt(connectors)

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

    config = types.GenerateContentConfig(
        tools=[gemini_tools] if gemini_tools else [],
        system_instruction=system,
        temperature=1,
        top_p=0.95,
        max_output_tokens=8192,
    )

    # Set thinking budget if supported (prevents thinking-only responses)
    try:
        config.thinking_config = types.ThinkingConfig(thinking_budget=2048)
    except Exception:
        pass

    # Agentic loop with streaming
    max_turns = 10
    thinking_retries = 0
    for turn in range(max_turns):
        try:
            streamed_text = ""
            function_calls = []
            had_thinking = False

            chunk_count = 0
            for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            ):
                chunk_count += 1
                if not chunk.candidates:
                    _log(f"Chunk {chunk_count}: no candidates")
                    continue
                candidate = chunk.candidates[0]
                finish = getattr(candidate, 'finish_reason', None)
                # Check for blocked / safety-filtered responses
                if finish and str(finish) not in ('STOP', 'MAX_TOKENS', 'FinishReason.STOP', 'FinishReason.MAX_TOKENS', '0', '1', 'None'):
                    _log(f"Blocked: finish_reason={finish}")
                    emit({"type": "error", "error": f"Response blocked: {finish}"})
                    return
                content = candidate.content
                if not content or not content.parts:
                    _log(f"Chunk {chunk_count}: finish_reason={finish}, no content/parts")
                    continue
                for part in content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        had_thinking = True
                        continue
                    if part.text:
                        streamed_text += part.text
                        emit({"type": "text", "text": part.text})
                    elif part.function_call:
                        function_calls.append(part)

            _log(f"Stream done: chunks={chunk_count}, text={len(streamed_text)}, calls={len(function_calls)}, thinking={had_thinking}")

            if not streamed_text and not function_calls:
                if had_thinking and thinking_retries < 2:
                    thinking_retries += 1
                    emit({"type": "thinking", "text": "Processing..."})
                    # Disable thinking on retry to force actual output
                    try:
                        config.thinking_config = types.ThinkingConfig(thinking_budget=0)
                    except Exception:
                        pass
                    continue
                emit({"type": "error", "error": "Empty response from Gemini"})
                return

        except Exception as e:
            emit({"type": "error", "error": str(e)[:300]})
            return

        if not function_calls:
            break

        # Execute tool calls
        function_response_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_name = fc.name
            args = dict(fc.args) if fc.args else {}
            conn_name, module, accounts = tool_map.get(tool_name, ("unknown", None, []))

            emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

            if tool_name == "get_briefing":
                try:
                    result = _get_briefing(connectors)
                except Exception as e:
                    result = f"Briefing error: {e}"
            elif tool_name == "search_knowledge":
                try:
                    import knowledge_base
                    result = knowledge_base.search(
                        args.get("query", ""),
                        connector=args.get("connector"),
                        max_results=args.get("max_results", 10),
                    )
                except Exception as e:
                    result = f"Knowledge search error: {e}"
            elif module:
                try:
                    result = _call_tool(module, tool_name, args, accounts)
                except Exception as e:
                    result = f"Tool error: {e}"
            else:
                result = f"Unknown tool: {tool_name}"

            truncated = len(result) > 500 if isinstance(result, str) else False
            emit({
                "type": "tool_result", "tool": tool_name, "connector": conn_name,
                "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                "truncated": truncated,
            })

            function_response_parts.append(
                types.Part(function_response=types.FunctionResponse(
                    name=tool_name,
                    response={"result": result},
                ))
            )

        # Build model's response for conversation history
        model_parts = []
        if streamed_text:
            model_parts.append(types.Part(text=streamed_text))
        model_parts.extend(function_calls)
        contents.append(types.Content(role="model", parts=model_parts))
        contents.append(types.Content(role="user", parts=function_response_parts))

    emit({"type": "done"})


# ── Provider: OpenAI ─────────────────────────────────────────────

def run_openai(message, history, connectors):
    import requests

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "OPENAI_API_KEY not set"})
        return

    emit({"type": "thinking", "text": "Connecting to OpenAI..."})

    # Smart tool routing — uses Gemini API key for routing even with OpenAI provider
    import tool_router
    gemini_key = os.environ.get("GEMINI_API_KEY")
    allowed_tools = tool_router.route(message, connectors, gemini_key)
    if allowed_tools:
        emit({"type": "thinking", "text": f"Routed to {len(allowed_tools)} tools"})

    # Build tool definitions + briefing + knowledge
    all_tool_defs, tool_map = build_tools_and_map(connectors, allowed_tools=allowed_tools)
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    import knowledge_base
    all_tool_defs.append(knowledge_base.KNOWLEDGE_TOOL_DEF)
    tool_map["search_knowledge"] = ("_knowledge", None, [])

    tool_defs = []
    for tool in all_tool_defs:
        tool_defs.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        })

    messages = [{"role": "system", "content": build_system_prompt(connectors)}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["text"]})
    messages.append({"role": "user", "content": message})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    max_turns = 20
    for turn in range(max_turns):
        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        body = {"model": model, "messages": messages}
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
                conn_name, module, accounts = tool_map.get(tool_name, ("unknown", None, []))

                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

                if tool_name == "get_briefing":
                    try:
                        result = _get_briefing(connectors)
                    except Exception as e:
                        result = f"Briefing error: {e}"
                elif tool_name == "search_knowledge":
                    try:
                        result = knowledge_base.search(
                            args.get("query", ""),
                            connector=args.get("connector"),
                            max_results=args.get("max_results", 10),
                        )
                    except Exception as e:
                        result = f"Knowledge search error: {e}"
                elif module:
                    try:
                        result = _call_tool(module, tool_name, args, accounts)
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

    # Smart tool routing
    import tool_router
    gemini_key = os.environ.get("GEMINI_API_KEY")
    allowed_tools = tool_router.route(message, connectors, gemini_key)
    if allowed_tools:
        emit({"type": "thinking", "text": f"Routed to {len(allowed_tools)} tools"})

    # Build tool definitions + briefing + knowledge
    all_tool_defs, tool_map = build_tools_and_map(connectors, allowed_tools=allowed_tools)
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    import knowledge_base
    all_tool_defs.append(knowledge_base.KNOWLEDGE_TOOL_DEF)
    tool_map["search_knowledge"] = ("_knowledge", None, [])

    tool_defs = []
    for tool in all_tool_defs:
        tool_defs.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        })

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
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            "max_tokens": 4096,
            "system": build_system_prompt(connectors),
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
                conn_name, module, accounts = tool_map.get(tool_name, ("unknown", None, []))

                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})

                if tool_name == "get_briefing":
                    try:
                        result = _get_briefing(connectors)
                    except Exception as e:
                        result = f"Briefing error: {e}"
                elif tool_name == "search_knowledge":
                    try:
                        result = knowledge_base.search(
                            args.get("query", ""),
                            connector=args.get("connector"),
                            max_results=args.get("max_results", 10),
                        )
                    except Exception as e:
                        result = f"Knowledge search error: {e}"
                elif module:
                    try:
                        result = _call_tool(module, tool_name, args, accounts)
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
    conn_names = list(connectors.keys())
    emit({"type": "thinking", "text": f"Loaded {len(conn_names)} connector(s): {', '.join(conn_names)}"})

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
