from src.storage import CodeInviterStorage


def test_storage_initializes_schema(tmp_path):
    storage = CodeInviterStorage(":memory:")
    storage.initialize()

    with storage.connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "codes" in tables
    assert "claim_records" in tables
    assert "pending_friend_flows" in tables
    assert "blocked_users" in tables
