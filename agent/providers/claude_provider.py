"""
claude_provider.py — Anthropic Claude tool-use wrapper.
"""

import os
import json
import anthropic


def _convert_tools_to_claude_format(tools: list) -> list:
    """Convert our connector tool definitions to Claude's tool format."""
    claude_tools = []
    for tool in tools:
        claude_tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        })
    return claude_tools


def chat(prompt: str, tools: list, route_fn) -> str:
    """
    Send a prompt to Claude with tool definitions.
    Handles the tool-use loop automatically.

    Args:
        prompt: The user's natural language question
        tools: List of tool definitions from all connectors
        route_fn: Function(tool_name, args) -> str that executes tool calls

    Returns:
        The final text response from Claude.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not set. Add it to your .env file."

    client = anthropic.Anthropic(api_key=api_key)
    claude_tools = _convert_tools_to_claude_format(tools)

    messages = [{"role": "user", "content": prompt}]
    system = (
        "You are ClawFounder, an AI assistant with access to various tools and services. "
        "Use the available tools to help answer the user's questions. "
        "When you need information from a service, call the appropriate tool. "
        "Be concise and helpful."
    )

    max_iterations = 10
    for _ in range(max_iterations):
        kwargs = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if claude_tools:
            kwargs["tools"] = claude_tools

        response = client.messages.create(**kwargs)

        # Check if we need to handle tool use
        if response.stop_reason != "tool_use":
            # Extract text from the response
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts) if text_parts else "No response from Claude."

        # Add assistant response to messages
        messages.append({"role": "assistant", "content": response.content})

        # Execute tool calls and build results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                fn_name = block.name
                args = block.input if isinstance(block.input, dict) else {}

                print(f"  🔧 Calling: {fn_name}({json.dumps(args)})")
                result = route_fn(fn_name, args)
                print(f"  📤 Result: {result[:200]}{'...' if len(result) > 200 else ''}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})

    return "Max tool-call iterations reached."
