"""Group trigger handling for code invitation flows."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .config import CodePoolConfig, PluginConfig
from .storage import CodeInviterStorage


@dataclass(slots=True)
class TriggerResult:
    matched: bool
    pool_id: str = ""
    guide_message: str = ""
    flow_id: int | None = None


class GroupTriggerService:
    """Create pending friend flows from exact group triggers."""

    def __init__(self, config: PluginConfig, storage: CodeInviterStorage) -> None:
        self.config = config
        self.storage = storage

    def handle_group_message(self, *, user_id: int, group_id: int, message: str) -> TriggerResult:
        pool = self._match_pool(group_id=group_id, message=message.strip())
        if pool is None:
            return TriggerResult(matched=False)

        token = self._new_token()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.config.token_ttl_minutes)
        flow_id = self.storage.create_pending_friend_flow(
            user_id=str(user_id),
            group_id=str(group_id),
            pool_id=pool.pool_id,
            verify_token=token,
            expires_at=expires_at.isoformat(),
        )
        verify_text = self.config.token_template.format(token=token)
        private_trigger = pool.private_triggers[0] if pool.private_triggers else pool.display_name
        return TriggerResult(
            matched=True,
            pool_id=pool.pool_id,
            flow_id=flow_id,
            guide_message=f"请添加机器人好友，验证信息填写：{verify_text}，然后私聊发送：{private_trigger}",
        )

    def _match_pool(self, *, group_id: int, message: str) -> CodePoolConfig | None:
        for pool in self._all_pools():
            if not self._is_pool_enabled(pool.pool_id, pool.enabled):
                continue
            if message not in self._group_triggers(pool):
                continue
            allowed_groups = pool.allowed_groups or self.config.global_allowed_groups
            if allowed_groups and group_id not in allowed_groups:
                return None
            return pool
        return None

    def _all_pools(self) -> list[CodePoolConfig]:
        pools = dict(self.config.pools)
        for pool_id in self.storage.list_pool_ids():
            if pool_id in pools:
                continue
            row = self.storage.get_pool(pool_id=pool_id)
            display_name = str(row["display_name"] or pool_id) if row else pool_id
            enabled = bool(int(row["enabled"])) if row else True
            pools[pool_id] = CodePoolConfig(
                pool_id=pool_id,
                display_name=display_name,
                enabled=enabled,
            )
        return list(pools.values())

    def _group_triggers(self, pool: CodePoolConfig) -> list[str]:
        dynamic_triggers = self.storage.list_pool_triggers(
            pool_id=pool.pool_id,
            trigger_type="group",
        )
        return dynamic_triggers or pool.group_triggers

    def _is_pool_enabled(self, pool_id: str, config_enabled: bool) -> bool:
        pool_row = self.storage.get_pool(pool_id=pool_id)
        if pool_row is not None:
            return bool(int(pool_row["enabled"]))
        return config_enabled

    def _new_token(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"
