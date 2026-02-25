"""
runner.py — ClawFounder CLI agent.

Usage:
    python -m agent.runner --provider gemini
    python -m agent.runner --provider openai
    python -m agent.runner --provider claude
    python -m agent.runner --dry-run          # Just list discovered tools
"""

import argparse
import sys
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")
except ImportError:
    project_root = Path(__file__).parent.parent
    # python-dotenv not installed — .env will not be loaded automatically
    # Install with: pip install python-dotenv

from agent.connector_loader import load_connectors, get_all_tools
from agent.tool_router import build_tool_map, route_tool_call


PROVIDERS = {
    "gemini": "agent.providers.gemini_provider",
    "openai": "agent.providers.openai_provider",
    "claude": "agent.providers.claude_provider",
}

BANNER = """
🦀 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   C L A W F O U N D E R
   Your AI agent that actually does things.
🦀 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def main():
    parser = argparse.ArgumentParser(description="ClawFounder — AI Agent Runner")
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "claude"],
        default="gemini",
        help="LLM provider to use (default: gemini)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just discover and list tools — don't start the chat",
    )
    parser.add_argument(
        "--connectors-dir",
        default=None,
        help="Path to connectors directory (default: ./connectors/)",
    )
    args = parser.parse_args()

    print(BANNER)

    # Load connectors
    connectors_dir = args.connectors_dir or str(project_root / "connectors")
    print("📦 Loading connectors...\n")
    connectors = load_connectors(connectors_dir)

    if not connectors:
        print("\n⚠️  No connectors found. Install some connectors first!")
        print("   See: connectors/_template/ for how to create one.")
        sys.exit(1)

    all_tools = get_all_tools(connectors)
    tool_map = build_tool_map(connectors)

    print(f"\n🔧 {len(all_tools)} tool(s) ready from {len(connectors)} connector(s):")
    for tool in all_tools:
        print(f"   • {tool['name']} — {tool['description']}")
    print()

    if args.dry_run:
        print("✅ Dry run complete. Tools discovered successfully.")
        return

    # Import the selected provider
    print(f"🤖 Using provider: {args.provider}\n")
    import importlib
    provider = importlib.import_module(PROVIDERS[args.provider])

    # Route function for the provider
    def route_fn(tool_name, tool_args):
        return route_tool_call(tool_map, tool_name, tool_args)

    # Interactive chat loop
    print("Type your question (or 'quit' to exit):\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Bye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("\n👋 Bye!")
            break

        print()
        try:
            response = provider.chat(user_input, all_tools, route_fn)
            print(f"\n🦀 ClawFounder: {response}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
