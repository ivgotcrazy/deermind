"""工作状态及新步骤的完整留痕；执行记录不参与业务投影重建。"""

import json
from typing import Literal
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.reading import EventFact, ReadAccess, ReadGrant, ReadPolicy
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions.contracts import Attempt, Execution, StepResult
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

Outcome = Literal[
    "accepted", "started", "stopped", "failed", "completed", "recovery_accepted", "progress_saved"
]
MODELS: dict[str, type[FactModel]] = {
    "runtime.executions": Execution,
    "runtime.execution_attempts": Attempt,
    "runtime.step_results": StepResult,
}


class ExecutionStateChanged(EventPayload):
    subject_ref: Ref
    outcome: Outcome
    reason_code: str | None


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """各记录必须属于当前工作；只保存本次新步骤，不复制全部历史。"""
    if not isinstance(payload, ExecutionStateChanged) or payload.subject_ref != draft.owner_ref:
        raise ValueError("Invalid execution event")
    counts: dict[str, int] = {}
    for record in payload.records:
        model = MODELS.get(record.record_type)
        if model is None or not isinstance(record.content, InlineContent):
            raise ValueError("Unknown execution record")
        parsed = model.model_validate_json(json.dumps(record.content.value))
        if not isinstance(parsed, (Execution, Attempt, StepResult)):
            raise ValueError("Invalid execution record schema")
        if parsed.execution_id != draft.scope_id:
            raise ValueError("Execution record belongs to another work")
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    if counts.get("runtime.executions") != 1 or counts.get("runtime.execution_attempts", 0) > 1:
        raise ValueError("Invalid execution record cardinality")
    if payload.outcome == "progress_saved" and counts.get("runtime.step_results", 0) != 1:
        raise ValueError("Step checkpoint must contain its saved step")


EXECUTION_REGISTRATION = EventRegistration(
    "ExecutionStateChanged",
    1,
    "runtime",
    "execution",
    ExecutionStateChanged,
    validate,
    {(name, 1): model for name, model in MODELS.items()},
)


async def record_change(
    connection: AsyncConnection,
    execution: Execution,
    outcome: Outcome,
    actor: Ref,
    *,
    attempt: Attempt | None = None,
    step: StepResult | None = None,
    reason: str | None = None,
    commit_id: UUID | None = None,
    request_id: str | None = None,
) -> None:
    """调用方已锁定工作；事实与状态、业务收尾共同提交。"""
    records = [
        FactRecord(
            record_id="execution",
            record_type="runtime.executions",
            schema_version=1,
            content=InlineContent(storage="inline", value=execution.model_dump(mode="json")),
        )
    ]
    for name, model in (("execution_attempts", attempt), ("step_results", step)):
        if model is not None:
            records.append(
                FactRecord(
                    record_id=name,
                    record_type="runtime." + name,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=model.model_dump(mode="json")),
                )
            )
    owner = Ref(owner="runtime", type="execution", id=str(execution.execution_id))
    scope = ("execution", execution.execution_id)
    sequence = await connection.scalar(
        text(
            "SELECT last_seq FROM runtime.scope_event_heads WHERE scope_kind=:kind AND scope_id=:id"
        ),
        {"kind": scope[0], "id": scope[1]},
    )
    payload = ExecutionStateChanged(
        subject_ref=owner, outcome=outcome, reason_code=reason, records=records
    )
    await EventStore([EXECUTION_REGISTRATION]).append(
        connection,
        ProducerAccess("runtime", actor, frozenset({scope})),
        [
            EventDraft(
                uuid4(),
                "ExecutionStateChanged",
                1,
                *scope,
                owner,
                payload.model_dump(mode="json"),
                request_id
                or (
                    attempt.retry_request_id
                    if attempt and attempt.retry_request_id
                    else execution.acceptance_key
                ),
                source_execution_ref=execution.execution_id,
                subject_refs=(
                    Ref(
                        owner=execution.owner, type=execution.scope_kind, id=str(execution.scope_id)
                    ),
                ),
            )
        ],
        commit_id=commit_id or uuid4(),
        correlation_id=execution.execution_id,
        expected_seq={scope: sequence or 0},
    )


def maintenance_grant(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    """沿既有维护授权读取完整执行快照，不开放到学生端。"""
    if access.maintenance_ref is None:
        return None
    return ReadGrant(
        {(name, 1): None for name in MODELS},
        frozenset({"subject_ref", "outcome", "reason_code"}),
        "工作执行记录",
    )


EXECUTION_READ_POLICY = ReadPolicy(
    "ExecutionStateChanged", 1, "runtime", "execution_support", maintenance_grant
)
