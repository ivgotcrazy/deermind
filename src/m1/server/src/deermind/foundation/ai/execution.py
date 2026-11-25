"""AI 调用生命周期和预算账本；短事务串行记账，外部 I/O 由适配层执行。

分层定位：foundation（AI 底座）
对外契约：Calls 实现 CallService，承接调用准备、身份守卫、预算记账、请求预约/结算与候选落盘。
边界约束：本层不含教材、学生、评价业务判断；模型与文件外部 I/O 在事务外由适配层完成。
"""

from uuid import UUID, uuid4

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.ai.contracts import (
    CallHandle,
    CallInput,
    ExecutionConfig,
    PromptCallInput,
    PurposeBinding,
)
from deermind.abstractions.ai.requests import ModelRequestFact
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.hashing import digest
from deermind.foundation.ai import store
from deermind.foundation.ai.prompts import PromptLibrary
from deermind.foundation.ai.records import CallAttemptFact, CallFact, CandidateFact
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.executions import store as executions
from deermind.foundation.system.executions.contracts import Registry
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class Calls:
    """由装配层提供当前授权和文件能力；不含教材、学生或评价业务判断。"""

    def __init__(
        self,
        engine: AsyncEngine,
        registry: Registry,
        attachments: FactAttachments,
        prompts: PromptLibrary | None = None,
    ) -> None:
        self.engine = engine
        self.registry = registry
        self.attachments = attachments
        self.prompts = prompts

    async def _configuration(
        self, run: RunInput, purpose: str
    ) -> tuple[Execution, ExecutionConfig, PurposeBinding]:
        # 独立短事务读取当前尝试与已固定的配置快照；守卫时再用调用方事务复核。
        async with self.engine.begin() as connection:
            execution = await executions.active(connection, self.registry, run, "step")
            config = await store.configuration(connection, execution.execution_id)
        binding = config.purpose_bindings.get(purpose)
        # 该用途在当前工作配置中未接线，拒绝本次调用。
        if binding is None:
            raise AIRejected("configuration_unavailable")
        return execution, config, binding

    def _instructions(self, binding: PurposeBinding, parts: list[str]) -> str:
        # 未装配提示词库时无法渲染指令，按配置不可用拒绝。
        if self.prompts is None:
            raise AIRejected("configuration_unavailable")
        return self.prompts.read(binding.prompt_ref, parts)

    async def prompt_instructions(self, run: RunInput, purpose: str, parts: list[str]) -> str:
        """准备 Activity 也可按固定用途渲染它所选的指令片段。"""
        _, _, binding = await self._configuration(run, purpose)
        return self._instructions(binding, parts)

    async def prepare(self, incoming: CallInput | PromptCallInput) -> CallHandle:
        """固定实际送模输入；复用候选仍检查当前工作权限。"""
        execution, config, binding = await self._configuration(incoming.run, incoming.purpose)
        # 本次受理授权的工具必须在用途接线白名单内，否则拒绝。
        if any(ref not in binding.tool_refs for ref in incoming.tool_grants):
            raise AIRejected("forbidden")
        # 提示词输入先按登记绑定渲染指令，归一为统一的 CallInput。
        if isinstance(incoming, PromptCallInput):
            incoming = CallInput(
                run=incoming.run,
                step_key=incoming.step_key,
                call_key=incoming.call_key,
                purpose=incoming.purpose,
                prompt=incoming.prompt,
                material_refs=incoming.material_refs,
                tool_grants=incoming.tool_grants,
                instructions=self._instructions(binding, incoming.prompt_parts),
            )
        # 尝试号和新恢复时限不属于固定输入；其他字段变化必须使用新的调用键。
        body = incoming.model_dump(mode="json", exclude={"run"})
        # 固定输入摘要 = 输入正文 + 用途绑定；守卫时按同一口径复算比对，识别输入被改动。
        input_hash = digest({"input": body, "binding": binding.model_dump(mode="json")})
        # 输入正文先固定为附件，取材键含执行与摘要以便同内容复用，体积受输入预算约束。
        source = Ref(owner="ai", type="execution", id=str(execution.execution_id))
        reference = await self.attachments.save_json(
            body,
            actor=source,
            source=source,
            artifact_key=f"ai-input:{execution.execution_id}:{input_hash}",
            max_bytes=config.budget.max_input_bytes,
        )
        async with self.engine.begin() as connection:
            execution = await executions.active(connection, self.registry, incoming.run, "step")
            # 按 执行+步骤+调用键 定位既有调用；查无 identity 表示调用键首次出现。
            identity = await connection.scalar(
                text(
                    "SELECT call_id FROM ai.ai_calls WHERE execution_id=:execution "
                    "AND step_key=:step AND call_key=:key"
                ),
                {
                    "execution": execution.execution_id,
                    "step": incoming.step_key,
                    "key": incoming.call_key,
                },
            )
            call = (
                await store.load(connection, "ai.ai_calls", CallFact, {"call_id": identity})
                if identity
                else None
            )
            timestamp = await store.now(connection)
            # 同一调用键下输入或绑定已变，判输入冲突，不允许覆盖旧记录。
            if call is not None and call.input_hash != input_hash:
                raise AIRejected("input_conflict")
            # 调用键首次出现：新建待受理调用，初始 pending、尚无候选，输入正文挂附件引用。
            if call is None:
                call = CallFact(
                    call_id=uuid4(),
                    execution_id=execution.execution_id,
                    step_key=incoming.step_key,
                    call_key=incoming.call_key,
                    input_hash=input_hash,
                    purpose=incoming.purpose,
                    schema_ref=binding.schema_ref,
                    input_ref=reference,
                    state="pending",
                    candidate_ref=None,
                    created_at=timestamp,
                )
            # 查本执行尝试在该调用下的最近一次 AI 尝试记录，判断是否已有可复用尝试。
            previous = (
                await connection.execute(
                    text(
                        "SELECT attempt_id FROM ai.ai_call_attempts WHERE call_id=:call "
                        "AND execution_attempt_id=:attempt ORDER BY attempt_no DESC LIMIT 1"
                    ),
                    {"call": call.call_id, "attempt": incoming.run.attempt_id},
                )
            ).scalar_one_or_none()
            # 本次尝试尚无记录且调用未产出候选：先封存上次遗留的未完成尝试，避免悬空 running。
            if previous is None and call.candidate_ref is None:
                await self.abandon_pending(connection, execution, call.call_id)
                # 捞出该调用下所有仍挂 running 的旧尝试，这些是上次中断遗留、结果未确认的记录。
                interrupted = (
                    (
                        await connection.execute(
                            text(
                                "SELECT attempt_id FROM ai.ai_call_attempts "
                                "WHERE call_id=:call AND outcome='running'"
                            ),
                            {"call": call.call_id},
                        )
                    )
                    .scalars()
                    .all()
                )
                # 逐条把上次未完成的尝试记为 unknown，并把调用置 failed，不再假定其外部结果。
                for identity in interrupted:
                    old = await store.load(
                        connection,
                        "ai.ai_call_attempts",
                        CallAttemptFact,
                        {"call_id": call.call_id, "attempt_id": identity},
                    )
                    assert old is not None
                    await store.record(
                        connection,
                        execution,
                        "AICallChanged",
                        "unknown",
                        [
                            ("ai.ai_calls", call.model_copy(update={"state": "failed"})),
                            (
                                "ai.ai_call_attempts",
                                old.model_copy(
                                    update={
                                        "outcome": "unknown",
                                        "finished_at": timestamp,
                                        "error": {
                                            "code": "execution_interrupted",
                                            "message": "上次执行未完成",
                                            "retryable": False,
                                        },
                                    }
                                ),
                            ),
                        ],
                        reason="execution_interrupted",
                    )
                # 新尝试序号取当前最大序号加一，保证同一调用内单调递增。
                number = await connection.scalar(
                    text(
                        "SELECT COALESCE(max(attempt_no),0)+1 FROM ai.ai_call_attempts "
                        "WHERE call_id=:call"
                    ),
                    {"call": call.call_id},
                )
                # 新建 AI 尝试：初始 running、未产出有效候选；单次 HTTP 重试不另开尝试。
                attempt = CallAttemptFact(
                    call_id=call.call_id,
                    attempt_id=uuid4(),
                    execution_attempt_id=incoming.run.attempt_id,
                    attempt_no=number,
                    started_at=timestamp,
                    finished_at=None,
                    outcome="running",
                    error=None,
                    valid_candidate=False,
                )
                # 调用状态翻 running，连同新尝试留痕为 started；本次 handle 指向新尝试。
                call = call.model_copy(update={"state": "running"})
                await store.record(
                    connection,
                    execution,
                    "AICallChanged",
                    "started",
                    [
                        ("ai.ai_calls", call),
                        ("ai.ai_call_attempts", attempt),
                    ],
                )
                previous = attempt.attempt_id
            # 本尝试无新记录时，回退指向已保存的有效候选，供幂等读回。
            if previous is None:
                previous = await connection.scalar(
                    text(
                        "SELECT attempt_id FROM ai.ai_call_attempts WHERE call_id=:call "
                        "AND valid_candidate ORDER BY attempt_no DESC LIMIT 1"
                    ),
                    {"call": call.call_id},
                )
            # 组装句柄：attempt_id 可能为空（纯读或已完成调用）；带回既有候选供幂等读回。
            return CallHandle(
                input=incoming,
                call_id=call.call_id,
                attempt_id=previous,
                binding=binding,
                budget=config.budget,
                candidate_ref=call.candidate_ref,
            )

    async def guard(self, connection: AsyncConnection, handle: CallHandle) -> CallFact:
        """任何新模型/工具I/O均核对当前执行及固定调用身份。"""
        await executions.active(connection, self.registry, handle.input.run, "step")
        config = await store.configuration(connection, handle.input.run.execution_id)
        # 当前配置的用途绑定或预算与受理时不一致，判配置漂移，拒绝后续 I/O。
        if (
            config.purpose_bindings.get(handle.input.purpose) != handle.binding
            or config.budget != handle.budget
        ):
            raise AIRejected("input_conflict")
        call = await store.load(connection, "ai.ai_calls", CallFact, {"call_id": handle.call_id})
        attempt = await store.load(
            connection,
            "ai.ai_call_attempts",
            CallAttemptFact,
            {"call_id": handle.call_id, "attempt_id": handle.attempt_id},
        )
        # 调用或尝试记录缺失，或归属到另一执行/用途/步骤/调用键/尝试，均拒绝。
        if (
            call is None
            or attempt is None
            or call.execution_id != handle.input.run.execution_id
            or call.purpose != handle.input.purpose
            or call.step_key != handle.input.step_key
            or call.call_key != handle.input.call_key
            or attempt.execution_attempt_id != handle.input.run.attempt_id
        ):
            raise AIRejected("forbidden")
        # 按与受理时相同的口径复算摘要：排除 run，输入正文加用途绑定。
        expected = digest(
            {
                "input": handle.input.model_dump(mode="json", exclude={"run"}),
                "binding": handle.binding.model_dump(mode="json"),
            }
        )
        # 重算输入与绑定摘要，与落库摘要不符说明输入被改动，判冲突。
        if call.input_hash != expected:
            raise AIRejected("input_conflict")
        return call

    async def remaining(self, handle: CallHandle) -> float:
        async with self.engine.begin() as connection:
            call = await self.guard(connection, handle)
            # 调用不在运行态，不能再继续占用时限。
            if call.state != "running":
                raise AIRejected("call_not_running")
            # 剩余时限以执行受理期限为基准，减去当前已消耗时间。
            seconds = (handle.input.run.deadline_at - await store.now(connection)).total_seconds()
        # 扣除收尾预留后剩余时限不足，判预算耗尽。
        remaining = seconds - handle.budget.finalize_reserve_seconds
        if remaining <= 0:
            raise AIRejected("budget_exhausted")
        return remaining

    async def reserve(
        self,
        handle: CallHandle,
        ordinal: int,
        transport: int,
        request_ref: Ref,
        input_tokens: int,
        *,
        repair: bool,
    ) -> ModelRequestFact:
        """先登记每次真实外发；失败、重试、修正共用原Execution账本。"""
        budget = handle.budget
        # 输入令牌数必须为非负且不超过单次输入上限。
        if input_tokens < 0 or input_tokens > budget.max_input_tokens:
            raise AIRejected("required_context_too_large")
        async with self.engine.begin() as connection:
            call = await self.guard(connection, handle)
            execution = await executions.load(connection, handle.input.run.execution_id)
            # 请求幂等键四元组：调用 + AI尝试 + 请求序号 + 传输次，定位同一次真实外发。
            key: dict[str, object] = {
                "call_id": handle.call_id,
                "attempt_id": handle.attempt_id,
                "request_ordinal": ordinal,
                "transport_attempt": transport,
            }
            saved = await store.load(connection, "ai.model_requests", ModelRequestFact, key)
            # 同键请求已存在：幂等返回，先核对请求引用与结果状态。
            if saved is not None:
                if saved.request_ref != request_ref:
                    raise AIRejected("input_conflict")
                # 上次请求结果尚未确认，不能假定其成败。
                if saved.outcome == "pending":
                    raise AIRejected("request_outcome_unknown")
                return saved
            # 调用已结束，不能再外发新请求。
            if call.state != "running":
                raise AIRejected("call_not_running")
            # 新一次传输前，先封存上次结果未确认的请求，避免悬空预约占用账本。
            await self.abandon_pending(connection, execution, call.call_id)
            # FOR UPDATE 串行锁住账本行，防止并发预约同一执行导致超发超支。
            usage = (
                (
                    await connection.execute(
                        text("SELECT * FROM ai.execution_usage WHERE execution_id=:id FOR UPDATE"),
                        {"id": execution.execution_id},
                    )
                )
                .mappings()
                .one()
            )
            # 已占用令牌 = 已结算已知用量 + 已预约未结算的预留用量，两类合计。
            consumed = sum(
                usage[name]
                for name in (
                    "known_input_tokens",
                    "known_output_tokens",
                    "reserved_input_tokens",
                    "reserved_output_tokens",
                )
            )
            # 三类预算任一超限即拒绝外发：请求次数、总令牌数、修正次数（仅修正请求计入）。
            if (
                usage["request_count"] >= budget.max_model_requests
                or consumed + input_tokens + budget.max_output_tokens > budget.max_total_tokens
                or (repair and usage["repair_count"] >= budget.max_repairs)
            ):
                raise AIRejected("budget_exhausted")
            # 预约阶段只记预留令牌、用量未知、结果 pending；实际令牌待结算回填，不填零用量。
            request = ModelRequestFact(
                call_id=handle.call_id,
                attempt_id=handle.attempt_id,
                request_ordinal=ordinal,
                transport_attempt=transport,
                model=handle.binding.profile.model,
                request_ref=request_ref,
                reserved_input_tokens=input_tokens,
                reserved_output_tokens=budget.max_output_tokens,
                actual_input_tokens=None,
                actual_output_tokens=None,
                usage_state="reserved",
                provider_request_id=None,
                outcome="pending",
                started_at=await store.now(connection),
                finished_at=None,
                response_ref=None,
            )
            await store.record(
                connection,
                execution,
                "ModelRequestChanged",
                "started",
                [("ai.model_requests", request)],
            )
            # 账本扣减：请求次数 +1；修正请求才计修正次数；本次预留输入/输出令牌累加进预留额度。
            await connection.execute(
                text(
                    "UPDATE ai.execution_usage SET request_count=request_count+1,"
                    "repair_count=repair_count+:repair,"
                    "reserved_input_tokens=reserved_input_tokens+:input,"
                    "reserved_output_tokens=reserved_output_tokens+:output,"
                    "updated_at=clock_timestamp() WHERE execution_id=:id"
                ),
                {
                    "repair": int(repair),
                    "input": input_tokens,
                    "output": budget.max_output_tokens,
                    "id": execution.execution_id,
                },
            )
            return request

    async def abandon_pending(
        self, connection: AsyncConnection, execution: Execution, call_id: UUID
    ) -> None:
        """下一次传输前封存未确认请求；保留预约，不假定上次外部请求没有发生。"""
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT attempt_id,request_ordinal,transport_attempt "
                        "FROM ai.model_requests "
                        "WHERE call_id=:call AND outcome='pending'"
                    ),
                    {"call": call_id},
                )
            )
            .mappings()
            .all()
        )
        # 逐条把未确认请求封存为 unknown，不计作成功也不计作失败。
        for row in rows:
            pending = await store.load(
                connection, "ai.model_requests", ModelRequestFact, {"call_id": call_id, **dict(row)}
            )
            assert pending is not None
            await store.record(
                connection,
                execution,
                "ModelRequestChanged",
                "unknown",
                [
                    (
                        "ai.model_requests",
                        pending.model_copy(
                            update={
                                "outcome": "unknown",
                                "usage_state": "unknown",
                                "finished_at": await store.now(connection),
                            }
                        ),
                    ),
                ],
                reason="request_outcome_unknown",
            )
        # 存在被封存的请求时，累加未知请求计数，供后续预算口径核对。
        if rows:
            await connection.execute(
                text(
                    "UPDATE ai.execution_usage SET "
                    "unknown_request_count=unknown_request_count+:count,"
                    "updated_at=clock_timestamp() WHERE execution_id=:id"
                ),
                {"count": len(rows), "id": execution.execution_id},
            )

    async def settle(
        self,
        handle: CallHandle,
        request: ModelRequestFact,
        *,
        response_ref: Ref | None,
        actual_usage: tuple[int, int] | None,
        provider_id: str | None,
        error_code: str | None,
    ) -> None:
        """即使工作已停止也保留已发生的外部调用；迟到结果不会获得业务提交资格。"""
        async with self.engine.begin() as connection:
            # 持工作锁串行结算，避免并发回执重复记账。
            execution = await executions.lock_owned(
                connection, self.registry, handle.input.run.execution_id
            )
            # 按请求幂等四元组定位被结算的预约记录。
            key = {
                name: getattr(request, name)
                for name in ("call_id", "attempt_id", "request_ordinal", "transport_attempt")
            }
            saved = await store.load(connection, "ai.model_requests", ModelRequestFact, key)
            # 请求记录不存在，无法结算。
            if saved is None:
                raise AIRejected("request_unavailable")
            # 回执归属到另一调用或尝试，拒绝结算。
            if request.call_id != handle.call_id or request.attempt_id != handle.attempt_id:
                raise AIRejected("forbidden")
            # 已结算过的请求幂等返回，不重复记账。
            if saved.outcome != "pending":
                return
            # 结算口径：有错误码记 failed，否则 success；带回完整用量记 known，否则 unknown。
            updated = ModelRequestFact.model_validate(
                {
                    **saved.model_dump(),
                    "outcome": "failed" if error_code else "success",
                    "usage_state": "known" if actual_usage is not None else "unknown",
                    "actual_input_tokens": actual_usage[0] if actual_usage else None,
                    "actual_output_tokens": actual_usage[1] if actual_usage else None,
                    "provider_request_id": provider_id,
                    "response_ref": response_ref,
                    "finished_at": await store.now(connection),
                }
            )
            await store.record(
                connection,
                execution,
                "ModelRequestChanged",
                "failed" if error_code else "completed",
                [("ai.model_requests", updated)],
                reason=error_code,
            )
            # 账本冲账：已知用量累加，对应预留额度释放；无用量回填则记一笔未知请求。
            await connection.execute(
                text(
                    "UPDATE ai.execution_usage SET known_input_tokens=known_input_tokens+:input,"
                    "known_output_tokens=known_output_tokens+:output,"
                    "reserved_input_tokens=reserved_input_tokens-:release_input,"
                    "reserved_output_tokens=reserved_output_tokens-:release_output,"
                    "unknown_request_count=unknown_request_count+:unknown,"
                    "updated_at=clock_timestamp() WHERE execution_id=:id"
                ),
                {
                    "id": execution.execution_id,
                    "input": actual_usage[0] if actual_usage else 0,
                    "output": actual_usage[1] if actual_usage else 0,
                    "release_input": saved.reserved_input_tokens if actual_usage else 0,
                    "release_output": saved.reserved_output_tokens if actual_usage else 0,
                    "unknown": int(actual_usage is None),
                },
            )

    async def candidate(self, handle: CallHandle, content: dict[str, JsonValue]) -> UUID:
        """调用者已按登记Schema验证；先固定完整内容，再原子保存候选及调用完成事实。"""
        # 候选正文先固定为附件，取材键含调用与摘要以便同内容复用，体积受结果预算约束。
        source = Ref(owner="ai", type="execution", id=str(handle.input.run.execution_id))
        reference = await self.attachments.save_json(
            content,
            actor=source,
            source=source,
            artifact_key=f"ai-candidate:{handle.call_id}:{digest(content)}",
            max_bytes=handle.budget.max_result_bytes,
        )
        # 候选工件记录附件引用与内容摘要，供回读时做完整性校验。
        artifact: dict[str, JsonValue] = {
            "storage": "file",
            "file_id": reference.id,
            "sha256": digest(content),
            "media_type": "application/json",
        }
        async with self.engine.begin() as connection:
            call = await self.guard(connection, handle)
            # 调用已有候选：核对内容摘要一致后幂等返回，不允许同一调用产出不同候选。
            if call.candidate_ref is not None:
                existing = await store.load(
                    connection,
                    "ai.ai_candidates",
                    CandidateFact,
                    {"candidate_id": call.candidate_ref},
                )
                if existing is None or existing.content_hash != digest(content):
                    raise AIRejected("input_conflict")
                return call.candidate_ref
            # 调用已结束，不能再保存新候选。
            if call.state != "running":
                raise AIRejected("call_not_running")
            execution = await executions.load(connection, call.execution_id)
            timestamp = await store.now(connection)
            # 构造候选事实：Schema、附件工件、内容摘要、取材引用与本尝试工具引用清单。
            candidate = CandidateFact(
                candidate_id=uuid4(),
                call_id=call.call_id,
                schema_ref=call.schema_ref,
                content=artifact,
                content_hash=digest(content),
                material_refs=handle.input.material_refs,
                # 收集本尝试上已完成的工具动作，作为候选可追溯的工具引用清单。
                tool_refs=[
                    Ref(owner="ai", type="tool_action", id=row)
                    for row in (
                        await connection.execute(
                            text(
                                "SELECT tool_action_key FROM ai.tool_actions WHERE call_id=:call "
                                "AND attempt_id=:attempt AND outcome='completed' "
                                "ORDER BY tool_action_key"
                            ),
                            {"call": call.call_id, "attempt": handle.attempt_id},
                        )
                    ).scalars()
                ],
                created_at=timestamp,
            )
            # 载入本 AI 尝试记录，作为候选归属与完成状态更新的依据。
            attempt = await store.load(
                connection,
                "ai.ai_call_attempts",
                CallAttemptFact,
                {"call_id": handle.call_id, "attempt_id": handle.attempt_id},
            )
            assert attempt is not None
            # 先留痕候选已记录。
            await store.record(
                connection,
                execution,
                "AICandidatePrepared",
                "recorded",
                [("ai.ai_candidates", candidate)],
            )
            # 调用置 completed 并挂候选，本尝试置 completed 且标记为有效候选。
            await store.record(
                connection,
                execution,
                "AICallChanged",
                "completed",
                [
                    (
                        "ai.ai_calls",
                        call.model_copy(
                            update={"state": "completed", "candidate_ref": candidate.candidate_id}
                        ),
                    ),
                    (
                        "ai.ai_call_attempts",
                        attempt.model_copy(
                            update={
                                "outcome": "completed",
                                "finished_at": timestamp,
                                "valid_candidate": True,
                            }
                        ),
                    ),
                ],
            )
            return candidate.candidate_id

    async def candidate_content(self, run: RunInput, candidate_id: UUID) -> dict[str, JsonValue]:
        """按受理工作的执行归属读取候选，不允许跨工作取模型结果。"""
        async with self.engine.begin() as connection:
            work = await executions.active(connection, self.registry, run, "step")
            candidate = await store.load(
                connection, "ai.ai_candidates", CandidateFact, {"candidate_id": candidate_id}
            )
            # 候选不存在，拒绝读取。
            if candidate is None:
                raise AIRejected("unknown_candidate")
            call = await store.load(
                connection, "ai.ai_calls", CallFact, {"call_id": candidate.call_id}
            )
            # 候选归属到另一执行，不允许跨工作取模型结果。
            if call is None or call.execution_id != work.execution_id:
                raise AIRejected("forbidden")
            config = await store.configuration(connection, work.execution_id)
        source = Ref(owner="ai", type="execution", id=str(work.execution_id))
        file = Ref(owner="runtime", type="file", id=str(candidate.content["file_id"]))
        # 按候选登记的附件引用回读，体积受结果预算约束。
        content = await self.attachments.read_json(
            file, source=source, max_bytes=config.budget.max_result_bytes
        )
        # 回读内容摘要与落库摘要不符，说明附件被篡改或损坏，拒绝交付。
        if digest(content) != candidate.content_hash:
            raise AIRejected("candidate_integrity")
        return content

    async def fail(self, handle: CallHandle, error_code: str) -> None:
        async with self.engine.begin() as connection:
            execution = await executions.lock_owned(
                connection, self.registry, handle.input.run.execution_id
            )
            # 载入调用与本尝试记录，作为失败状态更新的依据。
            call = await store.load(
                connection, "ai.ai_calls", CallFact, {"call_id": handle.call_id}
            )
            attempt = await store.load(
                connection,
                "ai.ai_call_attempts",
                CallAttemptFact,
                {"call_id": handle.call_id, "attempt_id": handle.attempt_id},
            )
            # 记录缺失、已有候选或尝试已结束，不再覆盖其状态。
            if (
                call is None
                or attempt is None
                or call.candidate_ref is not None
                or attempt.outcome != "running"
            ):
                return
            # 旧尝试仅结束自己的记录；不能把已恢复工作的新调用状态标为失败。
            if execution.active_attempt_id != handle.input.run.attempt_id:
                return
            # 失败前先封存结果未确认的请求，不留悬空预约。
            await self.abandon_pending(connection, execution, call.call_id)
            # 调用与尝试置 failed 并留痕；错误标记不可自动重试。
            await store.record(
                connection,
                execution,
                "AICallChanged",
                "failed",
                [
                    ("ai.ai_calls", call.model_copy(update={"state": "failed"})),
                    (
                        "ai.ai_call_attempts",
                        attempt.model_copy(
                            update={
                                "outcome": "failed",
                                "finished_at": await store.now(connection),
                                "error": {
                                    "code": error_code,
                                    "message": "AI调用未完成",
                                    "retryable": False,
                                },
                            }
                        ),
                    ),
                ],
                reason=error_code,
            )

    async def save_material(
        self,
        content: dict[str, JsonValue],
        *,
        actor: Ref,
        source: Ref,
        artifact_key: str,
        max_bytes: int,
    ) -> Ref:
        """适配器提交请求或响应材料，不暴露附件实现。"""
        return await self.attachments.save_json(
            content, actor=actor, source=source, artifact_key=artifact_key, max_bytes=max_bytes
        )

    async def read_material(
        self, reference: Ref, *, source: Ref, max_bytes: int
    ) -> dict[str, JsonValue]:
        return await self.attachments.read_json(reference, source=source, max_bytes=max_bytes)
