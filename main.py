"""AstrBot code inviter plugin entry point."""

from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

if __package__:
    from .src.admin_service import AdminService
    from .src.claim_service import ClaimService
    from .src.command_views import CommandViews
    from .src.config import parse_plugin_config
    from .src.friend_service import FriendApprovalService
    from .src.friend_request_adapter import (
        approve_onebot_friend_request,
        extract_onebot_friend_request,
    )
    from .src.handlers import PluginHandlers
    from .src.storage import CodeInviterStorage
    from .src.trigger_service import GroupTriggerService
else:
    from src.admin_service import AdminService
    from src.claim_service import ClaimService
    from src.command_views import CommandViews
    from src.config import parse_plugin_config
    from src.friend_service import FriendApprovalService
    from src.friend_request_adapter import (
        approve_onebot_friend_request,
        extract_onebot_friend_request,
    )
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
            command_views=self.command_views,
        )

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        logger.info(
            f"{self.name} loaded with data path {self.data_path} and export path {self.export_path}."
        )

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        result = self.handlers.handle_group_message(
            user_id=self._sender_id(event),
            group_id=self._group_id(event),
            message=event.message_str,
            is_admin=self._is_plugin_admin(event),
        )
        if not result.matched:
            return
        event.stop_event()
        yield event.plain_result(result.reply)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        result = self.handlers.handle_private_message(
            user_id=self._sender_id(event),
            message=event.message_str,
            is_admin=self._is_plugin_admin(event),
            user_nickname=event.get_sender_name(),
        )
        if not result.matched:
            return
        event.stop_event()
        yield event.plain_result(result.reply)

    @filter.event_message_type(filter.EventMessageType.OTHER_MESSAGE)
    async def on_other_message(self, event: AstrMessageEvent):
        payload = extract_onebot_friend_request(event)
        if payload is None:
            return
        result = self.handle_friend_request(user_id=payload.user_id, comment=payload.comment)
        if result["approved"]:
            approved = await approve_onebot_friend_request(event, flag=payload.flag)
            if approved:
                logger.info(f"{self.name} approved friend request for user {payload.user_id}.")
            else:
                logger.warning(f"{self.name} could not access OneBot friend approval API.")
        else:
            logger.info(
                f"{self.name} rejected friend request for user {payload.user_id}: {result['reason']}."
            )
        event.stop_event()

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
