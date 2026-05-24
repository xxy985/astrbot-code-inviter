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
                "inventory": ["发码库存", "全部库存"],
                "statistics": ["发码统计"],
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
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
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
        message="秋秋，发码库存",
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
        message="全部库存",
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
        message="秋秋，发码统计",
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
        message="秋秋，发码库存",
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
        message="秋秋，领邀请码",
        is_admin=False,
    )

    assert result.matched is True
    assert result.route == "group_trigger"
    assert result.pool_id == "invite"
