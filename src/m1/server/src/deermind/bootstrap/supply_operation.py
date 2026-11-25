"""把 Domain 的新题生成和独立检查接到现有模型底座。"""

from typing import ClassVar
from uuid import UUID

from deermind.abstractions.ai.contracts import (
    CallHandle,
    ExecutionConfig,
    PromptCallInput,
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


def supply_config() -> ExecutionConfig | None:
    base = material_config()
    if base is None:
        # 未配置模型/预算，供题生成与检查暂不可用。
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
                PromptCallInput(
                    run=run,
                    step_key="generate_candidates",
                    call_key="generate",
                    purpose=GENERATE.name,
                    prompt_parts=["instructions"],
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
                PromptCallInput(
                    run=run,
                    step_key="check_candidates",
                    call_key="check",
                    purpose=CHECK.name,
                    prompt_parts=["instructions"],
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
            # 业务活动失败：落失败回执后转不可重试应用错误。
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
            # 执行已完成，重复提交不覆盖选定结果。
            return
        body = await self.calls.candidate_content(run, UUID(candidate))
        checked = await self.calls.candidate_content(run, UUID(selected))
        await self.service.save(
            run,
            GeneratedQuestions.model_validate(body),
            QualityChecks.model_validate(checked),
            UUID(selected),
        )
