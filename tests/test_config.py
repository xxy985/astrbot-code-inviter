from src.config import parse_plugin_config


def test_parse_multi_pool_config():
    config = parse_plugin_config(
        {
            "admin_users": ["123"],
            "global_allowed_groups": ["456"],
            "friend_gate": {"token_ttl_minutes": 15},
            "csv": {"export_dir": "out"},
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "group_triggers": ["领邀请码"],
                    "private_triggers": ["领取邀请码"],
                }
            },
        }
    )

    assert config.admin_users == [123]
    assert config.global_allowed_groups == [456]
    assert config.token_ttl_minutes == 15
    assert config.require_group_source is True
    assert config.export_dir == "out"
    assert config.pools["invite"].display_name == "邀请码"
    assert config.pools["invite"].group_triggers == ["领邀请码"]
