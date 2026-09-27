"""SQLite storage. Raw prompt/response text is kept only for a short, configurable
demo window; everything else (keys, fingerprints) is stored hashed."""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    label TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    prompt_text TEXT,
    answer_text TEXT,
    fingerprint_hash TEXT NOT NULL,
    firewall_blocked INTEGER,
    firewall_reason TEXT,
    firewall_engine TEXT,
    risk_score REAL,
    risk_breakdown TEXT,
    outcome TEXT,
    is_trap INTEGER DEFAULT 0,
    trap_phrase TEXT,
    model_backend_used TEXT,
    reasoning_requested INTEGER DEFAULT 0,
    topics TEXT,
    minhash_signature TEXT,
    t_auth_us INTEGER,
    t_immunity_us INTEGER,
    t_firewall_us INTEGER,
    t_signals_us INTEGER,
    t_policy_us INTEGER,
    t_model_us INTEGER,
    t_total_us INTEGER
);

CREATE TABLE IF NOT EXISTS shared_fingerprints (
    fingerprint_hash TEXT PRIMARY KEY,
    origin_tenant_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- Model DNA: which trap phrase was planted for which account/question, and when.
-- Deliberately NOT subject to purge_expired_raw_text(): it is Puaro's own security
-- evidence (needed by the verifier), not customer conversation content.
CREATE TABLE IF NOT EXISTS trap_ledger (
    trap_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    trap_phrase TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_account ON requests(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_fingerprint ON requests(fingerprint_hash);
CREATE INDEX IF NOT EXISTS idx_trap_ledger_account ON trap_ledger(account_id);
"""


def get_connection() -> sqlite3.Connection:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def purge_expired_raw_text() -> int:
    """Blank out prompt/answer text older than the configured retention window.

    Does not touch trap_ledger: that table holds Puaro's own security evidence
    (which trap phrase went to which account/question), not raw customer
    conversation content, and the Model DNA verifier needs it to outlive the
    short conversation-retention window.
    """
    cutoff = time.time() - settings.raw_text_retention_minutes * 60
    with connection() as conn:
        cur = conn.execute(
            "UPDATE requests SET prompt_text = NULL, answer_text = NULL "
            "WHERE created_at < ? AND (prompt_text IS NOT NULL OR answer_text IS NOT NULL)",
            (cutoff,),
        )
        return cur.rowcount
