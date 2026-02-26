"""
Gmail connector — Read, search, and send personal Gmail.

For personal @gmail.com accounts. No admin setup needed — just click
"Sign in with Google" and authorize.

Credentials are stored at ~/.clawfounder/gmail_personal.json so they
don't conflict with the Work Email connector.
"""

import json
import base64
from pathlib import Path
from email.mime.text import MIMEText

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_TOKEN_DIR = Path.home() / ".clawfounder"
_TOKEN_FILE = _TOKEN_DIR / "gmail_personal.json"


def is_connected() -> bool:
    """Return True if personal Gmail credentials are available."""
    return _TOKEN_FILE.exists()


# ─── Tool Definitions ──────────────────────────────────────────

TOOLS = [
    {
        "name": "gmail_get_unread",
        "description": "Fetch unread emails from personal Gmail. Returns sender, subject, date, and snippet for each.",
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
            "Search personal Gmail with a query string (same syntax as Gmail search bar). "
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
        "description": "Send an email via personal Gmail.",
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
    """Build and return the Gmail API service using personal Gmail credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Gmail dependencies not installed. Run: bash connectors/gmail/install.sh"
        )

    if not _TOKEN_FILE.exists():
        raise ValueError(
            "Personal Gmail not authenticated. Click 'Sign in with Google' on the "
            "Gmail card in the ClawFounder dashboard."
        )

    try:
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

        # Set quota project if present in the token file
        token_data = json.loads(_TOKEN_FILE.read_text())
        quota_project = token_data.get("quota_project_id")
        if quota_project:
            creds = creds.with_quota_project(quota_project)

        # Always refresh if not valid (token may be missing or expired)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())

        if creds and creds.valid:
            return build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise ValueError(f"Gmail auth failed: {e}")

    raise ValueError("Gmail credentials are invalid. Please re-authenticate.")


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
