"""官方Temporal集成装配；模型和工具分别恢复，业务Workflow仍由Operation拥有。"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from deermind.abstractions.ai.calls import AIRejected, CallService
from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.ai.tools import ToolService
from deermind.abstractions.events import Ref
from deermind.infrastructure.ai.models import (
    ControlledModel,
    ModelFactory,
    SecretReader,
    provider_model,
)
from pydantic import BaseModel, JsonValue, TypeAdapter
from pydantic_ai import Agent, RunContext, Tool, ToolOutput
from pydantic_ai.capabilities import ResolveModelId
from pydantic_ai.durable_exec.temporal import TemporalDurability, TemporalRunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import Model, ModelResolutionContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets.function import FunctionToolset
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError


@dataclass(frozen=True)
class Purpose:
    """程序登记输出Schema和用途，模型不能自行选择另一份合同。"""

    name: str
    contract_ref: Ref
    prompt_ref: Ref
    schema_ref: Ref
    output: type[BaseModel]


class ToolContext(TemporalRunContext[CallHandle]):
    """只携带程序计算的工具位置，不复制整个会话到每次工具Activity。"""

    @classmethod
    def serialize_run_context(cls, ctx: RunContext[Any]) -> dict[str, Any]:
        # Any仅用于SDK序列化扩展点；位置由程序从本轮已保存模型响应计算。
        result = super().serialize_run_context(ctx)
        responses = [message for message in ctx.messages if isinstance(message, ModelResponse)]
        if ctx.tool_call_id and responses:
            # 在最后一条模型响应中定位本次工具调用的序号。
            positions = [
                index + 1
                for index, part in enumerate(responses[-1].parts)
                if isinstance(part, ToolCallPart)
                and part.tool_call_id == ctx.tool_call_id
                and part.tool_name == ctx.tool_name
            ]
            if len(positions) != 1:
                # 位置不唯一或缺失，无法把工具 Activity 关联到模型响应。
                raise AIRejected("invalid_tool_position")
            result["tool_call_metadata"] = {
                "model_response": len(responses),
                "tool_ordinal": positions[0],
                "business_position": sum(
                    isinstance(part, ToolCallPart) and part.tool_name != "submit_candidate"
                    for part in responses[-1].parts[: positions[0]]
                ),
            }
        return result


def authorized_tools(
    tools: ToolService, first_batch_limit: int | None = None
) -> FunctionToolset[CallHandle]:
    """使用官方可持久执行的FunctionToolset，每个工具独立落到Activity。"""

    descriptions = {tool.name: tool for tool in tools.descriptions()}

    async def prepare(
        ctx: RunContext[CallHandle], definition: ToolDefinition
    ) -> ToolDefinition | None:
        reference = descriptions[definition.name].reference
        if first_batch_limit is not None and any(
            isinstance(message, ModelResponse) for message in ctx.messages
        ):
            # 已进入补读批次后不再开放可补读工具。
            return None
        if reference in ctx.deps.binding.tool_refs and reference in ctx.deps.input.tool_grants:
            # 工具既在绑定范围内，又被本次会话显式授权，才挂给模型。
            return definition
        return None

    async def invoke(ctx: RunContext[CallHandle], **arguments: JsonValue) -> dict[str, JsonValue]:
        try:
            if workflow.in_workflow():
                # 工具 I/O 必须落在独立 Activity，Workflow 内不得直连工具服务。
                raise AIRejected("tool_io_requires_activity")
            metadata = TypeAdapter(dict[str, int]).validate_python(
                ctx.tool_call_metadata or {}, strict=True
            )
            turn, ordinal = metadata.get("model_response"), metadata.get("tool_ordinal")
            if not isinstance(turn, int) or not isinstance(ordinal, int) or ctx.tool_name is None:
                # 缺少模型响应序号或工具序号，无法定位工具调用来源。
                raise AIRejected("invalid_tool_position")
            if first_batch_limit is not None:
                position = metadata.get("business_position")
                if turn != 1 or position is None or not 1 <= position <= first_batch_limit:
                    # 超出首轮补读次数上限，工具返回参数非法而非执行。
                    return {
                        "status": "invalid_arguments",
                        "data": {"reason": "本轮补读次数已用完，请依据已有材料回应。"},
                        "source_refs": [],
                        "owner_receipt_ref": None,
                    }
            parameters = TypeAdapter(dict[str, JsonValue]).validate_python(arguments)
            result = await tools.invoke(ctx.deps, ctx.tool_name, parameters, turn, ordinal)
            if result.status == "source_changed":
                # 取材源已变更，当前候选失效，按拒绝处理。
                raise AIRejected("source_changed")
            return result.model_dump(mode="json")
        except Exception as error:
            # 工具异常统一转为不可重试的 ApplicationError，保留稳定错误码。
            code = str(error) if isinstance(error, AIRejected) else "tool_failed"
            raise ApplicationError(code, type="AIToolRejected", non_retryable=True) from None

    toolset = FunctionToolset[CallHandle](id="deermind_authorized_tools", max_retries=0)
    for registered in descriptions.values():
        tool = Tool[CallHandle].from_schema(
            invoke,
            registered.name,
            registered.description,
            registered.parameters.model_json_schema(),
            takes_ctx=True,
            sequential=True,
        )
        tool.prepare = prepare
        toolset.add_tool(tool)
    return toolset


def build_agent(
    purpose: Purpose,
    calls: CallService,
    tools: ToolService,
    credentials: SecretReader,
    *,
    factory: ModelFactory = provider_model,
    first_batch_limit: int | None = None,
) -> Agent[CallHandle, BaseModel]:
    """启动前登记；解析函数无I/O，当前密钥只在ControlledModel.request中读取。"""

    def resolve(ctx: ModelResolutionContext[CallHandle], model_id: str) -> Model[Any]:
        binding = ctx.deps.binding
        if (
            model_id != "deermind:controlled"
            or ctx.deps.input.purpose != purpose.name
            or binding.contract_ref != purpose.contract_ref
            or binding.prompt_ref.model_copy(update={"version": purpose.prompt_ref.version})
            != purpose.prompt_ref
            or binding.schema_ref != purpose.schema_ref
        ):
            # 模型标识、用途或合同/提示词/schema 引用与本 Agent 登记不符，拒绝解析。
            raise AIRejected("configuration_unavailable")
        return ControlledModel(ctx.deps, calls, credentials, factory=factory)

    def instructions(ctx: RunContext[CallHandle]) -> str:
        return ctx.deps.input.instructions

    return Agent(
        "deermind:controlled",
        deps_type=CallHandle,
        output_type=ToolOutput(purpose.output, name="submit_candidate"),
        name=purpose.name,
        instructions=instructions,
        defer_model_check=True,
        retries=1,
        toolsets=[authorized_tools(tools, first_batch_limit)],
        capabilities=[
            ResolveModelId(resolve),
            TemporalDurability(
                run_context_type=ToolContext,
                activity_config={
                    "start_to_close_timeout": timedelta(seconds=30),
                    "schedule_to_close_timeout": timedelta(seconds=60),
                    "retry_policy": RetryPolicy(maximum_attempts=1),
                },
                model_activity_config={
                    "start_to_close_timeout": timedelta(seconds=120),
                    "schedule_to_close_timeout": timedelta(seconds=250),
                    "retry_policy": RetryPolicy(maximum_attempts=2),
                },
            ),
        ],
    )
