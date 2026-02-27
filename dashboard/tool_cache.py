"""
ClawFounder — Shared Tool Cache

File-based TTL cache for connector tool results. Shared across all agents
(chat, voice, briefing) since each runs as a separate process.

Cache files are stored in ~/.clawfounder/cache/ as JSON.
"""

import json
import hashlib
import time
from pathlib import Path

_CACHE_DIR = Path.home() / ".clawfounder" / "cache"

# Default TTL per connector (seconds)
DEFAULT_TTL = 120  # 2 minutes

CONNECTOR_TTLS = {
    "gmail": 120,         # 2 min — emails change frequently
    "work_email": 120,
    "github": 180,        # 3 min — notifications are less volatile
    "telegram": 60,       # 1 min — messages are real-time
    "whatsapp": 60,
    "yahoo_finance": 300, # 5 min — stock prices don't change that fast for our purposes
    "firebase": 180,
    "supabase": 180,
}

# Briefing cache (the full gathered data) gets a longer TTL
BRIEFING_TTL = 300  # 5 minutes


def _cache_key(tool_name: str, args: dict, account_id: str = None) -> str:
    """Generate a deterministic cache key from tool name, args, and account."""
    key_data = json.dumps({"tool": tool_name, "args": args, "account": account_id}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()


def get(tool_name: str, args: dict, account_id: str = None, connector: str = None) -> str | None:
    """Return cached result if it exists and hasn't expired. None otherwise."""
    key = _cache_key(tool_name, args, account_id)
    cache_file = _CACHE_DIR / f"{key}.json"

    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        ttl = CONNECTOR_TTLS.get(connector, DEFAULT_TTL)
        if time.time() - data["ts"] < ttl:
            return data["result"]
        # Expired — clean up
        cache_file.unlink(missing_ok=True)
    except Exception:
        cache_file.unlink(missing_ok=True)

    return None


def put(tool_name: str, args: dict, result: str, account_id: str = None):
    """Store a tool result in the cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(tool_name, args, account_id)
    cache_file = _CACHE_DIR / f"{key}.json"

    try:
        cache_file.write_text(json.dumps({
            "ts": time.time(),
            "tool": tool_name,
            "result": result,
        }))
    except Exception:
        pass  # Cache write failure is non-fatal


def get_briefing(connectors_key: str) -> dict | None:
    """Return cached briefing gathered data if fresh. None otherwise."""
    cache_file = _CACHE_DIR / f"briefing_{connectors_key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        if time.time() - data["ts"] < BRIEFING_TTL:
            return data["gathered"]
    except Exception:
        pass

    return None


def put_briefing(connectors_key: str, gathered: dict):
    """Cache the full briefing gathered data."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"briefing_{connectors_key}.json"

    try:
        cache_file.write_text(json.dumps({
            "ts": time.time(),
            "gathered": gathered,
        }, default=str))
    except Exception:
        pass


def clear():
    """Clear all cached data."""
    if _CACHE_DIR.exists():
        for f in _CACHE_DIR.iterdir():
            try:
                f.unlink()
            except Exception:
                pass
