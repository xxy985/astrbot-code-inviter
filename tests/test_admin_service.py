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
    storage.add_code(pool_id="invite", code="CODE001")
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

    output_path, count = service.export_claim_records(pool_id="invite")

    assert count == 1
    content = output_path.read_text(encoding="utf-8-sig")
    assert "CODE001" in content
    assert "tester" in content

