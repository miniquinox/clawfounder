"""
Gmail OAuth helper — spawned by the dashboard.

Modes:
  --url-only              Print auth URL as JSON and exit instantly.
  --exchange-code CODE    Exchange auth code for token, save it, print result.
"""

import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

TOKEN_DIR = Path.home() / ".clawfounder"
TOKEN_FILE = TOKEN_DIR / "gmail_token.json"
REDIRECT_URI = "http://localhost:3001/api/gmail/callback"


def build_flow():
    from google_auth_oauthlib.flow import Flow

    creds_file = os.environ.get("GMAIL_CREDENTIALS_FILE")
    if creds_file:
        p = Path(creds_file) if Path(creds_file).is_absolute() else PROJECT_ROOT / creds_file
        if p.exists():
            flow = Flow.from_client_secrets_file(str(p), scopes=SCOPES, redirect_uri=REDIRECT_URI)
            return flow

    cid = os.environ.get("GMAIL_CLIENT_ID", "")
    secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    if cid:
        return Flow.from_client_config(
            {"installed": {
                "client_id": cid, "client_secret": secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }},
            scopes=SCOPES, redirect_uri=REDIRECT_URI,
        )
    return None


def url_only():
    flow = build_flow()
    if not flow:
        print(json.dumps({"error": "No OAuth credentials configured."}))
        return
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    print(json.dumps({"authUrl": url, "state": state}))


def exchange_code(code):
    flow = build_flow()
    if not flow:
        print(json.dumps({"success": False, "error": "No OAuth credentials."}))
        return

    flow.fetch_token(code=code)
    creds = flow.credentials

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json())

    email = "authenticated"
    try:
        from googleapiclient.discovery import build
        svc = build("oauth2", "v2", credentials=creds)
        email = svc.userinfo().get().execute().get("email", "unknown")
    except Exception:
        pass

    (TOKEN_DIR / "gmail_email.txt").write_text(email)
    print(json.dumps({"success": True, "email": email}))


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--url-only" in args:
        url_only()
    elif "--exchange-code" in args:
        exchange_code(args[args.index("--exchange-code") + 1])
    else:
        print(json.dumps({"error": "Usage: --url-only | --exchange-code CODE"}))
