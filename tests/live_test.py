"""
ClawFounder — Live Agentic Tests

Runs a real agentic loop for each connector:
1. Sends a test prompt to Gemini
2. The agent calls tools, reasons about results, loops as needed
3. After getting a final answer, a judge LLM evaluates PASS or FAIL

Usage:
  python3 tests/live_test.py                    # Test all connected connectors
  python3 tests/live_test.py gmail              # Test a specific connector
  python3 tests/live_test.py --list             # Show available tests
"""

import sys
import os
import json
import importlib.util
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── Test definitions ─────────────────────────────────────────────

TESTS = {
    "gmail": {
        "prompt": "Check my Gmail. Do I have any unread emails? If so, tell me the subject and sender of the most recent one. If not, search for the most recent email in my inbox and tell me about it.",
        "goal": "The agent successfully connected to Gmail and retrieved real email information (subject line, sender name/address). Any actual email data counts as a pass.",
        "required_env": ["GMAIL_CREDENTIALS_FILE"],
    },
    "telegram": {
        "prompt": "Check my Telegram bot for recent messages. Who sent the most recent message and what did they say? If there are no messages, just confirm you were able to connect to the Telegram API successfully.",
        "goal": "The agent successfully connected to the Telegram API and either retrieved messages or confirmed API connectivity. Any response showing real API interaction (not an authentication error) counts as a pass.",
        "required_env": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    },
    "github": {
        "prompt": "List my GitHub repositories. Which one was most recently updated? What language is it written in?",
        "goal": "The agent listed real GitHub repositories with actual repo names and details like language or last update time. Any real repo data counts as a pass.",
        "required_env": ["GITHUB_TOKEN"],
    },
    "supabase": {
        "prompt": "Connect to my Supabase database and list all tables. Pick the first table you find and tell me how many rows it has. If you can't count rows, just describe what columns it has.",
        "goal": "The agent connected to Supabase and retrieved real database information — table names, column info, or row data. Any actual database content counts as a pass.",
        "required_env": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"],
    },
    "firebase": {
        "prompt": "Connect to my Firebase Firestore database. List the collections. Pick the first collection and tell me about the documents in it — how many are there and what fields do they have?",
        "goal": "The agent connected to Firestore and retrieved real data — collection names, document fields, or document counts. Any actual Firestore content counts as a pass.",
        "required_env": ["FIREBASE_PROJECT_ID"],
    },
    "yahoo_finance": {
        "prompt": "What's the current stock price of Apple (AAPL)? Is it up or down today? Also check Tesla (TSLA) and tell me which one is performing better today.",
        "goal": "The agent retrieved real stock prices for AAPL and TSLA with actual dollar amounts and percentage changes. Any real financial data counts as a pass.",
        "required_env": [],
    },
}


# ── Connector loading ────────────────────────────────────────────

def _load_connector(name):
    """Dynamically load a connector module."""
    connector_dir = PROJECT_ROOT / "connectors" / name
    spec = importlib.util.spec_from_file_location(
        f"connectors.{name}.connector",
        connector_dir / "connector.py",
        submodule_search_locations=[str(connector_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Build Gemini tool schema ─────────────────────────────────────

def _build_tool_schema(tools):
    """Convert connector TOOLS list to the Gemini genai function schema."""
    from google.genai import types

    declarations = []
    for tool in tools:
        params = tool.get("parameters", {})
        declarations.append(types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=params,
        ))
    return types.Tool(function_declarations=declarations)


# ── Agentic Loop ─────────────────────────────────────────────────

def run_agentic_test(connector_name, test_config, verbose=True):
    """
    Run a full agentic loop:
    1. Send prompt + connector tools to Gemini
    2. Handle tool calls in a loop (up to 10 turns)
    3. Get final text response
    4. Ask a judge LLM to evaluate PASS/FAIL
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")

    # Check required env vars
    for var in test_config["required_env"]:
        val = os.environ.get(var)
        if not val:
            # Firebase: check alternative auth
            if connector_name == "firebase" and var in ("FIREBASE_CREDENTIALS_FILE",):
                if os.environ.get("FIREBASE_REFRESH_TOKEN"):
                    continue
                config_path = os.path.join(os.path.expanduser("~"), ".config", "configstore", "firebase-tools.json")
                if os.path.exists(config_path):
                    continue
            return {"status": "skip", "reason": f"{var} not set"}

    # Load connector
    try:
        module = _load_connector(connector_name)
    except Exception as e:
        return {"status": "fail", "reason": f"Failed to load connector: {e}"}

    tools = module.TOOLS
    handle_fn = module.handle

    # Set up Gemini client — try multiple auth methods
    client = None
    model_id = "gemini-2.0-flash"

    # Method 1: Standard API key (AIza...)
    if api_key and api_key.startswith("AIza"):
        client = genai.Client(api_key=api_key)
        if verbose:
            print("  🔑 Auth: API key")

    # Method 2: Vertex AI with ADC (gcloud auth application-default login)
    if not client:
        # Detect GCP project from gcloud config or env
        gcp_project = None
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                gcp_project = result.stdout.strip()
        except Exception:
            pass

        if not gcp_project:
            for env_var in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
                val = os.environ.get(env_var, "")
                if val and not val.startswith("#"):
                    gcp_project = val
                    break

        if gcp_project:
            try:
                client = genai.Client(
                    vertexai=True,
                    project=gcp_project,
                    location="us-central1",
                )
                if verbose:
                    print(f"  🔑 Auth: Vertex AI ({gcp_project})")
            except Exception:
                pass

    if not client:
        return {"status": "skip", "reason": "No Gemini auth available. Set GEMINI_API_KEY (AIza...) or run 'gcloud auth application-default login'"}

    gemini_tool = _build_tool_schema(tools)

    if verbose:
        print(f"\n  💬 Prompt: {test_config['prompt'][:80]}...")

    # Build initial contents
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=test_config["prompt"])],
        )
    ]

    system_instruction = (
        "You are a helpful assistant testing a connector. "
        "Use the available tools to answer the user's question. "
        "Be thorough — if a tool returns an error, try a different approach. "
        "When you have enough information, give a clear final answer."
    )

    max_turns = 10
    turn = 0
    all_tool_calls = []
    final_text = ""

    while turn < max_turns:
        turn += 1

        try:
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[gemini_tool],
                    system_instruction=system_instruction,
                ),
            )
        except Exception as e:
            err = str(e)
            if "invalid_grant" in err or "UNAUTHENTICATED" in err:
                return {"status": "fail", "reason": f"Auth expired. Run: gcloud auth application-default login\n  ({err[:80]}...)"}
            return {"status": "fail", "reason": f"Gemini API error: {err[:120]}"}

        # Check for function calls
        has_function_calls = False
        function_response_parts = []
        text_parts = []

        if not response.candidates or not response.candidates[0].content:
            break

        for part in response.candidates[0].content.parts:
            if part.function_call:
                has_function_calls = True
                fc = part.function_call
                tool_name = fc.name
                args = dict(fc.args) if fc.args else {}

                if verbose:
                    args_str = json.dumps(args, default=str)
                    print(f"  🔧 Turn {turn}: {tool_name}({args_str[:60]})")

                # Execute the tool
                try:
                    result = handle_fn(tool_name, args)
                except Exception as e:
                    result = f"Tool error: {e}"

                all_tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result[:300] if isinstance(result, str) else str(result)[:300],
                })

                function_response_parts.append(
                    types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    ))
                )

            elif part.text:
                text_parts.append(part.text)

        if not has_function_calls:
            final_text = " ".join(text_parts)
            break

        # Add the model response and function results to history
        contents.append(response.candidates[0].content)
        contents.append(types.Content(
            role="user",
            parts=function_response_parts,
        ))

    if not final_text and text_parts:
        final_text = " ".join(text_parts)

    if verbose:
        print(f"  📝 Response: {final_text[:150]}...")
        print(f"  🔄 Turns: {turn}, Tool calls: {len(all_tool_calls)}")

    if not final_text.strip():
        return {
            "status": "fail",
            "reason": "Agent produced no final text response",
            "turns": turn,
            "tool_calls": len(all_tool_calls),
        }

    # ── Judge evaluation ─────────────────────────────────────────
    judge_prompt = f"""You are a test evaluator. Determine if this agentic test PASSED or FAILED.

TEST GOAL: {test_config['goal']}

AGENT'S FINAL RESPONSE:
{final_text}

TOOL CALLS MADE ({len(all_tool_calls)} total):
{json.dumps(all_tool_calls, indent=2, default=str)[:2000]}

RULES:
- PASS if the agent retrieved REAL data from the service (not mock/placeholder data)
- PASS if the agent successfully connected and got a meaningful response
- FAIL if there were only errors, authentication failures, or no real data
- FAIL if the agent couldn't complete the task

Reply with EXACTLY one line in this format:
PASS: <brief reason>
or
FAIL: <brief reason>"""

    try:
        judge_response = client.models.generate_content(
            model=model_id,
            contents=judge_prompt,
        )
        verdict = judge_response.text.strip()
    except Exception as e:
        verdict = f"FAIL: Judge error: {e}"

    if verbose:
        print(f"  🧑‍⚖️ Verdict: {verdict}")

    passed = verdict.upper().startswith("PASS")

    return {
        "status": "pass" if passed else "fail",
        "verdict": verdict,
        "turns": turn,
        "tool_calls": len(all_tool_calls),
        "final_response": final_text[:300],
    }


# ── CLI ──────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--list" in args:
        print("\n📋 Available agentic tests:\n")
        for name, cfg in TESTS.items():
            env_ok = all(os.environ.get(v) for v in cfg["required_env"]) if cfg["required_env"] else True
            status = "✅ Ready" if env_ok else "⚠️  Missing env vars"
            print(f"  {name:20s} {status}")
            print(f"  {'':20s} {cfg['prompt'][:70]}...")
            print()
        return

    # Determine which tests to run
    if args and args[0] != "--list":
        test_names = [a for a in args if a in TESTS]
        if not test_names:
            print(f"❌ Unknown connector: {args[0]}")
            print(f"   Available: {', '.join(TESTS.keys())}")
            return
    else:
        test_names = list(TESTS.keys())

    print()
    print("🦀 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("   C L A W F O U N D E R")
    print("   Live Agentic Tests")
    print("🦀 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    results = {}

    for name in test_names:
        cfg = TESTS[name]
        print(f"\n{'─' * 50}")
        print(f"🧪 Testing: {name}")
        print(f"{'─' * 50}")

        result = run_agentic_test(name, cfg, verbose=True)
        results[name] = result

        if result["status"] == "skip":
            print(f"  ⏭️  Skipped: {result['reason']}")
        elif result["status"] == "pass":
            print(f"  ✅ PASSED")
        else:
            print(f"  ❌ FAILED: {result.get('verdict', result.get('reason', 'unknown'))}")

    # Summary
    print(f"\n{'━' * 50}")
    print("📊 RESULTS SUMMARY")
    print(f"{'━' * 50}")

    passed = sum(1 for r in results.values() if r["status"] == "pass")
    failed = sum(1 for r in results.values() if r["status"] == "fail")
    skipped = sum(1 for r in results.values() if r["status"] == "skip")

    for name, result in results.items():
        icon = {"pass": "✅", "fail": "❌", "skip": "⏭️"}[result["status"]]
        detail = ""
        if result["status"] == "pass":
            detail = f"({result['turns']} turns, {result['tool_calls']} tool calls)"
        elif result["status"] == "fail":
            detail = result.get("verdict", result.get("reason", ""))[:60]
        elif result["status"] == "skip":
            detail = result["reason"]
        print(f"  {icon} {name:20s} {detail}")

    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")
    print()

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
