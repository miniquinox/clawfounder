"""
ClawFounder — Knowledge Base

SQLite-backed cross-service memory. Passively indexes tool call results
and provides full-text search across all connected services.

Storage: ~/.clawfounder/knowledge.db (WAL mode for concurrent reads)
"""

import json
import re
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

_DB_PATH = Path.home() / ".clawfounder" / "knowledge.db"
_db_conn = None

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
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    try:
        conn.executescript(_FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass  # FTS5 may not be available on all builds

    # Auto-cleanup: delete items older than 90 days (once per session)
    try:
        conn.execute("DELETE FROM knowledge_items WHERE indexed_at < datetime('now', '-90 days')")
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


KNOWN_TOPICS = {
    "firebase", "supabase", "api key", "api keys", "deployment", "deploy",
    "production", "staging", "database", "auth", "authentication",
    "payment", "invoice", "contract", "deadline", "meeting", "review",
    "merge", "release", "bug", "fix", "feature", "sprint", "standup",
    "credentials", "password", "token", "secret", "config", "migration",
    "docker", "kubernetes", "ci/cd", "pipeline", "terraform",
}


def _extract_topics(text):
    """Extract topic entities from text using keyword matching."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for topic in KNOWN_TOPICS:
        if topic in text_lower:
            found.append(topic)
    # Jira-style ticket IDs: PROJECT-123
    found.extend(re.findall(r'\b[A-Z]{2,}-\d+\b', text))
    return list(set(found))[:5]


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
        snippet = email.get("snippet", email.get("body", ""))[:200]
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
            "snippet": str(item.get("body", item.get("body_preview", "")))[:200],
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
            "snippet": text[:200],
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
            "snippet": json.dumps(preview, default=str)[:200],
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
            "snippet": json.dumps(row, default=str)[:200],
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

        # Delete old entity links for this item (in case of re-index)
        db.execute("DELETE FROM item_entities WHERE item_id=?", (item_id,))

        # Insert entities and link them
        entity_texts = []
        for etype, evalue, erole in item.get("entities", []):
            if not evalue or not evalue.strip():
                continue
            normalized = evalue.strip().lower()
            entity_texts.append(evalue)

            db.execute(
                "INSERT OR IGNORE INTO entities (type, value, normalized) VALUES (?, ?, ?)",
                (etype, evalue.strip(), normalized),
            )
            entity_id = db.execute(
                "SELECT id FROM entities WHERE type=? AND normalized=?",
                (etype, normalized),
            ).fetchone()[0]

            db.execute(
                "INSERT OR IGNORE INTO item_entities (item_id, entity_id, role) VALUES (?, ?, ?)",
                (item_id, entity_id, erole),
            )

        # Update FTS index
        entity_text = " ".join(entity_texts)
        try:
            # Delete old FTS entry
            db.execute(
                "INSERT INTO knowledge_fts(knowledge_fts, rowid, title, snippet, entity_text) VALUES('delete', ?, ?, ?, ?)",
                (item_id, item.get("title", ""), item.get("snippet", ""), ""),
            )
        except Exception:
            pass
        try:
            db.execute(
                "INSERT INTO knowledge_fts(rowid, title, snippet, entity_text) VALUES (?, ?, ?, ?)",
                (item_id, item.get("title", ""), item.get("snippet", ""), entity_text),
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


def search(query, connector=None, max_results=10):
    """Search the knowledge base. Returns JSON string for the LLM."""
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
