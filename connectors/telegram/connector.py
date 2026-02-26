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
    {
        "name": "telegram_send_photo",
        "description": "Send a photo to a Telegram chat by URL or file_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "photo": {
                    "type": "string",
                    "description": "Photo URL or Telegram file_id",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target chat ID (defaults to TELEGRAM_CHAT_ID env var)",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the photo",
                },
                "parse_mode": {
                    "type": "string",
                    "description": "Parse mode for caption: 'Markdown' or 'HTML'",
                },
            },
            "required": ["photo"],
        },
    },
    {
        "name": "telegram_send_document",
        "description": "Send a document/file to a Telegram chat by URL or file_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "document": {
                    "type": "string",
                    "description": "Document URL or Telegram file_id",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target chat ID (defaults to TELEGRAM_CHAT_ID env var)",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the document",
                },
                "parse_mode": {
                    "type": "string",
                    "description": "Parse mode for caption: 'Markdown' or 'HTML'",
                },
            },
            "required": ["document"],
        },
    },
    {
        "name": "telegram_send_location",
        "description": "Send a GPS location to a Telegram chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitude of the location",
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude of the location",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target chat ID (defaults to TELEGRAM_CHAT_ID env var)",
                },
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "telegram_forward_message",
        "description": "Forward a message from one chat to another.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_chat_id": {
                    "type": "string",
                    "description": "Chat ID where the original message is from",
                },
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to forward",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target chat ID to forward to (defaults to TELEGRAM_CHAT_ID env var)",
                },
            },
            "required": ["from_chat_id", "message_id"],
        },
    },
    {
        "name": "telegram_edit_message",
        "description": "Edit a previously sent text message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to edit",
                },
                "text": {
                    "type": "string",
                    "description": "New text for the message",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID where the message is (defaults to TELEGRAM_CHAT_ID env var)",
                },
                "parse_mode": {
                    "type": "string",
                    "description": "Parse mode: 'Markdown' or 'HTML'",
                },
            },
            "required": ["message_id", "text"],
        },
    },
    {
        "name": "telegram_delete_message",
        "description": "Delete a message from a Telegram chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to delete",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID where the message is (defaults to TELEGRAM_CHAT_ID env var)",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "telegram_pin_message",
        "description": "Pin a message in a Telegram chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "integer",
                    "description": "ID of the message to pin",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID where the message is (defaults to TELEGRAM_CHAT_ID env var)",
                },
                "disable_notification": {
                    "type": "boolean",
                    "description": "If true, pin silently without notifying members",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "telegram_get_chat",
        "description": "Get info about a chat, group, or channel (title, type, member count, description).",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID to get info about (defaults to TELEGRAM_CHAT_ID env var)",
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


def _send_photo(photo: str, chat_id: str = None, caption: str = None, parse_mode: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "photo": photo}
    if caption:
        payload["caption"] = caption
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", json=payload)
    if resp.status_code == 200:
        return f"Photo sent to chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _send_document(document: str, chat_id: str = None, caption: str = None, parse_mode: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "document": document}
    if caption:
        payload["caption"] = caption
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", json=payload)
    if resp.status_code == 200:
        return f"Document sent to chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _send_location(latitude: float, longitude: float, chat_id: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendLocation", json=payload)
    if resp.status_code == 200:
        return f"Location ({latitude}, {longitude}) sent to chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _forward_message(from_chat_id: str, message_id: int, chat_id: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
    resp = requests.post(f"https://api.telegram.org/bot{token}/forwardMessage", json=payload)
    if resp.status_code == 200:
        return f"Message {message_id} forwarded from {from_chat_id} to {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _edit_message(message_id: int, text: str, chat_id: str = None, parse_mode: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(f"https://api.telegram.org/bot{token}/editMessageText", json=payload)
    if resp.status_code == 200:
        return f"Message {message_id} edited in chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _delete_message(message_id: int, chat_id: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "message_id": message_id}
    resp = requests.post(f"https://api.telegram.org/bot{token}/deleteMessage", json=payload)
    if resp.status_code == 200:
        return f"Message {message_id} deleted from chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _pin_message(message_id: int, chat_id: str = None, disable_notification: bool = False, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    payload = {"chat_id": chat_id, "message_id": message_id}
    if disable_notification:
        payload["disable_notification"] = True
    resp = requests.post(f"https://api.telegram.org/bot{token}/pinChatMessage", json=payload)
    if resp.status_code == 200:
        return f"Message {message_id} pinned in chat {chat_id}."
    return f"Telegram API error: {resp.status_code} — {resp.text}"


def _get_chat(chat_id: str = None, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    chat_id = chat_id or _get_chat_id(account_id)
    if not chat_id:
        return "Error: No chat_id provided and TELEGRAM_CHAT_ID not set."
    resp = requests.get(f"https://api.telegram.org/bot{token}/getChat", params={"chat_id": chat_id})
    if resp.status_code != 200:
        return f"Telegram API error: {resp.status_code} — {resp.text}"
    chat = resp.json().get("result", {})
    info = {
        "id": chat.get("id"),
        "type": chat.get("type"),
        "title": chat.get("title"),
        "username": chat.get("username"),
        "first_name": chat.get("first_name"),
        "description": chat.get("description"),
    }
    return json.dumps({k: v for k, v in info.items() if v is not None}, indent=2)


def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "telegram_send_message":
            return _send_message(args["text"], args.get("chat_id"), account_id=account_id)
        elif tool_name == "telegram_get_updates":
            return _get_updates(args.get("limit", 10), account_id=account_id)
        elif tool_name == "telegram_send_photo":
            return _send_photo(args["photo"], args.get("chat_id"), args.get("caption"), args.get("parse_mode"), account_id=account_id)
        elif tool_name == "telegram_send_document":
            return _send_document(args["document"], args.get("chat_id"), args.get("caption"), args.get("parse_mode"), account_id=account_id)
        elif tool_name == "telegram_send_location":
            return _send_location(args["latitude"], args["longitude"], args.get("chat_id"), account_id=account_id)
        elif tool_name == "telegram_forward_message":
            return _forward_message(args["from_chat_id"], args["message_id"], args.get("chat_id"), account_id=account_id)
        elif tool_name == "telegram_edit_message":
            return _edit_message(args["message_id"], args["text"], args.get("chat_id"), args.get("parse_mode"), account_id=account_id)
        elif tool_name == "telegram_delete_message":
            return _delete_message(args["message_id"], args.get("chat_id"), account_id=account_id)
        elif tool_name == "telegram_pin_message":
            return _pin_message(args["message_id"], args.get("chat_id"), args.get("disable_notification", False), account_id=account_id)
        elif tool_name == "telegram_get_chat":
            return _get_chat(args.get("chat_id"), account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Telegram error: {e}"
