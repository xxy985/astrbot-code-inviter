"""AstrBot code inviter plugin entry point."""

from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.config import parse_plugin_config
from src.friend_service import FriendApprovalService
from src.handlers import PluginHandlers
from src.storage import CodeInviterStorage
from src.trigger_service import GroupTriggerService


class AstrBotCodeInviterPlugin(Star):
    """Minimal plugin shell for AstrBot.

    The first slice keeps the plugin loadable, gives it a stable data
    directory, and leaves the actual code-pool logic for later commits.
    """

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
