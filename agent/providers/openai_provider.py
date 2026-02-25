"""
openai_provider.py — OpenAI function-calling wrapper.
"""

import os
import json
from openai import OpenAI


def _convert_tools_to_openai_format(tools: list) -> list:
    """Convert our connector tool definitions to OpenAI's function format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            }
        })
    return openai_tools


def chat(prompt: str, tools: list, route_fn) -> str:
    """
    Send a prompt to OpenAI with tool definitions.
    Handles the tool-call loop automatically.

    Args:
        prompt: The user's natural language question
        tools: List of tool definitions from all connectors
        route_fn: Function(tool_name, args) -> str that executes tool calls

    Returns:
        The final text response from OpenAI.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY not set. Add it to your .env file."

    client = OpenAI(api_key=api_key)
    openai_tools = _convert_tools_to_openai_format(tools)

    messages = [
        {
            "role": "system",
            "content": (
                "You are ClawFounder, an AI assistant with access to various tools and services. "
                "Use the available tools to help answer the user's questions. "
                "When you need information from a service, call the appropriate tool. "
                "Be concise and helpful."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    max_iterations = 10
    for _ in range(max_iterations):
        kwargs = {"model": "gpt-4o", "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        if not message.tool_calls:
            # No tool calls — we have our final answer
            return message.content or "No response from OpenAI."

        # Add the assistant message with tool calls
        messages.append(message)

        # Execute each tool call and send results back
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            print(f"  🔧 Calling: {fn_name}({json.dumps(args)})")
            result = route_fn(fn_name, args)
            print(f"  📤 Result: {result[:200]}{'...' if len(result) > 200 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "Max tool-call iterations reached."
