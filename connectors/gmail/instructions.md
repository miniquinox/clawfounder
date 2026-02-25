# Gmail Connector

Connects ClawFounder to your Gmail account using the Gmail API (Google's official Python client).

## What It Does

- Read unread emails
- Search emails by query
- Read full email body
- Send emails

## Authentication

Gmail uses **Application Default Credentials** (ADC) via the gcloud CLI — no Google Cloud project or credentials file needed.

### Quick Setup

```bash
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send
```

This opens a browser window to authorize access. After that, gcloud saves credentials locally and the connector picks them up automatically.

You can also click **Sign in with Google** on the Gmail card in the ClawFounder dashboard — it runs the same command for you.

> **Note:** If you previously used OAuth with a `credentials.json` file, the existing token at `~/.clawfounder/gmail_token.json` will continue to work. No migration needed.

## Setup

```bash
cd connectors/gmail
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `gmail_get_unread` | Fetch unread emails (returns sender, subject, date, snippet) |
| `gmail_search` | Search emails with a Gmail query (e.g., "from:boss subject:urgent") |
| `gmail_read_email` | Read the full body of an email by message ID |
| `gmail_send` | Send an email |

## Testing

```bash
python3 -m pytest connectors/gmail/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Do I have any unread emails?"
```
