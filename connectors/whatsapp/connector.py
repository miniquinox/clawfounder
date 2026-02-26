"""
WhatsApp connector — Send messages, media, and more via the Meta WhatsApp Cloud API.
"""

import os
import json
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = True

GRAPH_API = "https://graph.facebook.com/v21.0"


def is_connected() -> bool:
    """Return True if WhatsApp Cloud API credentials are set."""
    return bool(os.environ.get("WHATSAPP_ACCESS_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))


TOOLS = [
    {
        "name": "whatsapp_send_message",
        "description": "Send a text message to a WhatsApp phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The message text to send",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+' (e.g. '14155551234'). Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
                "preview_url": {
                    "type": "boolean",
                    "description": "If true, URLs in the message will show a preview (default: false)",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "whatsapp_send_template",
        "description": "Send a pre-approved template message. Required to initiate conversations outside the 24-hour window.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of the approved message template",
                },
                "language_code": {
                    "type": "string",
                    "description": "Language code for the template (e.g. 'en_US')",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+' (e.g. '14155551234'). Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
            },
            "required": ["template_name", "language_code"],
        },
    },
    {
        "name": "whatsapp_send_image",
        "description": "Send an image to a WhatsApp phone number by URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "Public URL of the image to send",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+'. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the image",
                },
            },
            "required": ["image_url"],
        },
    },
    {
        "name": "whatsapp_send_document",
        "description": "Send a document/file to a WhatsApp phone number by URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_url": {
                    "type": "string",
                    "description": "Public URL of the document to send",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+'. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the document",
                },
                "filename": {
                    "type": "string",
                    "description": "Optional filename to display for the document",
                },
            },
            "required": ["document_url"],
        },
    },
    {
        "name": "whatsapp_send_location",
        "description": "Send a GPS location to a WhatsApp phone number.",
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
                "name": {
                    "type": "string",
                    "description": "Optional name of the location",
                },
                "address": {
                    "type": "string",
                    "description": "Optional address of the location",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+'. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "whatsapp_send_contacts",
        "description": "Share a contact card via WhatsApp.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                    "description": "Contact's first name",
                },
                "last_name": {
                    "type": "string",
                    "description": "Contact's last name",
                },
                "phone": {
                    "type": "string",
                    "description": "Contact's phone number",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+'. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
            },
            "required": ["first_name", "phone"],
        },
    },
    {
        "name": "whatsapp_send_reaction",
        "description": "React to a WhatsApp message with an emoji.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "ID of the message to react to",
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji to react with (e.g. '\ud83d\udc4d')",
                },
                "to": {
                    "type": "string",
                    "description": "Phone number of the chat containing the message. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
            },
            "required": ["message_id", "emoji"],
        },
    },
    {
        "name": "whatsapp_mark_read",
        "description": "Mark a WhatsApp message as read (sends read receipts).",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "ID of the message to mark as read",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "whatsapp_send_interactive",
        "description": "Send an interactive message with buttons or a list menu.",
        "parameters": {
            "type": "object",
            "properties": {
                "interactive_type": {
                    "type": "string",
                    "description": "'button' for reply buttons (max 3) or 'list' for a list menu",
                },
                "body_text": {
                    "type": "string",
                    "description": "Main body text of the message",
                },
                "buttons": {
                    "type": "array",
                    "description": "For 'button' type: list of button objects with 'id' and 'title' (max 3). For 'list' type: list of section objects with 'title' and 'rows' (each row has 'id', 'title', optional 'description').",
                },
                "header_text": {
                    "type": "string",
                    "description": "Optional header text",
                },
                "footer_text": {
                    "type": "string",
                    "description": "Optional footer text",
                },
                "button_text": {
                    "type": "string",
                    "description": "For 'list' type: text on the menu button (e.g. 'Choose an option')",
                },
                "to": {
                    "type": "string",
                    "description": "Recipient phone number in international format without '+'. Defaults to WHATSAPP_DEFAULT_RECIPIENT env var.",
                },
            },
            "required": ["interactive_type", "body_text", "buttons"],
        },
    },
    {
        "name": "whatsapp_get_profile",
        "description": "Get the WhatsApp Business profile info (about text, address, email, websites, profile picture).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


# ─── Helpers ───────────────────────────────────────────────────────

def _resolve_env_keys(account_id=None):
    """Resolve the env var names for the given account."""
    if account_id is None or account_id == "default":
        return "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_DEFAULT_RECIPIENT"
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("whatsapp", []):
                if acct["id"] == account_id and "env_keys" in acct:
                    keys = acct["env_keys"]
                    return (
                        keys.get("WHATSAPP_ACCESS_TOKEN", f"WHATSAPP_ACCESS_TOKEN_{account_id.upper()}"),
                        keys.get("WHATSAPP_PHONE_NUMBER_ID", f"WHATSAPP_PHONE_NUMBER_ID_{account_id.upper()}"),
                        keys.get("WHATSAPP_DEFAULT_RECIPIENT", f"WHATSAPP_DEFAULT_RECIPIENT_{account_id.upper()}"),
                    )
        except Exception:
            pass
    return (
        f"WHATSAPP_ACCESS_TOKEN_{account_id.upper()}",
        f"WHATSAPP_PHONE_NUMBER_ID_{account_id.upper()}",
        f"WHATSAPP_DEFAULT_RECIPIENT_{account_id.upper()}",
    )


def _get_token(account_id=None):
    token_key, _, _ = _resolve_env_keys(account_id)
    token = os.environ.get(token_key)
    if not token:
        raise ValueError(f"{token_key} not set. Add it to your .env file.")
    return token


def _get_phone_number_id(account_id=None):
    _, pn_key, _ = _resolve_env_keys(account_id)
    pn_id = os.environ.get(pn_key)
    if not pn_id:
        raise ValueError(f"{pn_key} not set. Add it to your .env file.")
    return pn_id


def _get_default_recipient(account_id=None):
    _, _, recipient_key = _resolve_env_keys(account_id)
    return os.environ.get(recipient_key)


def _send_request(phone_number_id, token, payload):
    """Send a request to the WhatsApp Cloud API messages endpoint."""
    import requests
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        msg_id = data.get("messages", [{}])[0].get("id", "unknown")
        return f"Message sent successfully (id: {msg_id})."
    return f"WhatsApp API error: {resp.status_code} — {resp.text}"


# ─── Handler Functions ─────────────────────────────────────────────

def _send_message(text: str, to: str = None, preview_url: bool = False, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text},
    }
    return _send_request(phone_number_id, token, payload)


def _send_template(template_name: str, language_code: str, to: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    return _send_request(phone_number_id, token, payload)


def _send_image(image_url: str, to: str = None, caption: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    image_obj = {"link": image_url}
    if caption:
        image_obj["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_obj,
    }
    return _send_request(phone_number_id, token, payload)


def _send_document(document_url: str, to: str = None, caption: str = None, filename: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    doc_obj = {"link": document_url}
    if caption:
        doc_obj["caption"] = caption
    if filename:
        doc_obj["filename"] = filename
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": doc_obj,
    }
    return _send_request(phone_number_id, token, payload)


def _send_location(latitude: float, longitude: float, to: str = None, name: str = None, address: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    loc_obj = {"latitude": latitude, "longitude": longitude}
    if name:
        loc_obj["name"] = name
    if address:
        loc_obj["address"] = address
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "location",
        "location": loc_obj,
    }
    return _send_request(phone_number_id, token, payload)


def _send_contacts(first_name: str, phone: str, last_name: str = None, to: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    name_obj = {"first_name": first_name, "formatted_name": first_name}
    if last_name:
        name_obj["last_name"] = last_name
        name_obj["formatted_name"] = f"{first_name} {last_name}"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "contacts",
        "contacts": [
            {
                "name": name_obj,
                "phones": [{"phone": phone, "type": "CELL"}],
            }
        ],
    }
    return _send_request(phone_number_id, token, payload)


def _send_reaction(message_id: str, emoji: str, to: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": emoji},
    }
    return _send_request(phone_number_id, token, payload)


def _mark_read(message_id: str, account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    resp = requests.post(url, json=payload, headers=headers)
    if resp.status_code == 200:
        return f"Message {message_id} marked as read."
    return f"WhatsApp API error: {resp.status_code} — {resp.text}"


def _send_interactive(interactive_type: str, body_text: str, buttons, to: str = None, header_text: str = None, footer_text: str = None, button_text: str = None, account_id=None) -> str:
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    to = to or _get_default_recipient(account_id)
    if not to:
        return "Error: No recipient provided and WHATSAPP_DEFAULT_RECIPIENT not set."

    interactive_obj = {
        "type": interactive_type,
        "body": {"text": body_text},
    }
    if header_text:
        interactive_obj["header"] = {"type": "text", "text": header_text}
    if footer_text:
        interactive_obj["footer"] = {"text": footer_text}

    if interactive_type == "button":
        interactive_obj["action"] = {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                for b in buttons[:3]
            ]
        }
    elif interactive_type == "list":
        interactive_obj["action"] = {
            "button": button_text or "Options",
            "sections": buttons,
        }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive_obj,
    }
    return _send_request(phone_number_id, token, payload)


def _get_profile(account_id=None) -> str:
    import requests
    token = _get_token(account_id)
    phone_number_id = _get_phone_number_id(account_id)
    url = f"{GRAPH_API}/{phone_number_id}/whatsapp_business_profile"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params={"fields": "about,address,description,email,profile_picture_url,websites,vertical"}, headers=headers)
    if resp.status_code != 200:
        return f"WhatsApp API error: {resp.status_code} — {resp.text}"
    data = resp.json().get("data", [{}])
    if data:
        return json.dumps(data[0], indent=2)
    return "No profile data found."


# ─── Router ────────────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "whatsapp_send_message":
            return _send_message(args["text"], args.get("to"), args.get("preview_url", False), account_id=account_id)
        elif tool_name == "whatsapp_send_template":
            return _send_template(args["template_name"], args["language_code"], args.get("to"), account_id=account_id)
        elif tool_name == "whatsapp_send_image":
            return _send_image(args["image_url"], args.get("to"), args.get("caption"), account_id=account_id)
        elif tool_name == "whatsapp_send_document":
            return _send_document(args["document_url"], args.get("to"), args.get("caption"), args.get("filename"), account_id=account_id)
        elif tool_name == "whatsapp_send_location":
            return _send_location(args["latitude"], args["longitude"], args.get("to"), args.get("name"), args.get("address"), account_id=account_id)
        elif tool_name == "whatsapp_send_contacts":
            return _send_contacts(args["first_name"], args["phone"], args.get("last_name"), args.get("to"), account_id=account_id)
        elif tool_name == "whatsapp_send_reaction":
            return _send_reaction(args["message_id"], args["emoji"], args.get("to"), account_id=account_id)
        elif tool_name == "whatsapp_mark_read":
            return _mark_read(args["message_id"], account_id=account_id)
        elif tool_name == "whatsapp_send_interactive":
            return _send_interactive(
                args["interactive_type"], args["body_text"], args["buttons"],
                args.get("to"), args.get("header_text"), args.get("footer_text"),
                args.get("button_text"), account_id=account_id,
            )
        elif tool_name == "whatsapp_get_profile":
            return _get_profile(account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"WhatsApp error: {e}"
