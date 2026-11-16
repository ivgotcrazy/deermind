"""账号及监护事实的固定正文和投影；凭据不进入事实。"""

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
from deermind.product.accounts.usage_events import decode
from deermind.product.accounts.usage_facts import (
    USAGE_RECORDS,
    ConditionsFact,
    GuardianFact,
    RelationFact,
)
from pydantic import Field, field_validator


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
    """账号创建与资料更新的完整快照。"""

    account_id: UUID
    action: Literal["bootstrap_admin", "create_student", "update_student"]
    account_revision: Annotated[int, Field(ge=1)]
    relation_refs: list[Ref]


def account_content(payload: EventPayload) -> AccountFact:
    """按事件记录矩阵校验数量、类型、版本，再解码完整正文。"""
    if not isinstance(payload, AccountSaved):
        raise ValueError("Expected account fact")
    accounts = [r for r in payload.records if r.record_type == "product.accounts"]
    if len(accounts) != 1 or accounts[0].schema_version != 1:
        raise ValueError("Exactly one account record is required")
    record = accounts[0]
    if not isinstance(record.content, InlineContent):
        raise ValueError("Account projection requires decoded content")
    fact = AccountFact.model_validate_json(canonical_json(record.content.value))
    if fact.account_id != payload.account_id or fact.revision != payload.account_revision:
        raise ValueError("Account fact identity does not match event payload")
    if payload.action == "bootstrap_admin":
        if (
            fact.role != "admin"
            or fact.status != "active"
            or fact.revision != 1
            or len(payload.records) != 1
            or payload.relation_refs
        ):
            raise ValueError("Initial administrator requires one active account and no relations")
    else:
        if fact.role != "student" or (payload.action == "create_student" and fact.revision != 1):
            raise ValueError("Only student account management is allowed")
        conditions = 0
        relations: list[Ref] = []
        for item in payload.records:
            if item is record:
                continue
            related = decode(item)
            if isinstance(related, ConditionsFact):
                conditions += 1
                if related.student_id != fact.account_id:
                    raise ValueError("Conditions belong to another student")
            elif isinstance(related, RelationFact):
                if related.student_id != fact.account_id:
                    raise ValueError("Relationship belongs to another student")
                relations.append(
                    Ref(owner="product", type="guardian_relation", id=str(related.relation_id))
                )
            elif not isinstance(related, GuardianFact):
                raise ValueError("Account save cannot contain a confirmation")
        if conditions != 1 or relations != payload.relation_refs:
            raise ValueError(
                "Account save requires conditions and matching relationship references"
            )
    return fact


def validate_account(draft: EventDraft, payload: EventPayload) -> None:
    fact = account_content(payload)
    expected_owner = Ref(
        owner="product", type="account", id=str(fact.account_id), revision=fact.revision
    )
    if draft.scope_id != fact.account_id or draft.owner_ref != expected_owner:
        raise ValueError("Account event scope or owner does not match its fact")


def account_values(event: StoredEvent) -> dict[str, object]:
    """在线保存与维护重建共用转换，保留原身份、时间及来源。"""
    fact = account_content(event.payload)
    return {**fact.model_dump(), "source_event_id": event.draft.event_id}


ACCOUNT_REGISTRATION = EventRegistration(
    event_type="TrialAccountSaved",
    schema_version=1,
    producer="product",
    scope_kind="account",
    payload_model=AccountSaved,
    validate=validate_account,
    record_models={("product.accounts", 1): AccountFact, **USAGE_RECORDS},
)


def account_maintenance(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    """账号事实只向已授权维护读取开放；通用管理员事件页不展示账号敏感依据。"""
    if access.maintenance_ref is None:
        return None
    return ReadGrant(
        {("product.accounts", 1): None, **dict.fromkeys(USAGE_RECORDS)},
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
    "product",
    "projection_rebuild",
    account_maintenance,
)
