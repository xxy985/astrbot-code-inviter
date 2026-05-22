from src.command_views import CommandViews
from src.config import parse_plugin_config


def test_command_views_render_claim_success_with_pool_name():
    config = parse_plugin_config(
        {
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                }
            }
        }
    )

    text = CommandViews(config).claim_reply(
        {
            "claimed": True,
            "pool_id": "invite",
            "reason": "claimed",
            "code": "CODE001",
        }
    )

    assert text == "你的邀请码是：CODE001"


def test_command_views_parse_import_text_payload():
    payload = CommandViews(parse_plugin_config({})).parse_import_text(
        "/导入码 invite\nCODE001\n\nCODE002"
    )

    assert payload.pool_id == "invite"
    assert payload.lines == ["CODE001", "CODE002"]
