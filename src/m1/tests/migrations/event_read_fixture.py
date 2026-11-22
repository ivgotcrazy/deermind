"""只供事件读取测试的事件Schema，不登记为正式Interaction业务事件。"""

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
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
