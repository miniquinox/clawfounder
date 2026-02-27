"""
ClawFounder — Knowledge Base

SQLite-backed cross-service memory. Passively indexes tool call results
and provides full-text search across all connected services.

Storage: ~/.clawfounder/knowledge.db (WAL mode for concurrent reads)
Config:  ~/.clawfounder/knowledge_config.json (user-customizable settings)
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

_CLAWFOUNDER_DIR = Path.home() / ".clawfounder"
_DB_PATH = _CLAWFOUNDER_DIR / "knowledge.db"
_CONFIG_PATH = _CLAWFOUNDER_DIR / "knowledge_config.json"
_db_conn = None
_config_cache = None

# ── Configuration ──────────────────────────────────────────────────

# Default configuration values
_DEFAULT_CONFIG = {
    "version": 1,

    # Data retention
    "retention_days": 90,           # Auto-delete items older than this

    # Search limits
    "default_max_results": 10,      # Default search result count
    "quick_search_max_results": 5,  # Results per entity in quick_search
    "entity_extract_limit": 8,      # Max entities extracted from message

    # Snippet/text truncation
    "snippet_length": 200,          # Max snippet length stored
    "title_display_length": 80,     # Title truncation for display
    "snippet_display_length": 100,  # Snippet truncation for display

    # Cache settings
    "summary_cache_ttl": 300,       # Summary cache TTL in seconds (5 min)

    # Topic extraction - base topics (always included)
    "base_topics": [
        "firebase", "supabase", "api key", "api keys", "deployment", "deploy",
        "production", "staging", "database", "auth", "authentication",
        "payment", "invoice", "contract", "deadline", "meeting", "review",
        "merge", "release", "bug", "fix", "feature", "sprint", "standup",
        "credentials", "password", "token", "secret", "config", "migration",
        "docker", "kubernetes", "ci/cd", "pipeline", "terraform",
    ],

    # User-defined additional topics (extend base_topics)
    "custom_topics": [],

    # Max topics to extract per item
    "max_topics_per_item": 5,
}


def _load_config():
    """Load config from disk, merging with defaults. Cached in memory."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config = _DEFAULT_CONFIG.copy()

    if _CONFIG_PATH.exists():
        try:
            user_config = json.loads(_CONFIG_PATH.read_text())
            # Merge user config into defaults (user values override defaults)
            for key, value in user_config.items():
                if key in config:
                    config[key] = value
        except (json.JSONDecodeError, IOError):
            pass  # Use defaults on error

    _config_cache = config
    return config


def _get_config(key, default=None):
    """Get a single config value."""
    config = _load_config()
    return config.get(key, default)


def save_config(updates):
    """Save config updates to disk. Merges with existing config.

    Args:
        updates: dict of config keys to update

    Returns:
        The updated config dict
    """
    global _config_cache, _topics_cache

    # Load existing user config (not merged with defaults)
    user_config = {}
    if _CONFIG_PATH.exists():
        try:
            user_config = json.loads(_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            pass

    # Update with new values
    user_config.update(updates)
    user_config["version"] = 1

    # Write to disk
    _CLAWFOUNDER_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(user_config, indent=2))

    # Invalidate caches
    _config_cache = None
    _topics_cache = None

    return _load_config()


def get_config():
    """Get the full merged config (defaults + user overrides).

    Returns:
        dict with all config values
    """
    return _load_config().copy()


def reset_config():
    """Reset config to defaults by removing the config file."""
    global _config_cache, _topics_cache
    if _CONFIG_PATH.exists():
        _CONFIG_PATH.unlink()
    _config_cache = None
    _topics_cache = None


_topics_cache = None


def _get_known_topics():
    """Get combined set of base + custom topics. Cached in memory."""
    global _topics_cache
    if _topics_cache is not None:
        return _topics_cache
    config = _load_config()
    topics = set(config.get("base_topics", []))
    topics.update(config.get("custom_topics", []))
    _topics_cache = topics
    return topics

# ── Schema ────────────────────────────────────────────────────────

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS knowledge_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    connector   TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    account_id  TEXT,
    event_date  TEXT,
    indexed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    title       TEXT,
    snippet     TEXT,
    metadata    TEXT DEFAULT '{}',
    UNIQUE(connector, source_id, account_id)
);

CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    value      TEXT NOT NULL,
    normalized TEXT NOT NULL,
    UNIQUE(type, normalized)
);

CREATE TABLE IF NOT EXISTS item_entities (
    item_id   INTEGER NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role      TEXT DEFAULT 'mentioned',
    PRIMARY KEY (item_id, entity_id, role)
);

CREATE INDEX IF NOT EXISTS idx_items_connector ON knowledge_items(connector);
CREATE INDEX IF NOT EXISTS idx_items_event_date ON knowledge_items(event_date);
CREATE INDEX IF NOT EXISTS idx_entities_normalized ON entities(normalized);
CREATE INDEX IF NOT EXISTS idx_item_entities_entity ON item_entities(entity_id);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    title, snippet, entity_text,
    content='knowledge_items', content_rowid='id',
    tokenize='porter unicode61'
);
"""


def _get_db():
    """Get or create the SQLite connection. Creates schema on first call."""
    global _db_conn
    if _db_conn is not None:
        return _db_conn

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=5, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    try:
        conn.executescript(_FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass  # FTS5 may not be available on all builds

    # Auto-cleanup: delete items older than retention period (once per session)
    try:
        retention_days = _get_config("retention_days", 90)
        conn.execute(
            f"DELETE FROM knowledge_items WHERE indexed_at < datetime('now', '-{retention_days} days')"
        )
        conn.commit()
    except Exception:
        pass

    _db_conn = conn
    return conn


# ── Helpers ───────────────────────────────────────────────────────

def _parse_email_address(raw):
    """Parse 'Display Name <email@example.com>' → (name, email)."""
    if not raw or raw == "Unknown":
        return ("", "")
    match = re.match(r'^"?([^"<]*)"?\s*<?([^>]+@[^>]+)>?\s*$', raw.strip())
    if match:
        return (match.group(1).strip(), match.group(2).strip())
    if "@" in raw:
        return ("", raw.strip())
    return (raw.strip(), "")


def _extract_topics(text):
    """Extract topic entities from text using keyword matching."""
    if not text:
        return []
    config = _load_config()
    known_topics = _get_known_topics()
    max_topics = config.get("max_topics_per_item", 5)

    text_lower = text.lower()
    found = []
    for topic in known_topics:
        if topic in text_lower:
            found.append(topic)
    # Jira-style ticket IDs: PROJECT-123
    found.extend(re.findall(r'\b[A-Z]{2,}-\d+\b', text))
    return list(set(found))[:max_topics]


def _parse_date(raw):
    """Best-effort parse of various date formats to ISO 8601."""
    if not raw:
        return None
    # Already ISO 8601
    if re.match(r'^\d{4}-\d{2}-\d{2}', str(raw)):
        return str(raw)[:19]
    # Unix timestamp
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw).isoformat()[:19]
        except Exception:
            return None
    # RFC 2822 (email dates)
    try:
        return parsedate_to_datetime(str(raw)).isoformat()[:19]
    except Exception:
        return str(raw)[:19] if raw else None


# ── Per-Connector Extractors ──────────────────────────────────────

def _truncate_snippet(text, length=None):
    """Truncate text to configured snippet length."""
    if not text:
        return ""
    if length is None:
        length = _get_config("snippet_length", 200)
    return str(text)[:length]


def _extract_gmail(tool_name, result_str, connector, account_id):
    """Extract from gmail_get_unread, gmail_search, gmail_read_email."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else [data]
    out = []

    for email in items:
        if not isinstance(email, dict) or "id" not in email:
            continue

        entities = []
        from_name, from_email = _parse_email_address(email.get("from", ""))
        if from_name:
            entities.append(("person", from_name, "sender"))
        if from_email:
            entities.append(("person", from_email, "sender"))

        to_name, to_email = _parse_email_address(email.get("to", ""))
        if to_name:
            entities.append(("person", to_name, "recipient"))
        if to_email:
            entities.append(("person", to_email, "recipient"))

        subject = email.get("subject", "")
        snippet = _truncate_snippet(email.get("snippet", email.get("body", "")))
        for topic in _extract_topics(subject + " " + snippet):
            entities.append(("topic", topic, "mentioned"))

        out.append({
            "source_id": email["id"],
            "event_date": _parse_date(email.get("date")),
            "title": subject,
            "snippet": snippet,
            "metadata": {"from": email.get("from", ""), "to": email.get("to", "")},
            "entities": entities,
        })

    return out


def _extract_github(tool_name, result_str, account_id):
    """Extract from github_notifications, github_list_prs, github_list_issues, etc."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else [data]
    out = []

    for item in items:
        if not isinstance(item, dict):
            continue

        entities = []

        # Notifications have a different shape
        if tool_name == "github_notifications":
            source_id = f"notif-{item.get('id', '')}"
            repo = item.get("repository", item.get("repo", ""))
            subject = item.get("subject", "")
            if isinstance(subject, dict):
                title = subject.get("title", "")
                subj_type = subject.get("type", "")
            else:
                title = str(subject)
                subj_type = ""
            if repo:
                entities.append(("repo", repo, "mentioned"))
            out.append({
                "source_id": source_id,
                "event_date": _parse_date(item.get("updated_at", item.get("updated", ""))),
                "title": title,
                "snippet": f"{item.get('reason', '')} — {subj_type} in {repo}",
                "metadata": {"repo": repo, "reason": item.get("reason", ""), "type": subj_type},
                "entities": entities,
            })
            continue

        # PRs and Issues
        author = item.get("author", "")
        if author:
            entities.append(("person", author, "author"))

        for assignee in item.get("assignees", []):
            if isinstance(assignee, str):
                entities.append(("person", assignee, "assignee"))

        for label in item.get("labels", []):
            if isinstance(label, str):
                entities.append(("topic", label, "mentioned"))

        repo = item.get("repo", item.get("full_name", ""))
        if repo:
            entities.append(("repo", repo, "mentioned"))

        number = item.get("number", "")
        kind = "pr" if "review" in tool_name or "pr" in tool_name.lower() else "issue"
        source_id = f"{kind}-{repo}-{number}" if repo else f"{kind}-{number}"

        title = item.get("title", "")
        for topic in _extract_topics(title):
            entities.append(("topic", topic, "mentioned"))

        out.append({
            "source_id": source_id,
            "event_date": _parse_date(item.get("created_at", item.get("updated_at", item.get("created", "")))),
            "title": title,
            "snippet": _truncate_snippet(item.get("body", item.get("body_preview", ""))),
            "metadata": {
                "repo": repo, "state": item.get("state", ""),
                "number": number, "url": item.get("url", ""),
            },
            "entities": entities,
        })

    return out


def _extract_telegram(tool_name, result_str, account_id):
    """Extract from telegram_get_updates."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else [data]
    out = []

    for msg in items:
        if not isinstance(msg, dict):
            continue

        entities = []
        sender = msg.get("from", "Unknown")
        if sender and sender != "Unknown":
            entities.append(("person", sender, "sender"))

        text = msg.get("text", "")
        for topic in _extract_topics(text):
            entities.append(("topic", topic, "mentioned"))

        source_id = f"tg-{msg.get('date', '')}-{sender}"

        out.append({
            "source_id": source_id,
            "event_date": _parse_date(msg.get("date")),
            "title": f"Message from {sender}",
            "snippet": _truncate_snippet(text),
            "metadata": {"from": sender},
            "entities": entities,
        })

    return out


def _extract_yahoo_finance(tool_name, result_str, account_id):
    """Extract from yahoo_finance_quote, yahoo_finance_search."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else [data]
    out = []

    for item in items:
        if not isinstance(item, dict):
            continue

        symbol = item.get("symbol", "")
        name = item.get("name", symbol)
        entities = [("ticker", symbol, "mentioned")]
        if name and name != symbol:
            entities.append(("ticker", name, "mentioned"))

        source_id = f"quote-{symbol}-{datetime.now().strftime('%Y%m%d')}"

        out.append({
            "source_id": source_id,
            "event_date": datetime.now().isoformat()[:19],
            "title": f"{symbol} ({name})",
            "snippet": f"Price: {item.get('price', 'N/A')}, Change: {item.get('change_percent', 'N/A')}%",
            "metadata": {
                "symbol": symbol, "price": item.get("price"),
                "change": item.get("change"), "change_percent": item.get("change_percent"),
            },
            "entities": entities,
        })

    return out


def _extract_firebase(tool_name, result_str, args, account_id):
    """Extract from firebase tools."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    items = data if isinstance(data, list) else [data]
    out = []

    for item in items:
        if not isinstance(item, dict):
            continue

        doc_id = item.get("_id", item.get("id", ""))
        doc_path = item.get("_path", "")
        source_id = f"fb-{doc_path or doc_id}"

        entities = [("topic", "firebase", "mentioned")]
        # Extract emails from field values
        for v in item.values():
            if isinstance(v, str) and "@" in v and "." in v:
                entities.append(("person", v, "mentioned"))

        preview = {k: v for k, v in item.items() if not str(k).startswith("_")}

        out.append({
            "source_id": source_id,
            "event_date": datetime.now().isoformat()[:19],
            "title": f"Firestore: {doc_path or doc_id}",
            "snippet": _truncate_snippet(json.dumps(preview, default=str)),
            "metadata": {"path": doc_path, "id": doc_id},
            "entities": entities,
        })

    return out


def _extract_supabase(tool_name, result_str, args, account_id):
    """Extract from supabase tools."""
    try:
        data = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        return []

    table = (args or {}).get("table", "unknown")
    out = []

    for row in data:
        if not isinstance(row, dict):
            continue

        row_id = row.get("id", row.get("_id", ""))
        source_id = f"supa-{table}-{row_id}"

        entities = [("topic", "supabase", "mentioned")]
        for v in row.values():
            if isinstance(v, str) and "@" in v and "." in v:
                entities.append(("person", v, "mentioned"))

        out.append({
            "source_id": source_id,
            "event_date": row.get("created_at", row.get("updated_at", datetime.now().isoformat()[:19])),
            "title": f"{table}/{row_id}",
            "snippet": _truncate_snippet(json.dumps(row, default=str)),
            "metadata": {"table": table},
            "entities": entities,
        })

    return out


# ── Extraction dispatch ───────────────────────────────────────────

_EXTRACTORS = {
    "gmail": lambda tn, r, a, acc: _extract_gmail(tn, r, "gmail", acc),
    "work": lambda tn, r, a, acc: _extract_gmail(tn, r, "work_email", acc),
    "github": lambda tn, r, a, acc: _extract_github(tn, r, acc),
    "telegram": lambda tn, r, a, acc: _extract_telegram(tn, r, acc),
    "yahoo": lambda tn, r, a, acc: _extract_yahoo_finance(tn, r, acc),
    "firebase": lambda tn, r, a, acc: _extract_firebase(tn, r, a, acc),
    "supabase": lambda tn, r, a, acc: _extract_supabase(tn, r, a, acc),
}


# ── Indexing ──────────────────────────────────────────────────────

# Cache entity IDs to avoid repeated SELECTs (type+normalized → id)
_entity_id_cache = {}


def index(connector, tool_name, result, args=None, account_id=None):
    """Index a tool call result into the knowledge base. Never raises."""
    try:
        _index_impl(connector, tool_name, result, args, account_id)
    except Exception:
        pass


def _index_impl(connector, tool_name, result, args, account_id):
    """Actual indexing implementation."""
    if not isinstance(result, str) or not result.strip():
        return

    # Skip non-JSON results (plain text like "Email sent to X")
    if not result.strip().startswith(("{", "[")):
        return

    # Find the right extractor by connector prefix
    extractor = None
    for prefix, fn in _EXTRACTORS.items():
        if connector.startswith(prefix):
            extractor = fn
            break

    if not extractor:
        return

    items = extractor(tool_name, result, args, account_id)
    if not items:
        return

    db = _get_db()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id:
            continue

        # Upsert the knowledge item
        db.execute("""
            INSERT OR REPLACE INTO knowledge_items
                (connector, tool_name, source_id, account_id, event_date, title, snippet, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            connector, tool_name, source_id, account_id,
            item.get("event_date"), item.get("title", ""),
            item.get("snippet", ""), json.dumps(item.get("metadata", {}), default=str),
        ))
        item_id = db.execute(
            "SELECT id FROM knowledge_items WHERE connector=? AND source_id=? AND account_id IS ?",
            (connector, source_id, account_id)
        ).fetchone()
        if not item_id:
            continue
        item_id = item_id[0]

        # Read old FTS values BEFORE updating (needed for correct FTS delete)
        old_title, old_snippet, old_entity_text = "", "", ""
        try:
            old_row = db.execute(
                "SELECT title, snippet FROM knowledge_items WHERE id=?", (item_id,)
            ).fetchone()
            if old_row:
                old_title, old_snippet = old_row[0] or "", old_row[1] or ""
            # Get old entity text for FTS
            old_entities = db.execute("""
                SELECT e.value FROM entities e
                JOIN item_entities ie ON e.id = ie.entity_id
                WHERE ie.item_id = ?
            """, (item_id,)).fetchall()
            old_entity_text = " ".join(r[0] for r in old_entities)
        except Exception:
            pass

        # Delete old entity links for this item (in case of re-index)
        db.execute("DELETE FROM item_entities WHERE item_id=?", (item_id,))

        # Insert entities and link them (with ID caching)
        entity_texts = []
        for etype, evalue, erole in item.get("entities", []):
            if not evalue or not evalue.strip():
                continue
            normalized = evalue.strip().lower()
            entity_texts.append(evalue)

            cache_key = (etype, normalized)
            entity_id = _entity_id_cache.get(cache_key)
            if entity_id is None:
                db.execute(
                    "INSERT OR IGNORE INTO entities (type, value, normalized) VALUES (?, ?, ?)",
                    (etype, evalue.strip(), normalized),
                )
                entity_id = db.execute(
                    "SELECT id FROM entities WHERE type=? AND normalized=?",
                    (etype, normalized),
                ).fetchone()[0]
                _entity_id_cache[cache_key] = entity_id

            db.execute(
                "INSERT OR IGNORE INTO item_entities (item_id, entity_id, role) VALUES (?, ?, ?)",
                (item_id, entity_id, erole),
            )

        # Update FTS index (delete with OLD values, insert with NEW)
        new_title = item.get("title", "")
        new_snippet = item.get("snippet", "")
        entity_text = " ".join(entity_texts)
        try:
            db.execute(
                "INSERT INTO knowledge_fts(knowledge_fts, rowid, title, snippet, entity_text) VALUES('delete', ?, ?, ?, ?)",
                (item_id, old_title, old_snippet, old_entity_text),
            )
        except Exception:
            pass
        try:
            db.execute(
                "INSERT INTO knowledge_fts(rowid, title, snippet, entity_text) VALUES (?, ?, ?, ?)",
                (item_id, new_title, new_snippet, entity_text),
            )
        except Exception:
            pass

    db.commit()


# ── Search ────────────────────────────────────────────────────────

KNOWLEDGE_TOOL_DEF = {
    "name": "search_knowledge",
    "description": (
        "Search the knowledge base for information about people, topics, or events "
        "across ALL connected services (emails, GitHub, messages, finance, databases). "
        "Use this FIRST when the user mentions a person, project, or topic — it may already "
        "have relevant context from past interactions. Examples: 'Mostafa Firebase', "
        "'deployment deadline', 'PR review'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query — person name, topic, keyword, or phrase",
            },
            "connector": {
                "type": "string",
                "description": "Optional: filter to a specific service (gmail, github, telegram, etc.)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 10)",
            },
        },
        "required": ["query"],
    },
}


def search(query, connector=None, max_results=None):
    """Search the knowledge base. Returns JSON string for the LLM."""
    if max_results is None:
        max_results = _get_config("default_max_results", 10)

    db = _get_db()
    results = []
    seen_ids = set()

    # Phase 1: FTS5 full-text search
    try:
        fts_query = _fts5_escape(query)
        sql = """
            SELECT ki.id, ki.connector, ki.tool_name, ki.source_id, ki.event_date,
                   ki.title, ki.snippet, ki.metadata, ki.account_id
            FROM knowledge_fts
            JOIN knowledge_items ki ON knowledge_fts.rowid = ki.id
            WHERE knowledge_fts MATCH ?
        """
        params = [fts_query]
        if connector:
            sql += " AND ki.connector = ?"
            params.append(connector)
        sql += " ORDER BY rank LIMIT ?"
        params.append(max_results)

        for row in db.execute(sql, params):
            if row[0] not in seen_ids:
                seen_ids.add(row[0])
                results.append(_format_row(row))
    except Exception:
        pass  # FTS5 may not be available

    # Phase 2: Entity-based search (catches what FTS might miss)
    try:
        sql = """
            SELECT DISTINCT ki.id, ki.connector, ki.tool_name, ki.source_id, ki.event_date,
                   ki.title, ki.snippet, ki.metadata, ki.account_id
            FROM entities e
            JOIN item_entities ie ON e.id = ie.entity_id
            JOIN knowledge_items ki ON ie.item_id = ki.id
            WHERE e.normalized LIKE ?
        """
        params = [f"%{query.lower().strip()}%"]
        if connector:
            sql += " AND ki.connector = ?"
            params.append(connector)
        sql += " ORDER BY ki.event_date DESC LIMIT ?"
        params.append(max_results)

        for row in db.execute(sql, params):
            if row[0] not in seen_ids:
                seen_ids.add(row[0])
                results.append(_format_row(row))
    except Exception:
        pass

    # Sort by date, cap at max_results
    results.sort(key=lambda r: r.get("date", ""), reverse=True)
    results = results[:max_results]

    if not results:
        return json.dumps({
            "results": [],
            "message": f"No knowledge found for '{query}'. Try searching with a connector tool directly.",
        })

    return json.dumps({"results": results, "count": len(results)}, indent=2, default=str)


def _format_row(row):
    """Format a DB row into a result dict."""
    meta = {}
    try:
        meta = json.loads(row[7]) if row[7] else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "connector": row[1],
        "tool": row[2],
        "source_id": row[3],
        "date": row[4] or "",
        "title": row[5] or "",
        "snippet": row[6] or "",
        "metadata": meta,
        "account": row[8] or "",
    }


def _fts5_escape(query):
    """Escape a query for FTS5. OR-joins each word for broad matching."""
    words = [w.strip() for w in query.strip().split() if w.strip()]
    if not words:
        return '""'
    return " OR ".join(f'"{w}"' for w in words)


# ── Proactive Surfacing ───────────────────────────────────────────

_summary_cache = {"text": None, "ts": 0}


def get_summary():
    """Return a compact summary of knowledge base contents for system prompt.

    Returns top people, repos, and topics. Cached for configurable TTL.
    Returns None if the KB is empty.
    """
    import time
    now = time.time()
    cache_ttl = _get_config("summary_cache_ttl", 300)
    if _summary_cache["text"] is not None and (now - _summary_cache["ts"]) < cache_ttl:
        return _summary_cache["text"]

    try:
        db = _get_db()

        # Top people (by mention count, exclude raw emails)
        people = db.execute("""
            SELECT e.value, COUNT(*) as cnt FROM entities e
            JOIN item_entities ie ON e.id = ie.entity_id
            WHERE e.type = 'person' AND e.value NOT LIKE '%@%'
            GROUP BY e.normalized ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Top repos
        repos = db.execute("""
            SELECT e.value, COUNT(*) as cnt FROM entities e
            JOIN item_entities ie ON e.id = ie.entity_id
            WHERE e.type = 'repo'
            GROUP BY e.normalized ORDER BY cnt DESC LIMIT 5
        """).fetchall()

        # Top topics
        topics = db.execute("""
            SELECT e.value, COUNT(*) as cnt FROM entities e
            JOIN item_entities ie ON e.id = ie.entity_id
            WHERE e.type = 'topic'
            GROUP BY e.normalized ORDER BY cnt DESC LIMIT 5
        """).fetchall()

        # Total item count
        total = db.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]

        if total == 0:
            _summary_cache["text"] = None
            _summary_cache["ts"] = now
            return None

        parts = [f"Knowledge base: {total} items indexed."]
        if people:
            parts.append("Known people: " + ", ".join(f"{p[0]} ({p[1]})" for p in people))
        if repos:
            parts.append("Active repos: " + ", ".join(r[0] for r in repos))
        if topics:
            parts.append("Recent topics: " + ", ".join(t[0] for t in topics))

        result = " | ".join(parts)
        _summary_cache["text"] = result
        _summary_cache["ts"] = now
        return result

    except Exception:
        return None


# Common English words to skip when extracting names from messages (default set)
_BASE_COMMON_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "his", "how", "its", "let",
    "may", "new", "now", "old", "see", "way", "who", "did", "get", "got",
    "him", "hit", "just", "like", "make", "many", "some", "time", "very",
    "when", "come", "made", "find", "here", "know", "take", "want", "does",
    "been", "call", "each", "from", "have", "keep", "last", "long", "much",
    "than", "them", "then", "this", "what", "will", "with", "about", "could",
    "still", "their", "there", "these", "thing", "think", "those", "would",
    "after", "first", "where", "which", "while", "being", "every", "never",
    "other", "right", "since", "under", "using", "could", "email", "check",
    "send", "reply", "read", "show", "tell", "help", "look", "need", "also",
    "please", "thanks", "hey", "what's", "whats", "sure", "yeah", "okay",
    "yes", "any", "should", "doing", "going", "update", "give", "info",
    "I", "I'm", "I've", "I'll", "My", "We", "They", "He", "She", "It",
    "That", "This", "What", "When", "Where", "How", "Why", "Who",
}

# Pre-computed lowercase set (avoids rebuilding per word per message)
_BASE_COMMON_WORDS_LOWER = {w.lower() for w in _BASE_COMMON_WORDS}


def _extract_message_entities(message):
    """Extract potential entity names from a user message for proactive search.

    Looks for: capitalized words (potential names), known topic keywords,
    and @mentions.
    """
    if not message or len(message) < 3:
        return []

    entity_limit = _get_config("entity_extract_limit", 8)
    entities = set()

    # Known topic keywords
    for topic in _extract_topics(message):
        entities.add(topic)

    # @mentions
    for match in re.finditer(r'@(\w+)', message):
        entities.add(match.group(1))

    # Capitalized words that might be names (2+ chars, not at sentence start)
    words = message.split()
    for i, word in enumerate(words):
        clean = re.sub(r'[^\w]', '', word)
        if not clean or len(clean) < 2:
            continue
        # Skip common words
        if clean.lower() in _BASE_COMMON_WORDS_LOWER:
            continue
        # Capitalized word not at sentence start
        if clean[0].isupper() and (i > 0 or len(clean) > 2):
            # Skip ALL-CAPS short words (acronyms like "PR", "API" — handled by topics)
            if clean.isupper() and len(clean) <= 3:
                continue
            entities.add(clean)

    return list(entities)[:entity_limit]


def quick_search(message):
    """Proactive knowledge search based on a user message.

    Extracts entities/topics from the message, searches the KB for each,
    deduplicates, and returns a compact context string.
    Returns None if nothing relevant is found.
    """
    entities = _extract_message_entities(message)
    if not entities:
        return None

    db = _get_db()
    # Quick check: is there any data at all?
    try:
        count = db.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]
        if count == 0:
            return None
    except Exception:
        return None

    config = _load_config()
    max_results = config.get("quick_search_max_results", 5)
    title_len = config.get("title_display_length", 80)
    snippet_len = config.get("snippet_display_length", 100)

    results = []
    seen_ids = set()

    # Batch FTS: combine all entities into one OR query (1 query instead of N)
    try:
        fts_terms = []
        for entity in entities:
            words = [w.strip() for w in entity.strip().split() if w.strip()]
            fts_terms.extend(f'"{w}"' for w in words)
        if fts_terms:
            fts_query = " OR ".join(fts_terms)
            rows = db.execute("""
                SELECT ki.id, ki.connector, ki.tool_name, ki.source_id, ki.event_date,
                       ki.title, ki.snippet, ki.metadata, ki.account_id
                FROM knowledge_fts
                JOIN knowledge_items ki ON knowledge_fts.rowid = ki.id
                WHERE knowledge_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (fts_query, max_results * 2)).fetchall()
            for row in rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    results.append(_format_row(row))
    except Exception:
        pass

    # Batch entity match: combine into one query with OR (1 query instead of N)
    if len(results) < max_results:
        try:
            like_clauses = " OR ".join("e.normalized LIKE ?" for _ in entities)
            like_params = [f"%{e.lower().strip()}%" for e in entities]
            rows = db.execute(f"""
                SELECT DISTINCT ki.id, ki.connector, ki.tool_name, ki.source_id, ki.event_date,
                       ki.title, ki.snippet, ki.metadata, ki.account_id
                FROM entities e
                JOIN item_entities ie ON e.id = ie.entity_id
                JOIN knowledge_items ki ON ie.item_id = ki.id
                WHERE {like_clauses}
                ORDER BY ki.event_date DESC LIMIT ?
            """, like_params + [max_results * 2]).fetchall()
            for row in rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    results.append(_format_row(row))
        except Exception:
            pass

    if not results:
        return None

    # Sort by date, take top N results
    results.sort(key=lambda r: r.get("date", ""), reverse=True)
    results = results[:max_results]

    # Format as compact context string
    lines = []
    for r in results:
        source = r["connector"].replace("_", " ").title()
        date = r["date"][:10] if r["date"] else ""
        title = r["title"][:title_len] if r["title"] else ""
        snippet = r["snippet"][:snippet_len] if r["snippet"] else ""
        line = f"- [{source}] {title}"
        if date:
            line += f" ({date})"
        if snippet and snippet != title:
            line += f": {snippet}"
        lines.append(line)

    return "\n".join(lines)


def clear():
    """Clear all knowledge data."""
    db = _get_db()
    db.execute("DELETE FROM item_entities")
    db.execute("DELETE FROM entities")
    db.execute("DELETE FROM knowledge_items")
    try:
        db.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
    except Exception:
        pass
    db.commit()
