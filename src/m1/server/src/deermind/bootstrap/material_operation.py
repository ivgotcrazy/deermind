"""把教材业务步骤、模型适配与 Temporal 持久执行接到同一 Operation。"""

import asyncio
import base64
import os
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any, ClassVar, TypedDict
from uuid import UUID

from deermind.abstractions.ai.contracts import (
    Budget,
    CallHandle,
    ExecutionConfig,
    ModelProfile,
    PromptCallInput,
    PurposeBinding,
)
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import RunInput
from deermind.abstractions.file_records import FileObject
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tools
from deermind.foundation.system.files.uploads import MAX_BYTES
from deermind.foundation.system.public.errors import Issue
from deermind.infrastructure.ai.agent import Purpose, build_agent
from deermind.infrastructure.ai.execution import Activities as AIActivities
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.infrastructure.files.originals import render_original_page
from deermind.product.materials.assistant import WORKFLOW, MaterialAssistant
from deermind.product.materials.proposals import (
    MaterialProposal,
    OriginalCoverage,
    ProposedChapter,
    ProposedContent,
)
from deermind.product.public.material_assistant import TurnOutcome
from deermind.spaces.domain.public import SourceRef
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from pydantic_ai.messages import BinaryContent, UserContent
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

PURPOSE = Purpose(
    "material_extraction",
    Ref(owner="product", type="ai_purpose", id="material_extraction", version=1),
    Ref(owner="product", type="prompt", id="material_extraction", version=6),
    Ref(owner="product", type="ai_schema", id="MaterialProposal", version=1),
    MaterialProposal,
)
_MODEL_KEY = "M1_MATERIAL_MODEL_KEY"
_PAGE_BATCH = 4
_CONTEXT_PAGES = 2


def material_config() -> ExecutionConfig | None:
    if os.environ.get("M1_MATERIAL_MODEL_ENABLED") != "true":
        # 未显式启用教材抽取模型，返回空配置关闭该路径。
        return None
    return ExecutionConfig(
        revision="material-extraction-6",
        purpose_bindings={
            PURPOSE.name: PurposeBinding(
                contract_ref=PURPOSE.contract_ref,
                prompt_ref=PURPOSE.prompt_ref,
                schema_ref=PURPOSE.schema_ref,
                tool_refs=[],
                profile=ModelProfile(
                    connection_ref=Ref(owner="ai", type="connection", id="deepseek", version=1),
                    profile_ref=Ref(owner="ai", type="profile", id="material", version=1),
                    adapter="openai_chat",
                    base_url="https://api.deepseek.com",
                    credential_ref=_MODEL_KEY,
                    model=os.environ.get("M1_MATERIAL_MODEL", "deepseek-flash"),
                    thinking="disabled",
                    temperature=0,
                ),
            )
        },
        budget=Budget(
            max_model_requests=8,
            max_tool_attempts=0,
            max_repairs=1,
            max_input_tokens=64_000,
            max_output_tokens=8192,
            max_total_tokens=320_000,
            max_input_bytes=8 * 1024**2,
            max_result_bytes=1024**2,
            finalize_reserve_seconds=15,
        ),
    )


class ImagePage(FactModel):
    source: SourceRef
    name: str
    data: str


class PreparedRange(FactModel):
    pages: list[ImagePage]
    prompt: str
    gaps: list[str]
    next_offset: int | None


class _ActivityOptions(TypedDict):
    start_to_close_timeout: timedelta
    schedule_to_close_timeout: timedelta
    retry_policy: RetryPolicy


STEP_OPTIONS: _ActivityOptions = {
    "start_to_close_timeout": timedelta(seconds=40),
    "schedule_to_close_timeout": timedelta(seconds=85),
    "retry_policy": RetryPolicy(maximum_attempts=2),
}


@workflow.defn(name=WORKFLOW, sandboxed=False)
class MaterialWorkflow(PydanticAIWorkflow):
    agent: ClassVar[Agent[CallHandle, BaseModel]]

    @workflow.run
    async def run(self, body: str) -> str:
        run = RunInput.model_validate_json(body)
        candidates: list[UUID] = []
        shown: list[SourceRef] = []
        gaps: list[str] = []
        offset = 0
        try:
            await workflow.execute_activity("runtime.execution_started", body, **STEP_OPTIONS)
            # 按页批逐段抽取，直到取完或出现阻断性缺失。
            while True:
                packed = await workflow.execute_activity(
                    "material.render_pages", args=[body, offset], result_type=str, **STEP_OPTIONS
                )
                selection = PreparedRange.model_validate_json(packed)
                gaps.extend(selection.gaps)
                if selection.pages and not selection.gaps:
                    # 本批有可读页面且无缺失问题，才提交模型解析。
                    contents: list[UserContent] = [selection.prompt]
                    for page in selection.pages:
                        contents.extend(
                            [
                                f"{page.name}\n{page.source.model_dump_json()}",
                                BinaryContent(
                                    data=base64.b64decode(page.data), media_type="image/jpeg"
                                ),
                            ]
                        )
                    candidates.append(
                        await execute_ai_task(
                            self.agent,
                            PromptCallInput(
                                run=run,
                                step_key="parse",
                                call_key=f"pages-{offset}",
                                purpose=PURPOSE.name,
                                prompt_parts=["instructions"],
                                prompt=selection.prompt,
                                material_refs=[
                                    Ref(
                                        owner="product",
                                        type="material_page",
                                        id=page.source.source_id,
                                    )
                                    for page in selection.pages
                                ],
                                tool_grants=[],
                            ),
                            user_content=contents,
                        )
                    )
                    shown.extend(page.source for page in selection.pages)
                if selection.next_offset is None or selection.gaps:
                    # 已到末尾，或本批出现问题，停止翻页。
                    break
                offset = selection.next_offset
            await workflow.execute_activity(
                "material.finish",
                args=[
                    body,
                    [str(candidate) for candidate in candidates],
                    canonical_json([item.model_dump(mode="json") for item in shown]),
                    gaps,
                ],
                **STEP_OPTIONS,
            )
            return run.input_ref.id
        except ActivityError:
            # 活动失败：落失败回执后转不可重试应用错误。
            await workflow.execute_activity(
                "runtime.execution_failed", args=[body, "MATERIAL_ASSISTANT_FAILED"], **STEP_OPTIONS
            )
            raise ApplicationError("Material assistant failed", non_retryable=True) from None


class MaterialActivities:
    def __init__(self, service: MaterialAssistant, calls: Calls) -> None:
        self.service = service
        self.calls = calls

    @activity.defn(name="material.render_pages")
    async def render(self, body: str, offset: int) -> str:
        run = RunInput.model_validate_json(body)
        _work, turn = await self.service.current_input(run)
        pages = turn.input["pages"]
        problems = turn.input["gaps"]
        assert isinstance(pages, list) and isinstance(problems, list)
        gaps = [str(problem) for problem in problems]
        rendered: list[ImagePage] = []
        if not gaps:
            # 尚无缺失问题时，逐页校验原件并渲染为图片。
            overlap = _CONTEXT_PAGES if turn.input.get("neighbor_pages") else 0
            start = max(0, offset - overlap)
            stop = offset + _PAGE_BATCH
            for position, value in enumerate(pages[start : stop + overlap], start):
                assert isinstance(value, dict)
                index = value["file_page"]
                assert isinstance(index, int)
                file = await self.service.materials.uploads.registry.by_id(
                    UUID(str(value["file_id"]))
                )
                if (
                    file is None
                    or file.category != "original"
                    or file.sha256 != value["sha256"]
                    or file.media_type not in MAX_BYTES
                ):
                    # 原件缺失、类型不符、摘要不符或格式不支持，记问题并中止本批。
                    gaps.append(f"{value['original_name']} 第 {index} 页的原件缺失。")
                    break

                try:
                    image = await asyncio.to_thread(self._render_one, file, index)
                except (OSError, ValueError, RuntimeError):
                    # 页面渲染失败，记问题并中止本批。
                    gaps.append(f"{value['original_name']} 第 {index} 页无法读取。")
                    break
                rendered.append(
                    ImagePage(
                        source=SourceRef.model_validate(
                            {
                                "source_id": str(value["page_id"]),
                                "owner": "product",
                                "ref": {
                                    "type": "file",
                                    "file_id": file.file_id,
                                    "sha256": file.sha256,
                                },
                                "file_page": index,
                                "printed_page": None,
                                "region": None,
                            }
                        ),
                        name=("本批负责页 " if offset <= position < stop else "相邻对照页 ")
                        + str(value["original_name"]),
                        data=base64.b64encode(image).decode(),
                    )
                )
        previous = await self.service.previous_context(turn)
        prompt = str(turn.input["message"])
        if turn.input.get("focus_candidate"):
            prompt += f"\n定点修正候选 {turn.input['focus_candidate']}。用 replaces 指定它。"
        if previous:
            state = turn.input.get("previous_batch_state")
            if turn.input.get("focus_candidate"):
                prompt += (
                    "\n只修订所选项，解法附父题。preserved_items 仅列出其他项的标题；"
                    "这些项原样保留，不复查、不报告缺失。所选原文：\n"
                )
            elif state is None:
                # v1 已受理任务恢复时沿用原输入。
                prompt += (
                    "\n以下是所引用的上一批候选，只用于核对本次请求。"
                    "请保留与这条修正无关的原有内容，交付修正后的完整候选。\n"
                )
            else:
                prompt += f"\n所引用的上一批候选（受理时 decision_state={state}）：\n"
            prompt += previous
        return PreparedRange(
            pages=rendered,
            prompt=prompt,
            gaps=gaps,
            next_offset=offset + _PAGE_BATCH if offset + _PAGE_BATCH < len(pages) else None,
        ).model_dump_json()

    def _render_one(self, file: FileObject, index: int) -> bytes:
        with self.service.materials.open_file(
            file.bytes_ref(), MAX_BYTES[file.media_type]
        ) as source:
            return render_original_page(source, file.media_type, index)

    @activity.defn(name="material.finish")
    async def finish(self, body: str, keys: list[str], sources: str, gaps: list[str]) -> None:
        run = RunInput.model_validate_json(body)
        from pydantic import TypeAdapter

        selected = TypeAdapter(list[SourceRef]).validate_json(sources)
        values = [
            MaterialProposal.model_validate(await self.calls.candidate_content(run, UUID(key)))
            for key in keys
        ]
        page_count = len(selected)
        selected = list({page.source_id: page for page in selected}.values())
        proposal = (
            merge_proposals(values, selected, neighbors=page_count != len(selected))
            if values and not gaps
            else None
        )
        # 无缺失、且提案不处于待补充状态时，本轮才可标记完成。
        can_complete = not gaps and (proposal is None or proposal.outcome != "needs_input")
        outcome: TurnOutcome = "completed" if can_complete else "needs_input"
        reply = "\n".join(
            [
                *(gaps or []),
                *([proposal.reply, *proposal.questions] if proposal else []),
            ]
        )
        await self.service.finish(
            run,
            proposal,
            selected,
            reply,
            outcome,
            [Issue(code="source_unavailable", path="/selection", message=gap) for gap in gaps],
        )


def merge_proposals(
    proposals: list[MaterialProposal], shown: list[SourceRef], *, neighbors: bool = False
) -> MaterialProposal:
    """各页段使用自己的局部键，程序为合并后的提案消除键冲突。"""
    changes: list[ProposedContent] = []
    retire: list[str] = []
    chapters: list[ProposedChapter] = []
    coverage: list[OriginalCoverage] = []
    issues: list[str] = []
    questions: list[str] = []
    positions = {item.source_id: index for index, item in enumerate(shown)}
    preceding_sections: dict[str, str] = {}
    # 逐段合并候选，把各段局部键改写为全局唯一编号。
    for index, proposal in enumerate(proposals, 1):
        start = (index - 1) * _PAGE_BATCH
        stop = start + _PAGE_BATCH
        overlap = _CONTEXT_PAGES if neighbors else 0
        proposal = proposal.bind_sources(shown[max(0, start - overlap) : stop + overlap])

        roots = {
            item.local_key
            for item in proposal.changes
            if not item.parent_key
            and start <= min(positions[r.source_id] for r in item.content.source_refs) < stop
        }
        included = [
            item for item in proposal.changes if (item.parent_key or item.local_key) in roots
        ]
        keys = {item.local_key: f"{index}:{order}" for order, item in enumerate(proposal.changes)}
        sections = {
            item.local_key: f"{index}:{order}"
            for order, item in enumerate(proposal.catalog_changes)
        }
        current_sections: dict[str, str] = {}
        for chapter in proposal.catalog_changes:
            if chapter.local_key not in {item.chapter_key for item in included} and not any(
                start <= positions[page] < stop for page in chapter.source_ids
            ):
                continue
            # 同名且共享原页的相邻目录项表示同一章节。仅同名不合并。
            prior_key = preceding_sections.get(chapter.name)
            prior = next((c for c in chapters if c.local_key == prior_key), None)
            if prior and set(prior.source_ids).intersection(chapter.source_ids):
                sections[chapter.local_key] = prior.local_key
                prior.source_ids.extend(p for p in chapter.source_ids if p not in prior.source_ids)
            else:
                chapters.append(
                    chapter.model_copy(deep=True, update={"local_key": sections[chapter.local_key]})
                )
            current_sections[chapter.name] = sections[chapter.local_key]
        preceding_sections = current_sections
        changes.extend(
            item.model_copy(
                update={
                    "local_key": keys[item.local_key],
                    "chapter_key": sections[item.chapter_key],
                    # 有父级编号时一并改写为全局键，无父级保持空。
                    "parent_key": keys[item.parent_key] if item.parent_key else None,
                }
            )
            for item in included
        )
        coverage.extend(
            item for item in proposal.coverage if start <= positions[item.source_id] < stop
        )
        retire.extend(proposal.retire)
        issues.extend(proposal.issues)
        questions.extend(proposal.questions)
    return MaterialProposal(
        # 有待补充问题记 needs_input；有实际改动记 proposal；否则仅回复记 reply。
        outcome="needs_input"
        if questions
        else "proposal"
        if changes or chapters or retire
        else "reply",
        reply="\n".join(item.reply for item in proposals),
        changes=changes,
        # 退役项按出现顺序去重。
        retire=list(dict.fromkeys(retire)),
        catalog_changes=chapters,
        coverage=coverage,
        issues=issues,
        questions=questions,
    )


def model_credential(reference: str) -> str:
    return os.environ.get(reference, "") if reference == _MODEL_KEY else ""


def material_activities(
    service: MaterialAssistant, calls: Calls, schemas: Mapping[str, type[BaseModel]]
) -> list[Callable[..., Any]]:
    tools = Tools(calls, [])
    MaterialWorkflow.agent = build_agent(
        PURPOSE,
        calls,
        tools,
        model_credential,
    )
    MaterialWorkflow.__pydantic_ai_agents__ = [MaterialWorkflow.agent]
    ai = AIActivities(calls, {PURPOSE.schema_ref.model_dump_json(): MaterialProposal, **schemas})
    activity_service = MaterialActivities(service, calls)
    return [ai.prepare, ai.save, ai.fail, activity_service.render, activity_service.finish]
