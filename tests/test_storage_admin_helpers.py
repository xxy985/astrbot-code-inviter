from src.storage import CodeInviterStorage


def test_storage_lists_claim_records_by_user(tmp_path):
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.claim_next_code(pool_id="invite", user_id="123", user_nickname="tester")

    records = storage.list_claim_records_by_user(user_id="123")

    assert len(records) == 1
    assert records[0]["pool_id"] == "invite"
    assert records[0]["code"] == "CODE001"


def test_storage_can_block_and_unblock_user(tmp_path):
    storage = CodeInviterStorage(":memory:")
    storage.initialize()

    storage.upsert_blocked_user(user_id="123", reason="abuse", created_by="admin")
    assert storage.is_blocked_user(user_id="123") is True

    storage.remove_blocked_user(user_id="123")
    assert storage.is_blocked_user(user_id="123") is False


def test_storage_resets_user_claims(tmp_path):
    storage = CodeInviterStorage(":memory:")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.claim_next_code(pool_id="invite", user_id="123")

    assert storage.reset_user_claims(pool_id="invite", user_id="123") == 1
    assert storage.count_claims_for_user(pool_id="invite", user_id="123") == 0
    assert storage.count_codes_by_status(pool_id="invite")["unused"] == 1
