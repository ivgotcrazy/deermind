"""Evaluation records and the projections derived from a completed evidence batch."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.evaluation.interpretation import (
    ConditionFact,
    EvidenceSpan,
    ExecutionCheck,
    Qualification,
    Verdict,
)
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

COMPLETED = "BeliefEvaluationCompleted"
EVIDENCE = "evaluation.evidence"
REVISION = "evaluation.belief_revision"
SNAPSHOT = "evaluation.mastery_snapshot"
type Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
type Aspect = Literal["independent", "understanding", "transfer", "retention"]


class Subitem(FactModel):
    scope_id: UUID
    claim_id: UUID
    claim_revision: int
    method_id: UUID
    method_version: int
    aspect_code: Aspect


class EvidenceRecord(Subitem):
    evidence_id: UUID
    input_ref: UUID
    interpretation_ref: UUID
    source_kind: Literal["answer", "teaching"]
    source_id: UUID
    execution_checks: list[ExecutionCheck]
    rule_ref: Ref
    condition_facts: list[ConditionFact]
    source_spans: list[EvidenceSpan]
    source_refs: list[EventPartRef]
    qualification: Qualification
    verdict: Verdict | None
    reason_codes: list[str]
    reason: str
    limitations: list[str]
    created_at: datetime


class BeliefRevision(Subitem):
    belief_revision_id: UUID
    previous_revision_id: UUID | None
    evidence_ref: UUID
    update_kind: Literal["observation", "learning_transition"]
    p_obs_before: Probability | None
    p_current_before: Probability
    p_obs_after: Probability | None
    p_current_after: Probability
    last_observed_at: datetime | None
    parameter_ref: str
    algorithm_ref: str
    reason_codes: list[str]
    trigger_event_id: UUID
    created_at: datetime


class MasteryItem(Subitem):
    p_obs: Probability | None
    p_current: Probability
    last_observed_at: datetime | None
    belief_revision_ref: Ref | None
    observation_status: Literal["observed", "unknown"]
    evidence_coverage: list[Ref]
    unknown_reasons: list[str]
    source_refs: list[EventPartRef]


class MasterySnapshot(FactModel):
    snapshot_id: UUID
    scope_id: UUID
    publication_seq: int
    items: list[MasteryItem]
    coverage: list[Subitem]
    result_coverage: list[Ref]
    published_at: datetime


class BeliefCompleted(EventPayload):
    trigger_event_id: UUID
    input_ref: Ref
    evidence_refs: list[Ref]
    belief_revision_refs: list[Ref]
    snapshot_ref: Ref
    result_ref: Ref
    reason_codes: list[str]


def ref(kind: str, identity: UUID) -> Ref:
    return Ref(owner="evaluation", type=kind, id=str(identity))


def fact(table: str, identity: UUID, body: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=table,
        schema_version=1,
        content=InlineContent(storage="inline", value=body.model_dump(mode="json")),
    )


def _decode(item: FactRecord, model: type[FactModel]) -> FactModel:
    # 投影前记录正文必须是已解码的内联内容。
    if not isinstance(item.content, InlineContent):
        raise ValueError("Evidence and mastery records must be decoded")
    return model.model_validate_json(canonical_json(item.content.value))


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, BeliefCompleted):
        raise ValueError("Unexpected evaluation result event")
    # 触发事件、结果所有者与快照引用须与草稿身份逐项一致。
    if (
        draft.causation_event_id != payload.trigger_event_id
        or draft.owner_ref != payload.result_ref
        or payload.snapshot_ref != payload.result_ref
    ):
        raise ValueError("Evaluation result identity does not match the source")
    grouped: dict[str, list[Ref]] = {EVIDENCE: [], REVISION: [], SNAPSHOT: []}
    # 逐条解码记录，按三类分别核对归属并收集引用。
    for item in payload.records:
        table = item.record_type
        record = _decode(item, MODELS[table])
        if isinstance(record, EvidenceRecord):
            kind, identity = "evidence", record.evidence_id
            # 佐证必须挂在本次输入之下。
            if str(record.input_ref) != payload.input_ref.id:
                raise ValueError("Evidence does not match the input")
        elif isinstance(record, BeliefRevision):
            kind, identity = "belief_revision", record.belief_revision_id
            # 信念修订必须由本次触发事件产生。
            if record.trigger_event_id != payload.trigger_event_id:
                raise ValueError("Revision does not match the source")
        else:
            assert isinstance(record, MasterySnapshot)
            kind, identity = "mastery_snapshot", record.snapshot_id
        # 记录标识与范围须与事件草稿一致，不得越界混入。
        if str(identity) != item.record_id or record.scope_id != draft.scope_id:
            raise ValueError("Evaluation record is outside its event")
        grouped[table].append(ref(kind, identity))
    # 汇总出的三类引用列表须与事件正文声明的引用逐条吻合。
    if (
        grouped[EVIDENCE] != payload.evidence_refs
        or grouped[REVISION] != payload.belief_revision_refs
        or grouped[SNAPSHOT] != [payload.snapshot_ref]
    ):
        raise ValueError("Evaluation result references do not match the recorded rows")


MODELS: dict[str, type[FactModel]] = {
    EVIDENCE: EvidenceRecord,
    REVISION: BeliefRevision,
    SNAPSHOT: MasterySnapshot,
}
REGISTRATION = EventRegistration(
    COMPLETED,
    1,
    "evaluation",
    "learning_space",
    BeliefCompleted,
    validate,
    {(table, 1): model for table, model in MODELS.items()},
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, SNAPSHOT, 1, event.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        for table in MODELS:
            for item in event.payload.records:
                # 只处理当前表对应的记录。
                if item.record_type != table:
                    continue
                if not isinstance(item.content, InlineContent):
                    raise ValueError("Evaluation projection requires a decoded record")
                body = {**item.content.value, "source_event_id": str(event.draft.event_id)}
                # 表名仅来自本模块的固定登记。
                await db.execute(
                    text(
                        f"INSERT INTO {table} SELECT * FROM "
                        f"jsonb_populate_record(NULL::{table}, CAST(:body AS jsonb))"
                    ),
                    {"body": canonical_json(body)},
                )
                # 信念修订落表后刷新对应方面的当前信念指针。
                if table == REVISION:
                    await _current(db, UUID(item.record_id))
                # 快照落表后刷新范围的最新掌握快照指针。
                if table == SNAPSHOT:
                    await _head(db, UUID(item.record_id))


async def _current(db: AsyncConnection, identity: UUID) -> None:
    await db.execute(
        text("""
        INSERT INTO evaluation.belief_current (
            scope_id, claim_id, claim_revision, method_id, method_version, aspect_code,
            current_revision_ref, p_obs, p_current, last_observed_at
        )
        SELECT scope_id, claim_id, claim_revision, method_id, method_version, aspect_code,
            belief_revision_id, p_obs_after, p_current_after, last_observed_at
        FROM evaluation.belief_revision WHERE belief_revision_id=:id
        ON CONFLICT (scope_id, claim_id, claim_revision, method_id, method_version, aspect_code)
        DO UPDATE SET current_revision_ref=excluded.current_revision_ref,
            p_obs=excluded.p_obs, p_current=excluded.p_current,
            last_observed_at=excluded.last_observed_at
    """),
        {"id": identity},
    )


async def _head(db: AsyncConnection, identity: UUID) -> None:
    # 仅当新快照发布序号更靠后时才覆盖头指针，避免旧快照回写。
    await db.execute(
        text("""
        INSERT INTO evaluation.mastery_head (scope_id, current_snapshot_ref, publication_seq)
        SELECT scope_id, snapshot_id, publication_seq
        FROM evaluation.mastery_snapshot WHERE snapshot_id=:id
        ON CONFLICT (scope_id) DO UPDATE SET current_snapshot_ref=excluded.current_snapshot_ref,
            publication_seq=excluded.publication_seq
        WHERE excluded.publication_seq > evaluation.mastery_head.publication_seq
    """),
        {"id": identity},
    )
