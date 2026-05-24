from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.command_views import CommandViews
from src.config import parse_plugin_config
from src.friend_service import FriendApprovalService
from src.handlers import PluginHandlers
from src.storage import CodeInviterStorage
from src.trigger_service import GroupTriggerService


def _build_handlers(tmp_path) -> tuple[PluginHandlers, CodeInviterStorage]:
    config = parse_plugin_config(
        {
            "admin_users": [999],
            "bot_aliases": ["秋秋"],
            "global_allowed_groups": [100],
            "claim_gate": {"require_group_source": False},
            "admin_commands": {
                "inventory": ["库存", "发码库存", "全部库存"],
                "statistics": ["统计", "发码统计"],
                "import_codes": ["导入码"],
                "pool_admin": ["码池"],
                "trigger_admin": ["触发词"],
            },
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "group_triggers": ["领邀请码"],
                    "private_triggers": ["领取邀请码"],
                }
            },
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    handlers = PluginHandlers(
        trigger_service=GroupTriggerService(config, storage),
        claim_service=ClaimService(config, storage),
        friend_service=FriendApprovalService(config, storage),
        admin_service=AdminService(storage, tmp_path / "exports"),
        command_views=CommandViews(config),
    )
    return handlers, storage


def test_handlers_translate_group_trigger_result(tmp_path):
    handlers, storage = _build_handlers(tmp_path)

    result = handlers.handle_group_trigger(user_id=1, group_id=100, message="领邀请码")

    assert result.matched is True
    assert result.pool_id == "invite"
    assert "领取邀请码" in result.guide_message
    assert storage.find_latest_approved_flow(user_id="1") is None


def test_handlers_translate_private_claim_result(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    result = handlers.handle_private_claim(user_id=1, message="领取邀请码")

    assert result.claimed is True
    assert result.pool_id == "invite"
    assert result.code == "CODE001"


def test_group_message_routes_prefixed_inventory_alias_and_stops_takeover(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="秋秋，@发码库存",
        is_admin=True,
    )

    assert result.matched is True
    assert result.route == "admin:inventory"
    assert "invite: unused=1 claimed=0 disabled=0" in result.reply


def test_group_message_routes_configured_inventory_alias(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@全部库存",
        is_admin=True,
    )

    assert result.matched is True
    assert result.route == "admin:inventory"
    assert "unused=1" in result.reply


def test_group_message_routes_prefixed_statistics_alias(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="秋秋，@发码统计",
        is_admin=True,
    )

    assert result.matched is True
    assert result.route == "admin:statistics"
    assert "库存统计：unused=1 claimed=0 disabled=0 claim_records=0" == result.reply


def test_non_admin_matching_admin_command_is_intercepted(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="秋秋，@发码库存",
        is_admin=False,
    )

    assert result.matched is True
    assert result.route == "admin:inventory"
    assert result.reply == "无权限执行该命令。"


def test_unmatched_group_message_passes_through(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="普通聊天",
        is_admin=False,
    )

    assert result.matched is False


def test_prefixed_group_trigger_uses_code_pool_config(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="秋秋，@领邀请码",
        is_admin=False,
    )

    assert result.matched is True
    assert result.route == "group_trigger"
    assert result.pool_id == "invite"


def test_bare_group_trigger_passes_through(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="领邀请码",
        is_admin=False,
    )

    assert result.matched is False


def test_unknown_at_command_passes_through(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="@天气",
        is_admin=False,
    )

    assert result.matched is False


def test_bare_import_message_passes_through(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="导入码：123test",
        is_admin=True,
    )

    assert result.matched is False


def test_at_import_codes_routes_to_admin_state_machine(tmp_path):
    handlers, storage = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@导入码 invite\nCODE001\nCODE002",
        is_admin=True,
    )

    assert result.matched is True
    assert result.route == "admin:import_codes"
    assert result.reply == "导入完成：成功 2，重复 0，失败 0。"
    assert storage.count_codes_by_status(pool_id="invite")["unused"] == 2


def test_help_command_is_whitelisted(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="@帮助",
        is_admin=False,
    )

    assert result.matched is True
    assert result.route == "help"
    assert "@码池新增" in result.reply


def test_pool_admin_can_add_disable_enable_and_delete_empty_pool(tmp_path):
    handlers, storage = _build_handlers(tmp_path)

    add_result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@码池新增 beta 测试池",
        is_admin=True,
    )
    disable_result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@码池禁用 beta",
        is_admin=True,
    )
    enable_result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@码池启用 beta",
        is_admin=True,
    )
    delete_result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@码池删除 beta",
        is_admin=True,
    )

    assert add_result.reply == "已新增或更新码池 beta，展示名称：测试池。"
    assert disable_result.reply == "已禁用码池 beta。"
    assert enable_result.reply == "已启用码池 beta。"
    assert delete_result.reply == "已删除空码池 beta。"
    assert storage.get_pool(pool_id="beta") is None


def test_pool_admin_refuses_delete_pool_with_codes(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@码池删除 invite",
        is_admin=True,
    )

    assert result.reply == "码池 invite 存在库存或领取记录，未删除。"


def test_trigger_admin_updates_group_trigger_and_requires_at_prefix(tmp_path):
    handlers, _ = _build_handlers(tmp_path)

    update_result = handlers.handle_group_message(
        user_id=999,
        group_id=100,
        message="@触发词 invite 群 领内测码,领邀请码",
        is_admin=True,
    )
    bare_result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="领内测码",
        is_admin=False,
    )
    at_result = handlers.handle_group_message(
        user_id=1,
        group_id=100,
        message="@领内测码",
        is_admin=False,
    )

    assert update_result.reply == "已更新 invite 的群聊触发词：领内测码, 领邀请码。触发时需要带 @ 前缀。"
    assert bare_result.matched is False
    assert at_result.matched is True
    assert at_result.route == "group_trigger"


def test_trigger_admin_updates_private_trigger(tmp_path):
    handlers, storage = _build_handlers(tmp_path)
    storage.add_code(pool_id="invite", code="CODE001")

    update_result = handlers.handle_private_message(
        user_id=999,
        message="@触发词 invite 私 取码",
        is_admin=True,
    )
    bare_result = handlers.handle_private_message(
        user_id=1,
        message="取码",
        is_admin=False,
    )
    claim_result = handlers.handle_private_message(
        user_id=1,
        message="@取码",
        is_admin=False,
    )

    assert update_result.reply == "已更新 invite 的私聊触发词：取码。触发时需要带 @ 前缀。"
    assert bare_result.matched is False
    assert claim_result.matched is True
    assert claim_result.route == "private_claim"
    assert "CODE001" in claim_result.reply
