"""
Gmail connector — Read, search, and send emails via the Gmail API.
"""

import os
import json
import base64
from email.mime.text import MIMEText

TOOLS = [
    {
        "name": "gmail_get_unread",
        "description": "Fetch unread emails from Gmail. Returns sender, subject, and snippet for each.",
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
        "description": "Search Gmail with a query string (same syntax as Gmail search bar). Example: 'from:boss subject:urgent'",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                },
            },
            "required": ["query"],
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


def _get_gmail_service():
    """Build and return the Gmail API service using OAuth credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Gmail dependencies not installed. Run: bash connectors/gmail/install.sh"
        )

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    creds_file = os.environ.get("GMAIL_CREDENTIALS_FILE", "credentials.json")
    token_file = os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json")

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_file):
                raise FileNotFoundError(
                    f"Gmail credentials file not found: {creds_file}. "
                    f"Set GMAIL_CREDENTIALS_FILE in your .env"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


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
        msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="metadata").execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
        })

    return json.dumps(output, indent=2)


def _search(query: str, max_results: int = 10) -> str:
    service = _get_gmail_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return f"No emails found for query: {query}"

    output = []
    for msg_ref in messages:
        msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="metadata").execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append({
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", "Unknown"),
            "snippet": msg.get("snippet", ""),
        })

    return json.dumps(output, indent=2)


def _send(to: str, subject: str, body: str) -> str:
    service = _get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to} with subject: {subject}"


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "gmail_get_unread":
            return _get_unread(args.get("max_results", 10))
        elif tool_name == "gmail_search":
            return _search(args["query"], args.get("max_results", 10))
        elif tool_name == "gmail_send":
            return _send(args["to"], args["subject"], args["body"])
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Gmail error: {e}"
