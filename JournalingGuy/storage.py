"""SQLite storage for journal entries and the evolving memory summary.

Entries carry a mood score (1-10, self-reported), a small set of LLM-tagged
themes, and a word count, all captured at save time so later analysis
doesn't need to re-read every conversation.
"""
import sqlite3
import json
from datetime import datetime, timezone, date

from config import DB_PATH, ensure_config_dir


def get_conn():
    ensure_config_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            conversation TEXT NOT NULL,
            mood_score INTEGER,
            tags TEXT,
            word_count INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            summary TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add columns to older databases created before mood/tags existed."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(entries)").fetchall()}
    if "mood_score" not in existing:
        conn.execute("ALTER TABLE entries ADD COLUMN mood_score INTEGER")
    if "tags" not in existing:
        conn.execute("ALTER TABLE entries ADD COLUMN tags TEXT")
    if "word_count" not in existing:
        conn.execute("ALTER TABLE entries ADD COLUMN word_count INTEGER")
    conn.commit()


def _word_count(conversation):
    return sum(len(t["content"].split()) for t in conversation if t["role"] == "user")


def save_entry(conversation, mood_score=None, tags=None):
    """conversation: list of {"role": "assistant"/"user", "content": str}"""
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    wc = _word_count(conversation)
    conn.execute(
        "INSERT INTO entries (timestamp, conversation, mood_score, tags, word_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (ts, json.dumps(conversation), mood_score, json.dumps(tags or []), wc),
    )
    conn.commit()
    conn.close()
    return ts


def _row_to_entry(row):
    ts, conv_json, mood_score, tags_json, word_count = row
    return {
        "timestamp": ts,
        "conversation": json.loads(conv_json),
        "mood_score": mood_score,
        "tags": json.loads(tags_json) if tags_json else [],
        "word_count": word_count or 0,
    }


def get_recent_entries(n=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT timestamp, conversation, mood_score, tags, word_count "
        "FROM entries ORDER BY id DESC LIMIT ?",
        (n,),
    ).fetchall()
    conn.close()
    return [_row_to_entry(r) for r in reversed(rows)]  # chronological order


def get_all_entries():
    conn = get_conn()
    rows = conn.execute(
        "SELECT timestamp, conversation, mood_score, tags, word_count "
        "FROM entries ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [_row_to_entry(r) for r in rows]


def get_entries_since(since_date: date):
    """since_date: a datetime.date; returns entries with timestamp >= that date (UTC)."""
    conn = get_conn()
    since_iso = since_date.isoformat()
    rows = conn.execute(
        "SELECT timestamp, conversation, mood_score, tags, word_count "
        "FROM entries WHERE substr(timestamp, 1, 10) >= ? ORDER BY id ASC",
        (since_iso,),
    ).fetchall()
    conn.close()
    return [_row_to_entry(r) for r in rows]


def count_entries():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    conn.close()
    return n


def get_memory_summary():
    conn = get_conn()
    row = conn.execute("SELECT summary, updated_at FROM memory WHERE id = 1").fetchone()
    conn.close()
    if row:
        return {"summary": row[0], "updated_at": row[1]}
    return {"summary": "", "updated_at": None}


def save_memory_summary(summary_text):
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO memory (id, summary, updated_at) VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET summary = excluded.summary, updated_at = excluded.updated_at
        """,
        (summary_text, ts),
    )
    conn.commit()
    conn.close()
