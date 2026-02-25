"""
gemini_provider.py — Google Gemini function-calling wrapper.
"""

import os
import json
import google.generativeai as genai


def _convert_tools_to_gemini_format(tools: list) -> list:
    """Convert our connector tool definitions to Gemini's function declaration format."""
    declarations = []
    for tool in tools:
        declarations.append(
            genai.protos.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool.get("parameters", {"type": "object", "properties": {}}),
            )
        )
    return declarations


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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not set. Add it to your .env file."

    genai.configure(api_key=api_key)

    # Convert tools to Gemini format
    function_declarations = _convert_tools_to_gemini_format(tools)
    gemini_tools = [genai.protos.Tool(function_declarations=function_declarations)] if function_declarations else []

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=gemini_tools,
        system_instruction=(
            "You are ClawFounder, an AI assistant with access to various tools and services. "
            "Use the available tools to help answer the user's questions. "
            "When you need information from a service, call the appropriate tool. "
            "Be concise and helpful."
        ),
    )

    chat_session = model.start_chat()
    response = chat_session.send_message(prompt)

    # Tool-call loop: keep going until we get a text response
    max_iterations = 10
    for _ in range(max_iterations):
        # Check if the response has function calls
        function_calls = []
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                function_calls.append(part.function_call)

        if not function_calls:
            # No tool calls — we have our final answer
            break

        # Execute each tool call and send results back
        tool_responses = []
        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            print(f"  🔧 Calling: {fc.name}({json.dumps(args)})")
            result = route_fn(fc.name, args)
            print(f"  📤 Result: {result[:200]}{'...' if len(result) > 200 else ''}")
            tool_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        response = chat_session.send_message(tool_responses)

    # Extract final text
    text_parts = [part.text for part in response.parts if hasattr(part, "text") and part.text]
    return "\n".join(text_parts) if text_parts else "No response from Gemini."
