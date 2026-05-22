import pytest

from src.friend_request_adapter import (
    approve_onebot_friend_request,
    extract_onebot_friend_request,
)


class RawEvent:
    def __init__(self, payload):
        self.message_obj = type("Message", (), {"raw_message": payload})()


def test_extract_onebot_friend_request_payload():
    event = RawEvent(
        {
            "post_type": "request",
            "request_type": "friend",
            "user_id": 123,
            "comment": "领码-123456",
            "flag": "request-flag",
        }
    )

    payload = extract_onebot_friend_request(event)

    assert payload is not None
    assert payload.user_id == 123
    assert payload.comment == "领码-123456"
    assert payload.flag == "request-flag"


def test_extract_onebot_friend_request_ignores_group_request():
    event = RawEvent(
        {
            "post_type": "request",
            "request_type": "group",
            "user_id": 123,
            "flag": "request-flag",
        }
    )

    assert extract_onebot_friend_request(event) is None


@pytest.mark.asyncio
async def test_approve_onebot_friend_request_calls_action():
    calls = []

    async def call_action(action, **params):
        calls.append((action, params))

    api = type("Api", (), {})()
    api.call_action = call_action
    event = type("Event", (), {"bot": type("Bot", (), {"api": api})()})()

    assert await approve_onebot_friend_request(event, flag="request-flag") is True
    assert calls == [("set_friend_add_request", {"flag": "request-flag", "approve": True})]
