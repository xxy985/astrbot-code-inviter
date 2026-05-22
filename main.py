"""AstrBot code inviter plugin entry point."""

from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.command_views import CommandViews
from src.config import parse_plugin_config
from src.friend_service import FriendApprovalService
from src.handlers import PluginHandlers
from src.storage import CodeInviterStorage
from src.trigger_service import GroupTriggerService


class AstrBotCodeInviterPlugin(Star):
    """AstrBot plugin shell and event wiring."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.raw_config = config
        self.config = parse_plugin_config(dict(config))
        self.data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.storage = CodeInviterStorage(self.data_path / "code_inviter.sqlite3")
        self.storage.initialize()
        self.export_path = self.data_path / self.config.export_dir
        self.export_path.mkdir(parents=True, exist_ok=True)
        self.trigger_service = GroupTriggerService(self.config, self.storage)
        self.friend_service = FriendApprovalService(self.config, self.storage)
        self.claim_service = ClaimService(self.config, self.storage)
        self.admin_service = AdminService(self.storage, self.export_path, self.config.csv_encoding)
        self.command_views = CommandViews(self.config)
        self.handlers = PluginHandlers(
            trigger_service=self.trigger_service,
            claim_service=self.claim_service,
            friend_service=self.friend_service,
            admin_service=self.admin_service,
        )

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        logger.info(
            f"{self.name} loaded with data path {self.data_path} and export path {self.export_path}."
        )

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        result = self.handle_group_trigger(
            user_id=self._sender_id(event),
            group_id=self._group_id(event),
            message=event.message_str,
        )
        if not result["matched"]:
            return
        event.stop_event()
        yield event.plain_result(str(result["guide_message"]))

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        result = self.handle_private_claim(
            user_id=self._sender_id(event),
            message=event.message_str,
            user_nickname=event.get_sender_name(),
        )
        if result["reason"] == "trigger_not_matched":
            return
        event.stop_event()
        yield event.plain_result(self.command_views.claim_reply(result))

    @filter.command("发码库存")
    async def command_inventory(self, event: AstrMessageEvent, pool_id: str = ""):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        pools = [pool_id] if pool_id else self._known_pool_ids()
        if not pools:
            yield event.plain_result("暂无码池库存。")
            return
        lines = []
        for current_pool_id in pools:
            counts = self.admin_service.inventory(pool_id=current_pool_id)
            lines.append(
                f"{current_pool_id}: unused={counts['unused']} claimed={counts['claimed']} disabled={counts['disabled']}"
            )
        yield event.plain_result("\n".join(lines))

    @filter.command("查领取")
    async def command_query_claims(self, event: AstrMessageEvent, user_id: str, pool_id: str = ""):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        records = self.admin_service.query_user_claims(user_id=user_id, pool_id=pool_id)
        yield event.plain_result(self.command_views.claim_records(records))

    @filter.command("导入码")
    async def command_import_codes(self, event: AstrMessageEvent):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        payload = self.command_views.parse_import_text(event.message_str)
        if not payload.pool_id or not payload.lines:
            yield event.plain_result("用法：/导入码 <码池ID>，并在后续行粘贴码。")
            return
        summary = self.admin_service.import_text_codes(pool_id=payload.pool_id, lines=payload.lines)
        yield event.plain_result(
            f"导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"
        )

    @filter.command("导入csv")
    async def command_import_csv(self, event: AstrMessageEvent, pool_id: str, csv_path: str):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        summary = self.admin_service.import_csv_codes(pool_id=pool_id, csv_path=Path(csv_path))
        yield event.plain_result(
            f"CSV 导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"
        )

    @filter.command("导出领取记录")
    async def command_export_claims(
        self,
        event: AstrMessageEvent,
        pool_id: str,
        claimed_after: str = "",
        claimed_before: str = "",
    ):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        output_path, count = self.admin_service.export_claim_records(
            pool_id=pool_id,
            pool_name=self.command_views.pool_name(pool_id),
            claimed_after=claimed_after,
            claimed_before=claimed_before,
        )
        yield event.plain_result(f"导出完成：{count} 条，文件：{output_path}")

    @filter.command("禁领")
    async def command_block_user(self, event: AstrMessageEvent, user_id: str, reason: str = ""):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        self.admin_service.block_user(
            user_id=user_id,
            reason=reason,
            created_by=str(self._sender_id(event)),
        )
        yield event.plain_result(f"已禁领用户 {user_id}。")

    @filter.command("解禁")
    async def command_unblock_user(self, event: AstrMessageEvent, user_id: str):
        if not self._is_plugin_admin(event):
            yield event.plain_result("无权限执行该命令。")
            return
        self.admin_service.unblock_user(user_id=user_id)
        yield event.plain_result(f"已解除用户 {user_id} 的禁领状态。")

    def handle_group_trigger(self, *, user_id: int, group_id: int, message: str) -> dict[str, str | bool]:
        """Process a group trigger message."""

        result = self.handlers.handle_group_trigger(user_id=user_id, group_id=group_id, message=message)
        return {
            "matched": result.matched,
            "pool_id": result.pool_id,
            "guide_message": result.guide_message,
        }

    def handle_private_claim(
        self,
        *,
        user_id: int,
        message: str,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> dict[str, str | bool]:
        """Process a private claim message."""

        result = self.handlers.handle_private_claim(
            user_id=user_id,
            message=message,
            user_nickname=user_nickname,
            source_group_id=source_group_id,
            source_group_name=source_group_name,
        )
        return {
            "claimed": result.claimed,
            "reason": result.reason,
            "pool_id": result.pool_id,
            "code": result.code,
        }

    def handle_friend_request(self, *, user_id: int, comment: str) -> dict[str, str | bool | int | None]:
        """Process a friend request comment."""

        result = self.handlers.handle_friend_request(user_id=user_id, comment=comment)
        return {
            "approved": result.approved,
            "reason": result.reason,
            "pool_id": result.pool_id,
            "flow_id": result.flow_id,
        }

    def _is_plugin_admin(self, event: AstrMessageEvent) -> bool:
        return self._sender_id(event) in self.config.admin_users

    def _sender_id(self, event: AstrMessageEvent) -> int:
        return int(event.get_sender_id())

    def _group_id(self, event: AstrMessageEvent) -> int:
        return int(getattr(event.message_obj, "group_id", "") or 0)

    def _known_pool_ids(self) -> list[str]:
        config_pool_ids = list(self.config.pools.keys())
        storage_pool_ids = self.storage.list_pool_ids()
        return sorted(set(config_pool_ids + storage_pool_ids))
