"""成功登录和撤销的事实；不包含密码、散列、Cookie或CSRF秘密。"""

from typing import Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.reading import EventFact, ReadAccess, ReadGrant, ReadPolicy
from sqlalchemy.ext.asyncio import AsyncConnection


class AccountSignedIn(EventPayload):
    account_id: UUID
    session_id: UUID


class AccountSignedOut(AccountSignedIn):
    subject_ref: Ref
    outcome: Literal["signed_out", "invalidated"]
    reason_code: str | None


def validate_auth_fact(draft: EventDraft, payload: EventPayload) -> None:
    """限定账号身份且无业务正文；会话秘密不能以records变相保存。"""
    if (
        not isinstance(payload, AccountSignedIn)
        or payload.records
        or payload.account_id != draft.scope_id
        or draft.owner_ref != Ref(owner="product", type="account", id=str(payload.account_id))
    ):
        raise ValueError("Authentication fact does not match its account")
    if isinstance(payload, AccountSignedOut) and payload.subject_ref != draft.owner_ref:
        raise ValueError("Authentication subject differs from its owner")


async def record_only(connection: AsyncConnection, event: StoredEvent) -> None:
    """认证事件仅留痕；查询重建不能据此创建或恢复可用登录。"""


SIGNED_IN = EventRegistration(
    event_type="AccountSignedIn",
    schema_version=1,
    producer="product",
    scope_kind="account",
    payload_model=AccountSignedIn,
    validate=validate_auth_fact,
    projector_id="product.auth_audit.v1",
    project=record_only,
)

SIGNED_OUT = EventRegistration(
    event_type="AccountSignedOut",
    schema_version=1,
    producer="product",
    scope_kind="account",
    payload_model=AccountSignedOut,
    validate=validate_auth_fact,
    projector_id="product.auth_audit.v1",
    project=record_only,
)


def maintenance_read(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    """账号重建只读取不含秘密的审计事实，并跳过登录控制的恢复。"""
    if access.maintenance_ref is None:
        return None
    fields = {"account_id", "session_id"}
    if event.event_type == "AccountSignedOut":
        fields.update({"subject_ref", "outcome", "reason_code"})
    return ReadGrant({}, frozenset(fields), "账号认证记录")


AUTH_READ_POLICIES = [
    ReadPolicy(event, 1, "runtime", "projection_rebuild", maintenance_read)
    for event in ("AccountSignedIn", "AccountSignedOut")
]
