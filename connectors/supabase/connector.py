"""
Supabase connector — Query, insert, update, delete, and manage data in Supabase tables.
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
                    "description": "Columns to select (default: '*'). Supports Supabase select syntax like 'id, name, posts(title)' for joins.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default: 20)",
                },
                "filters": {
                    "type": "string",
                    "description": "Optional filter in 'column=value' format. Comma-separated for multiple.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Column to order by (prefix with '-' for descending, e.g. '-created_at')",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "supabase_insert",
        "description": "Insert one or more rows into a Supabase table.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
                },
                "data": {
                    "type": "string",
                    "description": "JSON string of the row(s) to insert. Single object or array of objects. E.g., '{\"name\": \"John\"}' or '[{\"name\": \"John\"}, {\"name\": \"Jane\"}]'",
                },
            },
            "required": ["table", "data"],
        },
    },
    {
        "name": "supabase_update",
        "description": "Update rows in a Supabase table matching a filter.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
                },
                "data": {
                    "type": "string",
                    "description": "JSON string of columns to update. E.g., '{\"status\": \"active\"}'",
                },
                "filters": {
                    "type": "string",
                    "description": "Filter for which rows to update in 'column=value' format. Comma-separated for multiple. REQUIRED to prevent accidental mass updates.",
                },
            },
            "required": ["table", "data", "filters"],
        },
    },
    {
        "name": "supabase_delete",
        "description": "Delete rows from a Supabase table matching a filter.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
                },
                "filters": {
                    "type": "string",
                    "description": "Filter for which rows to delete in 'column=value' format. Comma-separated for multiple. REQUIRED to prevent accidental mass deletes.",
                },
            },
            "required": ["table", "filters"],
        },
    },
    {
        "name": "supabase_upsert",
        "description": "Insert or update rows in a Supabase table (upsert). If a row with the same primary key exists, it is updated; otherwise, it is inserted.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
                },
                "data": {
                    "type": "string",
                    "description": "JSON string of the row(s) to upsert. Must include the primary key column. Single object or array.",
                },
            },
            "required": ["table", "data"],
        },
    },
    {
        "name": "supabase_count",
        "description": "Count rows in a Supabase table, optionally with filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name",
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
        "name": "supabase_list_tables",
        "description": "List all tables in the Supabase database with their column names and types.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "supabase_rpc",
        "description": "Call a Supabase RPC (remote procedure call) function / Edge Function.",
        "parameters": {
            "type": "object",
            "properties": {
                "function_name": {
                    "type": "string",
                    "description": "Name of the database function to call",
                },
                "params": {
                    "type": "string",
                    "description": "JSON string of parameters to pass to the function. E.g., '{\"user_id\": 123}'",
                },
            },
            "required": ["function_name"],
        },
    },
    {
        "name": "supabase_search",
        "description": "Full-text search on a Supabase table column using PostgreSQL text search.",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name to search",
                },
                "column": {
                    "type": "string",
                    "description": "Column to search in",
                },
                "query": {
                    "type": "string",
                    "description": "Search query text",
                },
                "select": {
                    "type": "string",
                    "description": "Columns to return (default: '*')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default: 10)",
                },
            },
            "required": ["table", "column", "query"],
        },
    },
    {
        "name": "supabase_storage_list",
        "description": "List files in a Supabase Storage bucket.",
        "parameters": {
            "type": "object",
            "properties": {
                "bucket": {
                    "type": "string",
                    "description": "Storage bucket name",
                },
                "path": {
                    "type": "string",
                    "description": "Folder path within the bucket (default: root)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max files to return (default: 20)",
                },
            },
            "required": ["bucket"],
        },
    },
]


# ─── Helpers ───────────────────────────────────────────────────────

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
        raise ImportError("supabase-py not installed. Run: uv pip install -r requirements.txt")

    url_key, key_key = _resolve_env_keys(account_id)
    url = os.environ.get(url_key)
    key = os.environ.get(key_key)
    if not url or not key:
        raise ValueError(f"{url_key} and {key_key} must be set in .env")
    return create_client(url, key)


def _apply_filters(q, filters):
    """Apply comma-separated 'column=value' filters to a query."""
    if not filters:
        return q
    for f in filters.split(","):
        f = f.strip()
        if "=" in f:
            col, val = f.split("=", 1)
            q = q.eq(col.strip(), val.strip())
    return q


# ─── Handler Functions ─────────────────────────────────────────────

def _query(table: str, select: str = "*", limit: int = 20, filters: str = None, order_by: str = None, account_id=None) -> str:
    client = _get_client(account_id)
    q = client.table(table).select(select).limit(limit)
    q = _apply_filters(q, filters)
    if order_by:
        desc = order_by.startswith("-")
        col = order_by.lstrip("-")
        q = q.order(col, desc=desc)
    result = q.execute()
    return json.dumps(result.data, indent=2, default=str)


def _insert(table: str, data: str, account_id=None) -> str:
    client = _get_client(account_id)
    try:
        row = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, TypeError) as e:
        return f"Invalid JSON data: {e}. Pass a valid JSON object like '{{\"name\": \"John\"}}'"
    result = client.table(table).insert(row).execute()
    count = len(result.data) if isinstance(result.data, list) else 1
    return f"Inserted {count} row(s) into '{table}'."


def _update(table: str, data: str, filters: str, account_id=None) -> str:
    client = _get_client(account_id)
    try:
        updates = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, TypeError) as e:
        return f"Invalid JSON data: {e}."
    q = client.table(table).update(updates)
    q = _apply_filters(q, filters)
    result = q.execute()
    count = len(result.data) if isinstance(result.data, list) else 0
    return f"Updated {count} row(s) in '{table}'."


def _delete(table: str, filters: str, account_id=None) -> str:
    client = _get_client(account_id)
    q = client.table(table).delete()
    q = _apply_filters(q, filters)
    result = q.execute()
    count = len(result.data) if isinstance(result.data, list) else 0
    return f"Deleted {count} row(s) from '{table}'."


def _upsert(table: str, data: str, account_id=None) -> str:
    client = _get_client(account_id)
    try:
        row = json.loads(data) if isinstance(data, str) else data
    except (json.JSONDecodeError, TypeError) as e:
        return f"Invalid JSON data: {e}."
    result = client.table(table).upsert(row).execute()
    count = len(result.data) if isinstance(result.data, list) else 1
    return f"Upserted {count} row(s) in '{table}'."


def _count(table: str, filters: str = None, account_id=None) -> str:
    client = _get_client(account_id)
    q = client.table(table).select("*", count="exact")
    q = _apply_filters(q, filters)
    result = q.execute()
    return f"Table '{table}' has {result.count} row(s)" + (f" matching filters: {filters}" if filters else "") + "."


def _list_tables(account_id=None) -> str:
    import requests
    url_key, key_key = _resolve_env_keys(account_id)
    url = os.environ.get(url_key)
    key = os.environ.get(key_key)
    if not url or not key:
        raise ValueError(f"{url_key} and {key_key} must be set in .env")

    # Use PostgREST's OpenAPI endpoint to discover tables
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    resp = requests.get(f"{url}/rest/v1/", headers=headers)
    if resp.status_code != 200:
        return f"Error listing tables: {resp.status_code} — {resp.text}"

    schema = resp.json()
    tables = []
    definitions = schema.get("definitions", {})
    for table_name, table_def in sorted(definitions.items()):
        cols = []
        for col_name, col_info in table_def.get("properties", {}).items():
            col_type = col_info.get("format") or col_info.get("type", "unknown")
            cols.append(f"{col_name} ({col_type})")
        tables.append({"table": table_name, "columns": cols})

    return json.dumps(tables, indent=2)


def _rpc(function_name: str, params: str = None, account_id=None) -> str:
    client = _get_client(account_id)
    try:
        p = json.loads(params) if params else {}
    except (json.JSONDecodeError, TypeError):
        p = {}
    result = client.rpc(function_name, p).execute()
    return json.dumps(result.data, indent=2, default=str)


def _search(table: str, column: str, query: str, select: str = "*", limit: int = 10, account_id=None) -> str:
    client = _get_client(account_id)
    result = client.table(table).select(select).text_search(column, query).limit(limit).execute()
    return json.dumps(result.data, indent=2, default=str)


def _storage_list(bucket: str, path: str = "", limit: int = 20, account_id=None) -> str:
    client = _get_client(account_id)
    result = client.storage.from_(bucket).list(path=path, options={"limit": limit})
    files = []
    for item in result:
        files.append({
            "name": item.get("name"),
            "id": item.get("id"),
            "size": item.get("metadata", {}).get("size"),
            "type": item.get("metadata", {}).get("mimetype"),
            "created_at": item.get("created_at"),
        })
    return json.dumps(files, indent=2, default=str)


# ─── Router ────────────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "supabase_query":
            return _query(
                args["table"],
                args.get("select", "*"),
                args.get("limit", 20),
                args.get("filters"),
                args.get("order_by"),
                account_id=account_id,
            )
        elif tool_name == "supabase_insert":
            return _insert(args["table"], args["data"], account_id=account_id)
        elif tool_name == "supabase_update":
            return _update(args["table"], args["data"], args["filters"], account_id=account_id)
        elif tool_name == "supabase_delete":
            return _delete(args["table"], args["filters"], account_id=account_id)
        elif tool_name == "supabase_upsert":
            return _upsert(args["table"], args["data"], account_id=account_id)
        elif tool_name == "supabase_count":
            return _count(args["table"], args.get("filters"), account_id=account_id)
        elif tool_name == "supabase_list_tables":
            return _list_tables(account_id=account_id)
        elif tool_name == "supabase_rpc":
            return _rpc(args["function_name"], args.get("params"), account_id=account_id)
        elif tool_name == "supabase_search":
            return _search(
                args["table"], args["column"], args["query"],
                args.get("select", "*"), args.get("limit", 10),
                account_id=account_id,
            )
        elif tool_name == "supabase_storage_list":
            return _storage_list(args["bucket"], args.get("path", ""), args.get("limit", 20), account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Supabase error: {e}"
