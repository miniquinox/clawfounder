# Telegram Connector

Connects ClawFounder to Telegram using the Telegram Bot API via HTTP requests.

## What It Does

- Send text messages, photos, documents, and locations
- Get recent incoming messages
- Forward, edit, delete, and pin messages
- Get chat/group/channel info

## Authentication

1. Open Telegram and talk to [@BotFather](https://t.me/BotFather)
2. Create a new bot: `/newbot`
3. Copy the bot token
4. Find your chat ID: talk to [@userinfobot](https://t.me/userinfobot)

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your chat ID (for sending messages to yourself) | Yes |

## Setup

```bash
cd connectors/telegram
bash install.sh
```

## Available Tools (10)

| Tool | Description |
|---|---|
| `telegram_send_message` | Send a text message to a Telegram chat |
| `telegram_get_updates` | Get recent incoming messages |
| `telegram_send_photo` | Send a photo by URL or file_id, with optional caption |
| `telegram_send_document` | Send a document/file by URL or file_id, with optional caption |
| `telegram_send_location` | Send a GPS location to a chat |
| `telegram_forward_message` | Forward a message from one chat to another |
| `telegram_edit_message` | Edit a previously sent text message |
| `telegram_delete_message` | Delete a message from a chat |
| `telegram_pin_message` | Pin a message in a chat |
| `telegram_get_chat` | Get info about a chat/group/channel (title, type, description) |

## Testing

```bash
python3 -m pytest connectors/telegram/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Send me a message on Telegram saying hello"
```
