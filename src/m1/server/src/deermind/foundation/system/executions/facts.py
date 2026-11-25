"""工作状态及新步骤的完整留痕；执行记录不参与业务投影重建。

分层定位：foundation（公共运行底座 / 执行生命周期）
对外契约：ExecutionStateChanged 事件正文、MODELS 记录模型与 record_change 事实追加。
边界约束：记录必须属于当前工作；只保存本次新步骤，不复制全部历史；不做业务投影重建。
"""

import json
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.executions import Attempt, Execution, StepResult
from deermind.foundation.system.events.store import EventStore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

Outcome = Literal[
    "accepted", "started", "stopped", "failed", "completed", "recovery_accepted", "progress_saved"
]
# 执行/尝试/步骤结果事实表名到记录模型的映射。
MODELS: dict[str, type[FactModel]] = {
    "runtime.executions": Execution,
    "runtime.execution_attempts": Attempt,
    "runtime.step_results": StepResult,
}


class ExecutionStateChanged(EventPayload):
    """执行状态变更事件正文：归属、结果与原因码。"""

    subject_ref: Ref
    outcome: Outcome
    reason_code: str | None


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """各记录必须属于当前工作；只保存本次新步骤，不复制全部历史。"""
    # 正文类型与归属主体必须与事件所有者一致。
    if not isinstance(payload, ExecutionStateChanged) or payload.subject_ref != draft.owner_ref:
        raise ValueError("Invalid execution event")
    counts: dict[str, int] = {}
    # 逐条解码记录，核对类型、schema 与归属，并按表名累计条数。
    for record in payload.records:
        model = MODELS.get(record.record_type)
        # 类型未登记或正文仍是未解附件，不能作为执行记录校验。
        if model is None or not isinstance(record.content, InlineContent):
            raise ValueError("Unknown execution record")
        parsed = model.model_validate_json(json.dumps(record.content.value))
        if not isinstance(parsed, (Execution, Attempt, StepResult)):
            raise ValueError("Invalid execution record schema")
        # 记录必须属于本事件范围对应的工作。
        if parsed.execution_id != draft.scope_id:
            raise ValueError("Execution record belongs to another work")
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    # 工作记录恰好一条，尝试记录至多一条，约束事件留痕的基数。
    if counts.get("runtime.executions") != 1 or counts.get("runtime.execution_attempts", 0) > 1:
        raise ValueError("Invalid execution record cardinality")
    # 进度落定事件必须携带本次保存的步骤结果。
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
    # 尝试与步骤为可选：本次有对应事实才追加进留痕记录。
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
                # 请求定位回退顺序：显式 request_id → 尝试重试请求号 → 工作受理键。
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
