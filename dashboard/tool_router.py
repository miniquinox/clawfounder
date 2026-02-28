"""
ClawFounder — Smart Tool Router

Uses a fast LLM to dynamically select which tools are relevant to the user's
message. Fully dynamic — reads tool names and descriptions from connectors,
no hardcoded keywords.

Router model: gemini-2.0-flash-lite (cheapest/fastest)
Fallback: lightweight heuristic if the router call fails
"""

import os
import json
import sys
import hashlib
from pathlib import Path

# Max tools to send to the main model
MAX_TOOLS = 25

# Models to try for routing (in order of preference — cheapest first)
ROUTER_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

ROUTER_PROMPT = """You are a tool router. Given the user's message, select which tools are relevant.

Available tools:
{manifest}

User message: "{message}"

Return ONLY a JSON array of tool name strings. Rules:
- Include only tools needed to fulfill the request
- For read queries, include read tools only
- For action queries (send, create, delete), include the action tool + its read counterpart for context
- When the intent is unclear, include broadly relevant read-only tools
- Max {max_tools} tools
- Return valid JSON array, nothing else"""


def _log(msg):
    print(f"[router] {msg}", file=sys.stderr, flush=True)


def _build_manifest(connectors):
    """Auto-generate tool manifest from loaded connectors. Fully dynamic."""
    lines = []
    for conn_name, info in sorted(connectors.items()):
        module = info["module"]
        for tool in module.TOOLS:
            desc = tool.get("description", "")[:100]
            lines.append(f"- {tool['name']}: {desc}")
    return "\n".join(lines)


def _call_router(message, manifest):
    """Call a fast LLM to pick relevant tools. Returns list of tool names or None on failure."""
    try:
        from google.genai import types
        from agent_shared import get_gemini_client
    except ImportError:
        return None

    try:
        client = get_gemini_client()
    except RuntimeError:
        return None

    prompt = ROUTER_PROMPT.format(
        manifest=manifest,
        message=message,
        max_tools=MAX_TOOLS,
    )

    for model in ROUTER_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=512,
                ),
            )

            text = resp.text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            tools = json.loads(text)
            if isinstance(tools, list) and all(isinstance(t, str) for t in tools):
                _log(f"Routed ({model}): {len(tools)} tools")
                return tools

        except Exception as e:
            _log(f"{model} failed: {str(e)[:80]}")
            continue

    return None


def _fallback(connectors):
    """Safe heuristic fallback — core read-only tools from each connector.
    Used when the LLM router fails (rate limit, timeout, etc.)."""
    allowed = set()
    for conn_name, info in connectors.items():
        module = info["module"]
        tools = module.TOOLS
        # Small connectors (≤12 tools): include everything
        if len(tools) <= 12:
            for t in tools:
                allowed.add(t["name"])
        else:
            # Large connectors: only the most essential tools (max 5 per connector)
            # Prioritize: notifications, search, list (broad overview tools)
            core_suffixes = ("notifications", "search", "get_me")
            list_suffixes = ("list_repos", "list_prs", "list_issues",
                             "get_updates", "query", "list_tables")
            for t in tools:
                name = t["name"]
                suffix = name.split(conn_name + "_", 1)[-1] if conn_name + "_" in name else name
                if suffix in core_suffixes or suffix in list_suffixes:
                    allowed.add(name)

    # Hard cap — if still too many, keep small connector tools + trim large ones
    if len(allowed) > MAX_TOOLS:
        _log(f"Fallback over cap ({len(allowed)}), trimming")
        small_tools = set()
        large_tools = set()
        for conn_name, info in connectors.items():
            tools_in = {t["name"] for t in info["module"].TOOLS if t["name"] in allowed}
            if len(info["module"].TOOLS) <= 12:
                small_tools.update(tools_in)
            else:
                large_tools.update(tools_in)
        # Keep all small connector tools, trim large connector tools
        allowed = small_tools
        for t in sorted(large_tools):
            if len(allowed) >= MAX_TOOLS:
                break
            allowed.add(t)

    _log(f"Fallback: {len(allowed)} tools")
    return allowed


def route(message, connectors):
    """Route a user message to the relevant tools.

    Returns a set of tool name strings. The caller should filter
    build_tools_and_map() to only include these tools.
    Returns None if all tools should be included (small connector set).
    """
    # Skip routing for short confirmation messages (saves 300-800ms)
    stripped = message.strip().lower()
    if len(stripped) < 20 or stripped in (
        "yes", "yep", "yeah", "no", "nope", "send it", "go", "do it",
        "confirm", "ok", "okay", "sure", "cancel", "stop", "thanks",
        "thank you", "go ahead", "sounds good", "send", "yes please",
    ):
        return None  # Let all tools through for quick follow-ups

    # Not worth routing for small connector sets
    total_tools = sum(len(info["module"].TOOLS) for info in connectors.values())
    if total_tools <= MAX_TOOLS:
        return None  # All tools are fine

    # Check cache first
    import tool_cache
    cache_key = hashlib.md5(message.lower().strip().encode()).hexdigest()[:12]
    cached = tool_cache.get("_router", {"q": cache_key}, connector="_router")
    if cached:
        try:
            tools = json.loads(cached)
            if isinstance(tools, list):
                _log(f"Cache hit: {len(tools)} tools")
                return set(tools)
        except (json.JSONDecodeError, TypeError):
            pass

    # Build manifest and call router
    manifest = _build_manifest(connectors)
    result = _call_router(message, manifest)

    if result:
        # Cache the routing result
        tool_cache.put("_router", {"q": cache_key}, json.dumps(result))
        return set(result)

    # Fallback if LLM router fails
    return _fallback(connectors)
