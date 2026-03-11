"""
ClawFounder — Shared Agent Utilities

Common code used by voice_agent.py and briefing_agent.py.
Single source of truth for connector loading, tool execution, and caching.
"""

import sys
import os
import json
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


# ── Environment setup ─────────────────────────────────────────────

def setup_env():
    """Add project root to path and load .env."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass


# ── Gemini client (Vertex AI preferred, AI Studio fallback) ───────

def get_gemini_client():
    """Create a google-genai Client. Prefers Vertex AI if configured, falls back to API key."""
    from google import genai

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if project:
        return genai.Client(vertexai=True, project=project, location=location)

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)

    raise RuntimeError(
        "No Gemini credentials. Set GOOGLE_CLOUD_PROJECT (Vertex AI) or GEMINI_API_KEY (AI Studio)."
    )


# ── JSONL output ──────────────────────────────────────────────────

def emit(event):
    """Write a JSONL event to stdout."""
    print(json.dumps(event, default=str), flush=True)


# ── Connector loading ─────────────────────────────────────────────

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


# ── Tool caching + execution ──────────────────────────────────────

# Read-only tools that are safe to cache
CACHEABLE_TOOLS = (
    "gmail_get_unread", "gmail_search", "gmail_read_email", "gmail_list_labels",
    "work_email_get_unread", "work_email_search", "work_email_read_email",
    "github_list_repos", "github_get_repo", "github_notifications", "github_list_prs",
    "github_list_issues", "github_get_issue", "github_get_pr", "github_search",
    "github_get_commits", "github_list_branches", "github_list_releases",
    "github_get_file", "github_get_me", "github_list_tags", "github_list_gists",
    "slack_list_channels", "slack_get_messages", "slack_list_users", "slack_search",
    "calendar_list_events", "calendar_get_event", "calendar_list_calendars",
    "yahoo_finance_quote", "yahoo_finance_history", "yahoo_finance_search",
    "telegram_get_updates",
)


def call_tool(module, tool_name, args, accounts, conn_name=None):
    """Call a connector's handle() with optional account_id routing + caching + knowledge indexing."""
    import tool_cache
    import knowledge_base

    args = dict(args)  # Shallow copy to avoid mutating caller's dict
    account_id = args.pop("account", None)
    if account_id is None and len(accounts) == 1:
        account_id = accounts[0]["id"]

    # Use conn_name from tool_map (accurate), fallback to parsing tool name
    connector = conn_name or tool_name.split("_")[0]

    if tool_name in CACHEABLE_TOOLS:
        cached = tool_cache.get(tool_name, args, account_id=account_id, connector=connector)
        if cached is not None:
            knowledge_base.index(connector, tool_name, cached, args, account_id)
            return cached

    supports_multi = getattr(module, "SUPPORTS_MULTI_ACCOUNT", False)
    if supports_multi and account_id:
        result = module.handle(tool_name, args, account_id=account_id)
    else:
        result = module.handle(tool_name, args)

    if tool_name in CACHEABLE_TOOLS and isinstance(result, str):
        tool_cache.put(tool_name, args, result, account_id=account_id)

    if isinstance(result, str):
        knowledge_base.index(connector, tool_name, result, args, account_id)

    return result


# ── Briefing helper ───────────────────────────────────────────────

_briefing_module = None


def get_briefing(connectors):
    """Gather data from all connected services and return a summary."""
    global _briefing_module
    if _briefing_module is None:
        briefing_path = Path(__file__).parent / "briefing_agent.py"
        spec = importlib.util.spec_from_file_location("briefing_agent", briefing_path)
        _briefing_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_briefing_module)

    config_file = Path.home() / ".clawfounder" / "briefing_config.json"
    connector_configs = {}
    if config_file.exists():
        try:
            connector_configs = json.loads(config_file.read_text()).get("connectors", {})
        except Exception:
            pass

    gathered = _briefing_module.gather_data(connectors, connector_configs)

    parts = []
    for conn_name, data in gathered.items():
        for item in data:
            result = item.get("result", item.get("error", ""))
            label = item.get("account", conn_name)
            result_str = str(result)[:3000]
            parts.append(f"[{conn_name}] {item.get('tool', '')} ({label}):\n{result_str}")

    return "\n\n".join(parts) if parts else "No data available from connected services."


# ── Voice agent utilities ─────────────────────────────────────────

def build_connector_map(connectors):
    """Build a map of tool names to (connector_name, module, accounts) tuples."""
    tool_map = {}
    for conn_name, info in connectors.items():
        for tool in info["module"].TOOLS:
            tool_map[tool["name"]] = (conn_name, info["module"], info["accounts"])
    return tool_map


def route_voice_tool(tool_name, args, tool_map, connectors):
    """Route a combined voice tool to the underlying connector.

    Handles special voice tools like get_briefing, search_knowledge, show_draft,
    and routes combined tools (email, github, calendar, messaging, finance) to
    their underlying connector implementations.
    """
    if tool_name == "get_briefing":
        return get_briefing(connectors)

    if tool_name == "search_knowledge":
        import knowledge_base
        return knowledge_base.search(args.get("query", ""), max_results=10)

    if tool_name == "show_draft":
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
        return f"Saved: {note.get('title', 'note')} (id: {note.get('id')})"

    if tool_name == "finance":
        lookup = tool_map.get("yahoo_finance_quote")
        if lookup:
            _, mod, accts = lookup
            return call_tool(mod, "yahoo_finance_quote", {"symbol": args.get("symbol", "")}, accts)
        return "Finance not connected."

    if tool_name == "email":
        action = args.get("action", "get_unread")
        account = args.get("account", "personal")
        prefix = "work_email" if "work" in account.lower() else "gmail"
        real_tool = f"{prefix}_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"Email action '{action}' not available."
        _, mod, accts = lookup
        call_args = {k: v for k, v in args.items() if k not in ("action", "account") and v is not None}
        return call_tool(mod, real_tool, call_args, accts)

    if tool_name == "github":
        action = args.get("action", "notifications")
        real_tool = f"github_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"GitHub action '{action}' not available."
        _, mod, accts = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return call_tool(mod, real_tool, call_args, accts)

    if tool_name == "calendar":
        action = args.get("action", "list_events")
        real_tool = f"calendar_{action}"
        lookup = tool_map.get(real_tool)
        if not lookup:
            return f"Calendar action '{action}' not available."
        _, mod, accts = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return call_tool(mod, real_tool, call_args, accts)

    if tool_name == "messaging":
        action = args.get("action", "")
        lookup = tool_map.get(action)
        if not lookup:
            return f"Messaging action '{action}' not available."
        _, mod, accts = lookup
        call_args = {k: v for k, v in args.items() if k != "action" and v is not None}
        return call_tool(mod, action, call_args, accts)

    return f"Unknown tool: {tool_name}"


def build_voice_system_prompt(connectors, briefing, memory, prompt_template):
    """Build the system prompt for voice agent sessions.

    Args:
        connectors: Dict of loaded connectors
        briefing: Pre-cached briefing text
        memory: SessionMemory instance (or None)
        prompt_template: Template string with {memory}, {services}, {briefing} placeholders

    Returns:
        Formatted system prompt string
    """
    memory_str = memory.format_for_prompt() if memory else "No prior context."
    services = ", ".join(sorted(connectors.keys())) or "none"
    return prompt_template.format(
        memory=memory_str,
        services=services,
        briefing=briefing[:800] if briefing else "Not yet loaded.",
    )
