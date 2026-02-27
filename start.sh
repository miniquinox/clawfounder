#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# 🦀 ClawFounder — Start
# Usage: bash start.sh
# Installs deps, sets up credentials, and launches the dashboard.
# ──────────────────────────────────────────────────────────────────
set -e

BOLD='\033[1m' DIM='\033[2m' GREEN='\033[0;32m'
YELLOW='\033[0;33m' CYAN='\033[0;36m' NC='\033[0m'

ok()   { echo -e "  ${GREEN}✔${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
step() { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo -e "${BOLD}\n  🦀 ClawFounder"
echo -e "${DIM}  ─────────────────────────${NC}\n"

# ── Install deps if needed ───────────────────────────────────────

if [ ! -d ".venv" ] || [ ! -d "dashboard/node_modules" ]; then
    echo -e "  ${CYAN}First run — installing dependencies...${NC}\n"
    bash install.sh
    echo ""
fi

# ── Ensure .env exists ───────────────────────────────────────────

if [ ! -f ".env" ]; then
    cp "${DIR}/.env.example" .env 2>/dev/null || touch .env
    ok "Created .env"
fi

# ── Helpers ──────────────────────────────────────────────────────

get_env() { grep -m1 "^$1=" .env 2>/dev/null | cut -d= -f2- | xargs; }

set_env() {
    if grep -q "^$1=" .env 2>/dev/null; then
        [[ "$OSTYPE" == darwin* ]] && sed -i '' "s|^$1=.*|$1=$2|" .env || sed -i "s|^$1=.*|$1=$2|" .env
    else
        echo "$1=$2" >> .env
    fi
}

prompt_key() {
    local env_key="$1" label="$2" url="$3"
    echo ""
    echo -e "  Get a key from: ${CYAN}${url}${NC}"
    echo ""
    read -sp "  Paste your ${label} API key: " input
    echo ""
    if [ -n "$input" ]; then
        set_env "$env_key" "$input"
        ok "${label} API key saved"
    else
        warn "No key entered — set it up later in the Connect tab"
    fi
}

# ── Check for LLM provider ──────────────────────────────────────

step "Checking AI provider..."

GEMINI_KEY=$(get_env GEMINI_API_KEY)
OPENAI_KEY=$(get_env OPENAI_API_KEY)
CLAUDE_KEY=$(get_env ANTHROPIC_API_KEY)

HAS_PROVIDER=false
[ -n "$GEMINI_KEY" ] && ok "Gemini" && HAS_PROVIDER=true
[ -n "$OPENAI_KEY" ] && ok "OpenAI" && HAS_PROVIDER=true
[ -n "$CLAUDE_KEY" ] && ok "Claude" && HAS_PROVIDER=true

if ! $HAS_PROVIDER; then
    echo ""
    echo -e "  ${YELLOW}No AI provider configured.${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} Google Gemini  ${DIM}— Chat + Voice (free)${NC}"
    echo -e "  ${CYAN}2)${NC} OpenAI         ${DIM}— Chat only${NC}"
    echo -e "  ${CYAN}3)${NC} Claude         ${DIM}— Chat only${NC}"
    echo -e "  ${CYAN}4)${NC} Skip"
    echo ""
    read -p "  Choose [1-4]: " choice

    case "$choice" in
        1) prompt_key GEMINI_API_KEY "Gemini" "https://aistudio.google.com/apikey" ;;
        2) prompt_key OPENAI_API_KEY "OpenAI" "https://platform.openai.com/api-keys" ;;
        3) prompt_key ANTHROPIC_API_KEY "Claude" "https://console.anthropic.com/settings/keys" ;;
        *) warn "Skipped" ;;
    esac
fi

# ── Check ADC for Gmail/Firebase (optional) ──────────────────────

step "Checking Google Cloud credentials..."

ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json"

if [ -f "$ADC_FILE" ]; then
    ok "ADC found (Gmail / Firebase)"
elif [ -f "$HOME/.clawfounder/gmail_personal.json" ]; then
    ok "Gmail OAuth token found"
elif command -v gcloud &>/dev/null; then
    echo -e "  ${DIM}Optional — needed for Gmail and Firebase connectors.${NC}"
    read -p "  Set up now? [y/N]: " yn
    if [[ "$yn" =~ ^[Yy] ]]; then
        gcloud auth application-default login \
            --scopes=openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/gmail.modify
        ok "ADC saved"
    else
        warn "Skipped — Gmail/Firebase won't be available"
    fi
else
    warn "gcloud not installed — Gmail/Firebase need it"
fi

# ── Summary + Launch ─────────────────────────────────────────────

step "Ready!"

GEMINI_KEY=$(get_env GEMINI_API_KEY)
OPENAI_KEY=$(get_env OPENAI_API_KEY)
CLAUDE_KEY=$(get_env ANTHROPIC_API_KEY)

echo ""
[ -n "$GEMINI_KEY" ] && echo -e "    ${GREEN}●${NC} Gemini (Chat + Voice)" || echo -e "    ${DIM}○ Gemini${NC}"
[ -n "$OPENAI_KEY" ] && echo -e "    ${GREEN}●${NC} OpenAI" || echo -e "    ${DIM}○ OpenAI${NC}"
[ -n "$CLAUDE_KEY" ] && echo -e "    ${GREEN}●${NC} Claude" || echo -e "    ${DIM}○ Claude${NC}"

echo -e "\n  ${GREEN}${BOLD}Starting ClawFounder...${NC}"
echo -e "  ${DIM}Open${NC} ${CYAN}http://localhost:5173${NC}\n"

cd dashboard
exec npm run dev
