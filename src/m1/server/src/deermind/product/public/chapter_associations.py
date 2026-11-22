"""教材章节采用任务和方法的公开视图。"""

from typing import Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.material_intake import JsonUUID
from deermind.product.public.authentication import SessionView
from deermind.product.public.materials import RequestId, Revision
from deermind.spaces.domain.public import KnowledgeRef, SolutionRef, TaskRef
from pydantic import Field

CHAPTER_ACTION = "product.save_chapter_association"


class ChapterAssociationCommand(FactModel):
    request_id: RequestId
    action: Literal["add", "update", "remove"]
    task_ref: TaskRef
    association_id: JsonUUID | None = None
    expected_revision: Revision | None = None
    method_refs: list[SolutionRef] = Field(default_factory=list[SolutionRef], max_length=50)


class ChapterAssociationView(FactModel):
    association_ref: Ref
    task_ref: TaskRef
    method_refs: list[SolutionRef]
    active: bool


class ChapterAssociationResult(ChapterAssociationView):
    kc_refs: list[KnowledgeRef]


class ChapterAssociationReceipt(FactModel):
    request_ref: UUID
    result: ChapterAssociationResult


class ChapterAssociationList(FactModel):
    items: list[ChapterAssociationView]
    next_cursor: str | None


class ChapterAssociationService(Protocol):
    async def decide(
        self,
        session: SessionView,
        textbook_id: UUID,
        chapter_id: UUID,
        command: ChapterAssociationCommand,
    ) -> ChapterAssociationReceipt: ...

    async def list(
        self,
        session: SessionView,
        textbook_id: UUID,
        chapter_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> ChapterAssociationList: ...
