"""装配 Domain 的定义提取、实例归类和模型调用。"""

from typing import ClassVar
from uuid import UUID

from deermind.abstractions.ai.contracts import (
    CallHandle,
    CallInput,
    ExecutionConfig,
    PurposeBinding,
)
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import RunInput
from deermind.bootstrap.material_operation import PURPOSE as MATERIAL_PURPOSE
from deermind.bootstrap.material_operation import STEP_OPTIONS, material_config, model_credential
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tools
from deermind.foundation.system.executions import store
from deermind.infrastructure.ai.agent import Purpose, build_agent
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.spaces.domain.analysis import WORKFLOW, DomainAnalysis, location_tables
from deermind.spaces.domain.public import EXTRACT, AnalysisOutput
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from temporalio import activity, workflow
from temporalio.exceptions import ActivityError, ApplicationError

PURPOSE = Purpose(
    "domain_intake_analysis",
    Ref(owner="domain", type="ai_purpose", id="domain_intake_analysis", version=1),
    Ref(owner="domain", type="prompt", id="domain_intake_analysis", version=5),
    Ref(owner="domain", type="ai_schema", id="AnalysisOutput", version=1),
    AnalysisOutput,
)


def analysis_config() -> ExecutionConfig | None:
    base = material_config()
    if base is None:
        # 未配置模型/预算，领域分析暂不可用。
        return None
    model = base.purpose_bindings[MATERIAL_PURPOSE.name].profile
    return ExecutionConfig(
        revision="domain-intake-analysis-5",
        purpose_bindings={
            PURPOSE.name: PurposeBinding(
                contract_ref=PURPOSE.contract_ref,
                prompt_ref=PURPOSE.prompt_ref,
                schema_ref=PURPOSE.schema_ref,
                tool_refs=[],
                profile=model,
            )
        },
        budget=base.budget.model_copy(
            update={
                "max_model_requests": 3,
                "max_input_tokens": 32_000,
                "max_output_tokens": 3072,
                "max_total_tokens": 96_000,
            }
        ),
    )


class AnalysisInput(FactModel):
    instructions: str
    prompt: str
    material_refs: list[Ref]


@workflow.defn(name=WORKFLOW, sandboxed=False)
class DomainAnalysisWorkflow(PydanticAIWorkflow):
    agent: ClassVar[Agent[CallHandle, BaseModel]]

    @workflow.run
    async def run(self, body: str) -> str:
        run = RunInput.model_validate_json(body)
        try:
            await workflow.execute_activity("runtime.execution_started", body, **STEP_OPTIONS)
            packed = await workflow.execute_activity(
                "domain.analysis_input", body, result_type=str, **STEP_OPTIONS
            )
            source = AnalysisInput.model_validate_json(packed)
            candidate = await execute_ai_task(
                self.agent,
                CallInput(
                    run=run,
                    step_key="derive",
                    call_key="fixed-material",
                    purpose=PURPOSE.name,
                    instructions=source.instructions,
                    prompt=source.prompt,
                    material_refs=source.material_refs,
                    tool_grants=[],
                ),
            )
            await workflow.execute_activity(
                "domain.analysis_finish", args=[body, str(candidate)], **STEP_OPTIONS
            )
            return str(candidate)
        except (ActivityError, ApplicationError):
            # 业务活动失败：落失败回执后转成不可重试的应用错误。
            await workflow.execute_activity(
                "runtime.execution_failed", args=[body, "DOMAIN_ANALYSIS_FAILED"], **STEP_OPTIONS
            )
            raise ApplicationError("Domain analysis failed", non_retryable=True) from None


class DomainAnalysisActivities:
    def __init__(self, service: DomainAnalysis, calls: Calls) -> None:
        self.service = service
        self.calls = calls
        DomainAnalysisWorkflow.agent = build_agent(
            PURPOSE, calls, Tools(calls, []), model_credential
        )
        DomainAnalysisWorkflow.__pydantic_ai_agents__ = [DomainAnalysisWorkflow.agent]

    @activity.defn(name="domain.analysis_input")
    async def prepare(self, body: str) -> str:
        run = RunInput.model_validate_json(body)
        value = await self.service.input(run)
        materials, definitions = location_tables(value.payload)
        part = "extract" if value.payload["action"] == EXTRACT else "compare"
        return AnalysisInput(
            instructions=await self.calls.prompt_instructions(
                run, PURPOSE.name, ["instructions", part]
            ),
            prompt=canonical_json(
                {
                    **value.payload,
                    "required_candidate_keys": list(definitions),
                    "available_material_locations": materials,
                    "available_definition_locations": definitions,
                }
            ),
            material_refs=[value.input_ref, *value.definition_refs],
        ).model_dump_json()

    @activity.defn(name="domain.analysis_finish")
    async def finish(self, body: str, key: str) -> None:
        run = RunInput.model_validate_json(body)
        async with self.service.engine.connect() as connection:
            saved = await store.load(connection, run.execution_id)
        if saved.state == "completed":
            # 执行已完成，重复回写不覆盖结果。
            return
        candidate = UUID(key)
        result = AnalysisOutput.model_validate(await self.calls.candidate_content(run, candidate))
        await self.service.finish(run, result, candidate)
