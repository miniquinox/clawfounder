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

## Tools

| Tool | Description |
|------|-------------|
| `work_email_get_unread` | Fetch unread emails (returns sender, subject, date, snippet) |
| `work_email_search` | Search emails with Gmail query syntax |
| `work_email_read_email` | Read full email body by message ID |
| `work_email_send` | Compose and send a new email |
| `work_email_reply` | Reply to an existing email thread (maintains conversation) |
| `work_email_forward` | Forward a work email to a new recipient (includes original body) |
| `work_email_create_draft` | Create a draft email (saved but NOT sent) |
| `work_email_trash` | Move an email to the trash |
| `work_email_mark_read` | Mark emails as read (supports multiple IDs) |
| `work_email_mark_unread` | Mark emails as unread (supports multiple IDs) |
| `work_email_toggle_star` | Star or unstar an email |
| `work_email_list_labels` | List all Gmail labels/folders |

## Search Query Examples

Use `work_email_search` with these queries (same syntax as the Gmail search bar):

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

- **"Read my latest work email from the CEO"** → `work_email_search` with `from:ceo` max_results=1, then `work_email_read_email`
- **"Reply to that email"** → `work_email_reply` with the message_id and reply body
- **"Forward that email to the team lead"** → `work_email_forward` with the message_id and recipient
- **"Draft a follow-up to the client"** → `work_email_search` to find it, then `work_email_create_draft`
- **"Mark all meeting emails as read"** → `work_email_search` for them, then `work_email_mark_read`
- **"Star that important email"** → `work_email_toggle_star` with the message_id
- **"What labels do I have?"** → `work_email_list_labels`
- **"Delete that spam email"** → `work_email_trash` with the message_id
