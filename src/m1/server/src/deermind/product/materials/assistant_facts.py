"""教材助手的完整事实由 Product 校验和投影。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.public.errors import Issue
from deermind.product.materials.facts import IMPORT, MaterialImportFact
from deermind.product.public.material_assistant import MaterialMessageView, TurnOutcome
from deermind.product.public.materials import Revision
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MESSAGE = "product.material_message"
TURN = "product.material_turn"
BATCH = "product.material_candidate_batch"
CANDIDATE = "product.material_candidate"
RECEIVED = "MaterialAssistantMessageReceived"
FINISHED = "MaterialAssistantTurnFinished"
PROPOSED = "MaterialCandidatePrepared"


class TurnFact(FactModel):
    request_ref: UUID
    import_id: UUID
    input_digest: str
    input: dict[str, JsonValue]
    runtime_ref: UUID
    state: Literal["accepted"] | TurnOutcome
    work_state_ref: Ref | None
    result_ref: Ref | None
    error: dict[str, JsonValue] | None
    created_at: datetime
    updated_at: datetime


class CandidateBatchFact(FactModel):
    batch_id: UUID
    batch_revision: Revision
    turn_ref: UUID
    scope: dict[str, JsonValue]
    read_set: list[dict[str, JsonValue]]
    write_set: list[dict[str, JsonValue]]
    coverage: dict[str, JsonValue]
    diff_summary: dict[str, JsonValue]
    decision_state: Literal["pending", "adopted", "declined", "superseded"]
    decision_revision: Revision
    created_at: datetime


class CandidateFact(FactModel):
    candidate_id: UUID
    candidate_revision: Revision
    batch_id: UUID
    import_id: UUID
    local_key: str
    kind: Literal["kc", "task_instance", "reference"]
    chapter_ref: Ref
    body: dict[str, JsonValue]
    parent_ref: Ref | None
    source_refs: list[Ref]
    basis_revision: int
    created_at: datetime


class AssistantMessageReceived(EventPayload):
    import_id: UUID
    request_ref: UUID
    message_ref: UUID


class CandidatePrepared(EventPayload):
    import_id: UUID
    request_ref: UUID
    batch_ref: Ref


class TurnFinished(EventPayload):
    import_id: UUID
    request_ref: UUID
    message_ref: UUID
    reply_ref: UUID | None
    candidate_batch_refs: list[Ref]
    outcome: TurnOutcome
    issues: list[Issue]


_MATRICES = {
    RECEIVED: {MESSAGE: 1, TURN: 1, IMPORT: 1},
    FINISHED: {MESSAGE: 1, TURN: 1, IMPORT: 1},
    PROPOSED: {BATCH: 1, IMPORT: 1},
}


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """只接受登记的记录组合与导入身份。"""
    if not isinstance(payload, (AssistantMessageReceived, CandidatePrepared, TurnFinished)):
        raise ValueError("Unknown material assistant fact")
    if draft.scope_id != payload.import_id:
        # 事件作用域须指向本批导入。
        raise ValueError("Material assistant fact does not match its import")
    counts: dict[str, int] = {}
    for record in payload.records:
        if not isinstance(record.content, InlineContent):
            raise ValueError("Material assistant fact requires hydrated records")
        value = record.content.value
        if "import_id" in value and value["import_id"] != str(payload.import_id):
            raise ValueError("Material record refers to a different import")
        if record.record_type == TURN and value["request_ref"] != str(payload.request_ref):
            # 轮次记录须归属本次请求。
            raise ValueError("Fact refers to a different material turn")
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    expected = dict(_MATRICES[draft.event_type])
    if isinstance(payload, TurnFinished) and payload.reply_ref is None:
        # 无回复消息的结束事件不携带消息记录。
        expected.pop(MESSAGE)
    if isinstance(payload, CandidatePrepared):
        if CANDIDATE in counts:
            expected[CANDIDATE] = counts[CANDIDATE]
        pending = 0
        superseded = 0
        for record in payload.records:
            if record.record_type != BATCH or not isinstance(record.content, InlineContent):
                continue
            value = record.content.value
            if value["decision_state"] == "pending" and value["batch_id"] == payload.batch_ref.id:
                pending += 1
            elif value["decision_state"] == "superseded":
                superseded += 1
        if pending != 1 or superseded not in (0, 1):
            # 新批次须恰好一条 pending，被取代批次至多一条。
            raise ValueError("Expected one new pending batch and at most one replaced batch")
        expected[BATCH] = 1 + superseded
    if counts != expected:
        # 记录矩阵数量须与事件类型约定一致。
        raise ValueError("Unexpected material assistant record combination")


_MODELS = {
    (MESSAGE, 1): MaterialMessageView,
    (TURN, 1): TurnFact,
    (BATCH, 1): CandidateBatchFact,
    (CANDIDATE, 1): CandidateFact,
    (IMPORT, 1): MaterialImportFact,
}
REGISTRATIONS = [
    EventRegistration(kind, 1, "product", "material_import", model, validate, _MODELS)
    for kind, model in (
        (RECEIVED, AssistantMessageReceived),
        (FINISHED, TurnFinished),
        (PROPOSED, CandidatePrepared),
    )
]

_INSERTS = {
    name: (
        f"INSERT INTO {name} SELECT * "
        f"FROM jsonb_populate_record(NULL::{name},CAST(:value AS jsonb))"
    )
    for name in (TURN, MESSAGE, BATCH, CANDIDATE)
}
_INSERTS[TURN] += (
    " ON CONFLICT(request_ref) DO UPDATE SET state=excluded.state,"
    "work_state_ref=excluded.work_state_ref,result_ref=excluded.result_ref,error=excluded.error,"
    "updated_at=excluded.updated_at,source_event_id=excluded.source_event_id"
)
_INSERTS[BATCH] += (
    " ON CONFLICT(batch_id) DO UPDATE SET decision_state=excluded.decision_state,"
    "decision_revision=excluded.decision_revision,source_event_id=excluded.source_event_id"
)
_INSERTS[IMPORT] = (
    "UPDATE product.material_import i SET revision=v.revision,updated_at=v.updated_at,"
    "source_event_id=v.source_event_id "
    "FROM jsonb_populate_record(NULL::product.material_import,CAST(:value AS jsonb)) v "
    "WHERE i.import_id=v.import_id"
)


async def project(connection: AsyncConnection, event: StoredEvent) -> None:
    """顺序来自本模块组装，先写轮次、随后写消息或候选。"""
    from deermind.abstractions.encoding import canonical_json

    for record in event.payload.records:
        if not isinstance(record.content, InlineContent):
            raise ValueError("Projection requires hydrated material records")
        # 按记录类型选择对应投影语句，冲突时覆盖当前快照。
        await connection.execute(
            text(_INSERTS[record.record_type]),
            {
                "value": canonical_json(
                    {**record.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
