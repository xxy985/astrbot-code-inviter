"""AstrBot event adapters for the code inviter plugin."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .admin_service import AdminService
from .claim_service import ClaimService
from .command_views import CommandViews
from .friend_service import FriendApprovalService
from .trigger_service import GroupTriggerService


@dataclass(slots=True)
class GroupTriggerView:
    matched: bool
    pool_id: str
    guide_message: str


@dataclass(slots=True)
class PrivateClaimView:
    claimed: bool
    reason: str
    pool_id: str
    code: str


@dataclass(slots=True)
class FriendRequestView:
    approved: bool
    reason: str
    pool_id: str
    flow_id: int | None


@dataclass(slots=True)
class RoutedMessageView:
    matched: bool
    reply: str = ""
    route: str = ""
    pool_id: str = ""


class PluginHandlers:
    """Thin translation layer between AstrBot events and services."""

    def __init__(
        self,
        *,
        trigger_service: GroupTriggerService,
        claim_service: ClaimService,
        friend_service: FriendApprovalService,
        admin_service: AdminService,
        command_views: CommandViews | None = None,
    ) -> None:
        self.trigger_service = trigger_service
        self.claim_service = claim_service
        self.friend_service = friend_service
        self.admin_service = admin_service
        self.command_views = command_views or CommandViews(trigger_service.config)

    def handle_group_message(
        self,
        *,
        user_id: int,
        group_id: int,
        message: str,
        is_admin: bool = False,
    ) -> RoutedMessageView:
        normalized = self._normalize_message(message)
        command_result = self.handle_admin_command(
            user_id=user_id,
            message=normalized,
            is_admin=is_admin,
        )
        if command_result.matched:
            return command_result

        trigger_result = self.handle_group_trigger(
            user_id=user_id,
            group_id=group_id,
            message=normalized,
        )
        if not trigger_result.matched:
            return RoutedMessageView(matched=False)
        return RoutedMessageView(
            matched=True,
            reply=trigger_result.guide_message,
            route="group_trigger",
            pool_id=trigger_result.pool_id,
        )

    def handle_private_message(
        self,
        *,
        user_id: int,
        message: str,
        is_admin: bool = False,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> RoutedMessageView:
        normalized = self._normalize_message(message)
        claim_result = self.handle_private_claim(
            user_id=user_id,
            message=normalized,
            user_nickname=user_nickname,
            source_group_id=source_group_id,
            source_group_name=source_group_name,
        )
        if claim_result.reason != "trigger_not_matched":
            return RoutedMessageView(
                matched=True,
                reply=self.command_views.claim_reply(
                    {
                        "claimed": claim_result.claimed,
                        "reason": claim_result.reason,
                        "pool_id": claim_result.pool_id,
                        "code": claim_result.code,
                    }
                ),
                route="private_claim",
                pool_id=claim_result.pool_id,
            )

        return self.handle_admin_command(
            user_id=user_id,
            message=normalized,
            is_admin=is_admin,
        )

    def handle_group_trigger(self, *, user_id: int, group_id: int, message: str) -> GroupTriggerView:
        result = self.trigger_service.handle_group_message(user_id=user_id, group_id=group_id, message=message)
        return GroupTriggerView(result.matched, result.pool_id, result.guide_message)

    def handle_private_claim(
        self,
        *,
        user_id: int,
        message: str,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> PrivateClaimView:
        result = self.claim_service.handle_private_message(
            user_id=user_id,
            message=message,
            user_nickname=user_nickname,
            source_group_id=source_group_id,
            source_group_name=source_group_name,
        )
        return PrivateClaimView(result.claimed, result.reason, result.pool_id, result.code)

    def handle_friend_request(self, *, user_id: int, comment: str) -> FriendRequestView:
        result = self.friend_service.evaluate_request(user_id=user_id, comment=comment)
        return FriendRequestView(result.approved, result.reason, result.pool_id, result.flow_id)

    def handle_admin_command(self, *, user_id: int, message: str, is_admin: bool) -> RoutedMessageView:
        parsed = self._parse_admin_command(message)
        if parsed is None:
            return RoutedMessageView(matched=False)
        command, args = parsed
        if not is_admin:
            return RoutedMessageView(matched=True, reply="无权限执行该命令。", route=f"admin:{command}")
        return RoutedMessageView(
            matched=True,
            reply=self._execute_admin_command(command=command, args=args, user_id=user_id, raw_message=message),
            route=f"admin:{command}",
        )

    def _parse_admin_command(self, message: str) -> tuple[str, str] | None:
        head = message.split(maxsplit=1)[0] if message else ""
        for command, aliases in self.trigger_service.config.admin_commands.aliases_by_command().items():
            for alias in aliases:
                if head == alias or message == alias:
                    args = message[len(alias):].lstrip()
                    return command, args
        return None

    def _execute_admin_command(self, *, command: str, args: str, user_id: int, raw_message: str) -> str:
        if command == "inventory":
            pool_id = self._first_arg(args)
            pools = [pool_id] if pool_id else self._known_pool_ids()
            if not pools:
                return "暂无码池库存。"
            lines = []
            for current_pool_id in pools:
                counts = self.admin_service.inventory(pool_id=current_pool_id)
                lines.append(
                    f"{current_pool_id}: unused={counts['unused']} claimed={counts['claimed']} disabled={counts['disabled']}"
                )
            return "\n".join(lines)

        if command == "statistics":
            pool_id = self._first_arg(args)
            stats = self.admin_service.statistics(pool_id=pool_id)
            return (
                "库存统计："
                f"unused={stats['unused']} claimed={stats['claimed']} "
                f"disabled={stats['disabled']} claim_records={stats['claim_records']}"
            )

        if command == "query_claims":
            parts = self._split_args(args)
            if not parts:
                return "用法：/查领取 <用户QQ> [码池ID]"
            pool_id = parts[1] if len(parts) > 1 else ""
            records = self.admin_service.query_user_claims(user_id=parts[0], pool_id=pool_id)
            return self.command_views.claim_records(records)

        if command == "import_codes":
            payload = self.command_views.parse_import_text(raw_message)
            if not payload.pool_id or not payload.lines:
                return "用法：/导入码 <码池ID>，并在后续行粘贴码。"
            summary = self.admin_service.import_text_codes(pool_id=payload.pool_id, lines=payload.lines)
            return f"导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"

        if command == "import_csv":
            parts = self._split_args(args)
            if len(parts) < 2:
                return "用法：/导入csv <码池ID> <本地CSV路径>"
            summary = self.admin_service.import_csv_codes(pool_id=parts[0], csv_path=Path(parts[1]))
            return f"CSV 导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"

        if command == "export_claims":
            parts = self._split_args(args)
            if not parts:
                return "用法：/导出领取记录 <码池ID> [开始日期] [结束日期]"
            claimed_after = parts[1] if len(parts) > 1 else ""
            claimed_before = parts[2] if len(parts) > 2 else ""
            output_path, count = self.admin_service.export_claim_records(
                pool_id=parts[0],
                pool_name=self.command_views.pool_name(parts[0]),
                claimed_after=claimed_after,
                claimed_before=claimed_before,
            )
            return f"导出完成：{count} 条，文件：{output_path}"

        if command == "reset_claims":
            parts = self._split_args(args)
            if len(parts) < 2:
                return "用法：/重置领取 <码池ID> <用户QQ>"
            count = self.admin_service.reset_user_claims(pool_id=parts[0], user_id=parts[1])
            return f"已重置 {parts[1]} 在 {parts[0]} 的 {count} 条领取记录。"

        if command == "block_user":
            parts = self._split_args(args, maxsplit=1)
            if not parts:
                return "用法：/禁领 <用户QQ> [原因]"
            reason = parts[1] if len(parts) > 1 else ""
            self.admin_service.block_user(user_id=parts[0], reason=reason, created_by=str(user_id))
            return f"已禁领用户 {parts[0]}。"

        if command == "unblock_user":
            parts = self._split_args(args)
            if not parts:
                return "用法：/解禁 <用户QQ>"
            self.admin_service.unblock_user(user_id=parts[0])
            return f"已解除用户 {parts[0]} 的禁领状态。"

        return "未知管理命令。"

    def _normalize_message(self, message: str) -> str:
        normalized = message.strip()
        for alias in self.trigger_service.config.bot_aliases:
            alias = alias.strip()
            if not alias or not normalized.startswith(alias):
                continue
            remainder = normalized[len(alias):]
            if not remainder:
                return normalized
            if remainder[0].isspace() or remainder[0] in "，,：:、;；":
                return remainder[1:].lstrip()
        return normalized

    def _known_pool_ids(self) -> list[str]:
        config_pool_ids = list(self.trigger_service.config.pools.keys())
        storage_pool_ids = self.admin_service.storage.list_pool_ids()
        return sorted(set(config_pool_ids + storage_pool_ids))

    def _first_arg(self, args: str) -> str:
        parts = self._split_args(args)
        return parts[0] if parts else ""

    def _split_args(self, args: str, maxsplit: int = -1) -> list[str]:
        return args.split(maxsplit=maxsplit) if args.strip() else []
