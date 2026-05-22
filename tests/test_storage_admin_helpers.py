from src.storage import CodeInviterStorage


def test_storage_lists_claim_records_by_user(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.claim_next_code(pool_id="invite", user_id="123", user_nickname="tester")

    records = storage.list_claim_records_by_user(user_id="123")

    assert len(records) == 1
    assert records[0]["pool_id"] == "invite"
    assert records[0]["code"] == "CODE001"


def test_storage_can_block_and_unblock_user(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()

    storage.upsert_blocked_user(user_id="123", reason="abuse", created_by="admin")
    assert storage.is_blocked_user(user_id="123") is True

    storage.remove_blocked_user(user_id="123")
    assert storage.is_blocked_user(user_id="123") is False
