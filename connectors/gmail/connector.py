"""
Gmail connector — Read, search, and send emails via the Gmail API.

Auth: Uses OAuth 2.0 with bundled client credentials for zero-config setup.
Token is stored at ~/.clawfounder/gmail_token.json and persists forever
(auto-refreshes). Users can override with GMAIL_CREDENTIALS_FILE env var.
"""

import os
import json
import base64
from pathlib import Path
from email.mime.text import MIMEText

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_TOKEN_DIR = Path.home() / ".clawfounder"
_TOKEN_FILE = _TOKEN_DIR / "gmail_token.json"


# ─── Tool Definitions ──────────────────────────────────────────

TOOLS = [
    {
        "name": "gmail_get_unread",
        "description": "Fetch unread emails from Gmail. Returns sender, subject, date, and snippet for each.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of unread emails to return (default: 10)",
                },
            },
        },
    },
    {
        "name": "gmail_search",
        "description": (
            "Search Gmail with a query string (same syntax as Gmail search bar). "
            "Results are returned newest-first. "
            "Examples: 'from:boss subject:urgent', 'from:ucdavis.edu newer_than:30d', "
            "'has:attachment filename:pdf'. "
            "To find the most recent email from someone, use 'from:<sender>' with max_results=1."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read_email",
        "description": "Read the full body of an email by its message ID. Use after gmail_search or gmail_get_unread to read the full content.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The Gmail message ID (returned by gmail_search and gmail_get_unread)",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": "Send an email via Gmail.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]


# ─── Auth ──────────────────────────────────────────────────────

def _get_gmail_service():
    """Build and return the Gmail API service using saved OAuth token."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Gmail dependencies not installed. Run: bash connectors/gmail/install.sh"
        )

    # Check for existing token
    token_file = Path(os.environ.get("GMAIL_TOKEN_FILE", str(_TOKEN_FILE)))
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json())
        else:
            raise ValueError(
                "Gmail not authenticated. Click 'Sign in with Google' in the "
                "ClawFounder dashboard to connect your Gmail account."
            )

    return build("gmail", "v1", credentials=creds)


# ─── Tool Implementations ──────────────────────────────────────

def _get_unread(max_results: int = 10) -> str:
    service = _get_gmail_service()
    results = service.users().messages().list(
        userId="me", labelIds=["UNREAD"], maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return "No unread emails."

    output = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "id": msg_ref["id"],
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", "Unknown"),
            "snippet": msg.get("snippet", ""),
        })

    return json.dumps(output, indent=2)


def _search(query: str, max_results: int = 5) -> str:
    service = _get_gmail_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return f"No emails found for query: {query}"

    output = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "id": msg_ref["id"],
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", "Unknown"),
            "snippet": msg.get("snippet", ""),
        })

    return json.dumps(output, indent=2)


def _read_email(message_id: str) -> str:
    service = _get_gmail_service()
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    # Extract plain-text body
    body = _extract_body(msg.get("payload", {}))

    return json.dumps({
        "id": message_id,
        "from": headers.get("From", "Unknown"),
        "to": headers.get("To", "Unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", "Unknown"),
        "body": body[:5000],  # Cap at 5k chars to avoid huge responses
    }, indent=2)


def _extract_body(payload: dict) -> str:
    """Recursively extract body from Gmail message payload.
    Prefers text/plain; falls back to text/html with tags stripped."""
    text = _find_part(payload, "text/plain")
    if text:
        return text
    html = _find_part(payload, "text/html")
    if html:
        return _strip_html(html)
    return "(no readable body found)"


def _find_part(payload: dict, mime: str) -> str | None:
    """Recursively find and decode the first part matching the given MIME type."""
    if payload.get("mimeType") == mime and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        if part.get("mimeType") == mime and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _find_part(part, mime)
        if result:
            return result
    return None


def _strip_html(html: str) -> str:
    """Best-effort HTML to plain text (no extra dependencies)."""
    import re
    # Remove style/script blocks entirely
    text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Convert common block elements to newlines
    text = re.sub(r'<br\s*/?>',  '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    import html as html_mod
    text = html_mod.unescape(text)
    # Collapse whitespace but keep newlines
    lines = [' '.join(line.split()) for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text.strip()


def _send(to: str, subject: str, body: str) -> str:
    service = _get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to} with subject: {subject}"


# ─── Handler ───────────────────────────────────────────────────

def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "gmail_get_unread":
            return _get_unread(args.get("max_results", 10))
        elif tool_name == "gmail_search":
            return _search(args["query"], args.get("max_results", 5))
        elif tool_name == "gmail_read_email":
            return _read_email(args["message_id"])
        elif tool_name == "gmail_send":
            return _send(args["to"], args["subject"], args["body"])
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Gmail error: {e}"
