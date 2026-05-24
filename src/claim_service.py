"""Private-chat code claim service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .config import CodePoolConfig, PluginConfig
from .storage import CodeInviterStorage


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
        if self.storage.is_blocked_user(user_id=user_id_text):
            return ClaimResult(claimed=False, reason="blocked", pool_id=pool.pool_id)

        limit_reason = self._claim_limit_reason(pool=pool, user_id=user_id_text)
        if limit_reason:
            return ClaimResult(claimed=False, reason=limit_reason, pool_id=pool.pool_id)

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

    def _claim_limit_reason(self, *, pool: CodePoolConfig, user_id: str) -> str:
        policy = pool.claim_policy
        records = self.storage.list_claim_records_by_user(user_id=user_id, pool_id=pool.pool_id)
        if policy.mode == "once_per_user":
            return "already_claimed" if records else ""
        if policy.mode == "limited_per_user" and len(records) >= policy.per_user_limit:
            return "limit_reached"
        if policy.mode == "limited_per_period":
            period_start = self._period_start(policy.period)
            recent = [
                row
                for row in records
                if self._parse_claimed_at(str(row["claimed_at"])) >= period_start
            ]
            if policy.period_limit > 0 and len(recent) >= policy.period_limit:
                return "limit_reached"
        if policy.cooldown_seconds > 0 and records:
            last_claimed_at = self._parse_claimed_at(str(records[0]["claimed_at"]))
            if datetime.now(UTC) - last_claimed_at < timedelta(seconds=policy.cooldown_seconds):
                return "cooldown"
        return ""

    def _period_start(self, period: str) -> datetime:
        now = datetime.now(UTC)
        if period == "day":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "week":
            start = now - timedelta(days=now.weekday())
            return start.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "month":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return datetime.min.replace(tzinfo=UTC)

    def _parse_claimed_at(self, claimed_at: str) -> datetime:
        parsed = datetime.fromisoformat(claimed_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

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
