# Gmail (Personal) — Email Connector

Connect your personal @gmail.com account to ClawFounder.

## Prerequisites

**One-time OAuth Setup (~2 minutes):**
1. Go to [console.cloud.google.com → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
2. Choose **External** → Create → Fill in app name (e.g. "ClawFounder") and your email
3. Add scopes: `gmail.readonly` and `gmail.send`
4. Under "Test users", add **your personal Gmail address**
5. Go to [Credentials](https://console.cloud.google.com/apis/credentials) → Create → **OAuth 2.0 Client ID** → **Desktop app**
6. Copy the **Client ID** and **Client Secret** into the dashboard

This is only needed once. After that, just click "Sign in with Google".

## Setup

1. Enter your OAuth Client ID and Client Secret in the Gmail card
2. Click **"Sign in with Google"**
3. Authorize in the browser

## Tools

| Tool | Description |
|------|-------------|
| `gmail_get_unread` | Fetch unread emails |
| `gmail_search` | Search emails with Gmail query syntax |
| `gmail_read_email` | Read full email body by ID |
| `gmail_send` | Send an email |

## Search Query Examples

| Query | What it finds |
|-------|---------------|
| `in:drafts` | Draft emails |
| `in:sent` | Sent emails |
| `is:starred` | Starred emails |
| `from:john@example.com` | Emails from a specific sender |
| `subject:meeting` | Emails with "meeting" in the subject |
| `newer_than:7d` | Emails from the last 7 days |
| `has:attachment filename:pdf` | Emails with PDF attachments |
| `label:important` | Important emails |
