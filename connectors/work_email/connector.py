"""
Work Email connector — Access your Google Workspace email via Gmail API.

For Google Workspace accounts (@yourcompany.com). Requires a one-time admin
whitelist of the Google Auth Library in the Workspace admin console.

Credentials are stored separately from personal Gmail at
~/.clawfounder/gmail_work.json so both can be active simultaneously.
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
_TOKEN_FILE = _TOKEN_DIR / "gmail_work.json"

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Return True if work email credentials are available."""
    return _TOKEN_FILE.exists()


# ─── Tool Definitions ──────────────────────────────────────────

TOOLS = [
    {
        "name": "work_email_get_unread",
        "description": "Fetch unread emails from your work email (Google Workspace). Returns sender, subject, date, and snippet.",
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
        "name": "work_email_search",
        "description": (
            "Search your work email (Google Workspace) with a query string (same syntax as Gmail search bar). "
            "Results are returned newest-first. "
            "Examples: 'from:boss subject:urgent', 'from:client.com newer_than:30d', "
            "'has:attachment filename:pdf'. "
            "To find the most recent email from someone, use 'from:<sender>' with max_results=1."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Email search query",
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
        "name": "work_email_read_email",
        "description": "Read the full body of a work email by its message ID. Use after work_email_search or work_email_get_unread.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The email message ID (returned by work_email_search and work_email_get_unread)",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "work_email_send",
        "description": "Send an email from your work email (Google Workspace).",
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
    {
        "name": "work_email_reply",
        "description": (
            "Reply to an existing work email thread. Use after work_email_read_email to reply to a specific message. "
            "Maintains the thread so the reply appears in the same conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The message ID to reply to",
                },
                "body": {
                    "type": "string",
                    "description": "Reply body (plain text)",
                },
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "work_email_create_draft",
        "description": "Create a draft email in your work email. The draft is saved but NOT sent.",
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
    {
        "name": "work_email_trash",
        "description": "Move a work email to the trash. Use the message ID from work_email_search or work_email_get_unread.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The message ID to trash",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "work_email_mark_read",
        "description": "Mark one or more work emails as read. Accepts a single message ID or a comma-separated list.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "string",
                    "description": "Message ID(s) to mark as read (comma-separated for multiple)",
                },
            },
            "required": ["message_ids"],
        },
    },
    {
        "name": "work_email_mark_unread",
        "description": "Mark one or more work emails as unread. Accepts a single message ID or a comma-separated list.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_ids": {
                    "type": "string",
                    "description": "Message ID(s) to mark as unread (comma-separated for multiple)",
                },
            },
            "required": ["message_ids"],
        },
    },
    {
        "name": "work_email_toggle_star",
        "description": "Star or unstar a work email.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The message ID to star/unstar",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "work_email_list_labels",
        "description": "List all labels (folders/categories) in the work email. Returns label names and IDs.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


# ─── Auth ──────────────────────────────────────────────────────

def _get_token_file(account_id=None):
    """Resolve the token file path for a given account."""
    if account_id is None or account_id == "default":
        return _TOKEN_FILE
    accounts_file = _TOKEN_DIR / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("work_email", []):
                if acct["id"] == account_id and "credential_file" in acct:
                    return _TOKEN_DIR / acct["credential_file"]
        except Exception:
            pass
    return _TOKEN_DIR / f"work_email_account_{account_id}.json"


def _get_gmail_service(account_id=None):
    """Build and return the Gmail API service using work email credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Work email dependencies not installed. Run: bash connectors/work_email/install.sh"
        )

    token_file = _get_token_file(account_id)

    if not token_file.exists():
        raise ValueError(
            "Work email not authenticated. Click 'Sign in with Google' on the "
            "Work Email card in the ClawFounder dashboard.\n\n"
            "⚠  Google Workspace accounts require a one-time admin whitelist:\n"
            "   1. Go to admin.google.com → Security → API Controls → App Access Control\n"
            "   2. Configure New App → Search 'Google Auth Library'\n"
            "   3. Allow for all company users → Choose Trusted"
        )

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)

        # Set quota project if present in the token file
        token_data = json.loads(token_file.read_text())
        quota_project = token_data.get("quota_project_id")
        if quota_project:
            creds = creds.with_quota_project(quota_project)

        # Always refresh if not valid (ADC tokens may have no initial token)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())

        if creds and creds.valid:
            return build("gmail", "v1", credentials=creds)
    except Exception as e:
        raise ValueError(f"Work email auth failed: {e}")

    raise ValueError("Work email credentials are invalid. Please re-authenticate.")


# ─── Tool Implementations ──────────────────────────────────────

_METADATA_HEADERS = ["From", "To", "Subject", "Date", "Reply-To", "Message-ID"]


def _batch_get_messages(service, message_refs):
    """Fetch multiple messages in a single batch request (1 HTTP call instead of N)."""
    results = {}

    def _callback(request_id, response, exception):
        if exception is None:
            results[request_id] = response

    batch = service.new_batch_http_request(callback=_callback)
    for msg_ref in message_refs:
        batch.add(
            service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=_METADATA_HEADERS,
            ),
            request_id=msg_ref["id"],
        )
    batch.execute()

    output = []
    for msg_ref in message_refs:
        msg = results.get(msg_ref["id"])
        if not msg:
            continue
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "id": msg_ref["id"],
            "from": headers.get("From", "Unknown"),
            "to": headers.get("To", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", "Unknown"),
            "snippet": msg.get("snippet", ""),
        })
    return output


def _get_unread(max_results: int = 10, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    results = service.users().messages().list(
        userId="me", labelIds=["UNREAD"], maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return "No unread work emails."

    output = _batch_get_messages(service, messages)
    return json.dumps(output, indent=2)


def _search(query: str, max_results: int = 5, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return f"No work emails found for query: {query}"

    output = _batch_get_messages(service, messages)
    return json.dumps(output, indent=2)


def _read_email(message_id: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_body(msg.get("payload", {}))

    return json.dumps({
        "id": message_id,
        "from": headers.get("From", "Unknown"),
        "to": headers.get("To", "Unknown"),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", "Unknown"),
        "body": body[:5000],
    }, indent=2)


def _extract_body(payload: dict) -> str:
    text = _find_part(payload, "text/plain")
    if text:
        return text
    html = _find_part(payload, "text/html")
    if html:
        return _strip_html(html)
    return "(no readable body found)"


def _find_part(payload: dict, mime: str) -> str | None:
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
    import re
    text = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    import html as html_mod
    text = html_mod.unescape(text)
    lines = [' '.join(line.split()) for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text.strip()


def _send(to: str, subject: str, body: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Work email sent to {to} with subject: {subject}"


def _reply(message_id: str, body: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    original = service.users().messages().get(
        userId="me", id=message_id, format="metadata"
    ).execute()
    headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
    thread_id = original.get("threadId")

    reply_msg = MIMEText(body)
    reply_msg["to"] = headers.get("Reply-To", headers.get("From", ""))
    reply_msg["subject"] = "Re: " + headers.get("Subject", "").removeprefix("Re: ")
    reply_msg["In-Reply-To"] = headers.get("Message-ID", "")
    reply_msg["References"] = headers.get("Message-ID", "")

    raw = base64.urlsafe_b64encode(reply_msg.as_bytes()).decode()
    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    service.users().messages().send(userId="me", body=send_body).execute()
    return f"Reply sent to {reply_msg['to']} in thread: {headers.get('Subject', '')}"


def _create_draft(to: str, subject: str, body: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return f"Draft created (ID: {draft['id']}) to {to} with subject: {subject}"


def _trash(message_id: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    service.users().messages().trash(userId="me", id=message_id).execute()
    return f"Email {message_id} moved to trash."


def _modify_labels(message_ids: str, add_labels: list = None, remove_labels: list = None, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    ids = [mid.strip() for mid in message_ids.split(",")]
    body = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels
    for mid in ids:
        service.users().messages().modify(userId="me", id=mid, body=body).execute()
    count = len(ids)
    return f"Updated {count} email(s)."


def _toggle_star(message_id: str, account_id=None) -> str:
    service = _get_gmail_service(account_id)
    msg = service.users().messages().get(userId="me", id=message_id, format="minimal").execute()
    labels = msg.get("labelIds", [])
    if "STARRED" in labels:
        service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["STARRED"]}
        ).execute()
        return f"Email {message_id} unstarred."
    else:
        service.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": ["STARRED"]}
        ).execute()
        return f"Email {message_id} starred."


def _list_labels(account_id=None) -> str:
    service = _get_gmail_service(account_id)
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    output = []
    for label in sorted(labels, key=lambda l: l.get("name", "")):
        output.append({
            "id": label["id"],
            "name": label.get("name", label["id"]),
            "type": label.get("type", "user"),
        })
    return json.dumps(output, indent=2)


# ─── Handler ───────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "work_email_get_unread":
            return _get_unread(args.get("max_results", 10), account_id=account_id)
        elif tool_name == "work_email_search":
            return _search(args["query"], args.get("max_results", 5), account_id=account_id)
        elif tool_name == "work_email_read_email":
            return _read_email(args["message_id"], account_id=account_id)
        elif tool_name == "work_email_send":
            return _send(args["to"], args["subject"], args["body"], account_id=account_id)
        elif tool_name == "work_email_reply":
            return _reply(args["message_id"], args["body"], account_id=account_id)
        elif tool_name == "work_email_create_draft":
            return _create_draft(args["to"], args["subject"], args["body"], account_id=account_id)
        elif tool_name == "work_email_trash":
            return _trash(args["message_id"], account_id=account_id)
        elif tool_name == "work_email_mark_read":
            return _modify_labels(args["message_ids"], remove_labels=["UNREAD"], account_id=account_id)
        elif tool_name == "work_email_mark_unread":
            return _modify_labels(args["message_ids"], add_labels=["UNREAD"], account_id=account_id)
        elif tool_name == "work_email_toggle_star":
            return _toggle_star(args["message_id"], account_id=account_id)
        elif tool_name == "work_email_list_labels":
            return _list_labels(account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Work email error: {e}"
