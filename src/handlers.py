"""AstrBot event adapters for the code inviter plugin."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .admin_service import AdminService
from .claim_service import ClaimService
from .command_views import CommandViews
from .friend_service import FriendApprovalService
from .trigger_service import GroupTriggerService


HELP_COMMANDS = ("帮助", "发码帮助", "码帮助")
TRIGGER_SEPARATORS = " \t\r\n，,：:、;；"


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
        prefixed = self._strip_at_prefix(normalized)
        if prefixed is None:
            return RoutedMessageView(matched=False)

        help_result = self._handle_help(prefixed)
        if help_result.matched:
            return help_result

        command_result = self.handle_admin_command(
            user_id=user_id,
            message=prefixed,
            is_admin=is_admin,
        )
        if command_result.matched:
            return command_result

        trigger_result = self.handle_group_trigger(
            user_id=user_id,
            group_id=group_id,
            message=prefixed,
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
        prefixed = self._strip_at_prefix(normalized)
        if prefixed is None:
            return RoutedMessageView(matched=False)

        help_result = self._handle_help(prefixed)
        if help_result.matched:
            return help_result

        command_result = self.handle_admin_command(
            user_id=user_id,
            message=prefixed,
            is_admin=is_admin,
        )
        if command_result.matched:
            return command_result

        claim_result = self.handle_private_claim(
            user_id=user_id,
            message=prefixed,
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

        return RoutedMessageView(matched=False)

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
        for command, aliases in self.trigger_service.config.admin_commands.aliases_by_command().items():
            matched = self._match_alias(message, aliases)
            if matched is None and command in ("pool_admin", "trigger_admin"):
                matched = self._match_compound_admin_alias(message, aliases)
            if matched is None:
                continue
            alias, args = matched
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

        if command == "pool_admin":
            return self._execute_pool_admin(args=args)

        if command == "trigger_admin":
            return self._execute_trigger_admin(args=args)

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
                return "用法：@记录 <用户QQ> [码池ID]"
            pool_id = parts[1] if len(parts) > 1 else ""
            records = self.admin_service.query_user_claims(user_id=parts[0], pool_id=pool_id)
            return self.command_views.claim_records(records)

        if command == "import_codes":
            payload = self.command_views.parse_import_text(raw_message)
            if not payload.pool_id or not payload.lines:
                return "用法：@导入码 <码池ID>，并在后续行粘贴码。"
            summary = self.admin_service.import_text_codes(pool_id=payload.pool_id, lines=payload.lines)
            return f"导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"

        if command == "import_csv":
            parts = self._split_args(args)
            if len(parts) < 2:
                return "用法：@导入csv <码池ID> <本地CSV路径>"
            summary = self.admin_service.import_csv_codes(pool_id=parts[0], csv_path=Path(parts[1]))
            return f"CSV 导入完成：成功 {summary.success}，重复 {summary.duplicate}，失败 {summary.failed}。"

        if command == "export_claims":
            parts = self._split_args(args)
            if not parts:
                return "用法：@导出领取记录 <码池ID> [开始日期] [结束日期]"
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
                return "用法：@重置领取 <码池ID> <用户QQ>"
            count = self.admin_service.reset_user_claims(pool_id=parts[0], user_id=parts[1])
            return f"已重置 {parts[1]} 在 {parts[0]} 的 {count} 条领取记录。"

        if command == "block_user":
            parts = self._split_args(args, maxsplit=1)
            if not parts:
                return "用法：@禁领 <用户QQ> [原因]"
            reason = parts[1] if len(parts) > 1 else ""
            self.admin_service.block_user(user_id=parts[0], reason=reason, created_by=str(user_id))
            return f"已禁领用户 {parts[0]}。"

        if command == "unblock_user":
            parts = self._split_args(args)
            if not parts:
                return "用法：@解禁 <用户QQ>"
            self.admin_service.unblock_user(user_id=parts[0])
            return f"已解除用户 {parts[0]} 的禁领状态。"

        return "未知管理命令。"

    def _handle_help(self, message: str) -> RoutedMessageView:
        matched = self._match_alias(message, HELP_COMMANDS)
        if matched is None:
            return RoutedMessageView(matched=False)
        return RoutedMessageView(matched=True, reply=self._help_text(), route="help")

    def _execute_pool_admin(self, *, args: str) -> str:
        parts = self._split_args(args, maxsplit=2)
        if not parts:
            pool_ids = self._known_pool_ids()
            if not pool_ids:
                return "暂无码池。用法：@码池新增 <码池ID> [展示名称]"
            lines = ["码池列表："]
            for pool_id in pool_ids:
                lines.append(self._pool_status_line(pool_id))
            lines.append("管理：@码池新增/修改/启用/禁用/删除 <码池ID> [展示名称]")
            return "\n".join(lines)

        action = parts[0]
        if action in ("新增", "添加", "add"):
            if len(parts) < 2:
                return "用法：@码池新增 <码池ID> [展示名称]"
            pool_id = parts[1]
            display_name = parts[2] if len(parts) > 2 else pool_id
            self.admin_service.upsert_pool(pool_id=pool_id, display_name=display_name, enabled=True)
            return f"已新增或更新码池 {pool_id}，展示名称：{display_name}。"

        if action in ("修改", "调整", "rename"):
            if len(parts) < 3:
                return "用法：@码池修改 <码池ID> <展示名称>"
            pool_id = parts[1]
            display_name = parts[2]
            self.admin_service.upsert_pool(pool_id=pool_id, display_name=display_name, enabled=True)
            return f"已调整码池 {pool_id}，展示名称：{display_name}。"

        if action in ("启用", "enable"):
            if len(parts) < 2:
                return "用法：@码池启用 <码池ID>"
            self.admin_service.set_pool_enabled(pool_id=parts[1], enabled=True)
            return f"已启用码池 {parts[1]}。"

        if action in ("禁用", "disable"):
            if len(parts) < 2:
                return "用法：@码池禁用 <码池ID>"
            self.admin_service.set_pool_enabled(pool_id=parts[1], enabled=False)
            return f"已禁用码池 {parts[1]}。"

        if action in ("删除", "移除", "delete"):
            if len(parts) < 2:
                return "用法：@码池删除 <码池ID>"
            deleted = self.admin_service.delete_empty_pool(pool_id=parts[1])
            if not deleted:
                return f"码池 {parts[1]} 存在库存或领取记录，未删除。"
            return f"已删除空码池 {parts[1]}。"

        return self._pool_status_line(action)

    def _execute_trigger_admin(self, *, args: str) -> str:
        parts = self._split_args(args, maxsplit=2)
        if not parts:
            return (
                "用法：\n"
                "@触发词 <码池ID>\n"
                "@触发词 <码池ID> 群 <触发词1,触发词2>\n"
                "@触发词 <码池ID> 私 <触发词1,触发词2>\n"
                "触发时需要带 @，例如：@领邀请码。"
            )

        pool_id = parts[0]
        if len(parts) == 1:
            group_triggers = self._effective_triggers(pool_id=pool_id, trigger_type="group")
            private_triggers = self._effective_triggers(pool_id=pool_id, trigger_type="private")
            return (
                f"{pool_id} 触发词：\n"
                f"群聊：{self._format_triggers(group_triggers)}\n"
                f"私聊：{self._format_triggers(private_triggers)}\n"
                "触发时需要带 @ 前缀。"
            )

        trigger_type = self._normalize_trigger_type(parts[1])
        if not trigger_type:
            return "触发词类型必须是 群 或 私。"
        if len(parts) < 3:
            return "用法：@触发词 <码池ID> 群|私 <触发词1,触发词2>"
        triggers = self._parse_trigger_list(parts[2])
        if not triggers:
            return "至少需要提供一个触发词。"
        self.admin_service.replace_pool_triggers(
            pool_id=pool_id,
            trigger_type=trigger_type,
            triggers=triggers,
        )
        label = "群聊" if trigger_type == "group" else "私聊"
        return f"已更新 {pool_id} 的{label}触发词：{', '.join(triggers)}。触发时需要带 @ 前缀。"

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

    def _strip_at_prefix(self, message: str) -> str | None:
        if not message.startswith("@"):
            return None
        command_text = message[1:].lstrip()
        return command_text or None

    def _match_alias(self, message: str, aliases) -> tuple[str, str] | None:
        for alias in sorted((alias.strip() for alias in aliases if alias.strip()), key=len, reverse=True):
            if message == alias:
                return alias, ""
            if message.startswith(alias):
                remainder = message[len(alias):]
                if remainder and remainder[0] in TRIGGER_SEPARATORS:
                    return alias, remainder[1:].lstrip()
        return None

    def _match_compound_admin_alias(self, message: str, aliases) -> tuple[str, str] | None:
        for alias in sorted((alias.strip() for alias in aliases if alias.strip()), key=len, reverse=True):
            if not message.startswith(alias):
                continue
            remainder = message[len(alias):].lstrip()
            if remainder:
                return alias, remainder
        return None

    def _known_pool_ids(self) -> list[str]:
        config_pool_ids = list(self.trigger_service.config.pools.keys())
        storage_pool_ids = self.admin_service.storage.list_pool_ids()
        return sorted(set(config_pool_ids + storage_pool_ids))

    def _pool_status_line(self, pool_id: str) -> str:
        status = self.admin_service.pool_status(pool_id=pool_id)
        enabled = "启用" if status["enabled"] else "禁用"
        display_name = str(status["display_name"] or self.command_views.pool_name(pool_id))
        return (
            f"{pool_id}({display_name}) {enabled}: "
            f"unused={status['unused']} claimed={status['claimed']} "
            f"disabled={status['disabled']} claim_records={status['claim_records']}"
        )

    def _effective_triggers(self, *, pool_id: str, trigger_type: str) -> list[str]:
        dynamic = self.admin_service.list_pool_triggers(pool_id=pool_id, trigger_type=trigger_type)
        if dynamic:
            return dynamic
        pool = self.trigger_service.config.pools.get(pool_id)
        if pool is None:
            return []
        if trigger_type == "group":
            return list(pool.group_triggers)
        return list(pool.private_triggers)

    def _format_triggers(self, triggers: list[str]) -> str:
        return ", ".join(f"@{trigger}" for trigger in triggers) if triggers else "未设置"

    def _normalize_trigger_type(self, trigger_type: str) -> str:
        if trigger_type in ("群", "群聊", "group"):
            return "group"
        if trigger_type in ("私", "私聊", "private"):
            return "private"
        return ""

    def _parse_trigger_list(self, raw: str) -> list[str]:
        normalized = raw.replace("，", ",").replace("、", ",")
        triggers = []
        seen = set()
        for item in normalized.split(","):
            trigger = item.strip()
            if not trigger or trigger in seen:
                continue
            triggers.append(trigger)
            seen.add(trigger)
        return triggers

    def _help_text(self) -> str:
        return (
            "发码插件命令：\n"
            "@帮助\n"
            "@领邀请码 进入对应码池加好友流程\n"
            "@领取邀请码 私聊领取邀请码\n"
            "@库存 [码池ID]\n"
            "@统计 [码池ID]\n"
            "@导入码 <码池ID>，后续行粘贴码\n"
            "@码池新增/修改/启用/禁用/删除 <码池ID> [展示名称]\n"
            "@触发词 <码池ID> 群|私 <触发词1,触发词2>\n"
            "只有预设 @命令词 会进入插件流程，其他消息交由 AstrBot 处理。"
        )

    def _first_arg(self, args: str) -> str:
        parts = self._split_args(args)
        return parts[0] if parts else ""

    def _split_args(self, args: str, maxsplit: int = -1) -> list[str]:
        return args.split(maxsplit=maxsplit) if args.strip() else []
