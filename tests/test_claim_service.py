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
        }
    )
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
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
        }
    )
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.add_code(pool_id="invite", code="CODE002")
    service = ClaimService(config, storage)

    first = service.handle_private_message(user_id=1, message="领取邀请码")
    second = service.handle_private_message(user_id=1, message="领取邀请码")

    assert first.claimed is True
    assert second.claimed is False
    assert second.reason == "already_claimed"

