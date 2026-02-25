#!/bin/bash
echo "📧 Installing Gmail connector..."
uv pip install -r "$(dirname "$0")/requirements.txt"
echo ""
echo "✅ Done! Sign in with Google via the ClawFounder dashboard."
echo ""
