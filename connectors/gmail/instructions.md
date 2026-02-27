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

## Tools

| Tool | Description |
|------|-------------|
| `gmail_get_unread` | Fetch unread emails (returns sender, subject, date, snippet) |
| `gmail_search` | Search emails with Gmail query syntax |
| `gmail_read_email` | Read full email body by message ID |
| `gmail_send` | Compose and send a new email |
| `gmail_reply` | Reply to an existing email thread (maintains conversation) |
| `gmail_forward` | Forward an email to a new recipient (includes original body) |
| `gmail_create_draft` | Create a draft email (saved but NOT sent) |
| `gmail_trash` | Move an email to the trash |
| `gmail_mark_read` | Mark emails as read (supports multiple IDs) |
| `gmail_mark_unread` | Mark emails as unread (supports multiple IDs) |
| `gmail_toggle_star` | Star or unstar an email |
| `gmail_list_labels` | List all Gmail labels/folders |

## Search Query Examples

Use `gmail_search` with these queries (same syntax as the Gmail search bar):

| Query | What it finds |
|-------|---------------|
| `in:drafts` | Draft emails |
| `in:sent` | Sent emails |
| `in:trash` | Trashed emails |
| `is:starred` | Starred emails |
| `is:unread` | Unread emails |
| `is:read` | Read emails |
| `from:john@example.com` | Emails from a specific sender |
| `to:jane@example.com` | Emails sent to a specific recipient |
| `subject:meeting` | Emails with "meeting" in the subject |
| `newer_than:7d` | Emails from the last 7 days |
| `older_than:30d` | Emails older than 30 days |
| `has:attachment` | Emails with any attachments |
| `has:attachment filename:pdf` | Emails with PDF attachments |
| `label:important` | Important emails |
| `category:promotions` | Promotional emails |
| `larger:5M` | Emails larger than 5MB |
| `from:boss subject:urgent newer_than:7d` | Combined search |

## Workflow Examples

- **"Read my latest email from John"** → `gmail_search` with `from:john` max_results=1, then `gmail_read_email`
- **"Reply to that email"** → `gmail_reply` with the message_id and reply body
- **"Forward that email to Sarah"** → `gmail_forward` with the message_id and recipient
- **"Draft a follow-up to the meeting email"** → `gmail_search` to find it, then `gmail_create_draft`
- **"Mark all emails from newsletters as read"** → `gmail_search` for them, then `gmail_mark_read`
- **"Star that important email"** → `gmail_toggle_star` with the message_id
- **"What labels do I have?"** → `gmail_list_labels`
- **"Delete that spam email"** → `gmail_trash` with the message_id
