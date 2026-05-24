"""SQLite storage for code inviter plugin."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


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

CREATE TABLE IF NOT EXISTS code_pools (
    pool_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_pool_triggers (
    pool_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pool_id, trigger_type, trigger_text)
);

CREATE INDEX IF NOT EXISTS idx_codes_pool_status ON codes(pool_id, status, id);
CREATE INDEX IF NOT EXISTS idx_claim_records_user_pool ON claim_records(user_id, pool_id);
CREATE INDEX IF NOT EXISTS idx_pending_friend_flows_user_status
    ON pending_friend_flows(user_id, status, expires_at);
"""


class CodeInviterStorage:
    """Thin SQLite wrapper with schema bootstrap."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = db_path
        self._memory_uri = ""
        self._memory_keeper: sqlite3.Connection | None = None
        if str(db_path) == ":memory:":
            self._memory_uri = f"file:code_inviter_{uuid.uuid4().hex}?mode=memory&cache=shared"
            # Keep the shared in-memory database alive across short-lived connections.
            self._memory_keeper = self._open_memory_connection()
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            return self._open_memory_connection()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = DELETE")
        return conn

    def _open_memory_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._memory_uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
            return conn.execute(
                "SELECT * FROM pending_friend_flows WHERE id = ?",
                (flow_id,),
            ).fetchone()

    def find_pending_friend_flow(self, *, user_id: str, verify_token: str) -> sqlite3.Row | None:
        with self._connection() as conn:
            return conn.execute(
                """
                SELECT *
                FROM pending_friend_flows
                WHERE user_id = ?
                  AND verify_token = ?
                  AND status = 'pending'
                ORDER BY expires_at DESC, id DESC
                LIMIT 1
                """,
                (user_id, verify_token),
            ).fetchone()

    def mark_pending_friend_flow_approved(self, flow_id: int) -> None:
        with self._connection() as conn:
            conn.execute(
                "UPDATE pending_friend_flows SET status = 'approved' WHERE id = ?",
                (flow_id,),
            )

    def find_latest_approved_flow(self, *, user_id: str) -> sqlite3.Row | None:
        with self._connection() as conn:
            return conn.execute(
                """
                SELECT *
                FROM pending_friend_flows
                WHERE user_id = ?
                  AND status = 'approved'
                ORDER BY expires_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

    def add_code(self, *, pool_id: str, code: str, batch: str = "", remark: str = "") -> bool:
        with self._connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO codes (pool_id, code, batch, remark)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pool_id, code, batch, remark),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def count_claims_for_user(self, *, pool_id: str, user_id: str) -> int:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM claim_records
                WHERE pool_id = ?
                  AND user_id = ?
                  AND status = 'success'
                """,
                (pool_id, user_id),
            ).fetchone()
            return int(row["total"] if row else 0)

    def count_codes_by_status(self, *, pool_id: str) -> dict[str, int]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM codes
                WHERE pool_id = ?
                GROUP BY status
                """,
                (pool_id,),
            ).fetchall()
            return {str(row["status"]): int(row["total"]) for row in rows}

    def count_claim_records(self, *, pool_id: str = "") -> int:
        with self._connection() as conn:
            if pool_id:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM claim_records
                    WHERE pool_id = ?
                      AND status = 'success'
                    """,
                    (pool_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM claim_records
                    WHERE status = 'success'
                    """
                ).fetchone()
            return int(row["total"] if row else 0)

    def list_pool_ids(self) -> list[str]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT pool_id
                FROM (
                    SELECT pool_id FROM code_pools
                    UNION
                    SELECT pool_id FROM codes
                    UNION
                    SELECT pool_id FROM claim_records
                )
                ORDER BY pool_id ASC
                """
            ).fetchall()
            return [str(row["pool_id"]) for row in rows]

    def upsert_pool(self, *, pool_id: str, display_name: str = "", enabled: bool = True) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO code_pools (pool_id, display_name, enabled)
                VALUES (?, ?, ?)
                ON CONFLICT(pool_id) DO UPDATE SET
                    display_name = CASE
                        WHEN excluded.display_name != '' THEN excluded.display_name
                        ELSE code_pools.display_name
                    END,
                    enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (pool_id, display_name, 1 if enabled else 0),
            )

    def get_pool(self, *, pool_id: str) -> sqlite3.Row | None:
        with self._connection() as conn:
            return conn.execute(
                "SELECT * FROM code_pools WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()

    def set_pool_enabled(self, *, pool_id: str, enabled: bool) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO code_pools (pool_id, enabled)
                VALUES (?, ?)
                ON CONFLICT(pool_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (pool_id, 1 if enabled else 0),
            )

    def replace_pool_triggers(
        self,
        *,
        pool_id: str,
        trigger_type: str,
        triggers: list[str],
    ) -> None:
        normalized = []
        seen = set()
        for trigger in triggers:
            value = trigger.strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM code_pool_triggers WHERE pool_id = ? AND trigger_type = ?",
                (pool_id, trigger_type),
            )
            conn.executemany(
                """
                INSERT INTO code_pool_triggers (pool_id, trigger_type, trigger_text)
                VALUES (?, ?, ?)
                """,
                [(pool_id, trigger_type, trigger) for trigger in normalized],
            )

    def list_pool_triggers(self, *, pool_id: str, trigger_type: str) -> list[str]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT trigger_text
                FROM code_pool_triggers
                WHERE pool_id = ?
                  AND trigger_type = ?
                ORDER BY trigger_text ASC
                """,
                (pool_id, trigger_type),
            ).fetchall()
            return [str(row["trigger_text"]) for row in rows]

    def delete_empty_pool(self, *, pool_id: str) -> bool:
        with self._connection() as conn:
            code_count = conn.execute(
                "SELECT COUNT(*) AS total FROM codes WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()
            claim_count = conn.execute(
                "SELECT COUNT(*) AS total FROM claim_records WHERE pool_id = ?",
                (pool_id,),
            ).fetchone()
            if int(code_count["total"]) > 0 or int(claim_count["total"]) > 0:
                return False
            conn.execute("DELETE FROM code_pools WHERE pool_id = ?", (pool_id,))
            return True

    def claim_next_code(
        self,
        *,
        pool_id: str,
        user_id: str,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> sqlite3.Row | None:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            code_row = conn.execute(
                """
                SELECT *
                FROM codes
                WHERE pool_id = ?
                  AND status = 'unused'
                ORDER BY id ASC
                LIMIT 1
                """,
                (pool_id,),
            ).fetchone()
            if code_row is None:
                return None

            claim_index = self._count_claims_for_user_in_conn(conn, pool_id=pool_id, user_id=user_id) + 1
            conn.execute(
                """
                UPDATE codes
                SET status = 'claimed',
                    claimed_at = CURRENT_TIMESTAMP,
                    claimed_by = ?
                WHERE id = ?
                """,
                (user_id, int(code_row["id"])),
            )
            cursor = conn.execute(
                """
                INSERT INTO claim_records (
                    pool_id, code_id, code, user_id, user_nickname,
                    source_group_id, source_group_name, claim_index_for_user
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pool_id,
                    int(code_row["id"]),
                    str(code_row["code"]),
                    user_id,
                    user_nickname,
                    source_group_id,
                    source_group_name,
                    claim_index,
                ),
            )
            record_id = int(cursor.lastrowid)
            return conn.execute(
                "SELECT * FROM claim_records WHERE id = ?",
                (record_id,),
            ).fetchone()

    def _count_claims_for_user_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        pool_id: str,
        user_id: str,
    ) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM claim_records
            WHERE pool_id = ?
              AND user_id = ?
              AND status = 'success'
            """,
            (pool_id, user_id),
        ).fetchone()
        return int(row["total"] if row else 0)

    def list_claim_records(
        self,
        *,
        pool_id: str,
        claimed_after: str = "",
        claimed_before: str = "",
    ) -> list[sqlite3.Row]:
        with self._connection() as conn:
            where = ["claim_records.pool_id = ?"]
            params: list[str] = [pool_id]
            if claimed_after:
                where.append("claim_records.claimed_at >= ?")
                params.append(claimed_after)
            if claimed_before:
                where.append("claim_records.claimed_at <= ?")
                params.append(claimed_before)
            sql = f"""
                SELECT claim_records.*, codes.batch AS batch
                FROM claim_records
                LEFT JOIN codes ON codes.id = claim_records.code_id
                WHERE {' AND '.join(where)}
                ORDER BY claim_records.claimed_at ASC, claim_records.id ASC
            """
            return conn.execute(sql, params).fetchall()

    def list_claim_records_by_user(self, *, user_id: str, pool_id: str = "") -> list[sqlite3.Row]:
        with self._connection() as conn:
            where = ["claim_records.user_id = ?"]
            params: list[str] = [user_id]
            if pool_id:
                where.append("claim_records.pool_id = ?")
                params.append(pool_id)
            sql = f"""
                SELECT claim_records.*, codes.batch AS batch
                FROM claim_records
                LEFT JOIN codes ON codes.id = claim_records.code_id
                WHERE {' AND '.join(where)}
                ORDER BY claim_records.claimed_at DESC, claim_records.id DESC
            """
            return conn.execute(sql, params).fetchall()

    def upsert_blocked_user(self, *, user_id: str, reason: str, created_by: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO blocked_users (user_id, reason, created_by)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    reason = excluded.reason,
                    created_by = excluded.created_by,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, reason, created_by),
            )

    def remove_blocked_user(self, *, user_id: str) -> None:
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM blocked_users WHERE user_id = ?",
                (user_id,),
            )

    def is_blocked_user(self, *, user_id: str) -> bool:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM blocked_users WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            return row is not None

    def reset_user_claims(self, *, pool_id: str, user_id: str) -> int:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT code_id
                FROM claim_records
                WHERE pool_id = ?
                  AND user_id = ?
                  AND status = 'success'
                """,
                (pool_id, user_id),
            ).fetchall()
            if not rows:
                return 0
            code_ids = [int(row["code_id"]) for row in rows]
            placeholders = ", ".join("?" for _ in code_ids)
            conn.execute(
                f"""
                UPDATE codes
                SET status = 'unused',
                    claimed_at = NULL,
                    claimed_by = NULL
                WHERE id IN ({placeholders})
                """,
                code_ids,
            )
            conn.execute(
                """
                UPDATE claim_records
                SET status = 'revoked'
                WHERE pool_id = ?
                  AND user_id = ?
                  AND status = 'success'
                """,
                (pool_id, user_id),
            )
            return len(rows)
