"""
OAuth login helper for personal Gmail accounts.

Uses InstalledAppFlow to perform a local OAuth consent flow using
the user's own OAuth client credentials (stored at
~/.clawfounder/gmail_client_secret.json).

This bypasses the gcloud client, which is blocked by Google for
sensitive Gmail scopes on personal accounts.
"""

import json
import sys
from pathlib import Path

_TOKEN_FILE = Path.home() / ".clawfounder" / "gmail_personal.json"
_CLIENT_SECRET = Path.home() / ".clawfounder" / "gmail_client_secret.json"

_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    if not _CLIENT_SECRET.exists():
        print(json.dumps({
            "error": "client_secret_missing",
            "message": "OAuth client credentials not found. Please set them up first.",
        }))
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            str(_CLIENT_SECRET),
            scopes=_SCOPES,
        )

        # Run local server flow — opens browser for consent
        creds = flow.run_local_server(
            port=8089,
            prompt="consent",
            success_message="✅ Gmail connected! You can close this tab.",
        )

        # Detect the user's email from the id_token
        email = None
        if hasattr(creds, "id_token") and creds.id_token:
            email = creds.id_token.get("email")

        # Build token data to save
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or _SCOPES),
        }
        if email:
            token_data["_email"] = email

        # Try to detect a quota project
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                token_data["quota_project_id"] = result.stdout.strip()
        except Exception:
            pass

        # Save
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

        print(json.dumps({
            "success": True,
            "email": email,
            "token_file": str(_TOKEN_FILE),
        }))

    except Exception as e:
        print(json.dumps({
            "error": "oauth_failed",
            "message": str(e),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
