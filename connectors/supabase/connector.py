"""
Supabase connector — Query tables, insert data, and run SQL.
"""

import os
import json

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
        "description": "Run a read-only SQL query on Supabase. Only SELECT statements are allowed.",
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


def _get_client():
    try:
        from supabase import create_client
    except ImportError:
        raise ImportError("supabase-py not installed. Run: bash connectors/supabase/install.sh")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def _query(table: str, select: str = "*", limit: int = 20, filters: str = None) -> str:
    client = _get_client()
    q = client.table(table).select(select).limit(limit)

    if filters:
        for f in filters.split(","):
            f = f.strip()
            if "=" in f:
                col, val = f.split("=", 1)
                q = q.eq(col.strip(), val.strip())

    result = q.execute()
    return json.dumps(result.data, indent=2, default=str)


def _insert(table: str, data: str) -> str:
    client = _get_client()
    row = json.loads(data)
    result = client.table(table).insert(row).execute()
    return f"Inserted {len(result.data)} row(s) into '{table}'"


def _sql(query: str) -> str:
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for safety."
    client = _get_client()
    result = client.rpc("", {}).execute()  # Fallback — see note below
    # Note: Direct SQL requires the pg_net extension or a custom RPC function.
    # For basic usage, use supabase_query instead.
    return "SQL execution requires a custom Supabase RPC function. Use supabase_query for basic queries."


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "supabase_query":
            return _query(
                args["table"],
                args.get("select", "*"),
                args.get("limit", 20),
                args.get("filters"),
            )
        elif tool_name == "supabase_insert":
            return _insert(args["table"], args["data"])
        elif tool_name == "supabase_sql":
            return _sql(args["query"])
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Supabase error: {e}"
