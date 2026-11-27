"""Contracts for the textbook editor and the fixed student reading edition."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.material_intake import JsonUUID
from deermind.product.public.materials import RequestId
from deermind.spaces.domain.public import KnowledgeRef, Prerequisite, SolutionRef, TaskRef
from pydantic import Field, JsonValue

type NodeKind = Literal[
    "book",
    "unit",
    "chapter",
    "section",
    "group",
    "example",
    "exercise",
    "subquestion",
    "solution",
    "heading",
    "paragraph",
    "caption",
    "formula",
    "table",
    "chart",
    "diagram",
    "image",
]
type EditionKind = Literal["tree", "extraction"]


class BookPage(FactModel):
    page_id: UUID
    source_id: UUID
    file_id: UUID
    name: str
    index: int
    printed: str | None


class ContentNode(FactModel):
    node_id: UUID
    parent_id: UUID | None
    node_kind: NodeKind
    sibling_order: Annotated[int, Field(ge=1)]
    content: dict[str, JsonValue] | None
    covered_page_ids: list[UUID]


class ChapterTask(FactModel):
    chapter_id: JsonUUID
    task_ref: TaskRef
    method_refs: list[SolutionRef]
    source_nodes: list[JsonUUID] = Field(default_factory=list[JsonUUID])


class MapTask(ChapterTask):
    name: str
    method_names: list[str]
    method_knowledge: list[list[KnowledgeRef]]
    knowledge: list[KnowledgeRef]
    knowledge_names: list[str]
    prerequisites: list[Prerequisite]


class EditionInfo(FactModel):
    edition_id: UUID
    textbook_id: UUID
    kind: EditionKind
    number: int
    tree_id: UUID | None
    status: Literal["draft", "published", "discarded"]
    revision: int
    created_at: datetime


class Edition(EditionInfo):
    base_edition_id: UUID | None = None
    pages: list[BookPage]
    nodes: list[ContentNode]
    entries: list[MapTask]
    related_tasks: list[MapTask] = Field(default_factory=list[MapTask])
    pending: list[ContentNode] | None = None
    issues: list[str] = Field(default_factory=list)


class EditionCommand(FactModel):
    request_id: RequestId
    action: Literal[
        "copy", "publish", "discard", "apply_correction", "reject_correction", "edit_tasks"
    ]
    revision: int = Field(ge=1)
    chapter_id: JsonUUID | None = None
    tasks: list[ChapterTask] = Field(default_factory=list[ChapterTask])


class EditionJob(FactModel):
    action: Literal["tree", "correct", "extract"]
    edition_id: JsonUUID | None = None
    revision: int | None = None
    node_id: JsonUUID | None = None


class EditionUsage(FactModel):
    target_ref: Ref
    title: str


class StudentBook(FactModel):
    tree: Edition
    extraction: Edition
    related_tasks: list[MapTask] = Field(default_factory=list[MapTask])
