"""Private-chat code claim service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.config import CodePoolConfig, PluginConfig
from src.storage import CodeInviterStorage


@dataclass(slots=True)
class ClaimResult:
    claimed: bool
    reason: str
    pool_id: str = ""
    code: str = ""


class ClaimService:
    """Claim one unused code from a matched pool."""

    def __init__(self, config: PluginConfig, storage: CodeInviterStorage) -> None:
        self.config = config
        self.storage = storage

    def handle_private_message(
        self,
        *,
        user_id: int,
        message: str,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> ClaimResult:
        pool = self._match_pool(message.strip())
        if pool is None:
            return ClaimResult(claimed=False, reason="trigger_not_matched")
        if not pool.enabled:
            return ClaimResult(claimed=False, reason="pool_disabled", pool_id=pool.pool_id)

        user_id_text = str(user_id)
        if self._is_once_per_user_limit_reached(pool=pool, user_id=user_id_text):
            return ClaimResult(claimed=False, reason="already_claimed", pool_id=pool.pool_id)

        source_group_id = source_group_id or self._resolve_source_group(user_id=user_id_text)
        if self.config.require_group_source and not source_group_id:
            return ClaimResult(claimed=False, reason="not_friend_flow", pool_id=pool.pool_id)

        record = self.storage.claim_next_code(
            pool_id=pool.pool_id,
            user_id=user_id_text,
            user_nickname=user_nickname,
            source_group_id=source_group_id,
            source_group_name=source_group_name,
        )
        if record is None:
            return ClaimResult(claimed=False, reason="out_of_stock", pool_id=pool.pool_id)

        return ClaimResult(
            claimed=True,
            reason="claimed",
            pool_id=pool.pool_id,
            code=str(record["code"]),
        )

    def _match_pool(self, message: str) -> CodePoolConfig | None:
        for pool in self.config.pools.values():
            if message in pool.private_triggers:
                return pool
        return None

    def _is_once_per_user_limit_reached(self, *, pool: CodePoolConfig, user_id: str) -> bool:
        policy = pool.claim_policy
        if policy.mode != "once_per_user":
            return False
        return self.storage.count_claims_for_user(pool_id=pool.pool_id, user_id=user_id) >= 1

    def _resolve_source_group(self, *, user_id: str) -> str:
        flow = self.storage.find_latest_approved_flow(user_id=user_id)
        if flow is None:
            return ""
        expires_at = datetime.fromisoformat(str(flow["expires_at"]))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        claim_source_deadline = datetime.now(UTC) - timedelta(hours=self.config.group_source_ttl_hours)
        if expires_at < claim_source_deadline:
            return ""
        return str(flow["group_id"])
