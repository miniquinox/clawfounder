#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# 🦀 ClawFounder — One-command install
# Usage: bash install.sh
# ──────────────────────────────────────────────────────────────────
set -e

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

step() { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }
ok()   { echo -e "  ${GREEN}✔${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✘${NC} $1"; }

echo -e "${BOLD}"
echo "  🦀 ClawFounder Installer"
echo -e "${DIM}  ─────────────────────────${NC}"
echo ""

# ── Check prerequisites ──────────────────────────────────────────

step "Checking prerequisites..."

if ! command -v node &>/dev/null; then
    fail "node not found. Install Node.js 18+ from https://nodejs.org"
    exit 1
fi
NODEVER=$(node --version)
ok "Node.js $NODEVER"

if ! command -v npm &>/dev/null; then
    fail "npm not found. It should come with Node.js."
    exit 1
fi
ok "npm $(npm --version)"

# ── Install uv if needed ─────────────────────────────────────────

step "Setting up Python environment (uv)..."

if ! command -v uv &>/dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    ok "Installed uv"
else
    ok "uv $(uv --version)"
fi

# ── Python virtual environment ───────────────────────────────────

if [ ! -d ".venv" ]; then
    uv venv
    ok "Created .venv/"
else
    ok ".venv/ already exists"
fi

# ── Python dependencies ──────────────────────────────────────────

step "Installing Python dependencies..."
uv pip install -r requirements.txt
ok "Core dependencies installed"

# Install connector requirements if they exist
for req in connectors/*/requirements.txt; do
    if [ -f "$req" ]; then
        connector=$(basename $(dirname "$req"))
        uv pip install -r "$req" 2>/dev/null && ok "$connector dependencies" || warn "$connector deps failed (non-critical)"
    fi
done

# ── Dashboard dependencies ───────────────────────────────────────

step "Installing dashboard dependencies..."

if [ -d "dashboard" ]; then
    cd dashboard
    npm install --silent 2>/dev/null
    ok "Dashboard npm packages installed"
    cd ..
else
    fail "dashboard/ directory not found"
    exit 1
fi

# ── Environment file ─────────────────────────────────────────────

step "Setting up environment..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ok "Created .env from .env.example"
        warn "Edit .env to add your API keys"
    else
        touch .env
        ok "Created empty .env"
        warn "Add your API keys to .env"
    fi
else
    ok ".env already exists"
fi

# ── Done ─────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}  ✅ Installation complete!${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "  ${DIM}1.${NC} Add your API keys to ${BOLD}.env${NC}"
echo -e "  ${DIM}2.${NC} Run: ${CYAN}cd dashboard && npm run dev${NC}"
echo -e "  ${DIM}3.${NC} Open: ${CYAN}http://localhost:5173${NC}"
echo ""
echo -e "  ${DIM}Or check your setup:${NC} ${CYAN}bash doctor.sh${NC}"
echo ""
