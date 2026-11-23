"""把 Domain 的新题生成和独立检查接到现有模型底座。"""

from typing import ClassVar
from uuid import UUID

from deermind.abstractions.ai.contracts import (
    CallHandle,
    CallInput,
    ExecutionConfig,
    PurposeBinding,
)
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput
from deermind.bootstrap.material_operation import PURPOSE as MATERIAL_PURPOSE
from deermind.bootstrap.material_operation import STEP_OPTIONS, material_config, model_credential
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tools
from deermind.foundation.system.executions import store
from deermind.infrastructure.ai.agent import Purpose, build_agent
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.spaces.domain.generated_tasks import GeneratedQuestions, QualityChecks
from deermind.spaces.domain.supply_generation import WORKFLOW, Basis, GenerateSupply
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from temporalio import activity, workflow
from temporalio.exceptions import ActivityError, ApplicationError

GENERATE = Purpose(
    "generate_supply",
    Ref(owner="domain", type="ai_purpose", id="generate_supply", version=1),
    Ref(owner="domain", type="prompt", id="generate_supply", version=2),
    Ref(owner="domain", type="ai_schema", id="GeneratedQuestions", version=2),
    GeneratedQuestions,
)
CHECK = Purpose(
    "check_supply",
    Ref(owner="domain", type="ai_purpose", id="check_supply", version=1),
    Ref(owner="domain", type="prompt", id="check_supply", version=1),
    Ref(owner="domain", type="ai_schema", id="QualityChecks", version=1),
    QualityChecks,
)
_GENERATE = (
    "根据 task_text、method_text 和 requested 生成不足的题。"
    "从正文理解变量、单位及允许取值，不扩展题意。按照 requested 的用途和文字范围出题。"
    "题面不得包含参考答案或提示。题目不得重复 seen_statements 的题。"
    "statement、answer_basis、method_body 分别用完整纯文本。"
    "method_number 是从 1 开始的方法编号。用纯文本表达必要算式。"
    "本次不能提供额外图像或表格附件。如题目必须依赖无法给出的内容，返回空题列。"
    "所有条件都能够达到才生成。"
)
_CHECK = (
    "独立按题面解题，再用给出的 Task、方法、用途、文字条件和接触范围核对。"
    "仅在题意完整、可解、答法正确、使用准许方法、与范围一致且未泄露提示时给 pass。"
    "题目编号从 1 开始，每道候选恰好一次。信息不足用 unknown。只返回简短检查依据。"
)


def supply_config() -> ExecutionConfig | None:
    base = material_config()
    if base is None:
        return None
    profile = base.purpose_bindings[MATERIAL_PURPOSE.name].profile
    return ExecutionConfig(
        revision="domain-supply-2",
        purpose_bindings={
            item.name: PurposeBinding(
                contract_ref=item.contract_ref,
                prompt_ref=item.prompt_ref,
                schema_ref=item.schema_ref,
                tool_refs=[],
                profile=profile,
            )
            for item in (GENERATE, CHECK)
        },
        budget=base.budget.model_copy(update={"max_model_requests": 4}),
    )


@workflow.defn(name=WORKFLOW, sandboxed=False)
class SupplyWorkflow(PydanticAIWorkflow):
    generate: ClassVar[Agent[CallHandle, BaseModel]]
    check: ClassVar[Agent[CallHandle, BaseModel]]

    @workflow.run
    async def run(self, raw: str) -> str:
        run = RunInput.model_validate_json(raw)
        try:
            await workflow.execute_activity("runtime.execution_started", raw, **STEP_OPTIONS)
            packed = await workflow.execute_activity(
                "domain.supply_context", raw, result_type=str, **STEP_OPTIONS
            )
            source = Basis.model_validate_json(packed)
            material_refs = [
                run.input_ref,
                source.requested.task_ref,
                *source.requested.allowed_method_refs,
            ]
            candidate = await execute_ai_task(
                self.generate,
                CallInput(
                    run=run,
                    step_key="generate_candidates",
                    call_key="generate",
                    purpose=GENERATE.name,
                    instructions=_GENERATE,
                    prompt=packed,
                    material_refs=material_refs,
                    tool_grants=[],
                ),
            )
            check_input = await workflow.execute_activity(
                "domain.supply_review_context",
                args=[raw, str(candidate)],
                result_type=str,
                **STEP_OPTIONS,
            )
            decision = await execute_ai_task(
                self.check,
                CallInput(
                    run=run,
                    step_key="check_candidates",
                    call_key="check",
                    purpose=CHECK.name,
                    instructions=_CHECK,
                    prompt=check_input,
                    material_refs=material_refs,
                    tool_grants=[],
                ),
            )
            await workflow.execute_activity(
                "domain.supply_commit",
                args=[raw, str(candidate), str(decision)],
                **STEP_OPTIONS,
            )
            return str(decision)
        except (ActivityError, ApplicationError):
            await workflow.execute_activity(
                "runtime.execution_failed",
                args=[raw, "TASK_SUPPLY_FAILED"],
                **STEP_OPTIONS,
            )
            raise ApplicationError("Task supply failed", non_retryable=True) from None


class SupplyActivities:
    def __init__(self, service: GenerateSupply, calls: Calls) -> None:
        self.service = service
        self.calls = calls
        tools = Tools(calls, [])
        SupplyWorkflow.generate = build_agent(GENERATE, calls, tools, model_credential)
        SupplyWorkflow.check = build_agent(CHECK, calls, tools, model_credential)
        SupplyWorkflow.__pydantic_ai_agents__ = [SupplyWorkflow.generate, SupplyWorkflow.check]

    @activity.defn(name="domain.supply_context")
    async def prepare(self, raw: str) -> str:
        return (await self.service.basis(RunInput.model_validate_json(raw))).model_dump_json()

    @activity.defn(name="domain.supply_review_context")
    async def review(self, raw: str, candidate: str) -> str:
        run = RunInput.model_validate_json(raw)
        basis = await self.service.basis(run)
        content = await self.calls.candidate_content(run, UUID(candidate))
        return canonical_json({"basis": basis.model_dump(mode="json"), "candidate": content})

    @activity.defn(name="domain.supply_commit")
    async def commit(self, raw: str, candidate: str, selected: str) -> None:
        run = RunInput.model_validate_json(raw)
        async with self.service.engine.connect() as db:
            execution = await store.load(db, run.execution_id)
        if execution.state == "completed":
            return
        body = await self.calls.candidate_content(run, UUID(candidate))
        checked = await self.calls.candidate_content(run, UUID(selected))
        await self.service.save(
            run,
            GeneratedQuestions.model_validate(body),
            QualityChecks.model_validate(checked),
            UUID(selected),
        )
