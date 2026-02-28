# Slack Connector

Connect your Slack workspace to ClawFounder.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (xoxb-...) from your Slack App | Yes |

## Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From Scratch
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `channels:read`, `channels:history` — read public channels
   - `groups:read`, `groups:history` — read private channels
   - `chat:write`, `chat:write.public` — send messages
   - `users:read` — list workspace members
   - `im:read` — read DMs
   - **User Token Scope**: `search:read` — search messages (requires user token)
3. Install App to Workspace → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Paste the token in the field above

## Tools

| Tool | Description |
|------|-------------|
| `slack_list_channels` | List channels and DMs |
| `slack_get_messages` | Get recent messages from a channel |
| `slack_send_message` | Send a message to a channel |
| `slack_search` | Search messages across workspace |
| `slack_list_users` | List workspace members |
| `slack_reply_thread` | Reply to a message thread |

## Workflow Examples

- **"What's happening in #engineering?"** → `slack_get_messages` with channel="engineering"
- **"Send a message to #general"** → `slack_send_message`
- **"Find messages about deployment"** → `slack_search` with query="deployment"
