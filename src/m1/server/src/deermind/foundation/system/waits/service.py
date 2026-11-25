"""登记、补查和接续；所有者持业务锁，底座只落定一次等待决定。

分层定位：foundation（公共运行底座 / 等待服务）
对外契约：Waits 提供等待登记、条件探测、命中接续与取消；mark_waiting 把执行置为等待状态。
边界约束：probe 只锁等待不取业务写锁；handle 的副作用与接续收据同事务提交；取消先落定则不能再执行。
"""

from datetime import datetime
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput
from deermind.abstractions.waits import Condition, Handling, Wait
from deermind.foundation.system.executions import steps, store
from deermind.foundation.system.executions.contracts import Caller, Registry
from deermind.foundation.system.waits import facts
from deermind.foundation.system.waits.contracts import Policies
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class Waits:
    """等待底座服务：持有注册表与等待策略，承接登记、探测、接续与取消。"""

    def __init__(self, entries: Registry, policies: Policies, *, maximum_seconds: int) -> None:
        # 等待总时长上限必须为正，拒绝零或负上限。
        if maximum_seconds <= 0:
            raise ValueError("Finite wait limit required")
        self.entries, self.policies, self.maximum_seconds = entries, policies, maximum_seconds

    async def register(
        self,
        connection: AsyncConnection,
        run: RunInput,
        *,
        step_key: str,
        owner: Ref,
        condition: Condition,
        probe_ref: Ref,
        deadline: datetime,
        reserve_seconds: int,
    ) -> Wait:
        """重复登记沿原截止时间；业务恢复位置与等待必须由调用方同事务提交。"""
        execution = await store.active(connection, self.entries, run, "step")
        # 登记条件与接续预算逐项校验，任一不合法即拒绝：
        if (
            not step_key.strip()  # 步骤键非空，用于同步骤重复登记去重
            or reserve_seconds <= 0  # 命中后留给接续动作的预算为正
            or condition.result_key
            and condition.result_key.scope_id != condition.scope_id  # 结果键归属同一范围
            or not set(condition.equals) <= {"event_id", "producer", "correlation_id"}  # 相等条件只允许固定字段
        ):
            raise ValueError("Invalid wait condition or continuation budget")
        digest = steps.input_hash(condition.model_dump(mode="json"))
        existing = await connection.scalar(
            text(
                "SELECT wait_id FROM runtime.waits WHERE execution_id=:execution "
                "AND step_key=:step "
                "AND condition_hash=:digest"
            ),
            {"execution": run.execution_id, "step": step_key, "digest": digest},
        )
        # 命中同步骤、同条件摘要的既有等待：恢复沿原等待，不新建第二条。
        if existing:
            saved = await facts.read_wait(connection, str(existing), lock=True)
            self.policies.resolve(saved, execution)
            # 探测程序或归属与原等待不一致，说明被另一处复用，判登记冲突。
            if saved.probe_ref != probe_ref or saved.owner_ref != owner:
                raise ValueError("Wait registration conflict")
            # 仍在等待中：核对恢复后到执行期限是否还留得出接续预算。
            if saved.resolution == "pending":
                now = await connection.scalar(text("SELECT clock_timestamp()"))
                if (
                    run.deadline_at - max(now, saved.deadline_at)
                ).total_seconds() < reserve_seconds:
                    raise ValueError("Recovery leaves no continuation budget")
                await mark_waiting(connection, run)
            return saved
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        # 截止时间必须带时区；等待时长落在允许区间内；且截止后到执行期限仍留得出接续预算。
        if (
            deadline.tzinfo is None
            or not 0 < (deadline - now).total_seconds() <= self.maximum_seconds
            or (run.deadline_at - deadline).total_seconds() < reserve_seconds
        ):
            raise ValueError("Wait exceeds its limit or leaves no continuation budget")
        # 按探测程序引用查找登记的等待策略；查无则拒绝，不接受未注册的探测方。
        policy = next((p for p in self.policies.items if p.ref == probe_ref), None)
        if policy is None:
            raise PermissionError("Unknown wait policy")
        saved = Wait(
            wait_id=uuid4(),
            owner_ref=owner,
            execution_id=run.execution_id,
            step_key=step_key,
            condition=condition,
            condition_hash=digest,
            probe_ref=probe_ref,
            deadline_at=deadline,
            resume_action_id=uuid4(),
            on_match=policy.on_match,
            on_timeout=policy.on_timeout,
            resolution="pending",
            matched_event_ref=None,
            result_ref=None,
            created_at=now,
            resolved_at=None,
        )
        self.policies.resolve(saved, execution)
        await connection.execute(
            text(
                "INSERT INTO runtime.waits SELECT * FROM jsonb_populate_record("
                "NULL::runtime.waits,CAST(:body AS jsonb))"
            ),
            {"body": saved.model_dump_json()},
        )
        await connection.execute(
            text(
                "INSERT INTO runtime.wait_handling(wait_id,resume_action_id,state,updated_at) "
                "VALUES (:id,:action,'awaiting',clock_timestamp())"
            ),
            {"id": saved.wait_id, "action": saved.resume_action_id},
        )
        await mark_waiting(connection, run)
        granted = await store.authorization(connection, run.execution_id)
        await facts.record(
            connection,
            saved,
            await facts.read_handling(connection, saved),
            "registered",
            granted.initiator_ref,
        )
        return saved

    async def probe(self, connection: AsyncConnection, run: RunInput, identity: UUID) -> Wait:
        """只锁Wait，不取得业务写锁；数据库读取失败不能伪装成未取得结果。"""
        execution = await store.load(connection, run.execution_id)
        current = await store.attempt(connection, run.attempt_id)
        # 任一条件不满足即视为旧尝试/已停止，拒绝本次探测：
        if (
            execution.active_attempt_id != run.attempt_id  # 提交者不是当前有效尝试
            or current.execution_id != run.execution_id  # 尝试不属于本执行
            or execution.state not in {"ready", "running", "waiting"}  # 工作已不在可活动状态
            or execution.implementation_ref != run.implementation_ref  # 实现引用漂移
            or execution.ai_config_ref != run.ai_config_ref  # 配置引用漂移
            or execution.input_ref != run.input_ref  # 输入引用漂移
            or current.deadline_at != run.deadline_at  # 尝试期限与受理记录不一致
        ):
            raise ValueError("Wait attempt is no longer active")
        await store.check(connection, self.entries, execution, "read")
        saved = await facts.read_wait(connection, str(identity), lock=True)
        policy = self.policies.resolve(saved, execution)
        handling = await facts.read_handling(connection, saved)
        # 等待已有终态或已被取消：直接返回原决定，不再探测。
        if saved.resolution != "pending" or handling.state == "cancelled":
            return saved
        probe_started = await connection.scalar(text("SELECT clock_timestamp()"))
        found = await policy.probe(connection, execution, saved.condition)
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        # 未命中且尚未到期：保持等待，本次探测返回空结果。
        if found is None and now < saved.deadline_at:
            return saved
        # 普通补查恰好跨过截止点时，还需做一次到期后的查询，不能沿用之前的空结果。
        if found is None and probe_started < saved.deadline_at <= now:
            found = await policy.probe(connection, execution, saved.condition)
            now = await connection.scalar(text("SELECT clock_timestamp()"))
        # 探测命中事件：回查事件记录，逐项核验是否确属等待条件。
        if found is not None:
            event = (
                (
                    await connection.execute(
                        text(
                            "SELECT event_type,scope_kind,scope_id,event_id,"
                            "producer,correlation_id "
                            "FROM runtime.events WHERE event_id=:id"
                        ),
                        {"id": found.event_id},
                    )
                )
                .mappings()
                .one()
            )
            # 类型、范围、生产者/关联键任一不符，即视为无关事件，拒绝据此接续。
            if (
                event["event_type"] not in saved.condition.event_types
                or event["scope_kind"] != saved.condition.scope_kind
                or event["scope_id"] != saved.condition.scope_id
                or any(str(event[k]) != value for k, value in saved.condition.equals.items())
            ):
                raise ValueError("Probe returned an unrelated event")
        outcome = "matched" if found is not None else "timed_out"
        await connection.execute(
            text(
                "UPDATE runtime.waits SET resolution=:resolution,matched_event_ref=:event,"
                "result_ref=CAST(:result AS jsonb),resolved_at=:now WHERE wait_id=:id"
            ),
            {
                "id": saved.wait_id,
                "resolution": outcome,
                "event": found.event_id if found else None,
                "result": found.result_ref.model_dump_json()
                if found and found.result_ref
                else None,
                "now": now,
            },
        )
        saved = await facts.read_wait(connection, str(identity))
        granted = await store.authorization(connection, run.execution_id)
        await facts.record(connection, saved, handling, outcome, granted.initiator_ref)
        return saved

    async def handle(self, connection: AsyncConnection, run: RunInput, identity: UUID) -> Handling:
        """业务锁→工作→Wait；副作用和接续收据共同提交，取消先落定便不能再执行。"""
        execution = await store.active(connection, self.entries, run, "step")
        saved = await facts.read_wait(connection, str(identity), lock=True)
        policy = self.policies.resolve(saved, execution)
        handling = await facts.read_handling(connection, saved)
        # 接续已定案（已提交或已取消）：幂等返回原处理记录。
        if handling.state in {"committed", "cancelled"}:
            return handling
        # 等待尚未得出结论，不能进入业务接续。
        if saved.resolution == "pending":
            raise ValueError("Cannot handle an unresolved wait")
        granted = await store.authorization(connection, run.execution_id)
        try:
            # 嵌套事务内执行业务接续，接续收据随外层事务一并提交或回滚。
            async with connection.begin_nested():
                receipt = await policy.handle(connection, execution, saved)
                await connection.execute(
                    text(
                        "UPDATE runtime.wait_handling SET state='committed',failure_ref=NULL,"
                        "handling_receipt_ref=CAST(:receipt AS jsonb),updated_at=clock_timestamp() "
                        "WHERE wait_id=:id"
                    ),
                    {"id": identity, "receipt": receipt.model_dump_json()},
                )
        # 业务或权限错误：接续记为 failed 并落失败引用，不中断当前事务后续留痕。
        except (ValueError, PermissionError) as error:
            failure = Ref(
                owner="runtime", type="wait_failure", id=str(identity), path=type(error).__name__
            )
            await connection.execute(
                text(
                    "UPDATE runtime.wait_handling SET state='failed',"
                    "failure_ref=CAST(:failure AS jsonb),"
                    "updated_at=clock_timestamp() WHERE wait_id=:id"
                ),
                {"id": identity, "failure": failure.model_dump_json()},
            )
        handling = await facts.read_handling(connection, saved)
        await facts.record(connection, saved, handling, "handled", granted.initiator_ref)
        # 接续成功：已无其他待决等待时，把执行与尝试从等待态恢复为运行态。
        if handling.state == "committed":
            await connection.execute(
                text(
                    "UPDATE runtime.executions SET state='running',updated_at=clock_timestamp() "
                    "WHERE execution_id=:id AND NOT EXISTS (SELECT 1 FROM runtime.waits "
                    "WHERE execution_id=:id AND resolution='pending')"
                ),
                {"id": run.execution_id},
            )
            await connection.execute(
                text(
                    "UPDATE runtime.execution_attempts SET state=(SELECT state "
                    "FROM runtime.executions "
                    "WHERE execution_id=:execution) WHERE attempt_id=:id"
                ),
                {"execution": run.execution_id, "id": run.attempt_id},
            )
        return handling

    async def cancel(self, connection: AsyncConnection, caller: Caller, identity: UUID) -> Handling:
        """校验调用者与归属后取消未提交的等待；已 committed/cancelled 的保留原决定。"""
        saved = await facts.read_wait(connection, str(identity))
        execution = await store.lock_owned(connection, self.entries, saved.execution_id)
        caller.require(execution, "cancel")
        await store.check(connection, self.entries, execution, "cancel")
        saved = await facts.read_wait(connection, str(identity), lock=True)
        self.policies.resolve(saved, execution)
        handling = await facts.read_handling(connection, saved)
        # 已提交或已取消的等待保留原决定，不再覆盖。
        if handling.state in {"committed", "cancelled"}:
            return handling
        await connection.execute(
            text(
                "UPDATE runtime.waits SET resolution='cancelled',resolved_at=clock_timestamp() "
                "WHERE wait_id=:id AND resolution='pending'"
            ),
            {"id": identity},
        )
        await connection.execute(
            text(
                "UPDATE runtime.wait_handling SET state='cancelled',failure_ref=NULL,"
                "updated_at=clock_timestamp() WHERE wait_id=:id"
            ),
            {"id": identity},
        )
        saved = await facts.read_wait(connection, str(identity))
        handling = await facts.read_handling(connection, saved)
        await facts.record(connection, saved, handling, "cancelled", caller.actor)
        return handling


async def mark_waiting(connection: AsyncConnection, run: RunInput) -> None:
    """首次登记与恢复使用同一控制状态；不延长等待或执行期限。"""
    await connection.execute(
        text(
            "UPDATE runtime.executions SET state='waiting',updated_at=clock_timestamp() "
            "WHERE execution_id=:id"
        ),
        {"id": run.execution_id},
    )
    await connection.execute(
        text("UPDATE runtime.execution_attempts SET state='waiting' WHERE attempt_id=:id"),
        {"id": run.attempt_id},
    )
