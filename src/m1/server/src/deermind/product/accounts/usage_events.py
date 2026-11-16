"""首次使用的事实与确定性投影；授权及条件计算由Product服务完成。"""

from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.reading import EventFact, ReadAccess, ReadGrant, ReadPolicy
from deermind.foundation.system.events.store import canonical_json
from deermind.product.accounts.usage_facts import (
    USAGE_RECORDS,
    ConditionsFact,
    ConfirmationFact,
    GuardianFact,
    RelationFact,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def record(name: str, kind: str, fact: FactModel) -> FactRecord:
    return FactRecord(
        record_id=name,
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=fact.model_dump(mode="json")),
    )


def decode(record: FactRecord) -> FactModel:
    model = USAGE_RECORDS.get((record.record_type, record.schema_version))
    if model is None or not isinstance(record.content, InlineContent):
        raise ValueError("Unsupported or undecoded usage record")
    return model.model_validate_json(canonical_json(record.content.value))


async def project_usage(connection: AsyncConnection, event: StoredEvent) -> None:
    """SQL标识符只来自程序登记的模型；JSON字段显式编码，绝不接受外来表名。"""
    keys = {
        GuardianFact: "guardian_id",
        RelationFact: "relation_id",
        ConfirmationFact: "confirmation_id",
        ConditionsFact: "student_id",
    }
    json_fields = {
        "verified_identity_ref",
        "verification_ref",
        "actor_ref",
        "notice_ref",
        "source_ref",
        "confirmation_refs",
        "reasons",
    }
    for item in event.payload.records:
        if (item.record_type, item.schema_version) not in USAGE_RECORDS:
            continue
        fact = decode(item)
        values: dict[str, object] = fact.model_dump()
        serialized = fact.model_dump(mode="json")
        for field in json_fields & values.keys():
            values[field] = canonical_json(serialized[field])
        values["source_event_id"] = event.draft.event_id
        columns = ",".join(values)
        parameters = ",".join(
            f"CAST(:{key} AS jsonb)" if key in json_fields else f":{key}" for key in values
        )
        conflict = ""
        if isinstance(fact, ConditionsFact):
            assignments = ",".join(f"{key}=EXCLUDED.{key}" for key in values if key != "student_id")
            conflict = f" ON CONFLICT (student_id) DO UPDATE SET {assignments}"
        elif type(fact) not in keys:
            raise ValueError("Unregistered usage projection")
        await connection.execute(
            text(f"INSERT INTO {item.record_type} ({columns}) VALUES ({parameters}){conflict}"),
            values,
        )


class UsageConfirmed(EventPayload):
    student_id: UUID
    confirmation_ref: Ref
    usage_conditions_ref: Ref
    notice_text: str


def validate_usage(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, UsageConfirmed) or len(payload.records) != 2:
        raise ValueError("Confirmation requires a decision and its conditions snapshot")
    facts = [decode(item) for item in payload.records]
    confirmations = [f for f in facts if isinstance(f, ConfirmationFact)]
    conditions = [f for f in facts if isinstance(f, ConditionsFact)]
    if len(confirmations) != 1 or len(conditions) != 1:
        raise ValueError("Invalid confirmation record matrix")
    confirmation, condition = confirmations[0], conditions[0]
    if (
        confirmation.student_id != payload.student_id
        or condition.student_id != payload.student_id
        or draft.scope_id != payload.student_id
        or draft.owner_ref != Ref(owner="product", type="account", id=str(payload.student_id))
        or payload.confirmation_ref
        != Ref(owner="product", type="usage_confirmation", id=str(confirmation.confirmation_id))
        or payload.usage_conditions_ref
        != Ref(
            owner="product",
            type="usage_conditions",
            id=str(payload.student_id),
            revision=condition.revision,
        )
        or payload.confirmation_ref not in condition.confirmation_refs
        or not payload.notice_text
    ):
        raise ValueError("Confirmation facts do not agree")


USAGE_CONFIRMED = EventRegistration(
    "UsageConfirmationRecorded",
    2,
    "product",
    "account",
    UsageConfirmed,
    validate_usage,
    "product.usage.v1",
    project_usage,
    USAGE_RECORDS,
)


def usage_read(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    if access.maintenance_ref is not None:
        return ReadGrant(
            dict.fromkeys(USAGE_RECORDS),
            frozenset({"student_id", "confirmation_ref", "usage_conditions_ref", "notice_text"}),
            "使用确认已记录",
        )
    return None


USAGE_READ_POLICY = ReadPolicy(
    "UsageConfirmationRecorded", 2, "runtime", "projection_rebuild", usage_read
)


def receipt_read(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    """只有服务端已核对收据归属的调用可读原结果；不开放任意账号事件读取。"""
    if access.execution_ref != event.correlation_id:
        return None
    return ReadGrant(
        {("product.usage_conditions", 1): None, ("product.usage_confirmations", 1): None},
        frozenset(),
        "使用确认结果",
    )


USAGE_RECEIPT_POLICY = ReadPolicy(
    "UsageConfirmationRecorded", 2, "product", "execution_support", receipt_read
)
