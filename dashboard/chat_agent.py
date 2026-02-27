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

from agent_shared import (
    setup_env, emit, load_all_connectors, call_tool as _call_tool, get_briefing as _get_briefing,
)
setup_env()


def _log(msg):
    """Log to stderr (visible in server.js but not in JSONL stdout)."""
    print(f"[chat] {msg}", file=sys.stderr, flush=True)


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

    # Add knowledge base summary (what the agent already knows)
    try:
        import knowledge_base
        kb_summary = knowledge_base.get_summary()
        if kb_summary:
            lines.append("## Memory")
            lines.append(f"You have a knowledge base with indexed data from past interactions. {kb_summary}")
            lines.append("Use the search_knowledge tool to look up details about any person, project, or topic mentioned above.")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


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


# ── Parallel tool execution ───────────────────────────────────────

def _execute_tool(tool_name, args, tool_map, connectors):
    """Execute a single tool call. Returns (tool_name, conn_name, result)."""
    conn_name, module, accounts = tool_map.get(tool_name, ("unknown", None, []))

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
            result = _call_tool(module, tool_name, args, accounts, conn_name=conn_name)
        except Exception as e:
            result = f"Tool error: {e}"
    else:
        result = f"Unknown tool: {tool_name}"

    return (tool_name, conn_name, result)


def _execute_tools_parallel(tool_calls_list, tool_map, connectors):
    """Execute multiple tool calls in parallel using threads.

    tool_calls_list: list of (tool_name, args) tuples
    Returns: list of (tool_name, conn_name, result) tuples in the same order.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if len(tool_calls_list) <= 1:
        # No benefit from parallelism for a single call
        results = []
        for tool_name, args in tool_calls_list:
            results.append(_execute_tool(tool_name, args, tool_map, connectors))
        return results

    results = [None] * len(tool_calls_list)
    with ThreadPoolExecutor(max_workers=min(len(tool_calls_list), 5)) as executor:
        future_to_idx = {}
        for idx, (tool_name, args) in enumerate(tool_calls_list):
            future = executor.submit(_execute_tool, tool_name, args, tool_map, connectors)
            future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                tn, _ = tool_calls_list[idx]
                results[idx] = (tn, "unknown", f"Tool error: {e}")

    return results


# ── Proactive Knowledge Surfacing ─────────────────────────────────

def _proactive_search(message):
    """Search the knowledge base proactively before the model call.

    Returns a context string to prepend to the user message, or None.
    Skips short confirmation messages to avoid unnecessary latency.
    """
    if not message or len(message.strip()) < 15:
        return None
    try:
        import knowledge_base
        context = knowledge_base.quick_search(message)
        if context:
            return (
                "[CONTEXT FROM YOUR CONNECTED SERVICES — use this if relevant to the user's question:\n"
                f"{context}\n"
                "Do NOT mention this context unless it's relevant to what the user is asking.]\n\n"
            )
    except Exception:
        pass
    return None


# ── Shared provider setup ─────────────────────────────────────────

def _provider_setup(message, connectors, router_api_key=None):
    """Run router + system prompt + proactive search in parallel.

    The router LLM call runs in a background thread while
    the system prompt and proactive search happen on the main thread.
    Returns (all_tool_defs, tool_map, system, enriched_message).
    """
    from concurrent.futures import ThreadPoolExecutor

    # Start router in background thread (300-800ms LLM call)
    import tool_router
    with ThreadPoolExecutor(max_workers=1) as executor:
        router_future = executor.submit(tool_router.route, message, connectors, router_api_key)

        # While router runs, do other setup work on main thread
        system = build_system_prompt(connectors)
        kb_context = _proactive_search(message)
        enriched_message = (kb_context + message) if kb_context else message
        if kb_context:
            emit({"type": "thinking", "text": "Found relevant context from knowledge base"})

        # Now wait for router result
        try:
            allowed_tools = router_future.result(timeout=5)
        except Exception:
            allowed_tools = None

    if allowed_tools:
        emit({"type": "thinking", "text": f"Routed to {len(allowed_tools)} tools"})

    # Build tool definitions
    all_tool_defs, tool_map = build_tools_and_map(connectors, allowed_tools=allowed_tools)
    all_tool_defs.append(BRIEFING_TOOL_DEF)
    tool_map["get_briefing"] = ("_briefing", None, [])

    import knowledge_base
    all_tool_defs.append(knowledge_base.KNOWLEDGE_TOOL_DEF)
    tool_map["search_knowledge"] = ("_knowledge", None, [])

    return all_tool_defs, tool_map, system, enriched_message


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

    # Parallel setup: router + system prompt + proactive search
    all_tool_defs, tool_map, system, enriched_message = _provider_setup(message, connectors, api_key)

    gemini_fns = []
    for tool in all_tool_defs:
        gemini_fns.append(types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool.get("parameters", {}),
        ))

    gemini_tools = types.Tool(function_declarations=gemini_fns) if gemini_fns else None

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
        parts=[types.Part(text=enriched_message)],
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

        # Execute tool calls in parallel
        tool_calls_list = []
        for part in function_calls:
            fc = part.function_call
            tool_name = fc.name
            args = dict(fc.args) if fc.args else {}
            conn_name = tool_map.get(tool_name, ("unknown", None, []))[0]
            emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})
            tool_calls_list.append((tool_name, args))

        results = _execute_tools_parallel(tool_calls_list, tool_map, connectors)

        function_response_parts = []
        for tool_name, conn_name, result in results:
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

    # Parallel setup: router + system prompt + proactive search
    gemini_key = os.environ.get("GEMINI_API_KEY")
    all_tool_defs, tool_map, system_prompt, enriched_message = _provider_setup(message, connectors, gemini_key)

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

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["text"]})
    messages.append({"role": "user", "content": enriched_message})

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

            # Collect and execute tool calls in parallel
            tool_calls_list = []
            tc_ids = []
            for tc in msg["tool_calls"]:
                tool_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {}
                conn_name = tool_map.get(tool_name, ("unknown", None, []))[0]
                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})
                tool_calls_list.append((tool_name, args))
                tc_ids.append(tc["id"])

            results = _execute_tools_parallel(tool_calls_list, tool_map, connectors)

            for (tool_name, conn_name, result), tc_id in zip(results, tc_ids):
                emit({
                    "type": "tool_result", "tool": tool_name, "connector": conn_name,
                    "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                    "truncated": len(result) > 500 if isinstance(result, str) else False,
                })
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})
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

    # Parallel setup: router + system prompt + proactive search
    gemini_key = os.environ.get("GEMINI_API_KEY")
    all_tool_defs, tool_map, system, enriched_message = _provider_setup(message, connectors, gemini_key)

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
    messages.append({"role": "user", "content": enriched_message})

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
            "system": system,
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

        # Emit text blocks and collect tool_use blocks
        tool_use_blocks = []
        for block in data.get("content", []):
            if block["type"] == "text":
                emit({"type": "text", "text": block["text"]})
            elif block["type"] == "tool_use":
                has_tool_use = True
                tool_use_blocks.append(block)

        if tool_use_blocks:
            # Collect and execute tool calls in parallel
            tool_calls_list = []
            block_ids = []
            for block in tool_use_blocks:
                tool_name = block["name"]
                args = block.get("input", {})
                conn_name = tool_map.get(tool_name, ("unknown", None, []))[0]
                emit({"type": "tool_call", "tool": tool_name, "connector": conn_name, "args": args})
                tool_calls_list.append((tool_name, args))
                block_ids.append(block["id"])

            results = _execute_tools_parallel(tool_calls_list, tool_map, connectors)

            for (tool_name, conn_name, result), block_id in zip(results, block_ids):
                emit({
                    "type": "tool_result", "tool": tool_name, "connector": conn_name,
                    "result": result[:2000] if isinstance(result, str) else str(result)[:2000],
                    "truncated": len(result) > 500 if isinstance(result, str) else False,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block_id,
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
