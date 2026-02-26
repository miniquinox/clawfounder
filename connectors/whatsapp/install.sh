#!/bin/bash
echo "Installing whatsapp connector..."
uv pip install -r "$(dirname "$0")/../../requirements.txt"
echo ""
echo "Done! Now set these environment variables in your .env file:"
echo "   WHATSAPP_ACCESS_TOKEN=your_token_here"
echo "   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here"
echo "   WHATSAPP_DEFAULT_RECIPIENT=14155551234  (optional)"
echo ""
