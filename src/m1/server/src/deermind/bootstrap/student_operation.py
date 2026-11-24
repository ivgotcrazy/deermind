"""装配学习助手的模型、输入与持久回复步骤。"""

import json
import os
from collections.abc import Awaitable, Callable
from typing import ClassVar
from uuid import UUID, uuid5

from deermind.abstractions.ai.contracts import (
    Budget,
    CallHandle,
    ExecutionConfig,
    ModelProfile,
    PromptCallInput,
    PurposeBinding,
)
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput
from deermind.abstractions.task_supply import SuppliedTask
from deermind.abstractions.waits import WaitCall
from deermind.bootstrap.material_operation import STEP_OPTIONS
from deermind.bootstrap.student_tools import configure_student_tools
from deermind.foundation.ai.execution import Calls
from deermind.foundation.system.executions import store
from deermind.foundation.system.waits.service import Waits
from deermind.infrastructure.ai.agent import Purpose, build_agent
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.infrastructure.temporal.waits import WaitSignals
from deermind.spaces.domain.public import TaskInstance, TaskRef
from deermind.spaces.evaluation.public import ClaimDetail, ClaimRef
from deermind.spaces.interaction import memory_steps
from deermind.spaces.interaction.detection_help import prepare_help
from deermind.spaces.interaction.detection_preparation import DetectionPreparation, PlanWork
from deermind.spaces.interaction.learning_materials import TOOL_REFS, reply_materials
from deermind.spaces.interaction.public import PREPARE_DETECTION, QuestionPart
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from deermind.spaces.interaction.student_turns import (
    ACKNOWLEDGE_ANSWER,
    WORKFLOW,
    MasteryFollowUp,
    ReadQuestion,
    StudentTurns,
)
from deermind.spaces.interaction.teaching_questions import TeachingCard, question_trigger
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity, workflow
from temporalio.exceptions import ActivityError, ApplicationError

_KEY = "M1_STUDENT_MODEL_KEY"

PURPOSE = Purpose(
    "student_conversation",
    Ref(owner="interaction", type="ai_purpose", id="student_conversation", version=1),
    Ref(owner="interaction", type="prompt", id="student_conversation", version=15),
    Ref(owner="interaction", type="ai_schema", id="ReplyCandidate", version=9),
    ReplyCandidate,
)


def student_config() -> ExecutionConfig | None:
    if os.environ.get("M1_STUDENT_MODEL_ENABLED") != "true":
        return None
    return ExecutionConfig(
        revision="student-conversation-12",
        purpose_bindings={
            PURPOSE.name: PurposeBinding(
                contract_ref=PURPOSE.contract_ref,
                prompt_ref=PURPOSE.prompt_ref,
                schema_ref=PURPOSE.schema_ref,
                tool_refs=list(TOOL_REFS.values()),
                profile=ModelProfile(
                    connection_ref=Ref(owner="ai", type="connection", id="deepseek", version=1),
                    profile_ref=Ref(owner="ai", type="profile", id="student", version=1),
                    adapter="openai_chat",
                    base_url="https://api.deepseek.com",
                    credential_ref=_KEY,
                    model=os.environ.get("M1_STUDENT_MODEL", "deepseek-flash"),
                    thinking="disabled",
                    temperature=0,
                ),
            )
        },
        budget=Budget(
            max_model_requests=4,
            max_tool_attempts=2,
            max_repairs=1,
            max_input_tokens=96_000,
            max_output_tokens=2048,
            max_total_tokens=200_000,
            max_input_bytes=128 * 1024,
            max_result_bytes=32 * 1024,
            finalize_reserve_seconds=15,
        ),
    )


def _credential(reference: str) -> str:
    return os.environ.get(_KEY, "") if reference == _KEY else ""


def configure_detection(
    student: StudentTurns,
    waiting: Waits,
    domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
    read_claim: Callable[[UUID, int | None], Awaitable[ClaimDetail]],
    supplied: Callable[
        [AsyncConnection, UUID, UUID], Awaitable[tuple[TaskInstance, SuppliedTask, UUID] | None]
    ],
) -> DetectionPreparation:
    async def read_task(claim: ClaimRef) -> TaskRef:
        return (await read_claim(claim.claim_id, claim.revision)).claim.definition.task_ref

    return DetectionPreparation(student, waiting, domain_for, read_task, supplied)


@workflow.defn(name=WORKFLOW, sandboxed=False)
class StudentWorkflow(PydanticAIWorkflow):
    agent: ClassVar[Agent[CallHandle, BaseModel]]

    def __init__(self) -> None:
        self.signals = WaitSignals()

    @workflow.signal(name="runtime.wait_changed")
    def resume_wait(self, identity: str) -> None:
        self.signals.receive(identity)

    @workflow.run
    async def run(self, raw: str) -> str:
        run = RunInput.model_validate_json(raw)
        try:
            await workflow.execute_activity("runtime.execution_started", raw, **STEP_OPTIONS)
            if run.implementation_ref.id == PREPARE_DETECTION:
                await self._prepare_detection(raw, None)
                return raw
            if workflow.patched("student_activity_memory"):
                await self._refresh_memory(run, raw)
            context = await workflow.execute_activity(
                "interaction.student_context", raw, result_type=str, **STEP_OPTIONS
            )
            if context == ACKNOWLEDGE_ANSWER:
                await workflow.execute_activity(
                    "interaction.acknowledge_answer", raw, **STEP_OPTIONS
                )
                return context
            prompt, refs, tools = reply_materials(context, run.input_ref)
            candidate = await execute_ai_task(
                self.agent,
                PromptCallInput(
                    run=run,
                    step_key="reply",
                    call_key="student-conversation",
                    purpose=PURPOSE.name,
                    prompt_parts=["instructions"],
                    prompt=prompt,
                    material_refs=refs,
                    tool_grants=tools,
                ),
            )
            post_close = False
            mode = json.loads(context.partition("\n本轮输入（JSON）\n")[0]).get("mode")
            if workflow.patched("student_answer_mastery") and mode == "detection_message":
                updated = await self._evaluation_follow_up(run, raw, str(candidate))
                if updated:
                    return str(candidate)
            if workflow.patched("student_detection_help") and mode == "detection_message":
                confirmed = await workflow.execute_activity(
                    "interaction.detection_help",
                    args=[raw, str(candidate)],
                    result_type=str,
                    **STEP_OPTIONS,
                )
                if confirmed:
                    context, post_close = confirmed, True
                    prompt, refs, tools = reply_materials(context, run.input_ref)
                    candidate = await execute_ai_task(
                        self.agent,
                        PromptCallInput(
                            run=run,
                            step_key="post_detection_help",
                            call_key="student-after-round",
                            purpose=PURPOSE.name,
                            prompt_parts=["instructions", "after_round"],
                            prompt=prompt,
                            material_refs=refs,
                            tool_grants=tools,
                        ),
                    )
            elif workflow.patched("student_prepare_detection") and await self._prepare_detection(
                raw, str(candidate)
            ):
                return str(candidate)
            if workflow.patched("verify_bound_teaching_rules"):
                await self._finish_checked(run, raw, context, str(candidate), post_close=post_close)
            else:
                await workflow.execute_activity(
                    "interaction.student_finish", args=[raw, str(candidate)], **STEP_OPTIONS
                )
            return str(candidate)
        except (ActivityError, ApplicationError):
            await workflow.execute_activity(
                "runtime.execution_failed",
                args=[raw, "STUDENT_REPLY_FAILED"],
                **STEP_OPTIONS,
            )
            raise ApplicationError("Student reply failed", non_retryable=True) from None

    async def _evaluation_follow_up(self, run: RunInput, raw: str, candidate: str) -> bool:
        prepared = await workflow.execute_activity(
            "interaction.wait_for_mastery", args=[raw, candidate], result_type=str, **STEP_OPTIONS
        )
        if not prepared:
            return False
        follow_up = MasteryFollowUp.model_validate_json(prepared)
        handling = await self.signals.resume(
            follow_up.waiting,
            activity_timeout=STEP_OPTIONS["start_to_close_timeout"],
            retry_policy=STEP_OPTIONS["retry_policy"],
        )
        reference = handling.handling_receipt_ref
        result = None
        if reference is not None and reference.type == "mastery_snapshot":
            context = await workflow.execute_activity(
                "interaction.follow_up_mastery",
                args=[prepared, reference.model_dump_json()],
                result_type=str,
                **STEP_OPTIONS,
            )
            if context:
                result = await execute_ai_task(
                    self.agent,
                    PromptCallInput(
                        run=run,
                        step_key="answer_mastery",
                        call_key="student-after-evaluation",
                        purpose=PURPOSE.name,
                        prompt_parts=["after_evaluation"],
                        prompt=context,
                        material_refs=[run.input_ref, reference],
                        tool_grants=[],
                    ),
                )
        await workflow.execute_activity(
            "interaction.complete_mastery_follow_up",
            args=[prepared, str(result) if result else None],
            **STEP_OPTIONS,
        )
        return True

    async def _refresh_memory(self, run: RunInput, raw: str) -> None:
        try:
            material = await workflow.execute_activity(
                "interaction.prepare_memory", raw, result_type=str, **STEP_OPTIONS
            )
            if not material:
                return
            picked = memory_steps.SummaryMaterial.model_validate_json(material)
            summary = await execute_ai_task(
                self.agent,
                PromptCallInput(
                    run=run,
                    step_key="activity_summary",
                    call_key="student-summary",
                    purpose=PURPOSE.name,
                    prompt_parts=["summary"],
                    prompt=material,
                    material_refs=picked.covered_refs,
                    tool_grants=[],
                ),
            )
            await workflow.execute_activity(
                "interaction.save_memory", args=[raw, material, str(summary)], **STEP_OPTIONS
            )
        except (ActivityError, ApplicationError):
            # 原消息仍可供主回应使用，摘要属于辅助步骤。
            workflow.logger.info("当前活动摘要不可用，使用已保存原文")

    async def _prepare_detection(self, raw: str, candidate: str | None) -> bool:
        prepared = await workflow.execute_activity(
            "interaction.prepare_detection",
            args=[raw, candidate],
            result_type=str,
            **STEP_OPTIONS,
        )
        if not prepared:
            return False
        plan = PlanWork.model_validate_json(prepared)
        available: list[str] = []
        for group in plan.groups:
            settlement = await self.signals.resume(
                group.waiting,
                activity_timeout=STEP_OPTIONS["start_to_close_timeout"],
                retry_policy=STEP_OPTIONS["retry_policy"],
            )
            result = settlement.handling_receipt_ref
            if result is not None and result.type == "supply_batch":
                available.append(str(group.trigger))
        await workflow.execute_activity(
            "interaction.finish_detection_plan",
            args=[raw, prepared, available],
            **STEP_OPTIONS,
        )
        return True

    async def _finish_checked(
        self, run: RunInput, raw: str, context: str, candidate: str, *, post_close: bool
    ) -> None:
        review = await workflow.execute_activity(
            "interaction.student_review",
            args=[raw, context, candidate],
            result_type=str,
            **STEP_OPTIONS,
        )
        checked = None
        if review:
            try:
                checked = await execute_ai_task(
                    self.agent,
                    PromptCallInput(
                        run=run,
                        step_key="verify_teaching",
                        call_key="verify-teaching",
                        purpose=PURPOSE.name,
                        prompt_parts=["check_teaching"],
                        prompt=review,
                        material_refs=[run.input_ref],
                        tool_grants=[],
                    ),
                )
            except (ActivityError, ApplicationError):
                # 无法核对时回到原候选的约束结果，仍由程序拦截它。
                pass
        arguments = [raw, candidate, str(checked) if checked else None]
        if post_close:
            await workflow.execute_activity(
                "interaction.student_finish", args=[*arguments, False, True], **STEP_OPTIONS
            )
            return
        if workflow.patched("student_wait_for_teaching_supply"):
            settled = None
            question = await workflow.execute_activity(
                "interaction.student_question",
                args=[raw, candidate],
                result_type=str,
                **STEP_OPTIONS,
            )
            if question:
                settled = await self.signals.resume(
                    WaitCall.model_validate_json(question),
                    activity_timeout=STEP_OPTIONS["start_to_close_timeout"],
                    retry_policy=STEP_OPTIONS["retry_policy"],
                )
            result_ref = settled.handling_receipt_ref if settled else None
            await workflow.execute_activity(
                "interaction.student_finish",
                args=[*arguments, bool(result_ref and result_ref.type == "supply_batch")],
                **STEP_OPTIONS,
            )
            return
        await workflow.execute_activity(
            "interaction.student_finish", args=arguments, **STEP_OPTIONS
        )


def post_round_reply(candidate: ReplyCandidate) -> ReplyCandidate:
    if candidate.intent == "detection_help" and candidate.teaching is not None:
        return candidate.model_copy(update={"intent": "question_answer"})
    return candidate


def rule_review_context(context: str, draft: ReplyCandidate) -> str:
    teaching = draft.teaching
    if teaching is None or draft.intent not in {"explanation", "question_answer"}:
        return ""
    packed, separator, raw_input = context.partition("\n本轮输入（JSON）\n")
    if not separator:
        return ""
    source = json.loads(packed)
    current = source["activity"]
    position = (
        "current"
        if teaching.placement == "continue" and current and current["type"] == draft.intent
        else "entry"
    )
    selected = next(
        (
            item
            for item in source["teaching_contexts"]
            if item["activity_type"] == draft.intent and item["position"] == position
        ),
        None,
    )
    if selected is None:
        return ""
    required = {item["ref"]["id"] for item in selected["rules"]}
    reported = {item.rule_id for item in teaching.rules}
    if required == reported and len(reported) == len(teaching.rules):
        return ""
    return (
        canonical_json(
            {
                "teaching_contexts": [selected],
                "allowed_rule_ids": sorted(required),
                "draft": draft.model_dump(
                    mode="json", exclude={"teaching": {"rules", "conditions"}}
                ),
            }
        )
        + separator
        + raw_input
    )


class StudentActivities:
    def __init__(
        self,
        service: StudentTurns,
        calls: Calls,
        waits: Waits,
        domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
        question: Callable[
            [AsyncConnection, UUID, UUID], Awaitable[tuple[TaskInstance, SuppliedTask, UUID] | None]
        ],
        fixed_question: ReadQuestion,
        detection: DetectionPreparation,
    ) -> None:
        self.service = service
        self.calls = calls
        self.waits, self.domain_for, self.question = waits, domain_for, question
        self.fixed_question = fixed_question
        self.detection = detection
        StudentWorkflow.agent = build_agent(
            PURPOSE,
            calls,
            configure_student_tools(service, calls),
            _credential,
            first_batch_limit=2,
        )
        StudentWorkflow.__pydantic_ai_agents__ = [StudentWorkflow.agent]

    @activity.defn(name="interaction.student_context")
    async def prepare(self, raw: str) -> str:
        return await self.service.context(RunInput.model_validate_json(raw), self.fixed_question)

    @activity.defn(name="interaction.wait_for_mastery")
    async def prepare_mastery(self, raw: str, candidate: str) -> str:
        run = RunInput.model_validate_json(raw)
        content = await self.calls.candidate_content(run, UUID(candidate))
        decoded = ReplyCandidate.model_validate_json(canonical_json(content))
        if decoded.intent != "clarify" or not decoded.use_latest_evaluation:
            return ""
        result = await self.service.wait_for_mastery(run, self.waits)
        return result.model_dump_json() if result else ""

    @activity.defn(name="interaction.follow_up_mastery")
    async def follow_up_mastery(self, prepared: str, reference: str) -> str:
        return await self.service.follow_up_context(
            MasteryFollowUp.model_validate_json(prepared),
            Ref.model_validate_json(reference),
            self.fixed_question,
        )

    @activity.defn(name="interaction.complete_mastery_follow_up")
    async def complete_mastery_follow_up(self, prepared: str, candidate: str | None) -> None:
        saved = MasteryFollowUp.model_validate_json(prepared)
        wording = None
        if candidate:
            content = await self.calls.candidate_content(saved.waiting.run, UUID(candidate))
            reply = ReplyCandidate.model_validate_json(canonical_json(content))
            if reply.intent == "clarify":
                wording = reply.wording
        await self.service.complete_mastery_follow_up(saved, wording)

    @activity.defn(name="interaction.acknowledge_answer")
    async def acknowledge_answer(self, raw: str) -> None:
        await self.service.acknowledge_answer(RunInput.model_validate_json(raw))

    @activity.defn(name="interaction.prepare_memory")
    async def prepare_memory(self, raw: str) -> str:
        material = await memory_steps.prepare(self.service, RunInput.model_validate_json(raw))
        return material.model_dump_json() if material else ""

    @activity.defn(name="interaction.save_memory")
    async def save_memory(self, raw: str, material: str, candidate_id: str) -> None:
        run = RunInput.model_validate_json(raw)
        value = await self.calls.candidate_content(run, UUID(candidate_id))
        candidate = ReplyCandidate.model_validate(value)
        if candidate.intent == "memory_summary":
            await memory_steps.save(
                self.service,
                run,
                memory_steps.SummaryMaterial.model_validate_json(material),
                candidate.wording,
                UUID(candidate_id),
            )

    @activity.defn(name="interaction.detection_help")
    async def detection_help(self, raw: str, candidate_id: str) -> str:
        run = RunInput.model_validate_json(raw)
        saved = await self.calls.candidate_content(run, UUID(candidate_id))
        candidate = ReplyCandidate.model_validate(saved)
        if candidate.intent != "detection_help" or not await prepare_help(
            self.service, run, candidate.help_quote
        ):
            return ""
        return await self.service.context(run, self.fixed_question, post_close=True)

    @activity.defn(name="interaction.student_review")
    async def review(self, raw: str, context: str, candidate_id: str) -> str:
        run = RunInput.model_validate_json(raw)
        saved = await self.calls.candidate_content(run, UUID(candidate_id))
        candidate = ReplyCandidate.model_validate(saved)
        mode = json.loads(context.partition("\n本轮输入（JSON）\n")[0]).get("mode")
        return rule_review_context(
            context, post_round_reply(candidate) if mode == "post_detection_help" else candidate
        )

    @activity.defn(name="interaction.prepare_detection")
    async def prepare_detection(self, raw: str, candidate_id: str | None) -> str:
        run = RunInput.model_validate_json(raw)
        if candidate_id:
            candidate = await self.calls.candidate_content(run, UUID(candidate_id))
            if ReplyCandidate.model_validate(candidate).intent != "detection":
                return ""
        return (await self.detection.prepare(run)).model_dump_json()

    @activity.defn(name="interaction.finish_detection_plan")
    async def finish_detection_plan(self, raw: str, prepared: str, available: list[str]) -> None:
        await self.detection.finish(
            RunInput.model_validate_json(raw),
            PlanWork.model_validate_json(prepared),
            {UUID(value) for value in available},
        )

    @activity.defn(name="interaction.student_question")
    async def prepare_question(self, raw: str, candidate_id: str) -> str:
        run = RunInput.model_validate_json(raw)
        saved = await self.calls.candidate_content(run, UUID(candidate_id))
        proposal = ReplyCandidate.model_validate(saved)
        if (
            proposal.question is None
            or proposal.teaching is None
            or proposal.teaching.placement != "continue"
            or proposal.intent not in {"explanation", "question_answer"}
            or proposal.teaching.action != "reply"
        ):
            return ""
        got = await self.service.request_question(
            run, proposal.question, self.waits, self.domain_for
        )
        return got.model_dump_json() if got else ""

    async def _read_card(
        self, run: RunInput, work_scope: UUID, proposal: ReplyCandidate
    ) -> TeachingCard | None:
        request = proposal.question
        if request is None:
            return None
        trigger = question_trigger(run.execution_id)
        async with self.service.engine.connect() as db:
            got = await self.question(db, work_scope, trigger)
        if got is None:
            return None
        question, supplied, cause = got
        if question.task_ref != request.task:
            return None
        solution = next(
            (
                item.content
                for item in question.reference_solutions
                if any(str(item.reference_id) == key.id for key in supplied.reference_solution_refs)
            ),
            None,
        )
        identity = uuid5(run.execution_id, "teaching-task-use")
        return TeachingCard(
            part=QuestionPart(
                part_id="question",
                type="question",
                title=question.title,
                purpose=request.purpose,
                task_use_ref=Ref(owner="interaction", type="task_use", id=str(identity)),
                statement=question.statement,
                worked_solution=solution if request.purpose == "example" else None,
            ),
            instance_ref=supplied.task_instance_ref,
            method_refs=supplied.matched_method_refs,
            supply_event_id=cause,
        )

    @activity.defn(name="interaction.student_finish")
    async def finish(
        self,
        raw: str,
        candidate_id: str,
        checked_id: str | None = None,
        supply_ready: bool = False,
        post_close: bool = False,
    ) -> None:
        run = RunInput.model_validate_json(raw)
        async with self.service.engine.connect() as connection:
            work = await store.load(connection, run.execution_id)
        if work.state == "completed" and work.active_attempt_id == run.attempt_id:
            return
        saved = await self.calls.candidate_content(run, UUID(candidate_id))
        original = ReplyCandidate.model_validate(saved)
        if post_close:
            original = post_round_reply(original)
        card = await self._read_card(run, work.scope_id, original) if supply_ready else None
        if checked_id and original.teaching:
            reviewed = await self.calls.candidate_content(run, UUID(checked_id))
            candidate = ReplyCandidate.model_validate(reviewed)
            if (
                candidate.intent == original.intent
                and candidate.topic == original.topic
                and candidate.teaching
                and candidate.teaching.placement == original.teaching.placement
                and candidate.teaching.placement_quote == original.teaching.placement_quote
            ):
                candidate = candidate.model_copy(update={"question": original.question})
                await self.service.finish(
                    run, candidate, UUID(checked_id), card, post_close=post_close
                )
                return
        await self.service.finish(run, original, UUID(candidate_id), card, post_close=post_close)
