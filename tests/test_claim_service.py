from src.claim_service import ClaimService
from src.config import parse_plugin_config
from src.storage import CodeInviterStorage


def test_private_claim_sends_one_unused_code(tmp_path):
    config = parse_plugin_config(
        {
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                    "claim_policy": {"mode": "once_per_user"},
                }
            },
            "claim_gate": {"require_group_source": False},
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    assert storage.add_code(pool_id="invite", code="CODE001") is True
    assert storage.add_code(pool_id="invite", code="CODE002") is True

    result = ClaimService(config, storage).handle_private_message(
        user_id=1,
        message="领取邀请码",
        user_nickname="tester",
        source_group_id="100",
    )

    assert result.claimed is True
    assert result.code == "CODE001"


def test_once_per_user_rejects_second_claim(tmp_path):
    config = parse_plugin_config(
        {
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                    "claim_policy": {"mode": "once_per_user"},
                }
            },
            "claim_gate": {"require_group_source": False},
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.add_code(pool_id="invite", code="CODE002")
    service = ClaimService(config, storage)

    first = service.handle_private_message(user_id=1, message="领取邀请码")
    second = service.handle_private_message(user_id=1, message="领取邀请码")

    assert first.claimed is True
    assert second.claimed is False
    assert second.reason == "already_claimed"


def test_private_claim_requires_approved_source_flow(tmp_path):
    config = parse_plugin_config(
        {
            "claim_gate": {"require_group_source": True},
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                    "claim_policy": {"mode": "once_per_user"},
                }
            },
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")

    result = ClaimService(config, storage).handle_private_message(
        user_id=1,
        message="领取邀请码",
    )

    assert result.claimed is False
    assert result.reason == "not_friend_flow"


def test_private_claim_rejects_blocked_user(tmp_path):
    config = parse_plugin_config(
        {
            "claim_gate": {"require_group_source": False},
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                }
            },
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.upsert_blocked_user(user_id="1", reason="abuse", created_by="admin")

    result = ClaimService(config, storage).handle_private_message(
        user_id=1,
        message="领取邀请码",
    )

    assert result.claimed is False
    assert result.reason == "blocked"


def test_limited_per_user_rejects_after_configured_limit(tmp_path):
    config = parse_plugin_config(
        {
            "claim_gate": {"require_group_source": False},
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                    "claim_policy": {
                        "mode": "limited_per_user",
                        "per_user_limit": 2,
                        "cooldown_seconds": 0,
                    },
                }
            },
        }
    )
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    for code in ["CODE001", "CODE002", "CODE003"]:
        storage.add_code(pool_id="invite", code=code)
    service = ClaimService(config, storage)

    assert service.handle_private_message(user_id=1, message="领取邀请码").claimed is True
    assert service.handle_private_message(user_id=1, message="领取邀请码").claimed is True
    third = service.handle_private_message(user_id=1, message="领取邀请码")

    assert third.claimed is False
    assert third.reason == "limit_reached"
