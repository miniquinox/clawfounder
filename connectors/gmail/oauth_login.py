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
import argparse
from pathlib import Path

_DEFAULT_TOKEN_FILE = Path.home() / ".clawfounder" / "gmail_personal.json"
_CLIENT_SECRET = Path.home() / ".clawfounder" / "gmail_client_secret.json"

_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token-file', type=str, default=None,
                        help='Override the token file path (for non-default accounts)')
    args = parser.parse_args()
    _TOKEN_FILE = Path(args.token_file) if args.token_file else _DEFAULT_TOKEN_FILE

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

        # Don't open browser — emit auth URL as JSON to stdout instead.
        # The dashboard frontend opens it in a popup window.
        # Double braces {{ }} produce literal braces in str.format().
        creds = flow.run_local_server(
            port=0,
            prompt="consent",
            open_browser=False,
            authorization_prompt_message='{{"auth_url": "{url}"}}',
            success_message="✅ Gmail connected! You can close this tab.",
        )

        # Detect the user's email
        email = None

        # Try id_token (may be a dict or a JWT string depending on library version)
        id_token = getattr(creds, "id_token", None)
        if isinstance(id_token, dict):
            email = id_token.get("email")

        # Fallback: call userinfo API with the access token
        if not email and creds.token:
            try:
                import urllib.request
                req = urllib.request.Request(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                resp = urllib.request.urlopen(req, timeout=5)
                user_data = json.loads(resp.read())
                email = user_data.get("email")
            except Exception:
                pass

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
