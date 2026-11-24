"""教材助手初次解析协议，候选身份与原件授权由程序维护。"""

from typing import Annotated, Literal, Self

from deermind.abstractions.events import FactModel, NonEmpty
from deermind.spaces.domain.public import RichContent, SourceRef
from pydantic import Field, model_validator

type Key = Annotated[str, Field(min_length=1, max_length=128)]


class OriginalCoverage(FactModel):
    source_id: Key
    status: Literal["processed", "unreadable", "excluded"]
    reason: str


class ProposedChapter(FactModel):
    action: Literal["add"]
    local_key: Key
    name: NonEmpty
    order: Annotated[int, Field(ge=1)]
    source_ids: list[Key] = Field(min_length=1)
    reason: str


class ProposedContent(FactModel):
    action: Literal["add"]
    local_key: Key
    chapter_key: Key
    kind: Literal["kc", "task_instance", "reference"]
    title: NonEmpty
    content: RichContent
    parent_key: Key | None
    replaces: Key | None = None
    reason: str
    teaching_aids: list[RichContent] = Field(default_factory=list[RichContent], max_length=8)

    @model_validator(mode="after")
    def kind_matches_body(self) -> Self:
        roles = {"kc": "definition", "task_instance": "statement", "reference": "reference"}
        if (
            self.content.role != roles[self.kind]
            or not self.content.blocks
            or not self.content.source_refs
            or (self.parent_key is not None) != (self.kind == "reference")
            or (self.teaching_aids and self.kind != "task_instance")
            or any(
                aid.role != "teaching_aid" or not aid.blocks or not aid.source_refs
                for aid in self.teaching_aids
            )
        ):
            raise ValueError("候选类型、正文用途、出处或父题不一致")
        return self


class MaterialProposal(FactModel):
    outcome: Literal["proposal", "needs_input", "reply"]
    reply: NonEmpty
    changes: list[ProposedContent] = Field(max_length=64)
    retire: list[Key] = Field(default_factory=list[Key], max_length=64)
    catalog_changes: list[ProposedChapter] = Field(max_length=32)
    coverage: list[OriginalCoverage]
    issues: list[str]
    questions: list[str]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.outcome == "proposal" and not (self.changes or self.catalog_changes or self.retire):
            raise ValueError("提案必须有内容或章节候选")
        if self.outcome == "needs_input" and not self.questions:
            raise ValueError("等待补充必须说明需要什么")
        if self.outcome == "reply" and (self.changes or self.catalog_changes or self.retire):
            raise ValueError("普通答复不得携带候选")
        by_key = {change.local_key: change for change in self.changes}
        chapters = {chapter.local_key for chapter in self.catalog_changes}
        if len(by_key) != len(self.changes) or len(chapters) != len(self.catalog_changes):
            raise ValueError("候选和章节的局部编号必须唯一")
        for change in self.changes:
            parent = by_key.get(change.parent_key) if change.parent_key else None
            if change.chapter_key not in chapters or (
                change.kind == "reference"
                and (
                    parent is None
                    or parent.kind != "task_instance"
                    or parent.chapter_key != change.chapter_key
                )
            ):
                raise ValueError("候选章节或参考解法的父题不在本批")
        return self

    def bind_sources(self, shown: list[SourceRef]) -> Self:
        """只接受实际提供的页编号，使用系统登记的文件身份保存出处。"""
        allowed = {source.source_id: source for source in shown}
        covered = {item.source_id for item in self.coverage}
        if len(covered) != len(self.coverage) or covered != allowed.keys():
            raise ValueError("覆盖清单必须对应本轮实际看到的页")
        for chapter in self.catalog_changes:
            if not set(chapter.source_ids) <= allowed.keys():
                raise ValueError("章节引用了未提供的页")

        def bind(body: RichContent) -> RichContent:
            sources: list[SourceRef] = []
            for ref in body.source_refs:
                source = allowed.get(ref.source_id)
                if source is None:
                    raise ValueError("候选出处超出已提供的页")
                sources.append(
                    source.model_copy(
                        update={
                            "region": ref.region,
                            "printed_page": source.printed_page or ref.printed_page,
                        }
                    )
                )
            return body.model_copy(update={"source_refs": sources})

        changes = [
            change.model_copy(
                update={
                    "content": bind(change.content),
                    "teaching_aids": [bind(aid) for aid in change.teaching_aids],
                }
            )
            for change in self.changes
        ]
        return self.model_copy(update={"changes": changes})
