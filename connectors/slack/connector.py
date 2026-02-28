"""
Slack connector — Read channels, send messages, search workspace.

Auth: Bot Token (SLACK_BOT_TOKEN env var).
Create a Slack App at api.slack.com/apps, add scopes, install to workspace.
"""

import os
import json
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = False


def is_connected() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


TOOLS = [
    {
        "name": "slack_list_channels",
        "description": "List Slack channels and DMs the bot can access.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max channels to return (default: 20)",
                },
                "types": {
                    "type": "string",
                    "description": "Comma-separated types: public_channel,private_channel,mpim,im (default: public_channel,private_channel)",
                },
            },
        },
    },
    {
        "name": "slack_get_messages",
        "description": "Get recent messages from a Slack channel. Use channel name (e.g. 'general') or channel ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name (without #) or channel ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of messages to return (default: 10)",
                },
            },
            "required": ["channel"],
        },
    },
    {
        "name": "slack_send_message",
        "description": "Send a message to a Slack channel.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name (without #) or channel ID",
                },
                "text": {
                    "type": "string",
                    "description": "Message text (supports Slack markdown)",
                },
            },
            "required": ["channel", "text"],
        },
    },
    {
        "name": "slack_search",
        "description": "Search messages across the Slack workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports Slack search syntax: from:user, in:channel, etc.)",
                },
                "count": {
                    "type": "integer",
                    "description": "Max results to return (default: 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "slack_list_users",
        "description": "List members in the Slack workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max users to return (default: 50)",
                },
            },
        },
    },
    {
        "name": "slack_reply_thread",
        "description": "Reply to a specific message thread in Slack.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name or ID where the thread is",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Timestamp of the parent message (returned in slack_get_messages)",
                },
                "text": {
                    "type": "string",
                    "description": "Reply text",
                },
            },
            "required": ["channel", "thread_ts", "text"],
        },
    },
]


# ── Auth ──────────────────────────────────────────────────────────

def _get_client(account_id=None):
    from slack_sdk import WebClient
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN not set. Add it to your .env file.")
    return WebClient(token=token)


# Channel name → ID cache (populated lazily)
_channel_cache = {}


def _resolve_channel(client, channel_input):
    """Resolve a channel name to its ID. Passes through if already an ID."""
    if channel_input.startswith("C") or channel_input.startswith("D") or channel_input.startswith("G"):
        if len(channel_input) > 8:  # Looks like an ID
            return channel_input

    # Check cache
    name = channel_input.lstrip("#").lower()
    if name in _channel_cache:
        return _channel_cache[name]

    # Fetch channels and populate cache
    try:
        resp = client.conversations_list(types="public_channel,private_channel", limit=200)
        for ch in resp.get("channels", []):
            _channel_cache[ch["name"].lower()] = ch["id"]
        if name in _channel_cache:
            return _channel_cache[name]
    except Exception:
        pass

    return channel_input  # Return as-is, let Slack API error if invalid


# ── Tool implementations ──────────────────────────────────────────

def _list_channels(limit=20, types="public_channel,private_channel", account_id=None):
    client = _get_client(account_id)
    resp = client.conversations_list(types=types, limit=limit, exclude_archived=True)
    channels = []
    for ch in resp.get("channels", []):
        channels.append({
            "id": ch["id"],
            "name": ch.get("name", ""),
            "topic": ch.get("topic", {}).get("value", ""),
            "members": ch.get("num_members", 0),
            "is_private": ch.get("is_private", False),
        })
    return json.dumps(channels, indent=2)


def _get_messages(channel, limit=10, account_id=None):
    client = _get_client(account_id)
    channel_id = _resolve_channel(client, channel)
    resp = client.conversations_history(channel=channel_id, limit=limit)
    messages = []
    for msg in resp.get("messages", []):
        messages.append({
            "ts": msg.get("ts", ""),
            "user": msg.get("user", ""),
            "text": msg.get("text", ""),
            "thread_ts": msg.get("thread_ts"),
            "reply_count": msg.get("reply_count", 0),
        })
    # Resolve user IDs to names (best effort)
    user_ids = {m["user"] for m in messages if m["user"]}
    if user_ids:
        try:
            names = {}
            for uid in user_ids:
                info = client.users_info(user=uid)
                u = info.get("user", {})
                names[uid] = u.get("real_name") or u.get("name", uid)
            for m in messages:
                m["user"] = names.get(m["user"], m["user"])
        except Exception:
            pass
    return json.dumps(messages, indent=2)


def _send_message(channel, text, account_id=None):
    client = _get_client(account_id)
    channel_id = _resolve_channel(client, channel)
    resp = client.chat_postMessage(channel=channel_id, text=text)
    if resp.get("ok"):
        return f"Message sent to #{channel}: {text[:100]}"
    return f"Slack error: {resp.get('error', 'unknown')}"


def _search(query, count=10, account_id=None):
    # search:read is a user token scope — use user token if available, else bot token
    token = os.environ.get("SLACK_USER_TOKEN") or os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return "No Slack token available for search."
    from slack_sdk import WebClient
    client = WebClient(token=token)
    resp = client.search_messages(query=query, count=count)
    matches = resp.get("messages", {}).get("matches", [])
    if not matches:
        return f"No Slack messages found for: {query}"
    results = []
    for m in matches:
        results.append({
            "channel": m.get("channel", {}).get("name", ""),
            "user": m.get("username", ""),
            "text": m.get("text", "")[:200],
            "ts": m.get("ts", ""),
            "permalink": m.get("permalink", ""),
        })
    return json.dumps(results, indent=2)


def _list_users(limit=50, account_id=None):
    client = _get_client(account_id)
    resp = client.users_list(limit=limit)
    users = []
    for u in resp.get("members", []):
        if u.get("deleted") or u.get("is_bot"):
            continue
        users.append({
            "id": u["id"],
            "name": u.get("real_name") or u.get("name", ""),
            "display_name": u.get("profile", {}).get("display_name", ""),
            "email": u.get("profile", {}).get("email", ""),
        })
    return json.dumps(users, indent=2)


def _reply_thread(channel, thread_ts, text, account_id=None):
    client = _get_client(account_id)
    channel_id = _resolve_channel(client, channel)
    resp = client.chat_postMessage(channel=channel_id, text=text, thread_ts=thread_ts)
    if resp.get("ok"):
        return f"Reply sent in thread {thread_ts}: {text[:100]}"
    return f"Slack error: {resp.get('error', 'unknown')}"


# ── Handler ───────────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "slack_list_channels":
            return _list_channels(args.get("limit", 20), args.get("types", "public_channel,private_channel"), account_id=account_id)
        elif tool_name == "slack_get_messages":
            return _get_messages(args["channel"], args.get("limit", 10), account_id=account_id)
        elif tool_name == "slack_send_message":
            return _send_message(args["channel"], args["text"], account_id=account_id)
        elif tool_name == "slack_search":
            return _search(args["query"], args.get("count", 10), account_id=account_id)
        elif tool_name == "slack_list_users":
            return _list_users(args.get("limit", 50), account_id=account_id)
        elif tool_name == "slack_reply_thread":
            return _reply_thread(args["channel"], args["thread_ts"], args["text"], account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Slack error: {e}"
