"""只供授权查询测试的事件Schema，不登记为正式Interaction业务事件。"""

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import (
    EventFact,
    EventPartRef,
    ReadAccess,
    ReadGrant,
    ReadHandler,
    ReadPolicy,
)
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
)


class TestMessage(FactModel):
    body: str
    secret: str
    source: EventPartRef | None


class TestPayload(EventPayload):
    action: str
    hidden_reason: str


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if len(payload.records) != 1:
        raise ValueError("The test event requires one record")
    record = payload.records[0]
    if (
        record.record_type != "test.messages"
        or record.schema_version != 1
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Unexpected test record")
    TestMessage.model_validate_json(canonical_json(record.content.value))


REGISTRATIONS = tuple(
    EventRegistration(
        event_type=kind,
        schema_version=1,
        producer="interaction",
        scope_kind="learning_space",
        payload_model=TestPayload,
        validate=validate,
        record_models={("test.messages", 1): TestMessage},
    )
    for kind in ("TestChatRecorded", "TestPrivateRecorded")
)


def grant(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    if access.purpose == "student_history":
        if event.event_type == "TestPrivateRecorded":
            return None
        return ReadGrant(
            {("test.messages", 1): frozenset({"body", "source"})},
            frozenset({"action"}),
            "学生可见记录",
        )
    if access.purpose == "evaluation_basis":
        if event.owner_ref not in access.resource_refs:
            return None
        return ReadGrant(
            {("test.messages", 1): frozenset({"body"})}, frozenset({"action"}), "本次获准取证记录"
        )
    if access.purpose == "projection_rebuild":
        return ReadGrant(
            {("test.messages", 1): None}, frozenset({"action", "hidden_reason"}), "维护读取"
        )
    return None


HANDLERS = (
    ReadHandler("test.student", "product", "student_history"),
    ReadHandler("test.evaluation", "evaluation", "evaluation_basis"),
    ReadHandler("test.maintenance", "runtime", "projection_rebuild"),
)
POLICIES = tuple(
    ReadPolicy(kind.event_type, 1, handler.module, handler.purpose, grant)
    for kind in REGISTRATIONS
    for handler in HANDLERS
)
