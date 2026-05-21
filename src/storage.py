"""SQLite storage for code inviter plugin."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id TEXT NOT NULL,
    code TEXT NOT NULL,
    batch TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unused',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at TEXT,
    claimed_by TEXT,
    UNIQUE(pool_id, code)
);

CREATE TABLE IF NOT EXISTS claim_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id TEXT NOT NULL,
    code_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_nickname TEXT NOT NULL DEFAULT '',
    source_group_id TEXT NOT NULL DEFAULT '',
    source_group_name TEXT NOT NULL DEFAULT '',
    claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_index_for_user INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS pending_friend_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    pool_id TEXT NOT NULL,
    verify_token TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS blocked_users (
    user_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_codes_pool_status ON codes(pool_id, status, id);
CREATE INDEX IF NOT EXISTS idx_claim_records_user_pool ON claim_records(user_id, pool_id);
CREATE INDEX IF NOT EXISTS idx_pending_friend_flows_user_status
    ON pending_friend_flows(user_id, status, expires_at);
"""


class CodeInviterStorage:
    """Thin SQLite wrapper with schema bootstrap."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def create_pending_friend_flow(
        self,
        *,
        user_id: str,
        group_id: str,
        pool_id: str,
        verify_token: str,
        expires_at: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pending_friend_flows (
                    user_id, group_id, pool_id, verify_token, expires_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, group_id, pool_id, verify_token, expires_at),
            )
            return int(cursor.lastrowid)

    def get_pending_friend_flow(self, flow_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM pending_friend_flows WHERE id = ?",
                (flow_id,),
            ).fetchone()
