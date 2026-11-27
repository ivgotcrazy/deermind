"""Prepare bounded book inputs and deliver a versioned candidate to the material assistant."""

from datetime import UTC, datetime
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import RunInput
from deermind.foundation.ai.execution import Calls
from deermind.infrastructure.ai.agent import Purpose
from deermind.product.materials.assistant import MaterialAssistant
from deermind.product.materials.edition_proposals import (
    OutlineBatch,
    TeachingBatch,
    assemble,
    parse_choices,
)
from deermind.product.materials.editions import related_tasks, select_tasks
from deermind.product.public.material_editions import BookPage, Edition, EditionJob, MapTask
from pydantic import BaseModel, TypeAdapter
from temporalio import activity


def purpose(name: str, output: type[BaseModel], prompt_version: int = 1) -> Purpose:
    return Purpose(
        name,
        Ref(owner="product", type="ai_purpose", id=name, version=1),
        Ref(owner="product", type="prompt", id=name, version=prompt_version),
        Ref(owner="product", type="ai_schema", id=output.__name__, version=1),
        output,
    )


OUTLINE = purpose("book_outline", OutlineBatch)
TEACHING = purpose("book_teaching", TeachingBatch, prompt_version=2)


class EditionInput(FactModel):
    purpose: str
    prompt: str
    next_offset: int | None


class EditionActivities:
    def __init__(self, assistant: MaterialAssistant, calls: Calls) -> None:
        self.assistant = assistant
        self.calls = calls

    @activity.defn(name="material.edition_input")
    async def prepare(self, body: str, offset: int, prior: str | None) -> str:
        run = RunInput.model_validate_json(body)
        _, turn = await self.assistant.current_input(run)
        if not turn.input.get("edition_job"):
            return ""
        job = EditionJob.model_validate_json(canonical_json(turn.input["edition_job"]))
        context = turn.input["edition_context"]
        assert isinstance(context, dict)
        source = (
            Edition.model_validate_json(canonical_json(context["source"]))
            if "source" in context
            else None
        )
        if job.action == "extract":
            assert source is not None
            catalog = TypeAdapter(list[MapTask]).validate_json(canonical_json(context["catalog"]))
            chapters = [
                n.node_id for n in source.nodes if n.node_kind in {"chapter", "section", "unit"}
            ]
            parents = {n.node_id: n.parent_id for n in source.nodes}
            chosen = set(chapters[offset : offset + 4])

            def relevant(node: UUID) -> bool:
                while node not in chapters:
                    parent = parents.get(node)
                    if parent is None:
                        return False
                    node = parent
                return node in chosen

            prompt = canonical_json(
                {
                    "chapters": [str(c) for c in chapters[offset : offset + 4]],
                    "nodes": [
                        n.model_dump(mode="json") for n in source.nodes if relevant(n.node_id)
                    ],
                    "tasks": [
                        {"task": i, "name": t.name, "methods": t.method_names}
                        for i, t in enumerate(catalog, 1)
                    ],
                }
            )
            return EditionInput(
                purpose=TEACHING.name,
                prompt=prompt,
                next_offset=offset + 4 if offset + 4 < len(chapters) else None,
            ).model_dump_json()
        prompt = (
            str(turn.input["message"])
            + f"\n本批从全书第 {offset + 1} 页起，请使用全书页序编排同级顺序。"
        )
        if source:
            prompt += (
                "\n引用位置 "
                + str(job.node_id)
                + "\n现有原文树 "
                + canonical_json([n.model_dump(mode="json") for n in source.nodes])
            )
        if prior:
            prev = OutlineBatch.model_validate(await self.calls.candidate_content(run, UUID(prior)))
            prompt += "\n上批目录与末尾节点，跨页续题可沿用父键：" + canonical_json(
                [
                    n.model_dump(mode="json", exclude={"structured_json"})
                    for i, n in enumerate(prev.nodes)
                    if n.kind in {"unit", "chapter", "section", "example", "exercise"}
                    or i >= len(prev.nodes) - 4
                ]
            )
        return EditionInput(purpose=OUTLINE.name, prompt=prompt, next_offset=None).model_dump_json()

    @activity.defn(name="material.edition_finish")
    async def finish(self, body: str, keys: list[str]) -> None:
        run = RunInput.model_validate_json(body)
        _, turn = await self.assistant.current_input(run)
        job = EditionJob.model_validate_json(canonical_json(turn.input["edition_job"]))
        context = turn.input["edition_context"]
        assert isinstance(context, dict)
        source = (
            Edition.model_validate_json(canonical_json(context["source"]))
            if "source" in context
            else None
        )
        values = [await self.calls.candidate_content(run, UUID(key)) for key in keys]
        source_pages = turn.input["pages"]
        assert isinstance(source_pages, list)
        pages = [
            BookPage(
                page_id=UUID(str(p["page_id"])),
                source_id=UUID(str(p["source_id"])),
                file_id=UUID(str(p["file_id"])),
                name=str(p["original_name"]),
                index=int(str(p["file_page"])),
                printed=None,
            )
            for p in source_pages
            if isinstance(p, dict)
        ]
        book = UUID(str(turn.input["textbook_id"]))
        entries = []
        related = []
        nodes = []
        issues = []
        if job.action == "extract":
            assert source is not None
            proposals = [TeachingBatch.model_validate(v) for v in values]
            catalog = TypeAdapter(list[MapTask]).validate_json(canonical_json(context["catalog"]))
            entries = select_tasks(parse_choices(proposals, catalog), catalog, source.nodes)
            related = related_tasks(entries, catalog)
            issues = [issue for proposal in proposals for issue in proposal.gaps]
            for proposal in proposals:
                for choice in proposal.choices:
                    if not choice.methods and not any(
                        s.startswith(choice.chapter + " ") for s in issues
                    ):
                        issues.append(f"{choice.chapter} 请为本节确认合适的任务和方法。")
            pages = source.pages
        else:
            try:
                nodes, pages = assemble(
                    source.edition_id if source else turn.request_ref,
                    source.pages if source else pages,
                    [OutlineBatch.model_validate(v) for v in values],
                    source.nodes if source else None,
                )
            except ValueError as exc:
                await self.assistant.finish(
                    run, None, [], f"原页校对未通过：{exc}。请补充说明后重试。", "needs_input", []
                )
                return
        if job.action == "correct":
            assert source is not None
            result = source.model_copy(update={"pending": nodes})
        else:
            result = Edition(
                edition_id=turn.request_ref,
                textbook_id=book,
                kind="extraction" if source else "tree",
                number=1,
                tree_id=source.edition_id if source else None,
                status="draft",
                revision=1,
                created_at=datetime.now(UTC),
                pages=pages,
                entries=entries,
                nodes=nodes,
                issues=issues,
                related_tasks=related,
            )
        await self.assistant.finish(
            run,
            None,
            [],
            "修正已就绪，请核对差异。" if result.pending else "整本草稿已保存。",
            "completed",
            [],
            edition=result,
        )
