"""登记、补查和接续；所有者持业务锁，底座只落定一次等待决定。"""

from datetime import datetime
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions import steps, store
from deermind.foundation.system.executions.contracts import Caller, Registry, RunInput
from deermind.foundation.system.waits import facts
from deermind.foundation.system.waits.contracts import Condition, Handling, Policies, Wait
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class Waits:
    def __init__(self, entries: Registry, policies: Policies, *, maximum_seconds: int) -> None:
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
        if (
            not step_key.strip()
            or reserve_seconds <= 0
            or condition.result_key
            and condition.result_key.scope_id != condition.scope_id
            or not set(condition.equals) <= {"event_id", "producer", "correlation_id"}
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
        if existing:
            saved = await facts.read_wait(connection, str(existing), lock=True)
            self.policies.resolve(saved, execution)
            if saved.probe_ref != probe_ref or saved.owner_ref != owner:
                raise ValueError("Wait registration conflict")
            if saved.resolution == "pending":
                now = await connection.scalar(text("SELECT clock_timestamp()"))
                if (
                    run.deadline_at - max(now, saved.deadline_at)
                ).total_seconds() < reserve_seconds:
                    raise ValueError("Recovery leaves no continuation budget")
                await mark_waiting(connection, run)
            return saved
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        if (
            deadline.tzinfo is None
            or not 0 < (deadline - now).total_seconds() <= self.maximum_seconds
            or (run.deadline_at - deadline).total_seconds() < reserve_seconds
        ):
            raise ValueError("Wait exceeds its limit or leaves no continuation budget")
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
        if (
            execution.active_attempt_id != run.attempt_id
            or current.execution_id != run.execution_id
            or execution.state not in {"ready", "running", "waiting"}
            or execution.implementation_ref != run.implementation_ref
            or execution.ai_config_ref != run.ai_config_ref
            or execution.input_ref != run.input_ref
            or current.deadline_at != run.deadline_at
        ):
            raise ValueError("Wait attempt is no longer active")
        await store.check(connection, self.entries, execution, "read")
        saved = await facts.read_wait(connection, str(identity), lock=True)
        policy = self.policies.resolve(saved, execution)
        handling = await facts.read_handling(connection, saved)
        if saved.resolution != "pending" or handling.state == "cancelled":
            return saved
        probe_started = await connection.scalar(text("SELECT clock_timestamp()"))
        found = await policy.probe(connection, execution, saved.condition)
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        if found is None and now < saved.deadline_at:
            return saved
        # 普通补查恰好跨过截止点时，还需做一次到期后的查询，不能沿用之前的空结果。
        if found is None and probe_started < saved.deadline_at <= now:
            found = await policy.probe(connection, execution, saved.condition)
            now = await connection.scalar(text("SELECT clock_timestamp()"))
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
        if handling.state in {"committed", "cancelled"}:
            return handling
        if saved.resolution == "pending":
            raise ValueError("Cannot handle an unresolved wait")
        granted = await store.authorization(connection, run.execution_id)
        try:
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
        saved = await facts.read_wait(connection, str(identity))
        execution = await store.lock_owned(connection, self.entries, saved.execution_id)
        caller.require(execution, "cancel")
        await store.check(connection, self.entries, execution, "cancel")
        saved = await facts.read_wait(connection, str(identity), lock=True)
        self.policies.resolve(saved, execution)
        handling = await facts.read_handling(connection, saved)
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
