#!/bin/bash
echo "⚡ Installing Supabase connector..."
pip3 install -r "$(dirname "$0")/requirements.txt"
echo ""
echo "✅ Done! Set in your .env:"
echo "   SUPABASE_URL=https://your-project.supabase.co"
echo "   SUPABASE_SERVICE_KEY=your_service_role_key"
echo ""
