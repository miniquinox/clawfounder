#!/bin/bash
echo "📦 Installing your_service connector..."
pip3 install -r "$(dirname "$0")/requirements.txt"
echo ""
echo "✅ Done! Now set these environment variables in your .env file:"
echo "   YOUR_API_KEY=your_key_here"
echo ""
