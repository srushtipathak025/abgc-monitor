"""
database/db.py — SQLite database layer for the ABGC Monitoring Agent.

Tables:
  guideline_snapshots  — Full HTML snapshots of each monitored page.
  guideline_changes    — Detected diffs with AI summaries and approval state.
  recipients           — Patients and clinicians who receive updates.
  outbound_messages    — Every message ever sent, for full audit trail.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


# ─── Connection helper ────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema init ─────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't already exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS guideline_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    NOT NULL,
                content_hash TEXT   NOT NULL,
                raw_text    TEXT    NOT NULL,
                fetched_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guideline_changes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                url             TEXT    NOT NULL,
                old_snapshot_id INTEGER REFERENCES guideline_snapshots(id),
                new_snapshot_id INTEGER REFERENCES guideline_snapshots(id),
                diff_text       TEXT    NOT NULL,
                ai_summary      TEXT,
                patient_draft   TEXT,
                clinician_draft TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                -- status: pending | approved | rejected | sent
                detected_at     TEXT    NOT NULL,
                approved_at     TEXT,
                approved_by     TEXT,
                sent_at         TEXT
            );

            CREATE TABLE IF NOT EXISTS recipients (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT    NOT NULL,
                email               TEXT    NOT NULL UNIQUE,
                type                TEXT    NOT NULL,
                -- type: patient | clinician
                relevant_conditions TEXT    DEFAULT '[]',
                -- JSON array e.g. ["BRCA", "Lynch syndrome"]
                active              INTEGER NOT NULL DEFAULT 1,
                created_at          TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbound_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                change_id   INTEGER REFERENCES guideline_changes(id),
                recipient_id INTEGER REFERENCES recipients(id),
                subject     TEXT    NOT NULL,
                body        TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                -- status: pending | sent | failed
                sent_at     TEXT,
                error       TEXT,
                created_at  TEXT    NOT NULL
            );
        """)
    print("✅ Database initialized.")


# ─── Snapshot helpers ─────────────────────────────────────────────────────────

def save_snapshot(url: str, content_hash: str, raw_text: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO guideline_snapshots (url, content_hash, raw_text, fetched_at) "
            "VALUES (?, ?, ?, ?)",
            (url, content_hash, raw_text, datetime.utcnow().isoformat())
        )
        return cur.lastrowid


def get_latest_snapshot(url: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM guideline_snapshots WHERE url = ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (url,)
        ).fetchone()


# ─── Change helpers ───────────────────────────────────────────────────────────

def save_change(
    url: str,
    old_snapshot_id: int | None,
    new_snapshot_id: int,
    diff_text: str,
    ai_summary: str,
    patient_draft: str,
    clinician_draft: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO guideline_changes
               (url, old_snapshot_id, new_snapshot_id, diff_text,
                ai_summary, patient_draft, clinician_draft, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (url, old_snapshot_id, new_snapshot_id, diff_text,
             ai_summary, patient_draft, clinician_draft,
             datetime.utcnow().isoformat())
        )
        return cur.lastrowid


def get_change(change_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM guideline_changes WHERE id = ?", (change_id,)
        ).fetchone()


def get_pending_changes() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM guideline_changes WHERE status = 'pending' ORDER BY detected_at DESC"
        ).fetchall()


def approve_change(change_id: int, approved_by: str = "admin"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE guideline_changes SET status='approved', approved_at=?, approved_by=? WHERE id=?",
            (datetime.utcnow().isoformat(), approved_by, change_id)
        )


def reject_change(change_id: int, approved_by: str = "admin"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE guideline_changes SET status='rejected', approved_at=?, approved_by=? WHERE id=?",
            (datetime.utcnow().isoformat(), approved_by, change_id)
        )


def mark_change_sent(change_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE guideline_changes SET status='sent', sent_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), change_id)
        )


# ─── Recipient helpers ────────────────────────────────────────────────────────

def add_recipient(name: str, email: str, recipient_type: str, conditions: list[str] = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO recipients (name, email, type, relevant_conditions, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, email, recipient_type,
             json.dumps(conditions or []),
             datetime.utcnow().isoformat())
        )
        return cur.lastrowid


def get_active_recipients() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM recipients WHERE active = 1"
        ).fetchall()


def get_recipients_by_type(recipient_type: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM recipients WHERE active = 1 AND type = ?",
            (recipient_type,)
        ).fetchall()


# ─── Outbound message helpers ─────────────────────────────────────────────────

def save_outbound_message(
    change_id: int, recipient_id: int, subject: str, body: str
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO outbound_messages (change_id, recipient_id, subject, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (change_id, recipient_id, subject, body, datetime.utcnow().isoformat())
        )
        return cur.lastrowid


def mark_message_sent(message_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE outbound_messages SET status='sent', sent_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), message_id)
        )


def mark_message_failed(message_id: int, error: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE outbound_messages SET status='failed', error=? WHERE id=?",
            (error, message_id)
        )
