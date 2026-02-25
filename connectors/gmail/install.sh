#!/bin/bash
echo "📧 Installing Gmail connector..."
pip3 install -r "$(dirname "$0")/requirements.txt"
echo ""
echo "✅ Done! Now:"
echo "  1. Get OAuth credentials from Google Cloud Console"
echo "  2. Set in your .env:"
echo "     GMAIL_CREDENTIALS_FILE=path/to/credentials.json"
echo ""
