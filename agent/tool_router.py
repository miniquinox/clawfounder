"""
tool_router.py — Routes tool calls from the LLM to the right connector.
"""


def build_tool_map(connectors: dict) -> dict:
    """
    Build a mapping from tool_name → (connector_name, handle_function).

    Args:
        connectors: The dict returned by connector_loader.load_connectors()

    Returns:
        {
            "gmail_get_unread": ("gmail", <handle_fn>),
            "telegram_send_message": ("telegram", <handle_fn>),
            ...
        }
    """
    tool_map = {}
    for connector_name, connector in connectors.items():
        for tool in connector["tools"]:
            tool_name = tool["name"]
            if tool_name in tool_map:
                existing = tool_map[tool_name][0]
                print(f"⚠️  Tool name conflict: '{tool_name}' in both "
                      f"'{existing}' and '{connector_name}'. Using '{connector_name}'.")
            tool_map[tool_name] = (connector_name, connector["handle"])
    return tool_map


def route_tool_call(tool_map: dict, tool_name: str, args: dict) -> str:
    """
    Execute a tool call by routing to the correct connector.

    Args:
        tool_map: The dict returned by build_tool_map()
        tool_name: The name of the tool to call
        args: The arguments to pass to the tool

    Returns:
        The string result from the connector's handle() function.
    """
    if tool_name not in tool_map:
        return f"Error: Unknown tool '{tool_name}'. Available tools: {list(tool_map.keys())}"

    connector_name, handle_fn = tool_map[tool_name]
    try:
        result = handle_fn(tool_name, args)
        if not isinstance(result, str):
            result = str(result)
        return result
    except Exception as e:
        return f"Error calling {tool_name} (connector: {connector_name}): {e}"
