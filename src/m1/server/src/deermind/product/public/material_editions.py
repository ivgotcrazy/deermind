"""Contracts for the textbook editor and the fixed student reading edition."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.material_intake import JsonUUID
from deermind.product.public.materials import Name, RequestId
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
    node_id: JsonUUID
    parent_id: JsonUUID | None
    node_kind: NodeKind
    sibling_order: Annotated[int, Field(ge=1)]
    content: dict[str, JsonValue] | None
    covered_page_ids: list[JsonUUID]


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


class TeachingMethod(FactModel):
    name: Name
    rationale: str = ""
    applicability: str = ""
    steps: str
    knowledge: list[Name]


class TeachingConcept(FactModel):
    name: Name
    meaning: Name
    applicability: Name
    observable_behavior: str = ""
    insufficient_example: str = ""
    test_method: Name


class TeachingTask(FactModel):
    chapter_id: JsonUUID
    name: Name
    description: str
    expected_output: str = ""
    completion_conditions: str = ""
    source_nodes: list[JsonUUID]
    methods: list[TeachingMethod]
    prerequisites: list[Name]
    # 每个正式知识点须有直接考查它的任务与方法；其他方法也可引用它。
    direct_knowledge: list[TeachingConcept]


class TeachingDependency(FactModel):
    task_key: Name
    reason: Name


class ModelMethod(FactModel):
    key: Name
    name: Name
    steps: str
    rationale: str
    applicability: str
    dependencies: list[TeachingDependency]


class ModelKnowledge(FactModel):
    key: Name
    name: Name
    meaning: str
    applicability: str


class ModelTask(FactModel):
    key: Name
    name: Name
    task_type: Literal["knowledge", "composite"]
    knowledge_key: Name | None
    chapter_id: JsonUUID
    source_nodes: list[JsonUUID]
    description: str
    expected_output: str
    completion_conditions: str
    insufficient_example: str = ""
    methods: list[ModelMethod]


class TeachingModel(FactModel):
    knowledge: list[ModelKnowledge]
    tasks: list[ModelTask]


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
    teaching: TeachingModel | list[TeachingTask] | None = None
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
        "copy",
        "publish",
        "discard",
        "edit_tree",
        "edit_teaching",
    ]
    revision: int = Field(ge=1)
    teaching: TeachingModel | None = None
    nodes: list[ContentNode] | None = None


class EditionJob(FactModel):
    action: Literal["tree", "extract", "assess"]
    edition_id: JsonUUID | None = None
    revision: int | None = None
    node_id: JsonUUID | None = None
    model_name: Name | None = None


class EditionUsage(FactModel):
    target_ref: Ref
    title: str


class StudentBook(FactModel):
    tree: Edition
    extraction: Edition
    related_tasks: list[MapTask] = Field(default_factory=list[MapTask])
