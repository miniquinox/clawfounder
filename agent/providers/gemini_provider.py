"""
gemini_provider.py — Google Gemini function-calling wrapper.

Uses the google-genai SDK with gemini-3-flash-preview + thinking.
"""

import os
import json

GEMINI_MODEL = "gemini-3-flash-preview"


def _build_tool_schema(tools: list):
    """Convert connector tool definitions to Gemini FunctionDeclaration format."""
    from google.genai import types

    declarations = []
    for tool in tools:
        declarations.append(types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool.get("parameters", {"type": "object", "properties": {}}),
        ))
    return types.Tool(function_declarations=declarations) if declarations else None


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
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_CLOUD_API_KEY", "")
    if not api_key:
        return "Error: GEMINI_API_KEY not set. Add it to your .env file."

    client = genai.Client(api_key=api_key)

    # Build tool schema
    gemini_tool = _build_tool_schema(tools)

    system_instruction = (
        "You are ClawFounder, an AI assistant with access to various tools and services. "
        "Use the available tools to help answer the user's questions. "
        "When you need information from a service, call the appropriate tool. "
        "Be concise and helpful."
    )

    # Build initial contents
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )
    ]

    # Generation config with thinking
    config = types.GenerateContentConfig(
        tools=[gemini_tool] if gemini_tool else [],
        system_instruction=system_instruction,
        temperature=1,
        top_p=0.95,
        max_output_tokens=65535,
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
    )

    # Agentic loop
    max_turns = 10
    for turn in range(max_turns):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
        except Exception as e:
            return f"Gemini API error: {e}"

        if not response.candidates or not response.candidates[0].content:
            break

        # Process parts
        has_function_calls = False
        function_response_parts = []
        text_parts = []

        for part in response.candidates[0].content.parts:
            # Skip thinking parts
            if hasattr(part, 'thought') and part.thought:
                continue

            if part.function_call:
                has_function_calls = True
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                print(f"  🔧 Calling: {fc.name}({json.dumps(args, default=str)})")
                result = route_fn(fc.name, args)
                print(f"  📤 Result: {result[:200]}{'...' if len(result) > 200 else ''}")

                function_response_parts.append(
                    types.Part(function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    ))
                )

            elif part.text:
                text_parts.append(part.text)

        if not has_function_calls:
            return "\n".join(text_parts) if text_parts else "No response from Gemini."

        # Add model response and tool results to conversation
        contents.append(response.candidates[0].content)
        contents.append(types.Content(
            role="user",
            parts=function_response_parts,
        ))

    # Extract any remaining text
    return "\n".join(text_parts) if text_parts else "No response from Gemini."
