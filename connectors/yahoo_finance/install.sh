#!/bin/bash
echo "📈 Installing Yahoo Finance connector..."
uv pip install -r "$(dirname "$0")/requirements.txt"
echo ""
echo "✅ Done! No API key needed — yfinance is free and open."
echo ""
