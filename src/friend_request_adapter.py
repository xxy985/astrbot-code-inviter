"""OneBot friend request adapter helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FriendRequestPayload:
    user_id: int
    comment: str
    flag: str


def extract_onebot_friend_request(event: Any) -> FriendRequestPayload | None:
    """Extract a OneBot v11 friend request from an AstrBot event."""

    raw = getattr(getattr(event, "message_obj", None), "raw_message", None)
    if not raw or _raw_get(raw, "post_type") != "request":
        return None
    if _raw_get(raw, "request_type") != "friend":
        return None

    user_id = _raw_get(raw, "user_id")
    flag = str(_raw_get(raw, "flag") or "")
    if user_id in ("", None) or not flag:
        return None
    return FriendRequestPayload(
        user_id=int(user_id),
        comment=str(_raw_get(raw, "comment") or ""),
        flag=flag,
    )


async def approve_onebot_friend_request(event: Any, *, flag: str) -> bool:
    """Approve a OneBot v11 friend request through AstrBot's aiocqhttp API."""

    call_action = _resolve_call_action(event)
    if call_action is None:
        return False
    await call_action("set_friend_add_request", flag=flag, approve=True)
    return True


def _resolve_call_action(event: Any):
    bot = getattr(event, "bot", None)
    api = getattr(bot, "api", None)
    call_action = getattr(api, "call_action", None)
    return call_action if callable(call_action) else None


def _raw_get(raw: Any, key: str) -> Any:
    if isinstance(raw, dict):
        return raw.get(key)
    get = getattr(raw, "get", None)
    if callable(get):
        return get(key)
    return getattr(raw, key, None)
