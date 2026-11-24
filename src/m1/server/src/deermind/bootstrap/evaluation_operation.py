"""把评价解释接到共享 Temporal Worker 和受控模型。"""

import os
from typing import ClassVar
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
from deermind.bootstrap.material_operation import STEP_OPTIONS
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tools
from deermind.foundation.system.events.query import EventReader
from deermind.infrastructure.ai.agent import Purpose, build_agent
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.infrastructure.ai.models import SecretReader
from deermind.spaces.evaluation import interpretation
from deermind.spaces.evaluation.inputs import INTERPRETATION_REF, EvaluationInputs
from deermind.spaces.evaluation.mastery import Mastery
from deermind.spaces.evaluation.operations import TEACHING_WORKFLOW, WORKFLOW, EvaluationOperations
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from temporalio import activity, workflow
from temporalio.exceptions import ActivityError, ApplicationError

PURPOSE = Purpose(
    "interpret_submission",
    Ref(owner="evaluation", type="ai_purpose", id="interpret_submission", version=1),
    Ref(owner="evaluation", type="prompt", id="interpret_submission", version=1),
    Ref(owner="evaluation", type="ai_schema", id=INTERPRETATION_REF, version=1),
    interpretation.Interpretation,
)
TEACHING = Purpose(
    "interpret_teaching",
    Ref(owner="evaluation", type="ai_purpose", id="interpret_teaching", version=1),
    Ref(owner="evaluation", type="prompt", id="interpret_teaching", version=1),
    PURPOSE.schema_ref,
    interpretation.Interpretation,
)
_KEY = "M1_EVALUATION_API_KEY"


def evaluation_config(combinations: int) -> tuple[ExecutionConfig, int]:
    """按固定候选规模计算请求和工作上限，模型配置与教学分开。"""
    count = max(1, combinations)
    requests = 8 * count
    profile = ModelProfile(
        connection_ref=Ref(owner="ai", type="connection", id="deepseek", version=1),
        profile_ref=Ref(owner="ai", type="profile", id="evaluation", version=1),
        adapter="openai_chat",
        base_url="https://api.deepseek.com",
        credential_ref=_KEY,
        model=os.environ.get("M1_EVALUATION_MODEL", "deepseek-flash"),
        thinking="disabled",
        temperature=0,
    )
    config = ExecutionConfig(
        revision="evaluation-1",
        purpose_bindings={
            purpose.name: PurposeBinding(
                contract_ref=purpose.contract_ref,
                prompt_ref=purpose.prompt_ref,
                schema_ref=purpose.schema_ref,
                tool_refs=[],
                profile=profile,
            )
            for purpose in (PURPOSE, TEACHING)
        },
        budget=Budget(
            max_model_requests=requests,
            max_tool_attempts=0,
            max_repairs=1,
            max_input_tokens=32768,
            max_output_tokens=8192,
            max_total_tokens=requests * 40960,
            max_input_bytes=128 * 1024,
            max_result_bytes=64 * 1024,
            finalize_reserve_seconds=30,
        ),
    )
    return config, 600 * count


def evaluation_credential(reference: str) -> str:
    return os.environ.get(_KEY, "") if reference == _KEY else ""


def configure_evaluation_operation(
    inputs: EvaluationInputs, task_queue: str, reader: EventReader
) -> EvaluationOperations:
    return EvaluationOperations(inputs, task_queue, evaluation_config, reader)


class ModelMaterial(FactModel):
    input_ref: Ref
    material_refs: list[Ref]
    prompt: str | None
    interpretation_ref: Ref | None = None


async def _evaluate(raw: str, agent: Agent[CallHandle, BaseModel], purpose: Purpose) -> str:
    run = RunInput.model_validate_json(raw)
    try:
        await workflow.execute_activity("runtime.execution_started", raw, **STEP_OPTIONS)
        payload = await workflow.execute_activity(
            "evaluation.prepare_input", raw, result_type=str, **STEP_OPTIONS
        )
        material = ModelMaterial.model_validate_json(payload)
        publish_mastery = workflow.patched("evaluation-publish-mastery")
        if material.interpretation_ref is not None or (publish_mastery and material.prompt is None):
            basis = material.interpretation_ref or material.input_ref
            return await _publish(raw, basis)
        if material.prompt is None:
            await workflow.execute_activity(
                "runtime.execution_completed",
                args=[raw, material.input_ref.model_dump_json()],
                **STEP_OPTIONS,
            )
            return material.input_ref.id
        candidate = await execute_ai_task(
            agent,
            PromptCallInput(
                run=run,
                step_key=purpose.name,
                call_key="interpret",
                purpose=purpose.name,
                prompt_parts=["instructions"],
                prompt=material.prompt,
                material_refs=material.material_refs,
                tool_grants=[],
            ),
        )
        arguments = (
            [raw, str(candidate), publish_mastery] if publish_mastery else [raw, str(candidate)]
        )
        interpretation_id = await workflow.execute_activity(
            "evaluation.save_interpretation",
            args=arguments,
            result_type=str,
            **STEP_OPTIONS,
        )
        if not publish_mastery:
            return interpretation_id
        return await _publish(
            raw, Ref(owner="evaluation", type="interpretation", id=interpretation_id)
        )
    except (ActivityError, ApplicationError):
        await workflow.execute_activity(
            "runtime.execution_failed",
            args=[raw, "EVALUATION_INTERPRETATION_FAILED"],
            **STEP_OPTIONS,
        )
        raise ApplicationError("Evaluation interpretation failed", non_retryable=True) from None


async def _publish(raw: str, basis: Ref) -> str:
    return await workflow.execute_activity(
        "evaluation.publish_mastery",
        args=[raw, basis.model_dump_json()],
        result_type=str,
        **STEP_OPTIONS,
    )


@workflow.defn(name=WORKFLOW, sandboxed=False)
class EvaluationWorkflow(PydanticAIWorkflow):
    agent: ClassVar[Agent[CallHandle, BaseModel]]

    @workflow.run
    async def run(self, raw: str) -> str:
        return await _evaluate(raw, self.agent, PURPOSE)


@workflow.defn(name=TEACHING_WORKFLOW, sandboxed=False)
class TeachingWorkflow(PydanticAIWorkflow):
    agent: ClassVar[Agent[CallHandle, BaseModel]]

    @workflow.run
    async def run(self, raw: str) -> str:
        return await _evaluate(raw, self.agent, TEACHING)


class EvaluationActivities:
    def __init__(
        self, service: EvaluationOperations, calls: Calls, credential: SecretReader
    ) -> None:
        self.service, self.calls = service, calls
        self.mastery = Mastery(service.inputs, service.registry)
        tools = Tools(calls, [])
        EvaluationWorkflow.agent = build_agent(PURPOSE, calls, tools, credential)
        EvaluationWorkflow.__pydantic_ai_agents__ = [EvaluationWorkflow.agent]
        TeachingWorkflow.agent = build_agent(TEACHING, calls, tools, credential)
        TeachingWorkflow.__pydantic_ai_agents__ = [TeachingWorkflow.agent]

    @activity.defn(name="evaluation.prepare_input")
    async def prepare(self, raw: str) -> str:
        run = RunInput.model_validate_json(raw)
        checkpoint = await self.service.checkpoint(run)
        bundle = await self.service.materials(run)
        input_ref = Ref(owner="evaluation", type="evaluation_input", id=str(bundle.record.input_id))
        prompt = None
        if checkpoint is None and interpretation.choices(bundle):
            historical = await self.service.history(bundle)
            prompt = interpretation.prompt(bundle, historical.checks, list(historical.comparison))
        return ModelMaterial(
            input_ref=input_ref,
            material_refs=[input_ref, *bundle.domain.keys()],
            prompt=prompt,
            interpretation_ref=checkpoint,
        ).model_dump_json()

    @activity.defn(name="evaluation.save_interpretation")
    async def save(self, raw: str, candidate: str, publish_mastery: bool = False) -> str:
        run = RunInput.model_validate_json(raw)
        candidate_id = UUID(candidate)
        content = await self.calls.candidate_content(run, candidate_id)
        decoded = interpretation.Interpretation.model_validate_json(canonical_json(content))
        result = await self.service.save(run, candidate_id, decoded, publish_mastery)
        return result.id

    @activity.defn(name="evaluation.publish_mastery")
    async def publish(self, raw: str, basis: str) -> str:
        reference = await self.mastery.save(
            RunInput.model_validate_json(raw), Ref.model_validate_json(basis)
        )
        return reference.id
