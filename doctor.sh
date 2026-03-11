#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# 🦀 ClawFounder Doctor — Diagnose your setup
# Usage: bash doctor.sh
# ──────────────────────────────────────────────────────────────────

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0

ok()   { echo -e "  ${GREEN}✔${NC} $1"; ((PASS++)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; ((WARN++)); }
fail() { echo -e "  ${RED}✘${NC} $1"; ((FAIL++)); }
section() { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }

echo -e "${BOLD}"
echo "  🦀 ClawFounder Doctor"
echo -e "${DIM}  ─────────────────────────${NC}"

# ── System dependencies ──────────────────────────────────────────

section "System"

if command -v python3 &>/dev/null; then
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYMAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PYMINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PYMAJOR" -ge 3 ] && [ "$PYMINOR" -ge 10 ]; then
        ok "Python $PYVER"
    else
        warn "Python $PYVER (3.10+ recommended)"
    fi
else
    fail "python3 not found — install from https://python.org"
fi

if command -v node &>/dev/null; then
    NODEVER=$(node --version | tr -d 'v')
    NODEMAJOR=$(echo "$NODEVER" | cut -d. -f1)
    if [ "$NODEMAJOR" -ge 18 ]; then
        ok "Node.js v$NODEVER"
    else
        warn "Node.js v$NODEVER (18+ recommended)"
    fi
else
    fail "node not found — install from https://nodejs.org"
fi

if command -v npm &>/dev/null; then
    ok "npm $(npm --version)"
else
    fail "npm not found"
fi

# ── Virtual environment ──────────────────────────────────────────

section "Python Environment"

if command -v uv &>/dev/null; then
    ok "uv $(uv --version)"
else
    fail "uv not found — install from https://docs.astral.sh/uv/"
fi

if [ -d ".venv" ]; then
    ok ".venv/ exists"
elif [ -d "venv" ]; then
    warn "Legacy venv/ found — consider switching: uv venv"
else
    fail ".venv/ missing — run: uv venv"
fi

# Activate venv for package checks
VENV_ACTIVATE=""
if [ -f ".venv/bin/activate" ]; then
    VENV_ACTIVATE=".venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    VENV_ACTIVATE="venv/bin/activate"
fi

if [ -n "$VENV_ACTIVATE" ]; then
    source "$VENV_ACTIVATE"

    # Check core packages
    for pkg in dotenv requests; do
        if python3 -c "import $pkg" 2>/dev/null; then
            ok "python: $pkg"
        else
            fail "python: $pkg missing — run: uv pip install -r requirements.txt"
        fi
    done

    # Check google-genai
    if python3 -c "from google import genai" 2>/dev/null; then
        ok "python: google-genai"
    else
        fail "python: google-genai missing — run: uv pip install google-genai"
    fi
fi

# ── Dashboard ────────────────────────────────────────────────────

section "Dashboard"

if [ -d "dashboard/node_modules" ]; then
    ok "dashboard/node_modules/ exists"
else
    fail "dashboard/node_modules/ missing — run: cd dashboard && npm install"
fi

if [ -f "dashboard/package.json" ]; then
    ok "dashboard/package.json"
else
    fail "dashboard/package.json missing"
fi

if [ -f "dashboard/server.js" ]; then
    ok "dashboard/server.js"
else
    fail "dashboard/server.js missing"
fi

# ── Environment variables ────────────────────────────────────────

section "API Keys (.env)"

if [ -f ".env" ]; then
    ok ".env file exists"
    
    # Check for at least one LLM provider
    HAS_LLM=false
    
    GEMINI=$(grep -E "^GEMINI_API_KEY=.+" .env 2>/dev/null | grep -v "^#" | cut -d= -f2 | sed 's/#.*//' | xargs)
    if [ -n "$GEMINI" ]; then
        ok "GEMINI_API_KEY is set"
        HAS_LLM=true
    else
        warn "GEMINI_API_KEY not set"
    fi
    
    OPENAI=$(grep -E "^OPENAI_API_KEY=.+" .env 2>/dev/null | grep -v "^#" | cut -d= -f2 | sed 's/#.*//' | xargs)
    if [ -n "$OPENAI" ]; then
        ok "OPENAI_API_KEY is set"
        HAS_LLM=true
    else
        warn "OPENAI_API_KEY not set (optional)"
    fi
    
    ANTHROPIC=$(grep -E "^ANTHROPIC_API_KEY=.+" .env 2>/dev/null | grep -v "^#" | cut -d= -f2 | sed 's/#.*//' | xargs)
    if [ -n "$ANTHROPIC" ]; then
        ok "ANTHROPIC_API_KEY is set"
        HAS_LLM=true
    else
        warn "ANTHROPIC_API_KEY not set (optional)"
    fi
    
    if [ "$HAS_LLM" = false ]; then
        fail "No LLM provider configured — set at least one API key in .env"
    fi
else
    fail ".env missing — run: cp .env.example .env"
fi

# ── Connectors ───────────────────────────────────────────────────

section "Connectors"

CONNECTOR_COUNT=0
for dir in connectors/*/; do
    name=$(basename "$dir")
    [ "$name" = "_template" ] && continue
    
    if [ -f "$dir/connector.py" ]; then
        ok "$name"
        ((CONNECTOR_COUNT++))
    else
        warn "$name/ missing connector.py"
    fi
done

if [ "$CONNECTOR_COUNT" -eq 0 ]; then
    warn "No connectors found"
else
    echo -e "  ${DIM}$CONNECTOR_COUNT connector(s) found${NC}"
fi

# ── Connectivity ─────────────────────────────────────────────────

section "Connectivity"

# Check Firebase CLI auth
FIREBASE_CONFIG="$HOME/.config/configstore/firebase-tools.json"
if [ -f "$FIREBASE_CONFIG" ]; then
    if grep -q "refresh_token" "$FIREBASE_CONFIG" 2>/dev/null; then
        ok "Firebase CLI authenticated"
    else
        warn "Firebase CLI config exists but no token — run: npx firebase-tools login"
    fi
else
    warn "Firebase CLI not authenticated (optional) — run: npx firebase-tools login"
fi

# Check Gmail auth
GMAIL_TOKEN="$HOME/.clawfounder/gmail_token.json"
if [ -f "$GMAIL_TOKEN" ]; then
    ok "Gmail authenticated"
else
    warn "Gmail not authenticated (optional) — sign in via the dashboard"
fi

# Check if ports are available
if lsof -ti :5173 &>/dev/null; then
    warn "Port 5173 in use (Vite may already be running)"
else
    ok "Port 5173 available"
fi

if lsof -ti :3001 &>/dev/null; then
    warn "Port 3001 in use (API server may already be running)"
else
    ok "Port 3001 available"
fi

# ── Summary ──────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}  ── Summary ──${NC}"
echo -e "  ${GREEN}✔ $PASS passed${NC}  ${YELLOW}⚠ $WARN warnings${NC}  ${RED}✘ $FAIL errors${NC}"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo -e "  ${RED}${BOLD}Fix the errors above, then run: bash doctor.sh${NC}"
    echo ""
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo ""
    echo -e "  ${YELLOW}Mostly good! Check warnings above.${NC}"
    echo -e "  ${DIM}Ready to launch:${NC} ${CYAN}cd dashboard && npm run dev${NC}"
    echo ""
    exit 0
else
    echo ""
    echo -e "  ${GREEN}${BOLD}Everything looks great! 🦀${NC}"
    echo -e "  ${DIM}Launch:${NC} ${CYAN}cd dashboard && npm run dev${NC}"
    echo ""
    exit 0
fi
