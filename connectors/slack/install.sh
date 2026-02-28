#!/bin/bash
echo "💬 Installing Slack connector..."
uv pip install -r "$(dirname "$0")/requirements.txt"
echo "✅ Done! Set in your .env:"
echo "   SLACK_BOT_TOKEN=xoxb-your-bot-token"
