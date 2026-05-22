from datetime import UTC, datetime, timedelta

from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.config import parse_plugin_config
from src.storage import CodeInviterStorage


def test_import_text_codes_counts_duplicates(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")

    summary = service.import_text_codes(
        pool_id="invite",
        lines=["CODE001", "CODE001", "", "CODE002"],
    )

    assert summary.success == 2
    assert summary.duplicate == 1
    assert summary.failed == 0
    assert service.inventory(pool_id="invite")["unused"] == 2


def test_export_claim_records_writes_csv(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001", batch="batch-a")
    config = parse_plugin_config(
        {
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "private_triggers": ["领取邀请码"],
                }
            }
        }
    )
    ClaimService(config, storage).handle_private_message(
        user_id=1,
        message="领取邀请码",
        user_nickname="tester",
        source_group_id="100",
        source_group_name="测试群",
    )
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")

    output_path, count = service.export_claim_records(pool_id="invite", pool_name="邀请码")

    assert count == 1
    content = output_path.read_text(encoding="utf-8-sig")
    assert "CODE001" in content
    assert "batch-a" in content
    assert "邀请码" in content
    assert "tester" in content


def test_import_csv_codes_counts_failures_and_duplicates(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")
    csv_path = tmp_path / "codes.csv"
    csv_path.write_text("code,batch,remark\nCODE001,b1,one\nCODE001,b1,dup\n,b2,empty\n", encoding="utf-8-sig")

    summary = service.import_csv_codes(pool_id="invite", csv_path=csv_path)

    assert summary.success == 1
    assert summary.duplicate == 1
    assert summary.failed == 1
    assert service.inventory(pool_id="invite")["unused"] == 1


def test_query_user_claims_returns_claim_summaries(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001", batch="batch-a")
    storage.claim_next_code(pool_id="invite", user_id="123", user_nickname="tester")
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")

    records = service.query_user_claims(user_id="123", pool_id="invite")

    assert len(records) == 1
    assert records[0].pool_id == "invite"
    assert records[0].code == "CODE001"
    assert records[0].batch == "batch-a"


def test_block_and_unblock_user(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")

    service.block_user(user_id="123", reason="abuse", created_by="admin")
    assert storage.is_blocked_user(user_id="123") is True

    service.unblock_user(user_id="123")
    assert storage.is_blocked_user(user_id="123") is False


def test_export_claim_records_filters_date_range(tmp_path):
    storage = CodeInviterStorage(tmp_path / "code_inviter.sqlite3")
    storage.initialize()
    storage.add_code(pool_id="invite", code="CODE001")
    storage.claim_next_code(pool_id="invite", user_id="123")
    claimed_after = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    service = AdminService(storage=storage, export_dir=tmp_path / "exports")

    _, count = service.export_claim_records(pool_id="invite", claimed_after=claimed_after)

    assert count == 0
