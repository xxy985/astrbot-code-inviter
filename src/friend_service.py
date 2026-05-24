"""Friend request verification service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .config import PluginConfig
from .storage import CodeInviterStorage


@dataclass(slots=True)
class FriendApprovalDecision:
    approved: bool
    reason: str
    pool_id: str = ""
    flow_id: int | None = None


class FriendApprovalService:
    """Validate friend requests against pending group-trigger flows."""

    def __init__(self, config: PluginConfig, storage: CodeInviterStorage) -> None:
        self.config = config
        self.storage = storage

    def evaluate_request(self, *, user_id: int, comment: str) -> FriendApprovalDecision:
        token = self._extract_token(comment)
        if not token:
            return FriendApprovalDecision(approved=False, reason="missing_token")

        flow = self.storage.find_pending_friend_flow(user_id=str(user_id), verify_token=token)
        if flow is None:
            return FriendApprovalDecision(approved=False, reason="pending_flow_not_found")

        if self._is_expired(str(flow["expires_at"])):
            return FriendApprovalDecision(
                approved=False,
                reason="token_expired",
                pool_id=str(flow["pool_id"]),
                flow_id=int(flow["id"]),
            )

        self.storage.mark_pending_friend_flow_approved(int(flow["id"]))
        return FriendApprovalDecision(
            approved=True,
            reason="approved",
            pool_id=str(flow["pool_id"]),
            flow_id=int(flow["id"]),
        )

    def _extract_token(self, comment: str) -> str:
        prefix, marker, suffix = self.config.token_template.partition("{token}")
        if not marker:
            return comment.strip()
        text = comment.strip()
        if prefix and not text.startswith(prefix):
            return ""
        if suffix and not text.endswith(suffix):
            return ""
        start = len(prefix)
        end = len(text) - len(suffix) if suffix else len(text)
        return text[start:end].strip()

    def _is_expired(self, expires_at: str) -> bool:
        parsed = datetime.fromisoformat(expires_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed <= datetime.now(UTC)
