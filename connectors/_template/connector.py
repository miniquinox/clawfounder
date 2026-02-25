"""
Template connector — copy this and fill it in.

Every connector must export:
  TOOLS  — a list of tool definitions (name, description, parameters)
  handle — a function that executes tool calls
"""

import os

# ─── Tool Definitions ──────────────────────────────────────────────
# These tell the AI what your connector can do.
# The AI reads the descriptions to decide when to use each tool.

TOOLS = [
    {
        "name": "your_service_example_action",
        "description": "Describe what this tool does. Be specific — the AI uses this to decide when to call it.",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "What this parameter is for",
                },
            },
            "required": [],  # List required param names here
        },
    },
]


# ─── Handler ────────────────────────────────────────────────────────
# This function gets called when the AI decides to use one of your tools.

def handle(tool_name: str, args: dict) -> str:
    """
    Execute a tool call. Must return a string.

    Args:
        tool_name: Which tool the AI wants to call (matches a "name" in TOOLS)
        args: The arguments the AI provided (matches "parameters" in TOOLS)

    Returns:
        A string result. The AI will read this and incorporate it into its response.
    """
    if tool_name == "your_service_example_action":
        # TODO: Implement your logic here
        param1 = args.get("param1", "default")
        return f"Example result for param1={param1}"

    return f"Unknown tool: {tool_name}"
