"""
Telegram connector — Send and receive messages via a Telegram bot.
"""

import os
import json
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Return True if Telegram bot credentials are set."""
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


TOOLS = [
    {
        "name": "telegram_send_message",
        "description": "Send a text message to a Telegram chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The message text to send",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target chat ID (defaults to TELEGRAM_CHAT_ID env var)",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "telegram_get_updates",
        "description": "Get recent incoming messages to the Telegram bot.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of messages to return (default: 10)",
                },
            },
        },
    },
]


def _resolve_env_keys(account_id=None):
    """Resolve the env var names for the given account."""
    if account_id is None or account_id == "default":
        return "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("telegram", []):
                if acct["id"] == account_id and "env_keys" in acct:
                    keys = acct["env_keys"]
                    return keys.get("TELEGRAM_BOT_TOKEN", f"TELEGRAM_BOT_TOKEN_{account_id.upper()}"), \
                           keys.get("TELEGRAM_CHAT_ID", f"TELEGRAM_CHAT_ID_{account_id.upper()}")
        except Exception:
            pass
    return f"TELEGRAM_BOT_TOKEN_{account_id.upper()}", f"TELEGRAM_CHAT_ID_{account_id.upper()}"


def _get_token(account_id=None):
    token_key, _ = _resolve_env_keys(account_id)
    token = os.environ.get(token_key)
    if not token:
        raise ValueError(f"{token_key} not set. Add it to your .env file.")
    return token


def _get_chat_id(account_id=None):
    _, chat_id_key = _resolve_env_keys(account_id)
    return os.environ.get(chat_id_key)


def _send_message(text: str, chat_id: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})

    if resp.status_code == 200:
        return f"Message sent to chat {chat_id}: {text}"
    else:
        return f"Telegram API error: {resp.status_code} — {resp.text}"


def _get_updates(limit: int = 10, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    resp = requests.get(url, params={"limit": limit})

    if resp.status_code != 200:
        return f"Telegram API error: {resp.status_code} — {resp.text}"

    updates = resp.json().get("result", [])
    if not updates:
        return "No recent messages."

    messages = []
    for update in updates:
        msg = update.get("message", {})
        messages.append({
            "from": msg.get("from", {}).get("first_name", "Unknown"),
            "text": msg.get("text", "(no text)"),
            "date": msg.get("date", ""),
        })

    return json.dumps(messages, indent=2)


def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "telegram_send_message":
            return _send_message(args["text"], args.get("chat_id"), account_id=account_id)
        elif tool_name == "telegram_get_updates":
            return _get_updates(args.get("limit", 10), account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Telegram error: {e}"
