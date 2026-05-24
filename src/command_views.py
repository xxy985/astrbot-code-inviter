"""Text views for AstrBot command responses."""

from __future__ import annotations

from dataclasses import dataclass

from .admin_service import ClaimRecordSummary
from .config import PluginConfig


@dataclass(slots=True)
class ImportTextPayload:
    pool_id: str
    lines: list[str]


class CommandViews:
    """Render small text responses for AstrBot commands."""

    def __init__(self, config: PluginConfig) -> None:
        self.config = config

    def pool_name(self, pool_id: str) -> str:
        pool = self.config.pools.get(pool_id)
        return pool.display_name if pool else pool_id

    def claim_reply(self, result: dict[str, str | bool]) -> str:
        pool_id = str(result["pool_id"])
        pool_name = self.pool_name(pool_id)
        reason = str(result["reason"])
        if result["claimed"]:
            return f"你的{pool_name}是：{result['code']}"
        messages = {
            "already_claimed": f"你已经领取过{pool_name}了。",
            "blocked": "你当前无法领取，请联系管理员。",
            "cooldown": "操作太频繁，请稍后再试。",
            "limit_reached": f"你当前已达到{pool_name}领取上限。",
            "not_friend_flow": "请先在指定群触发领取流程。",
            "out_of_stock": f"{pool_name}当前库存不足。",
            "pool_disabled": f"{pool_name}暂未开放领取。",
        }
        return messages.get(reason, "领取失败，请联系管理员。")

    def claim_records(self, records: list[ClaimRecordSummary]) -> str:
        if not records:
            return "未找到领取记录。"
        return "\n".join(
            f"{record.claimed_at} {record.pool_id} {record.user_id} {record.code} #{record.claim_index}"
            for record in records
        )

    def parse_import_text(self, message: str) -> ImportTextPayload:
        lines = [line.strip() for line in message.splitlines()]
        if not lines:
            return ImportTextPayload(pool_id="", lines=[])
        first_line = lines[0].removeprefix("@").strip()
        separator_indexes = [
            first_line.find(separator)
            for separator in ("：", ":", "，", ",")
            if first_line.find(separator) >= 0
        ]
        if separator_indexes:
            index = min(separator_indexes)
            first_line = f"{first_line[:index]} {first_line[index + 1:]}"
        head = first_line.split(maxsplit=1)
        if len(head) < 2:
            return ImportTextPayload(pool_id="", lines=[])
        return ImportTextPayload(pool_id=head[1].strip(), lines=[line for line in lines[1:] if line])
