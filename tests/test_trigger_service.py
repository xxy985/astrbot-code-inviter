from src.config import parse_plugin_config
from src.storage import CodeInviterStorage
from src.trigger_service import GroupTriggerService


def test_group_trigger_creates_pending_flow(tmp_path):
    config = parse_plugin_config(
        {
            "global_allowed_groups": [100],
            "friend_gate": {"token_ttl_minutes": 30, "token_template": "领码-{token}"},
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

    result = GroupTriggerService(config, storage).handle_group_message(
        user_id=1,
        group_id=100,
        message="领邀请码",
    )

    assert result.matched is True
    assert result.pool_id == "invite"
    assert "领取邀请码" in result.guide_message
    assert result.flow_id is not None
    flow = storage.get_pending_friend_flow(result.flow_id)
    assert flow is not None
    assert flow["user_id"] == "1"
    assert flow["group_id"] == "100"
    assert flow["pool_id"] == "invite"


def test_group_trigger_rejects_unallowed_group(tmp_path):
    config = parse_plugin_config(
        {
            "global_allowed_groups": [100],
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "group_triggers": ["领邀请码"],
                }
            },
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()

    result = GroupTriggerService(config, storage).handle_group_message(
        user_id=1,
        group_id=200,
        message="领邀请码",
    )

    assert result.matched is False
