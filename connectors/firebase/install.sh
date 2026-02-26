#!/bin/bash
echo "🔥 Installing Firebase connector..."
uv pip install -r "$(dirname "$0")/../../requirements.txt"
echo ""
echo "✅ Done! Set in your .env:"
echo "   FIREBASE_PROJECT_ID=your-project-id"
echo "   FIREBASE_CREDENTIALS_FILE=path/to/service-account.json"
echo ""
