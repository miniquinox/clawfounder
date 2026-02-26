#!/bin/bash
echo "🐙 Installing GitHub connector..."
uv pip install -r "$(dirname "$0")/../../requirements.txt"
echo ""
echo "✅ Done! Set in your .env:"
echo "   GITHUB_TOKEN=your_personal_access_token"
echo ""
