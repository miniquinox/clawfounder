"""
Telegram connector — Send and receive messages via a Telegram bot.
"""

import os
import json

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


def _get_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set. Add it to your .env file.")
    return token


def _send_message(text: str, chat_id: str = None) -> str:
    import requests
    token = _get_token()
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})

    if resp.status_code == 200:
        return f"Message sent to chat {chat_id}: {text}"
    else:
        return f"Telegram API error: {resp.status_code} — {resp.text}"


def _get_updates(limit: int = 10) -> str:
    import requests
    token = _get_token()
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


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "telegram_send_message":
            return _send_message(args["text"], args.get("chat_id"))
        elif tool_name == "telegram_get_updates":
            return _get_updates(args.get("limit", 10))
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Telegram error: {e}"
