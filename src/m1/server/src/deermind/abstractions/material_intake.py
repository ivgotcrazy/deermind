"""教材提交给 Domain 的固定来源与父题选择合同。

分层定位：abstractions（跨层合同）
对外契约：教材→Domain 入库请求/决定事件正文，及候选、父题绑定引用结构。
边界约束：只定义事件正文与校验，不含入库处理与归类实现。
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventPayload, FactModel, Ref

type JsonUUID = Annotated[UUID, Field(strict=False)]
type CandidateKey = tuple[UUID, int, int]

REQUESTED = "DomainIntakeRequested"
RECEIVED = "DomainIntakeReceived"
REJECTED = "DomainIntakeRejected"
DELETED = "MaterialImportDeleted"


class CandidateRef(FactModel):
    """候选定位：候选编号、候选修订与依据修订。"""

    candidate_id: JsonUUID
    candidate_revision: Annotated[int, Field(ge=1)]
    basis_revision: Annotated[int, Field(ge=0)]

    def key(self) -> CandidateKey:
        """返回候选稳定三元组键，用于去重与比对。"""
        return self.candidate_id, self.candidate_revision, self.basis_revision


class ParentBinding(FactModel):
    """候选与唯一父题的绑定；候选父、入库项父、题目实例父三类引用恰好其一。"""

    candidate_ref: CandidateRef
    parent_candidate_ref: CandidateRef | None = None
    parent_item_ref: Ref | None = None
    task_instance_ref: Ref | None = None

    @model_validator(mode="after")
    def one_parent(self) -> Self:
        # 三类父引用必须恰好选一个；存储父题还必须是固定的 Domain 引用。
        selected = (self.parent_candidate_ref, self.parent_item_ref, self.task_instance_ref)
        # 三类父引用必须恰好一个，不能悬空也不能多重父题。
        if sum(reference is not None for reference in selected) != 1:
            raise ValueError("A reference needs exactly one parent")
        # 逐项核对存储父题引用的所有者、类型与版本标识。
        for ref, kind, version in (
            (self.parent_item_ref, "intake_item", "revision"),
            (self.task_instance_ref, "task_instance", "version"),
        ):
            if ref is not None:
                UUID(ref.id)
                # 存储父题必须是固定的 Domain 引用，且带对应版本标识。
                if ref.owner != "domain" or ref.type != kind or getattr(ref, version) is None:
                    raise ValueError("A stored parent must be a fixed Domain reference")
        return self


class IntakeSource(FactModel):
    """候选来源：候选引用、候选事实定位与采用引用。"""

    candidate_ref: CandidateRef
    candidate_fact: EventPartRef
    adoption_ref: Ref


class IntakeRequested(EventPayload):
    """入库请求事件正文：领域、请求编号、候选集合、来源与父题绑定。"""

    domain_id: UUID
    intake_request_id: UUID
    candidate_refs: list[CandidateRef]
    sources: list[IntakeSource]
    parent_bindings: list[ParentBinding]


class IntakeDecided(EventPayload):
    """入库受理/拒收决定事件正文：触发事件、收据、结果、入库项与问题清单。"""

    trigger_event_id: UUID
    domain_id: UUID
    intake_request_id: UUID
    receipt_ref: Ref
    result_ref: Ref
    outcome: Literal["received", "rejected"]
    items: list[Ref]
    issues: list[dict[str, str]]
