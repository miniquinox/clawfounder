"""
ClawFounder — Briefing Agent (JSONL streaming)

Scans all connected services, gathers recent data, then asks the LLM
to generate a prioritized task list. Outputs JSONL events for SSE.

Events emitted:
  {"type": "thinking",  "text": "..."}
  {"type": "gather",    "connector": "...", "tool": "...", "count": N}
  {"type": "briefing",  "tasks": [...]}
  {"type": "error",     "error": "..."}
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


# ── Reuse connector loading from chat_agent ─────────────────────

def _read_accounts_registry():
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            return json.loads(accounts_file.read_text())
        except Exception:
            pass
    return {"version": 1, "accounts": {}}


def load_all_connectors():
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


_CACHEABLE_PREFIXES = (
    "gmail_get_unread", "gmail_search", "gmail_read_email", "gmail_list_labels",
    "work_email_get_unread", "work_email_search", "work_email_read_email",
    "github_list_repos", "github_get_repo", "github_notifications", "github_list_prs",
    "github_list_issues", "github_get_issue", "github_get_pr", "github_search",
    "yahoo_finance_quote", "yahoo_finance_history", "yahoo_finance_search",
    "telegram_get_updates",
)


def _call_tool(module, tool_name, args, accounts):
    import tool_cache
    import knowledge_base

    account_id = args.pop("account", None)
    if account_id is None and len(accounts) == 1:
        account_id = accounts[0]["id"]

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

    if tool_name in _CACHEABLE_PREFIXES and isinstance(result, str):
        tool_cache.put(tool_name, args, result, account_id=account_id)

    if isinstance(result, str):
        knowledge_base.index(connector, tool_name, result, args, account_id)

    return result


# ── Briefing tool config — which tools to call per connector ─────

BRIEFING_TOOLS = {
    "gmail": [
        {"tool": "gmail_get_unread", "args": {"max_results": 10}},
    ],
    "work_email": [
        {"tool": "work_email_get_unread", "args": {"max_results": 10}},
    ],
    "github": [
        {"tool": "github_notifications", "args": {}},
    ],
    "telegram": [
        {"tool": "telegram_get_updates", "args": {"limit": 10}},
    ],
    "whatsapp": [],  # No read endpoint — Cloud API is send-only
    "supabase": [],  # Skip unless user configures specific queries
    "firebase": [],
    "yahoo_finance": [],
}


def _resolve_ticker(input_text, module):
    """Search Yahoo Finance and return the top matching ticker symbol."""
    try:
        result = module.handle("yahoo_finance_search", {"query": input_text.strip(), "max_results": 1})
        matches = json.loads(result) if isinstance(result, str) else result
        if matches:
            return matches[0]["symbol"]
    except Exception:
        pass
    return input_text.strip().upper()


def build_tool_configs(conn_name, cfg, modules=None):
    """Build tool call list for a connector, incorporating user settings.

    For most connectors, returns the static BRIEFING_TOOLS entry.
    For yahoo_finance: generates one yahoo_finance_quote call per symbol.
    For github: keeps notifications + one github_list_prs per watched repo.
    """
    if conn_name == "yahoo_finance":
        symbols_raw = cfg.get("symbols", "")
        symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
        if not symbols:
            return []
        # Resolve company names / fuzzy inputs to real tickers
        yf_module = (modules or {}).get("yahoo_finance")
        resolved = []
        for sym in symbols:
            if yf_module:
                ticker = _resolve_ticker(sym, yf_module)
            else:
                ticker = sym.upper()
            if ticker and ticker not in resolved:
                resolved.append(ticker)
        return [
            {"tool": "yahoo_finance_quote", "args": {"symbol": sym}}
            for sym in resolved
        ]

    if conn_name == "github":
        tools = [{"tool": "github_notifications", "args": {}}]
        repos_raw = cfg.get("repos", "")
        repos = [r.strip() for r in repos_raw.split(",") if r.strip()]
        for repo in repos:
            tools.append({"tool": "github_list_prs", "args": {"repo": repo, "state": "open"}})
        return tools

    return BRIEFING_TOOLS.get(conn_name, [])


# ── Phase 1: Gather data from all connected connectors ───────────

def gather_data(connectors, connector_configs=None):
    """Call read-only tools on each connected connector. Returns raw data dict."""
    import tool_cache
    import hashlib

    if connector_configs is None:
        connector_configs = {}

    # Check briefing-level cache
    cache_key = hashlib.md5(
        json.dumps(sorted(connectors.keys())).encode()
    ).hexdigest()
    cached = tool_cache.get_briefing(cache_key)
    if cached is not None:
        emit({"type": "thinking", "text": "Using cached briefing data..."})
        return cached

    gathered = {}

    for conn_name, info in connectors.items():
        cfg = connector_configs.get(conn_name, {})

        # Skip if user explicitly disabled this connector
        if cfg.get("enabled") is False:
            continue

        module = info["module"]
        accounts = info["accounts"]
        # Build module lookup for resolvers that need cross-connector access
        all_modules = {cn: ci["module"] for cn, ci in connectors.items()}
        tool_configs = build_tool_configs(conn_name, cfg, modules=all_modules)

        if not tool_configs:
            continue

        emit({"type": "thinking", "text": f"Checking {conn_name}..."})

        conn_data = []
        for tc in tool_configs:
            tool_name = tc["tool"]
            args = dict(tc["args"])

            # Apply max_results override from user config
            user_max = cfg.get("max_results")
            if user_max is not None:
                if "max_results" in args:
                    args["max_results"] = user_max
                elif "limit" in args:
                    args["limit"] = user_max

            # For multi-account connectors, call each account
            if info["supports_multi"] and len(accounts) > 1:
                for acct in accounts:
                    call_args = {**args, "account": acct["id"]}
                    try:
                        result = _call_tool(module, tool_name, call_args, accounts)
                        conn_data.append({
                            "tool": tool_name,
                            "account": acct.get("label", acct["id"]),
                            "result": result,
                        })
                    except Exception as e:
                        conn_data.append({"tool": tool_name, "account": acct["id"], "error": str(e)})
            else:
                try:
                    result = _call_tool(module, tool_name, args, accounts)
                    conn_data.append({"tool": tool_name, "result": result})
                except Exception as e:
                    conn_data.append({"tool": tool_name, "error": str(e)})

        # Count items for progress
        total_items = 0
        for d in conn_data:
            r = d.get("result", "")
            if isinstance(r, str):
                try:
                    parsed = json.loads(r)
                    if isinstance(parsed, list):
                        total_items += len(parsed)
                except (json.JSONDecodeError, TypeError):
                    if r and not r.startswith("Error") and r != "No recent messages.":
                        total_items += 1

        emit({"type": "gather", "connector": conn_name, "tool": tool_configs[0]["tool"], "count": total_items})
        gathered[conn_name] = conn_data

    # Cache the full briefing result
    tool_cache.put_briefing(cache_key, gathered)

    return gathered


# ── Phase 2: LLM analysis ────────────────────────────────────────

BRIEFING_SYSTEM_PROMPT = """You are generating a daily briefing for the user. You will receive raw data from their connected services (email, GitHub, messaging, finance, etc.).

Analyze it and return ONLY a valid JSON array of tasks. Each task must have:
- "id": unique string (e.g. "task_1", "task_2")
- "source": connector name (e.g. "gmail", "github", "telegram", "yahoo_finance")
- "priority": "high", "medium", or "low"
- "title": short actionable title (under 80 chars)
- "summary": 1-2 sentences of context
- "suggested_action": primary action (a natural language instruction for chat)
- "follow_ups": array of 2-3 specific follow-up actions the user might want. Each is an object with "label" (short button text, 2-4 words) and "prompt" (the chat message to send).

Follow-up guidelines per connector:
- gmail/work_email: ["Reply to this", "Mark as read", "Archive it"] or ["Draft a reply", "Forward to team", "Snooze for later"]
- github: ["Review the PR", "Check CI status", "View the diff"] or ["Merge it", "Request changes", "View repo"]
- telegram/whatsapp: ["Reply to them", "Mark as read"] or ["Draft a response", "Ignore"]
- yahoo_finance: ["Show price history", "Analyze this stock", "Compare with sector"] or ["Show 1-month chart data", "Get detailed financials", "Check news about {company}"]
- supabase/firebase: ["Show recent rows", "Run query", "Check logs"]

Make follow-ups SPECIFIC to the actual item. For example:
- For META stock: [{"label": "META history", "prompt": "Show me META price history for the last month"}, {"label": "Analyze META", "prompt": "Analyze META stock performance and give me your take"}, {"label": "Tech sector", "prompt": "How is META performing compared to other tech stocks?"}]
- For a PR: [{"label": "Review PR", "prompt": "Show me the changes in PR #42 on owner/repo"}, {"label": "CI status", "prompt": "Check the CI status for PR #42 on owner/repo"}]
- For an email: [{"label": "Draft reply", "prompt": "Draft a reply to the email from John about the project update"}, {"label": "Summarize thread", "prompt": "Summarize the full email thread from John"}]

Priority guidelines:
- HIGH: Urgent emails needing reply, failing CI, PR review requests, direct messages, stocks with >5% daily change
- MEDIUM: FYI emails, open PRs to check, notification digests, notable stock movements (2-5%)
- LOW: Newsletters, automated notifications, non-urgent updates, routine stock updates

For email data (gmail, work_email): Be selective. Only create tasks for emails that genuinely require action — direct messages needing a reply, important requests, or time-sensitive items. Skip newsletters, marketing emails, automated notifications, social media alerts, and FYI-only emails entirely. Group any remaining low-priority emails into a single summary item if needed. Quality over quantity.

For yahoo_finance data: Report notable movers with price, change %, and significant movements relative to 52-week range. Group minor movements into a single low-priority summary item rather than listing each stock separately.

For github data: Highlight PRs awaiting your review, failing checks, and direct mentions. Group routine notifications into summary items.

Sort by priority (high first), then by recency. Max 15 tasks.
Return ONLY the JSON array. No markdown, no explanation, no code fences."""


TIMEFRAME_LABELS = {
    "1h": "1 hour", "2h": "2 hours", "5h": "5 hours",
    "12h": "12 hours", "24h": "24 hours", "48h": "48 hours", "7d": "7 days",
}


def analyze_with_gemini(gathered, provider="gemini", connector_configs=None):
    """Send gathered data to LLM for analysis. Returns structured task list."""
    if connector_configs is None:
        connector_configs = {}

    # Build the data summary for the LLM
    data_text = "Here is the raw data from the user's connected services:\n\n"
    for conn_name, entries in gathered.items():
        data_text += f"## {conn_name}\n"
        for entry in entries:
            if "account" in entry:
                data_text += f"Account: {entry['account']}\n"
            if "error" in entry:
                data_text += f"Error: {entry['error']}\n"
            else:
                result = entry.get("result", "")
                # Truncate very long results
                if len(result) > 3000:
                    result = result[:3000] + "\n...(truncated)"
                data_text += f"Tool: {entry['tool']}\n{result}\n"
        data_text += "\n"

    if not any(gathered.values()):
        return []

    # Build timeframe instructions for the LLM
    timeframe_lines = []
    for conn_name in gathered:
        cfg = connector_configs.get(conn_name, {})
        tf = cfg.get("timeframe", "24h")
        label = TIMEFRAME_LABELS.get(tf, tf)
        timeframe_lines.append(f"- {conn_name}: only include items from the last {label}")

    timeframe_prompt = ""
    if timeframe_lines:
        timeframe_prompt = (
            "\n\nIMPORTANT — The user has set these timeframe preferences. "
            "Exclude any items with timestamps older than the specified window:\n"
            + "\n".join(timeframe_lines)
        )

    emit({"type": "thinking", "text": "Analyzing and prioritizing..."})

    system_prompt = BRIEFING_SYSTEM_PROMPT + timeframe_prompt

    if provider == "gemini":
        return _analyze_gemini(data_text, system_prompt)
    elif provider == "openai":
        return _analyze_openai(data_text, system_prompt)
    elif provider == "claude":
        return _analyze_claude(data_text, system_prompt)
    else:
        emit({"type": "error", "error": f"Unknown provider: {provider}"})
        return []


def _analyze_gemini(data_text, system_prompt):
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "GEMINI_API_KEY not set."})
        return []

    client = genai.Client(api_key=api_key)

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(
        model=model,
        contents=data_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=4096,
        ),
    )
    return _parse_tasks(response.text)


def _analyze_openai(data_text, system_prompt):
    import requests

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "OPENAI_API_KEY not set."})
        return []

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data_text},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=60,
    )
    if resp.status_code != 200:
        emit({"type": "error", "error": f"OpenAI error: {resp.status_code}"})
        return []

    text = resp.json()["choices"][0]["message"]["content"]
    return _parse_tasks(text)


def _analyze_claude(data_text, system_prompt):
    import requests

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        emit({"type": "error", "error": "ANTHROPIC_API_KEY not set."})
        return []

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": data_text}],
        },
        timeout=60,
    )
    if resp.status_code != 200:
        emit({"type": "error", "error": f"Claude error: {resp.status_code}"})
        return []

    text = resp.json()["content"][0]["text"]
    return _parse_tasks(text)


def _parse_tasks(text):
    """Parse LLM response into task list. Handles markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        tasks = json.loads(text)
        if isinstance(tasks, list):
            return tasks
    except json.JSONDecodeError:
        emit({"type": "error", "error": "Failed to parse LLM response as JSON"})
    return []


# ── Main ─────────────────────────────────────────────────────────

def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception as e:
        emit({"type": "error", "error": f"Invalid input: {e}"})
        emit({"type": "done"})
        return

    provider = input_data.get("provider", "gemini")
    briefing_config = input_data.get("briefing_config", {})
    connector_configs = briefing_config.get("connectors", {})

    # Load connectors
    connectors = load_all_connectors()
    conn_names = list(connectors.keys())

    if not conn_names:
        emit({"type": "error", "error": "No connectors are connected. Set up at least one in the Connect tab."})
        emit({"type": "done"})
        return

    # Filter to only enabled connectors (report which are active)
    active_names = [
        n for n in conn_names
        if connector_configs.get(n, {}).get("enabled", True) is not False
    ]
    if not active_names:
        emit({"type": "error", "error": "All connectors are disabled in briefing settings."})
        emit({"type": "done"})
        return

    emit({"type": "thinking", "text": f"Starting briefing with {len(active_names)} connector(s): {', '.join(active_names)}"})

    # Phase 1: Gather data (config-aware)
    gathered = gather_data(connectors, connector_configs)

    # Check if we got anything
    has_data = any(
        any(not e.get("error") for e in entries)
        for entries in gathered.values()
    )
    if not has_data:
        emit({"type": "briefing", "tasks": []})
        emit({"type": "done"})
        return

    # Phase 2: LLM analysis (with timeframe context)
    try:
        tasks = analyze_with_gemini(gathered, provider, connector_configs)
    except Exception as e:
        emit({"type": "error", "error": f"Analysis error: {e}"})
        tasks = []

    emit({"type": "briefing", "tasks": tasks})
    emit({"type": "done"})


if __name__ == "__main__":
    main()
