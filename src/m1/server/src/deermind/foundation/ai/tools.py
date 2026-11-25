"""AI 工具的登记、授权闸门与调用留痕；工具真正的业务读取/写入由各工具所有者闭包处理。

分层定位：foundation（AI 底座）
对外契约：`Tool` 供装配层登记；`Tools` 实现 `ToolService`，向适配层（infrastructure/ai/agent.py）
提供公开描述与受控调用。
边界约束：本层只做身份核验、授权闸门、幂等留痕与预算记账；教材、学生、评价等业务规则
放在工具自身的 `check`/`invoke` 闭包中，不在此判断。
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.ai.tools import ToolDescription, ToolResult
from deermind.abstractions.events import Ref
from deermind.abstractions.hashing import digest
from deermind.foundation.ai import store
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.records import ToolActionFact
from deermind.foundation.system.executions import store as executions
from pydantic import BaseModel, JsonValue, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Tool:
    """单个已登记工具；只能由程序在装配层登记，模型不可自行新增或改名。

    reference：工具引用，授权闸门据此与接线白名单、本次受理授权逐项比对。
    effect：`read` 只读；`draft_write` 允许写草稿，须用稳定 work_key 自行核验业务位置与幂等。
    check：事务内的业务位置/授权核验，返回是否放行；不放行则不调用 `invoke`。
    invoke：工具所有者的实际处理，返回结构化 `ToolResult`；业务写入与收据对账由其负责。
    """

    reference: Ref
    name: str
    description: str
    parameters: type[BaseModel]
    effect: Literal["read", "draft_write"]
    timeout_seconds: int
    check: Callable[[AsyncConnection, CallHandle, BaseModel], Awaitable[bool]]
    invoke: Callable[[CallHandle, BaseModel, str | None], Awaitable[ToolResult]]


class Tools:
    """工具集：按名称索引已登记工具，统一承接模型侧的描述下发与受控调用。

    协作方：`Calls` 提供当前调用身份、附件与预算；适配层 agent.py 经 `ToolService` 接口调用本类。
    不变量：工具名全局唯一；每个工具的时限必须为正，装配时即校验。
    """

    def __init__(self, calls: Calls, tools: Sequence[Tool]) -> None:
        """登记工具集，校验名称唯一且时限为正。

        calls：当前调用的授权、附件与预算能力；tools：装配层登记的工具序列。
        """
        self.calls = calls
        self.tools = {tool.name: tool for tool in tools}
        # 重名会导致模型调用无法定位到确定工具；时限必须为正才能进入超时控制。
        if len(self.tools) != len(tools) or any(tool.timeout_seconds <= 0 for tool in tools):
            raise ValueError("Tools require unique names and finite deadlines")

    def descriptions(self) -> tuple[ToolDescription, ...]:
        """返回工具公开描述（引用、名称、说明、参数 schema）。

        边界：事务校验和执行函数不交给 SDK；SDK 只见描述，真正授权与执行在 `invoke` 内完成。
        """
        return tuple(
            ToolDescription(t.reference, t.name, t.description, t.parameters)
            for t in self.tools.values()
        )

    async def invoke(
        self,
        handle: CallHandle,
        name: str,
        parameters: dict[str, JsonValue],
        turn: int,
        ordinal: int,
    ) -> ToolResult:
        """执行一次模型工具调用：程序补身份与权限，授权后才运行工具，并按动作键幂等留痕。

        入参：
        - handle：当前受理的调用身份，含接线授权 `tool_refs`、受理授权 `tool_grants` 与预算。
        - name：模型请求的工具名；parameters：模型给出的原始参数。
        - turn/ordinal：模型响应中的工具轮次与位置，由 ToolContext 从已保存响应计算。
        返回：工具结构化结果；已完成的动作直接读回既有结果，不重复调用工具。
        副作用：参数与结果写入附件；写 `ai.tool_actions` 并记录 `ToolActionChanged`；
        草稿工具复用稳定 work_key，供所有者按收据幂等。
        边界：授权三闸门（接线白名单 → 受理授权 → 所有者 check）；同一动作键重试复用收据，
        不重复写草稿；参数冲突、超预算、调用失败均抛 `AIRejected`。
        """
        # 工具位置由程序从模型响应计算，非法位置不进入授权与留痕。
        if turn < 1 or ordinal < 1:
            raise AIRejected("invalid_tool_position")
        # 动作幂等键：同一调用、尝试、轮次、位置唯一确定一次工具动作。
        action_key = f"{handle.call_id}/{handle.attempt_id}/{turn}/{ordinal}"
        source = Ref(owner="ai", type="execution", id=str(handle.input.run.execution_id))
        # 参数先固化为附件，后续留痕与冲突比对只引用附件，不内联大正文。
        reference = await self.calls.attachments.save_json(
            parameters,
            actor=source,
            source=source,
            artifact_key=f"ai-tool-input:{action_key}:{digest(parameters)}",
            max_bytes=handle.budget.max_input_bytes,
        )
        tool = self.tools.get(name)
        parsed: BaseModel | None = None
        if tool is not None:
            try:
                # 严格按登记 schema 校验；校验失败不阻塞流程，转入 invalid_arguments 结果。
                parsed = tool.parameters.model_validate(parameters, strict=True)
            except ValidationError:
                pass
        async with self.calls.engine.begin() as connection:
            # 复核当前执行与固定调用身份，防止恢复后跨工作、跨调用借用身份。
            call = await self.calls.guard(connection, handle)
            if call.state != "running":
                raise AIRejected("call_not_running")
            execution = await executions.load(connection, handle.input.run.execution_id)
            saved = await store.load(
                connection,
                "ai.tool_actions",
                ToolActionFact,
                {"tool_action_key": action_key, "attempt_id": handle.attempt_id},
            )
            # 同一动作键已有记录时，参数引用或工具名不一致属于输入被改写，判冲突。
            if saved is not None and (saved.parameters_ref != reference or saved.tool_name != name):
                raise AIRejected("input_conflict")
            # 授权闸门一/二：用途接线白名单 + 本次受理授权，两道都在才继续。
            allowed = (
                tool is not None
                and tool.reference in handle.binding.tool_refs
                and tool.reference in handle.input.tool_grants
            )
            # 授权闸门三：工具所有者在事务内核验当前业务位置与权限。
            if allowed and parsed is not None and tool is not None:
                allowed = await tool.check(connection, handle, parsed)
            # 仅首次记录或上次未完成时才占用工具次数；已完成动作不重复扣预算。
            if saved is None or saved.outcome == "pending":
                # FOR UPDATE 串行记账，避免并发工具调用超出 max_tool_attempts。
                count = await connection.scalar(
                    text(
                        "SELECT tool_count FROM ai.execution_usage "
                        "WHERE execution_id=:id FOR UPDATE"
                    ),
                    {"id": execution.execution_id},
                )
                if count >= handle.budget.max_tool_attempts:
                    raise AIRejected("budget_exhausted")
                await connection.execute(
                    text(
                        "UPDATE ai.execution_usage SET tool_count=tool_count+1,"
                        "updated_at=clock_timestamp() WHERE execution_id=:id"
                    ),
                    {"id": execution.execution_id},
                )
            if saved is None:
                timestamp = await store.now(connection)
                # 草稿工具分配稳定 work_key；只读工具不登记，供所有者区分幂等边界。
                work_key = (
                    f"{handle.call_id}/tool/{turn}/{ordinal}"
                    if tool and tool.effect == "draft_write"
                    else None
                )
                saved = ToolActionFact(
                    tool_action_key=action_key,
                    attempt_id=handle.attempt_id,
                    call_id=handle.call_id,
                    tool_name=name,
                    parameters_ref=reference,
                    result_ref=None,
                    authorization_result="allowed" if allowed else "denied",
                    work_key=work_key,
                    owner_receipt_ref=None,
                    outcome="pending" if allowed else "denied",
                    started_at=timestamp,
                    finished_at=None if allowed else timestamp,
                )
                # 授权通过记 started 待执行；拒绝记 denied 并立即结束，不留待执行状态。
                await store.record(
                    connection,
                    execution,
                    "ToolActionChanged",
                    "started" if allowed else "denied",
                    [("ai.tool_actions", saved)],
                    reason=None if allowed else "forbidden",
                )
        if not allowed or tool is None:
            raise AIRejected("forbidden")
        # 重试命中已完成动作：读回既有结果，不再触发工具的业务写入。
        if saved.outcome == "completed" and saved.result_ref is not None:
            body = await self.calls.attachments.read_json(
                saved.result_ref, source=source, max_bytes=handle.budget.max_result_bytes
            )
            return ToolResult.model_validate(body)
        # 上次动作已失败/被拒等终态，不允许在同一动作键上重试出不同结果。
        if saved.outcome != "pending":
            raise AIRejected("tool_already_failed")
        error: str | None = None
        result_ref: Ref | None = None
        result: ToolResult | None = None
        try:
            if parsed is None:
                # 参数校验失败：返回 invalid_arguments，不调用工具实现。
                result = ToolResult(
                    status="invalid_arguments", data={}, source_refs=[], owner_receipt_ref=None
                )
            else:
                # 工具时限与执行剩余时限取小，避免占用恢复预留时间。
                remaining = await self.calls.remaining(handle)
                async with asyncio.timeout(min(tool.timeout_seconds, remaining)):
                    result = await tool.invoke(handle, parsed, saved.work_key)
            result_ref = await self.calls.attachments.save_json(
                result.model_dump(mode="json"),
                actor=source,
                source=source,
                artifact_key=f"ai-tool-result:{action_key}",
                max_bytes=handle.budget.max_result_bytes,
            )
        except (Exception, asyncio.CancelledError):
            # 工具异常与取消统一归为 tool_failed，由留痕闭环记录失败结果。
            error = "tool_failed"
        async with self.calls.engine.begin() as connection:
            execution = await executions.lock_owned(
                connection, self.calls.registry, handle.input.run.execution_id
            )
            finished = saved.model_copy(
                update={
                    "result_ref": result_ref,
                    # owner_receipt_ref 由工具结果回传，供业务侧收据对账。
                    "owner_receipt_ref": result.owner_receipt_ref if result else None,
                    "outcome": "failed" if error else "completed",
                    "finished_at": await store.now(connection),
                }
            )
            await store.record(
                connection,
                execution,
                "ToolActionChanged",
                "failed" if error else "completed",
                [("ai.tool_actions", finished)],
                reason=error,
            )
        if error or result is None:
            raise AIRejected("tool_failed")
        return result
