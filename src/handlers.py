"""AstrBot event adapters for the code inviter plugin."""

from __future__ import annotations

from dataclasses import dataclass

from src.admin_service import AdminService
from src.claim_service import ClaimService
from src.friend_service import FriendApprovalService
from src.trigger_service import GroupTriggerService


@dataclass(slots=True)
class GroupTriggerView:
    matched: bool
    pool_id: str
    guide_message: str


@dataclass(slots=True)
class PrivateClaimView:
    claimed: bool
    reason: str
    pool_id: str
    code: str


@dataclass(slots=True)
class FriendRequestView:
    approved: bool
    reason: str
    pool_id: str
    flow_id: int | None


class PluginHandlers:
    """Thin translation layer between AstrBot events and services."""

    def __init__(
        self,
        *,
        trigger_service: GroupTriggerService,
        claim_service: ClaimService,
        friend_service: FriendApprovalService,
        admin_service: AdminService,
    ) -> None:
        self.trigger_service = trigger_service
        self.claim_service = claim_service
        self.friend_service = friend_service
        self.admin_service = admin_service

    def handle_group_trigger(self, *, user_id: int, group_id: int, message: str) -> GroupTriggerView:
        result = self.trigger_service.handle_group_message(user_id=user_id, group_id=group_id, message=message)
        return GroupTriggerView(result.matched, result.pool_id, result.guide_message)

    def handle_private_claim(
        self,
        *,
        user_id: int,
        message: str,
        user_nickname: str = "",
        source_group_id: str = "",
        source_group_name: str = "",
    ) -> PrivateClaimView:
        result = self.claim_service.handle_private_message(
            user_id=user_id,
            message=message,
            user_nickname=user_nickname,
            source_group_id=source_group_id,
            source_group_name=source_group_name,
        )
        return PrivateClaimView(result.claimed, result.reason, result.pool_id, result.code)

    def handle_friend_request(self, *, user_id: int, comment: str) -> FriendRequestView:
        result = self.friend_service.evaluate_request(user_id=user_id, comment=comment)
        return FriendRequestView(result.approved, result.reason, result.pool_id, result.flow_id)

