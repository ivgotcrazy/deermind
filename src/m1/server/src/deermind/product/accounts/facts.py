"""首个账号事实的固定正文和投影；凭据及登录不属于本增量。"""

from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    NonEmpty,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.reading import EventFact, ReadAccess, ReadGrant, ReadPolicy
from deermind.foundation.system.events.store import canonical_json
from pydantic import Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class AccountFact(FactModel):
    """product.accounts v1完整业务列；不含派生的source_event_id。"""

    account_id: UUID
    login_identifier: NonEmpty
    display_name: NonEmpty
    role: Literal["admin", "student"]
    status: Literal["active", "disabled"]
    revision: Annotated[int, Field(ge=1)]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("Fact timestamps must be UTC")
        return value

    @field_validator("login_identifier")
    @classmethod
    def normalized_login(cls, value: str) -> str:
        if value != value.strip().casefold():
            raise ValueError("Login identifier must already be normalized")
        return value


class AccountSaved(EventPayload):
    """E01-05仅接线bootstrap_admin子集，其他动作在账号增量实现。"""

    account_id: UUID
    action: Literal["bootstrap_admin", "create_student", "update_student"]
    account_revision: Annotated[int, Field(ge=1)]
    relation_refs: list[Ref]


def account_content(payload: EventPayload) -> AccountFact:
    """按事件记录矩阵校验数量、类型、版本，再解码完整正文。"""
    if not isinstance(payload, AccountSaved) or payload.relation_refs or len(payload.records) != 1:
        raise ValueError("Initial administrator requires exactly one account and no relations")
    record = payload.records[0]
    if record.record_type != "product.accounts" or record.schema_version != 1:
        raise ValueError("Unsupported account fact record")
    if not isinstance(record.content, InlineContent):
        raise ValueError("Account projection requires decoded content")
    fact = AccountFact.model_validate_json(canonical_json(record.content.value))
    if (
        payload.action != "bootstrap_admin"
        or fact.role != "admin"
        or fact.status != "active"
        or fact.revision != 1
    ):
        raise ValueError("Only an initial administrator fact is implemented in this increment")
    if fact.account_id != payload.account_id or fact.revision != payload.account_revision:
        raise ValueError("Account fact identity does not match event payload")
    return fact


def validate_account(draft: EventDraft, payload: EventPayload) -> None:
    fact = account_content(payload)
    expected_owner = Ref(owner="product", type="account", id=str(fact.account_id), revision=1)
    if draft.scope_id != fact.account_id or draft.owner_ref != expected_owner:
        raise ValueError("Account event scope or owner does not match its fact")


async def project_account(connection: AsyncConnection, event: StoredEvent) -> None:
    """只从事实正文生成投影；不生成身份、时间，不反查旧业务正文。"""
    fact = account_content(event.payload)
    await connection.execute(
        text(
            "INSERT INTO product.accounts "
            "(account_id, login_identifier, display_name, role, status, revision, "
            "created_at, source_event_id) "
            "VALUES (:account_id, :login_identifier, :display_name, :role, :status, :revision, "
            ":created_at, :source_event_id)"
        ),
        {**fact.model_dump(), "source_event_id": event.draft.event_id},
    )


ACCOUNT_REGISTRATION = EventRegistration(
    event_type="TrialAccountSaved",
    schema_version=1,
    producer="product",
    scope_kind="account",
    payload_model=AccountSaved,
    validate=validate_account,
    projector_id="product.accounts.v1",
    project=project_account,
    record_models={("product.accounts", 1): AccountFact},
)


def account_maintenance(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    """账号事实只向已授权维护读取开放；通用管理员事件页不展示账号敏感依据。"""
    if access.maintenance_ref is None:
        return None
    return ReadGrant(
        {("product.accounts", 1): None},
        frozenset(
            {
                "account_id",
                "action",
                "account_revision",
                "relation_refs",
            }
        ),
        "初始账号已保存",
    )


ACCOUNT_READ_POLICY = ReadPolicy(
    "TrialAccountSaved",
    1,
    "runtime",
    "projection_rebuild",
    account_maintenance,
)
