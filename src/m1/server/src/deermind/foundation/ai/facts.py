"""AI 事件记录矩阵；正文转换由本所有者提供，事件底座只校验。

分层定位：foundation（AI 底座）
对外契约：MODELS/MATRIX 登记事件类型到事实表的映射，decode/validate 供事件底座解码与校验。
边界约束：只做正文登记、解码与一致性校验，不含账本记账或模型调用。
"""

import hashlib
from collections import Counter
from typing import Literal
from uuid import UUID

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.ai.requests import ModelRequestFact
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    FileContent,
    InlineContent,
    Ref,
)
from deermind.foundation.ai.records import (
    CallAttemptFact,
    CallFact,
    CandidateFact,
    ConfigurationFact,
    ToolActionFact,
)
from pydantic import TypeAdapter

# 事实表名到事实模型的映射，解码与投影据此选择类型。
MODELS: dict[str, type[FactModel]] = {
    "ai.execution_configs": ConfigurationFact,
    "ai.ai_calls": CallFact,
    "ai.ai_call_attempts": CallAttemptFact,
    "ai.model_requests": ModelRequestFact,
    "ai.tool_actions": ToolActionFact,
    "ai.ai_candidates": CandidateFact,
}
# 事件类型到事实表的数量区间（最少, 最多）；校验时核对记录种类与条数。
MATRIX = {
    "AIConfigurationPinned": {"ai.execution_configs": (1, 1)},
    "AICallChanged": {"ai.ai_calls": (1, 1), "ai.ai_call_attempts": (0, 1)},
    "ModelRequestChanged": {"ai.model_requests": (1, 1)},
    "ToolActionChanged": {"ai.tool_actions": (1, 1)},
    "AICandidatePrepared": {"ai.ai_candidates": (1, 1)},
}


class AIEvent(EventPayload):
    """AI 事件正文信封：归属引用、处置结果与原因码。"""

    subject_ref: Ref
    outcome: Literal["recorded", "started", "completed", "failed", "cancelled", "unknown", "denied"]
    reason_code: str | None


def decode(record: FactRecord) -> FactModel:
    """只接收本所有者已登记的完整正文；附件须先由授权读取解开。"""
    # 版本不符、类型未登记或正文仍是未解开的附件，均不能按 AI 事实解码。
    if (
        record.schema_version != 1
        or record.record_type not in MODELS
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Unknown or undecoded AI fact")
    return MODELS[record.record_type].model_validate_json(canonical_json(record.content.value))


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """校验矩阵、身份及固定hash；不能用额外records夹带其他模块的数据。"""
    # 正文类型与归属主体必须与事件所有者一致。
    if not isinstance(payload, AIEvent) or payload.subject_ref != draft.owner_ref:
        raise ValueError("AI event subject differs from its owner")
    matrix = MATRIX[draft.event_type]
    counts = Counter(record.record_type for record in payload.records)
    # 记录种类须在矩阵内，且每种条数落在矩阵给定的最少/最多区间。
    if set(counts) - set(matrix) or any(
        not minimum <= counts[name] <= maximum for name, (minimum, maximum) in matrix.items()
    ):
        raise ValueError("AI records differ from the event matrix")
    # 配置落定与候选准备属“已落库”事件，其余事件 outcome 不得记为 recorded。
    recorded = draft.event_type in {"AIConfigurationPinned", "AICandidatePrepared"}
    if (payload.outcome == "recorded") != recorded:
        raise ValueError("Invalid AI event outcome")
    # 失败/取消/未知/拒绝均属非成功终态，必须带原因码。
    if payload.outcome in {"failed", "cancelled", "unknown", "denied"} and not payload.reason_code:
        raise ValueError("Unsuccessful AI facts require a reason code")

    calls: list[UUID] = []
    # 逐条解码事实，核对归属、内容哈希并收集所属调用。
    for record in payload.records:
        value = decode(record)
        # 配置与调用事实必须属于本事件范围对应的执行。
        if (
            isinstance(value, (ConfigurationFact, CallFact))
            and value.execution_id != draft.scope_id
        ):
            raise ValueError("AI fact belongs to another execution")
        if isinstance(value, ConfigurationFact):
            config = ExecutionConfig.model_validate_json(canonical_json(value.config))
            # 修订号须与正文记录一致，配置哈希须由当前正文重算匹配。
            if (
                config.revision != value.config_revision
                or value.config_hash
                != hashlib.sha256(canonical_json(value.config).encode()).hexdigest()
            ):
                raise ValueError("AI configuration hash or revision differs")
        if isinstance(value, CandidateFact):
            artifact = TypeAdapter(FileContent | InlineContent).validate_json(
                canonical_json(value.content)
            )
            # 附件取存证哈希，内联正文按规范化 JSON 现算哈希。
            digest = (
                artifact.sha256
                if isinstance(artifact, FileContent)
                else hashlib.sha256(canonical_json(artifact.value).encode()).hexdigest()
            )
            if value.content_hash != digest:
                raise ValueError("Candidate hash differs")
        # 调用相关事实收集 call_id，供末尾核对同事件不混入多个无关调用。
        if isinstance(
            value, (CallFact, CallAttemptFact, ModelRequestFact, ToolActionFact, CandidateFact)
        ):
            calls.append(value.call_id)
    # 同一事件内出现多个不同 call_id，说明夹带了无关调用。
    if len(set(calls)) > 1:
        raise ValueError("AI event combines unrelated calls")


# 按矩阵生成的事件合同登记，供事件底座做类型校验、解码与记录模型查找。
REGISTRATIONS = [
    EventRegistration(
        event_type,
        1,
        "ai",
        "execution",
        AIEvent,
        validate,
        {(name, 1): MODELS[name] for name in matrix},
    )
    for event_type, matrix in MATRIX.items()
]
