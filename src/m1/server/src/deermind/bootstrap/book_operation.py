"""Prepare bounded book inputs and deliver a versioned candidate to the material assistant."""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import RunInput
from deermind.foundation.ai.execution import Calls
from deermind.foundation.system.public.errors import RequestError
from deermind.infrastructure.ai.agent import Purpose
from deermind.product.materials.assistant import MaterialAssistant
from deermind.product.materials.edition_proposals import (
    OutlineBatch,
    TeachingModelBatch,
    assemble,
)
from deermind.product.materials.editions import read_edition
from deermind.product.materials.teaching_model import validate_model
from deermind.product.public.material_editions import BookPage, Edition, EditionJob, TeachingModel
from deermind.spaces.evaluation.assessment_models import store_model
from deermind.spaces.evaluation.public import AssessmentBatch, AssessmentModel
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
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
TEACHING = purpose("book_teaching", TeachingModelBatch, prompt_version=4)


ASSESS = purpose("book_assessment", AssessmentBatch)


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
        if job.action == "assess":
            assert source is not None
            tasks = list({entry.task_ref: entry for entry in source.entries}.values())
            task = tasks[offset]
            if isinstance(source.teaching, TeachingModel):
                details = next(
                    (
                        t
                        for t in source.teaching.tasks
                        if uuid5(source.edition_id, "task:" + t.key) == task.task_ref.object_id
                    ),
                    None,
                )
            else:
                details = next((t for t in source.teaching or [] if t.name == task.name), None)
            return EditionInput(
                purpose=ASSESS.name,
                prompt=canonical_json(
                    {
                        "focus": turn.input["message"],
                        "task": task.model_dump(mode="json"),
                        "definition": details.model_dump(mode="json") if details else None,
                    }
                ),
                next_offset=offset + 1 if offset + 1 < len(tasks) else None,
            ).model_dump_json()
        if job.action == "extract":
            assert source is not None
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

            previous = (
                TeachingModelBatch.model_validate(
                    await self.calls.candidate_content(run, UUID(prior))
                )
                if prior
                else None
            )
            prompt = canonical_json(
                {
                    "previous_tasks": [
                        {"key": t.key, "type": t.task_type, "name": t.name} for t in previous.tasks
                    ]
                    if previous
                    else [],
                    "key_prefix": f"b{offset}_",
                    "chapters": [str(c) for c in chapters[offset : offset + 4]],
                    "nodes": [
                        n.model_dump(mode="json") for n in source.nodes if relevant(n.node_id)
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
        if job.action == "assess":
            assert source is not None and job.model_name is not None
            model_name = job.model_name
            claims = [
                claim
                for value in values
                for claim in AssessmentBatch.model_validate_json(canonical_json(value)).claims
            ]

            async def save(db: AsyncConnection, actor: Ref) -> None:
                fixed = await read_edition(db, source.textbook_id, source.edition_id)
                if fixed.status != "published" or fixed.revision != source.revision:
                    raise ValueError("生成期间来源提炼已变化")
                number = await db.scalar(
                    text(
                        "SELECT coalesce(max(number),0)+1 FROM evaluation.assessment_model WHERE "
                        "extraction_id=:id"
                    ),
                    {"id": source.edition_id},
                )
                model = AssessmentModel(
                    model_id=turn.request_ref,
                    extraction_id=source.edition_id,
                    name=model_name,
                    number=number,
                    revision=1,
                    status="draft",
                    created_at=datetime.now(UTC),
                    claims=claims,
                )
                await store_model(
                    db,
                    self.assistant.events,
                    self.assistant.attachments,
                    actor,
                    turn.request_ref,
                    model,
                )

            await self.assistant.finish(
                run,
                None,
                [],
                "评估标准草稿已生成，可按任务核对。",
                "completed",
                [],
                save_assessment=save,
            )
            return
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
        teaching: TeachingModel | None = None
        nodes = []
        issues = []
        if job.action == "extract":
            assert source is not None
            proposals = [TeachingModelBatch.model_validate_json(canonical_json(v)) for v in values]
            teaching = TeachingModel(
                knowledge=[k for proposal in proposals for k in proposal.knowledge],
                tasks=[t for proposal in proposals for t in proposal.tasks],
            )
            issues = [issue for proposal in proposals for issue in proposal.gaps]
            try:
                validate_model(teaching, source.nodes)
            except RequestError as exc:
                await self.assistant.finish(
                    run, None, [], f"提炼关系需重新核对：{exc.message}", "needs_input", []
                )
                return
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
            entries=[],
            teaching=teaching,
            nodes=nodes,
            issues=issues,
        )
        await self.assistant.finish(
            run,
            None,
            [],
            "整本草稿已保存。",
            "completed",
            [],
            edition=result,
        )
