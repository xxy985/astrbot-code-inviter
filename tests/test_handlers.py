from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.config import parse_plugin_config
from src.friend_service import FriendApprovalService
from src.handlers import PluginHandlers
from src.storage import CodeInviterStorage
from src.trigger_service import GroupTriggerService


def _build_handlers(tmp_path) -> tuple[PluginHandlers, CodeInviterStorage]:
    config = parse_plugin_config(
        {
            "global_allowed_groups": [100],
            "claim_gate": {"require_group_source": False},
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
