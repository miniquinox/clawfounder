# Telegram Connector

Connects ClawFounder to Telegram using the [python-telegram-bot](https://python-telegram-bot.org/) library.

## What It Does

- Send messages to a chat
- Get recent messages from a chat
- Send files/documents

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

## Available Tools

| Tool | Description |
|---|---|
| `telegram_send_message` | Send a text message to a Telegram chat |
| `telegram_get_updates` | Get recent incoming messages |

## Testing

```bash
python3 -m pytest connectors/telegram/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Send me a message on Telegram saying hello"
```
