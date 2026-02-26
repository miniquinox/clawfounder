"""
Supabase connector — Query tables, insert data, and run SQL.
"""

import os
import json
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Return True if Supabase credentials are set."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


TOOLS = [
    {
        "name": "supabase_query",
        "description": "Query a Supabase table. Returns rows matching the filter.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name to query",
                },
                "select": {
                    "type": "string",
                    "description": "Columns to select (default: '*')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default: 20)",
                },
                "filters": {
                    "type": "string",
                    "description": "Optional filter in 'column=value' format. Comma-separated for multiple.",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "supabase_insert",
        "description": "Insert a row into a Supabase table.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
                },
                "data": {
                    "type": "string",
                    "description": "JSON string of the row data to insert (e.g., '{\"name\": \"John\", \"email\": \"john@test.com\"}')",
                },
            },
            "required": ["table", "data"],
        },
    },
    {
        "name": "supabase_sql",
        "description": "Run a read-only SQL query on Supabase (requires a custom RPC function — prefer supabase_query for most use cases). Only SELECT statements are allowed.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to run",
                },
            },
            "required": ["query"],
        },
    },
]


def _resolve_env_keys(account_id=None):
    """Resolve the env var names for the given account."""
    if account_id is None or account_id == "default":
        return "SUPABASE_URL", "SUPABASE_SERVICE_KEY"
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("supabase", []):
                if acct["id"] == account_id and "env_keys" in acct:
                    keys = acct["env_keys"]
                    return keys.get("SUPABASE_URL", f"SUPABASE_URL_{account_id.upper()}"), \
                           keys.get("SUPABASE_SERVICE_KEY", f"SUPABASE_SERVICE_KEY_{account_id.upper()}")
        except Exception:
            pass
    return f"SUPABASE_URL_{account_id.upper()}", f"SUPABASE_SERVICE_KEY_{account_id.upper()}"


def _get_client(account_id=None):
    try:
        from supabase import create_client
    except ImportError:
        raise ImportError("supabase-py not installed. Run: bash connectors/supabase/install.sh")

    url_key, key_key = _resolve_env_keys(account_id)
    url = os.environ.get(url_key)
    key = os.environ.get(key_key)
    if not url or not key:
        raise ValueError(f"{url_key} and {key_key} must be set in .env")
    return create_client(url, key)


def _query(table: str, select: str = "*", limit: int = 20, filters: str = None, account_id=None) -> str:
    client = _get_client(account_id)
    q = client.table(table).select(select).limit(limit)

    if filters:
        for f in filters.split(","):
            f = f.strip()
            if "=" in f:
                col, val = f.split("=", 1)
                q = q.eq(col.strip(), val.strip())

    result = q.execute()
    return json.dumps(result.data, indent=2, default=str)


def _insert(table: str, data: str, account_id=None) -> str:
    client = _get_client(account_id)
    try:
        row = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, TypeError) as e:
        return f"Invalid JSON data: {e}. Pass a valid JSON object like '{{\"name\": \"John\"}}'"
    result = client.table(table).insert(row).execute()
    return f"Inserted {len(result.data)} row(s) into '{table}'"


def _sql(query: str, account_id=None) -> str:
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for safety."
    client = _get_client()
    result = client.rpc("", {}).execute()  # Fallback — see note below
    # Note: Direct SQL requires the pg_net extension or a custom RPC function.
    # For basic usage, use supabase_query instead.
    return "SQL execution requires a custom Supabase RPC function. Use supabase_query for basic queries."


def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "supabase_query":
            return _query(
                args["table"],
                args.get("select", "*"),
                args.get("limit", 20),
                args.get("filters"),
                account_id=account_id,
            )
        elif tool_name == "supabase_insert":
            return _insert(args["table"], args["data"], account_id=account_id)
        elif tool_name == "supabase_sql":
            return _sql(args["query"], account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Supabase error: {e}"
