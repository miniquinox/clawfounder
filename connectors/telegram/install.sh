#!/bin/bash
echo "💬 Installing Telegram connector..."
uv pip install -r "$(dirname "$0")/../../requirements.txt"
echo ""
echo "✅ Done! Set these in your .env:"
echo "   TELEGRAM_BOT_TOKEN=your_bot_token"
echo "   TELEGRAM_CHAT_ID=your_chat_id"
echo ""
