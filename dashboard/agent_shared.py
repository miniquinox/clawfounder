"""
ClawFounder — Shared Agent Utilities

Common code used by chat_agent.py, voice_agent.py, and briefing_agent.py.
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
