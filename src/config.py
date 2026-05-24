"""Configuration parsing for the code inviter plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ClaimMode = Literal["once_per_user", "limited_per_user", "limited_per_period", "unlimited"]
ClaimPeriod = Literal["none", "day", "week", "month"]


DEFAULT_ADMIN_COMMANDS: dict[str, list[str]] = {
    "inventory": ["库存", "发码库存", "全部库存"],
    "statistics": ["统计", "发码统计"],
    "query_claims": ["记录", "查领取"],
    "import_codes": ["导入码"],
    "import_csv": ["导入csv", "导入CSV"],
    "export_claims": ["导出领取记录"],
    "reset_claims": ["重置领取"],
    "block_user": ["禁领"],
    "unblock_user": ["解禁"],
    "pool_admin": ["码池"],
    "trigger_admin": ["触发词"],
}


@dataclass(slots=True)
class ClaimPolicy:
    mode: ClaimMode = "once_per_user"
    per_user_limit: int = 1
    period: ClaimPeriod = "none"
    period_limit: int = 0
    cooldown_seconds: int = 30


@dataclass(slots=True)
class CodePoolConfig:
    pool_id: str
    display_name: str
    enabled: bool = True
    allowed_groups: list[int] = field(default_factory=list)
    group_triggers: list[str] = field(default_factory=list)
    private_triggers: list[str] = field(default_factory=list)
    claim_policy: ClaimPolicy = field(default_factory=ClaimPolicy)
    messages: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AdminCommandConfig:
    inventory: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["inventory"]))
    statistics: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["statistics"]))
    query_claims: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["query_claims"]))
    import_codes: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["import_codes"]))
    import_csv: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["import_csv"]))
    export_claims: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["export_claims"]))
    reset_claims: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["reset_claims"]))
    block_user: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["block_user"]))
    unblock_user: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["unblock_user"]))
    pool_admin: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["pool_admin"]))
    trigger_admin: list[str] = field(default_factory=lambda: list(DEFAULT_ADMIN_COMMANDS["trigger_admin"]))

    def aliases_by_command(self) -> dict[str, list[str]]:
        return {
            "inventory": self.inventory,
            "statistics": self.statistics,
            "query_claims": self.query_claims,
            "import_codes": self.import_codes,
            "import_csv": self.import_csv,
            "export_claims": self.export_claims,
            "reset_claims": self.reset_claims,
            "block_user": self.block_user,
            "unblock_user": self.unblock_user,
            "pool_admin": self.pool_admin,
            "trigger_admin": self.trigger_admin,
        }


@dataclass(slots=True)
class PluginConfig:
    enabled: bool = True
    admin_users: list[int] = field(default_factory=list)
    bot_aliases: list[str] = field(default_factory=lambda: ["秋秋"])
    admin_commands: AdminCommandConfig = field(default_factory=AdminCommandConfig)
    global_allowed_groups: list[int] = field(default_factory=list)
    token_ttl_minutes: int = 30
    token_template: str = "领码-{token}"
    require_group_source: bool = True
    group_source_ttl_hours: int = 24
    csv_encoding: str = "utf-8-sig"
    export_dir: str = "exports"
    pools: dict[str, CodePoolConfig] = field(default_factory=dict)


def parse_plugin_config(raw: dict[str, Any]) -> PluginConfig:
    """Parse AstrBot config into typed plugin settings."""

    pools_raw = raw.get("code_pools", {})
    pools_raw = pools_raw if isinstance(pools_raw, dict) else {}
    pools = {
        str(pool_id): _parse_pool(str(pool_id), pool_raw)
        for pool_id, pool_raw in pools_raw.items()
        if isinstance(pool_raw, dict)
    }
    friend_gate = raw.get("friend_gate", {})
    claim_gate = raw.get("claim_gate", {})
    csv_config = raw.get("csv", {})
    return PluginConfig(
        enabled=bool(raw.get("enabled", True)),
        admin_users=_int_list(raw.get("admin_users", [])),
        bot_aliases=_str_list(raw.get("bot_aliases", ["秋秋"])),
        admin_commands=_parse_admin_commands(raw.get("admin_commands", {})),
        global_allowed_groups=_int_list(raw.get("global_allowed_groups", [])),
        token_ttl_minutes=int(friend_gate.get("token_ttl_minutes", 30)),
        token_template=str(friend_gate.get("token_template", "领码-{token}")),
        require_group_source=bool(claim_gate.get("require_group_source", True)),
        group_source_ttl_hours=int(claim_gate.get("group_source_ttl_hours", 24)),
        csv_encoding=str(csv_config.get("encoding", "utf-8-sig")),
        export_dir=str(csv_config.get("export_dir", "exports")),
        pools=pools,
    )


def _parse_pool(pool_id: str, raw: dict[str, Any]) -> CodePoolConfig:
    return CodePoolConfig(
        pool_id=pool_id,
        display_name=str(raw.get("display_name", pool_id)),
        enabled=bool(raw.get("enabled", True)),
        allowed_groups=_int_list(raw.get("allowed_groups", [])),
        group_triggers=[str(v) for v in raw.get("group_triggers", [])],
        private_triggers=[str(v) for v in raw.get("private_triggers", [])],
        claim_policy=_parse_claim_policy(raw.get("claim_policy", {})),
        messages={str(k): str(v) for k, v in raw.get("messages", {}).items()},
    )


def _parse_claim_policy(raw: dict[str, Any]) -> ClaimPolicy:
    return ClaimPolicy(
        mode=str(raw.get("mode", "once_per_user")),  # type: ignore[arg-type]
        per_user_limit=int(raw.get("per_user_limit", 1)),
        period=str(raw.get("period", "none")),  # type: ignore[arg-type]
        period_limit=int(raw.get("period_limit", 0)),
        cooldown_seconds=int(raw.get("cooldown_seconds", 30)),
    )


def _parse_admin_commands(raw: Any) -> AdminCommandConfig:
    raw = raw if isinstance(raw, dict) else {}
    values = {
        key: _str_list(raw.get(key, DEFAULT_ADMIN_COMMANDS[key]))
        for key in DEFAULT_ADMIN_COMMANDS
    }
    return AdminCommandConfig(**values)


def _int_list(value: Any) -> list[int]:
    return [int(item) for item in value or []]


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = [value]
    return [str(item).strip() for item in candidates if str(item).strip()]
