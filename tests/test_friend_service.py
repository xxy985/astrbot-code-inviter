from datetime import UTC, datetime, timedelta

from src.config import parse_plugin_config
from src.friend_service import FriendApprovalService
from src.storage import CodeInviterStorage


def test_friend_request_approves_matching_token(tmp_path):
    config = parse_plugin_config({"friend_gate": {"token_template": "领码-{token}"}})
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    flow_id = storage.create_pending_friend_flow(
        user_id="1",
        group_id="100",
        pool_id="invite",
        verify_token="123456",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )

    decision = FriendApprovalService(config, storage).evaluate_request(
        user_id=1,
        comment="领码-123456",
    )

    assert decision.approved is True
    assert decision.reason == "approved"
    assert decision.flow_id == flow_id
    flow = storage.get_pending_friend_flow(flow_id)
    assert flow is not None
    assert flow["status"] == "approved"


def test_friend_request_rejects_expired_token(tmp_path):
    config = parse_plugin_config({"friend_gate": {"token_template": "领码-{token}"}})
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.create_pending_friend_flow(
        user_id="1",
        group_id="100",
        pool_id="invite",
        verify_token="123456",
        expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )

    decision = FriendApprovalService(config, storage).evaluate_request(
        user_id=1,
        comment="领码-123456",
    )

    assert decision.approved is False
    assert decision.reason == "token_expired"

