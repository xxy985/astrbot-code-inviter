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


def test_parse_trigger_takeover_config():
    config = parse_plugin_config(
        {
            "bot_aliases": ["秋秋", "bot"],
            "admin_commands": {
                "inventory": ["库存", "全部库存"],
                "statistics": ["统计"],
            },
            "code_pools": {
                "invite": {
                    "display_name": "邀请码",
                    "group_triggers": ["群领"],
                    "private_triggers": ["私领"],
                },
                "redeem": {
                    "display_name": "兑换码",
                    "group_triggers": ["兑换群领"],
                    "private_triggers": ["兑换私领"],
                },
            },
        }
    )

    assert config.bot_aliases == ["秋秋", "bot"]
    assert config.admin_commands.inventory == ["库存", "全部库存"]
    assert config.admin_commands.statistics == ["统计"]
    assert config.admin_commands.query_claims == ["查领取", "/查领取"]
    assert config.pools["invite"].group_triggers == ["群领"]
    assert config.pools["redeem"].private_triggers == ["兑换私领"]
