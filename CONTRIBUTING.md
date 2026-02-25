# Contributing to ClawFounder 🦀

Thanks for wanting to add a connector! Here's everything you need to know.

---

## The 5-Minute Version

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/clawfounder.git
cd clawfounder

# 2. Set up a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Copy the template
cp -r connectors/_template connectors/your_service

# 4. Fill in the 5 files (see below)

# 5. Validate
python tests/validate_connector.py connectors/your_service

# 6. Test with the agent
python -m agent.runner --provider gemini
# Ask a question that triggers your connector

# 7. Run your unit tests
python -m pytest connectors/your_service/test_connector.py -v

# 8. Open a PR
```

---

## The 5 Files

Every connector is a folder inside `connectors/` with exactly these files:

### 1. `instructions.md`

Explain your connector in plain English:
- What service does it connect to?
- What can it do?
- What API keys or credentials are needed?
- How does authentication work?
- Any gotchas or limitations?

This is for humans, not machines. Write it like you're explaining it to a friend.

### 2. `connector.py`

This is the code. It must export:

```python
TOOLS = [
    {
        "name": "tool_name",           # Unique, snake_case
        "description": "What it does", # The AI reads this to decide when to use it
        "parameters": {                # JSON Schema format
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "What this param is"
                }
            },
            "required": ["param1"]     # Optional — list required params
        }
    }
]

def handle(tool_name: str, args: dict) -> str:
    """Execute a tool call. Must return a string."""
    if tool_name == "tool_name":
        # Do the thing
        return "result as a string"
    return f"Unknown tool: {tool_name}"
```

**Rules:**
- Tool names must be globally unique. Prefix with your service name (e.g., `gmail_get_unread`, `telegram_send_message`).
- `handle()` must always return a string.
- Load API keys from environment variables using `os.environ.get()`.
- Never hardcode credentials.
- Handle errors gracefully — return error messages as strings, don't crash.

### 3. `requirements.txt`

List your Python dependencies, one per line:

```
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
```

### 4. `install.sh`

A shell script that installs your dependencies:

```bash
#!/bin/bash
echo "Installing Gmail connector..."
pip install -r requirements.txt
echo "Done! Set these env vars in your .env file:"
echo "  GMAIL_CREDENTIALS_FILE=path/to/credentials.json"
```

Make it helpful. Tell people what env vars they need to set.

### 5. `test_connector.py`

Unit tests for your connector. At minimum:

```python
import pytest
from connector import TOOLS, handle

def test_tools_defined():
    """TOOLS list exists and is not empty."""
    assert isinstance(TOOLS, list)
    assert len(TOOLS) > 0

def test_tool_schema():
    """Each tool has name, description, parameters."""
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool

def test_handle_unknown_tool():
    """handle() returns a message for unknown tools."""
    result = handle("nonexistent_tool", {})
    assert isinstance(result, str)

# Add your own tests below!
# Mock external APIs — don't make real API calls in tests.
```

---

## Naming Conventions

- **Folder name**: lowercase, underscores (e.g., `google_calendar`, `yahoo_finance`)
- **Tool names**: `servicename_action` (e.g., `gmail_get_unread`, `github_list_repos`)
- **No spaces, no hyphens** in tool names

---

## Validation Checklist

Before you open a PR, make sure:

- [ ] All 5 files exist in your connector folder
- [ ] `connector.py` exports `TOOLS` (list) and `handle` (function)
- [ ] Every tool has `name`, `description`, and `parameters`
- [ ] `handle()` returns strings for all tool calls
- [ ] `test_connector.py` passes: `python3 -m pytest connectors/your_service/test_connector.py -v`
- [ ] Structure validation passes: `python3 tests/validate_connector.py connectors/your_service`
- [ ] Your `.env.example` additions are documented (if you need new env vars)
- [ ] `instructions.md` explains everything a first-timer needs to know
- [ ] You tested with at least one provider: `python3 -m agent.runner --provider gemini`

---

## Tips

- **Mock your APIs in tests.** Don't make real API calls — other contributors won't have your credentials.
- **Keep tools focused.** One tool = one action. Don't make a mega-tool that does everything.
- **Write good descriptions.** The AI uses your tool descriptions to decide when to call them. Be specific.
- **Handle errors.** If the API is down or creds are missing, return a helpful error string. Don't throw exceptions.

---

## Questions?

Open an issue. We're friendly. 🦀
