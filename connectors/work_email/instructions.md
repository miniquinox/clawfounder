# Work Email (Google Workspace) — Gmail Connector

Connect your Google Workspace email (@yourcompany.com) to ClawFounder.

## Prerequisites

⚠ **Google Workspace Admin Step (one-time):**
1. Go to [admin.google.com → API Controls](https://admin.google.com/ac/owl/list?tab=configuredApps)
2. Click **"Configure New App"**
3. Search **"Google Auth Library"**
4. Allow for **all company users**
5. Choose **Trusted**
6. Done

This is only needed once by a Workspace admin. Personal @gmail.com accounts do not need this — use the **Gmail** connector instead.

## Setup

Click **"Sign in with Google"** on the Work Email card in the dashboard.
Everything else is automated.

## Tools

| Tool | Description |
|------|-------------|
| `work_email_get_unread` | Fetch unread emails |
| `work_email_search` | Search emails with Gmail query syntax |
| `work_email_read_email` | Read full email body by ID |
| `work_email_send` | Send an email |
