# Gmail Connector

Connects ClawFounder to your Gmail account using the Gmail API (Google's official Python client).

## What It Does

- Read unread emails
- Search emails by query
- Send emails

## Authentication

Gmail uses OAuth 2.0. You need to:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Gmail API**
4. Create **OAuth 2.0 credentials** (Desktop app type)
5. Download the `credentials.json` file

The first time you use this connector, it will open a browser window to authorize access. After that, it saves a token locally so you don't have to re-authorize.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GMAIL_CREDENTIALS_FILE` | Path to your `credentials.json` from Google Cloud Console | Yes |
| `GMAIL_TOKEN_FILE` | Path to store the OAuth token (default: `gmail_token.json`) | No |

## Setup

```bash
cd connectors/gmail
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `gmail_get_unread` | Fetch unread emails (returns sender, subject, snippet) |
| `gmail_search` | Search emails with a Gmail query (e.g., "from:boss subject:urgent") |
| `gmail_send` | Send an email |

## Testing

```bash
python3 -m pytest connectors/gmail/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Do I have any unread emails?"
```
