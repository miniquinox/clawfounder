"""
gemini_provider.py — Google Gemini function-calling wrapper.
Uses the modern google-genai SDK.
"""

import os
import json
from google import genai
from google.genai import types

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _convert_tools(tools: list) -> types.Tool | None:
    """Convert connector tool definitions to Gemini FunctionDeclarations."""
    if not tools:
        return None
    declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool.get("parameters", {}),
        )
        for tool in tools
    ]
    return types.Tool(function_declarations=declarations)


def chat(prompt: str, tools: list, route_fn) -> str:
    """
    Send a prompt to Gemini with tool definitions.
    Handles the tool-call loop automatically.

    Args:
        prompt: The user's natural language question
        tools: List of tool definitions from all connectors
        route_fn: Function(tool_name, args) -> str that executes tool calls

    Returns:
        The final text response from Gemini.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_CLOUD_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not set. Add it to your .env file."

    # AI Studio keys start with "AIza", everything else is a GCP key needing Vertex AI
    if api_key.startswith("AIza"):
        client = genai.Client(api_key=api_key)
    else:
        client = genai.Client(vertexai=True)
    gemini_tools = _convert_tools(tools)

    system = (
        "You are ClawFounder, an AI assistant with access to various tools and services. "
        "Use the available tools to help answer the user's questions. "
        "When you need information from a service, call the appropriate tool. "
        "Be concise and helpful."
    )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

    config = types.GenerateContentConfig(
        tools=[gemini_tools] if gemini_tools else [],
        system_instruction=system,
        temperature=1,
        max_output_tokens=8192,
    )

    max_iterations = 10
    for _ in range(max_iterations):
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents, config=config,
        )

        if not response.candidates or not response.candidates[0].content:
            return "No response from Gemini."

        # Check for function calls
        function_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'thought') and part.thought:
                continue
            if part.function_call:
                function_calls.append(part.function_call)

        if not function_calls:
            # Final text answer
            text_parts = [
                p.text for p in response.candidates[0].content.parts
                if p.text and not (hasattr(p, 'thought') and p.thought)
            ]
            return "\n".join(text_parts) if text_parts else "No response from Gemini."

        # Execute tool calls
        function_response_parts = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            print(f"  Calling: {fc.name}({json.dumps(args)})")
            result = route_fn(fc.name, args)
            print(f"  Result: {result[:200]}{'...' if len(result) > 200 else ''}")
            function_response_parts.append(
                types.Part(function_response=types.FunctionResponse(
                    name=fc.name,
                    response={"result": result},
                ))
            )

        contents.append(response.candidates[0].content)
        contents.append(types.Content(role="user", parts=function_response_parts))

    return "Max tool-call iterations reached."
