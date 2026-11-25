"""评价解释和程序校验的持久记录。"""

from datetime import datetime
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.evaluation.interpretation import CheckedEvidence, Interpretation
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PREPARED = "EvaluationInterpretationPrepared"
TABLE = "evaluation.interpretation"


class InterpretationRecord(FactModel):
    interpretation_id: UUID
    input_ref: UUID
    ai_call_ref: Ref
    contract_ref: Ref
    candidate: Interpretation
    validation: list[CheckedEvidence]
    created_at: datetime


class InterpretationPrepared(EventPayload):
    interpretation_ref: Ref
    evaluation_input_ref: Ref


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 正文类型与记录基数须符合约定：恰好一条解释记录。
    if not isinstance(payload, InterpretationPrepared) or len(payload.records) != 1:
        raise ValueError("A prepared interpretation must carry exactly one record")
    item = payload.records[0]
    # 记录类型与内联正文不符，说明前置解码未完成。
    if item.record_type != TABLE or not isinstance(item.content, InlineContent):
        raise ValueError("The interpretation record must be decoded")
    record = InterpretationRecord.model_validate_json(canonical_json(item.content.value))
    # 主体、记录编号、解释标识与输入引用必须与事件身份逐项一致。
    if (
        payload.interpretation_ref != draft.owner_ref
        or item.record_id != draft.owner_ref.id
        or str(record.interpretation_id) != item.record_id
        or str(record.input_ref) != payload.evaluation_input_ref.id
    ):
        raise ValueError("The interpretation record does not match its event")


REGISTRATION = EventRegistration(
    PREPARED,
    1,
    "evaluation",
    "learning_space",
    InterpretationPrepared,
    validate,
    {(TABLE, 1): InterpretationRecord},
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, TABLE, 1, event.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        value = event.payload.records[0].content
        # 投影前正文仍须是已解码内联内容。
        if not isinstance(value, InlineContent):
            raise ValueError("The interpretation record is not decoded")
        await db.execute(
            text(
                "INSERT INTO evaluation.interpretation SELECT * FROM "
                "jsonb_populate_record(NULL::evaluation.interpretation, CAST(:body AS jsonb))"
            ),
            {"body": canonical_json({**value.value, "source_event_id": str(event.draft.event_id)})},
        )
