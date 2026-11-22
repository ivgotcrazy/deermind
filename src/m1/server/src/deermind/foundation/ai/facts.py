"""AI事件记录矩阵；正文转换由本所有者提供，事件底座只校验。"""

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

MODELS: dict[str, type[FactModel]] = {
    "ai.execution_configs": ConfigurationFact,
    "ai.ai_calls": CallFact,
    "ai.ai_call_attempts": CallAttemptFact,
    "ai.model_requests": ModelRequestFact,
    "ai.tool_actions": ToolActionFact,
    "ai.ai_candidates": CandidateFact,
}
MATRIX = {
    "AIConfigurationPinned": {"ai.execution_configs": (1, 1)},
    "AICallChanged": {"ai.ai_calls": (1, 1), "ai.ai_call_attempts": (0, 1)},
    "ModelRequestChanged": {"ai.model_requests": (1, 1)},
    "ToolActionChanged": {"ai.tool_actions": (1, 1)},
    "AICandidatePrepared": {"ai.ai_candidates": (1, 1)},
}


class AIEvent(EventPayload):
    subject_ref: Ref
    outcome: Literal["recorded", "started", "completed", "failed", "cancelled", "unknown", "denied"]
    reason_code: str | None


def decode(record: FactRecord) -> FactModel:
    """只接收本所有者已登记的完整正文；附件须先由授权读取解开。"""
    if (
        record.schema_version != 1
        or record.record_type not in MODELS
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Unknown or undecoded AI fact")
    return MODELS[record.record_type].model_validate_json(canonical_json(record.content.value))


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """校验矩阵、身份及固定hash；不能用额外records夹带其他模块的数据。"""
    if not isinstance(payload, AIEvent) or payload.subject_ref != draft.owner_ref:
        raise ValueError("AI event subject differs from its owner")
    matrix = MATRIX[draft.event_type]
    counts = Counter(record.record_type for record in payload.records)
    if set(counts) - set(matrix) or any(
        not minimum <= counts[name] <= maximum for name, (minimum, maximum) in matrix.items()
    ):
        raise ValueError("AI records differ from the event matrix")
    recorded = draft.event_type in {"AIConfigurationPinned", "AICandidatePrepared"}
    if (payload.outcome == "recorded") != recorded:
        raise ValueError("Invalid AI event outcome")
    if payload.outcome in {"failed", "cancelled", "unknown", "denied"} and not payload.reason_code:
        raise ValueError("Unsuccessful AI facts require a reason code")

    calls: list[UUID] = []
    for record in payload.records:
        value = decode(record)
        if (
            isinstance(value, (ConfigurationFact, CallFact))
            and value.execution_id != draft.scope_id
        ):
            raise ValueError("AI fact belongs to another execution")
        if isinstance(value, ConfigurationFact):
            config = ExecutionConfig.model_validate_json(canonical_json(value.config))
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
            digest = (
                artifact.sha256
                if isinstance(artifact, FileContent)
                else hashlib.sha256(canonical_json(artifact.value).encode()).hexdigest()
            )
            if value.content_hash != digest:
                raise ValueError("Candidate hash differs")
        if isinstance(
            value, (CallFact, CallAttemptFact, ModelRequestFact, ToolActionFact, CandidateFact)
        ):
            calls.append(value.call_id)
    if len(set(calls)) > 1:
        raise ValueError("AI event combines unrelated calls")


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
