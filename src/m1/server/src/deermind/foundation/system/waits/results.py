"""不可变公开结果的登记与读取；生产方不查询等待者，也不接收其期限。

分层定位：foundation（公共运行底座 / 结果登记）
对外契约：Results 管理结果期待登记、结果发布与只读查询；按生产方/类型固定策略核对归属。
边界约束：结果一经发布不可被异内容覆盖；读取不触发评价、不修改生产记录；通知不能代替原文。
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.waits import Publication, ResultKey, ResultView
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Caller, Registry
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ResultPolicy:
    """固定结果语义及可读模块；所有者核对载荷与正式事件，不能以通知代替原文。"""

    producer: str
    kind: str
    readers: frozenset[str]
    check: Callable[[AsyncConnection, Execution, Publication], Awaitable[None]]


class Results:
    """结果登记仓储：持有注册表与结果策略，承接期待登记、结果发布与只读查询。"""

    def __init__(self, entries: Registry, policies: Sequence[ResultPolicy]) -> None:
        self.entries = entries
        self.policies = {(p.producer, p.kind): p for p in policies}
        # 同生产方同类型重复登记会互相覆盖，判重复策略。
        if len(self.policies) != len(policies):
            raise ValueError("Duplicate result policy")

    def policy(self, key: ResultKey) -> ResultPolicy:
        """按生产方与结果类型解析固定策略，未登记则拒绝。"""
        policy = self.policies.get((key.producer, key.result_kind))
        # 该生产方+类型未登记策略，不允许发布或读取其结果。
        if policy is None:
            raise PermissionError("Result type is not registered")
        return policy

    async def expect(self, connection: AsyncConnection, run: RunInput, key: ResultKey) -> None:
        """受理方持工作锁登记；恢复沿原结果键，不重新创建生产工作。"""
        self.policy(key)
        execution = await store.active(connection, self.entries, run, "step")
        # 结果归属的生产方与范围必须与当前执行一致。
        if execution.owner != key.producer or execution.scope_id != key.scope_id:
            raise PermissionError("Result does not belong to this producer")
        trigger = await connection.scalar(
            text("SELECT scope_id FROM runtime.events WHERE event_id=:id"),
            {"id": key.trigger_event_id},
        )
        # 触发事件必须属于本结果范围，不能跨范围引用其他事件。
        if trigger != key.scope_id:
            raise PermissionError("Result trigger belongs to another scope")
        await connection.execute(
            text("""
                INSERT INTO runtime.expected_results
                (scope_id,trigger_event_id,producer,result_kind,execution_id,accepted_at)
                VALUES (:scope_id,:trigger_event_id,:producer,:result_kind,:execution,
                        clock_timestamp()) ON CONFLICT DO NOTHING
            """),
            {**key.model_dump(), "execution": execution.execution_id},
        )
        saved = await connection.scalar(
            text("SELECT execution_id FROM runtime.expected_results WHERE " + key_filter()),
            key.model_dump(),
        )
        # 结果键已被另一工作占有，判身份冲突。
        if saved != execution.execution_id:
            raise ValueError("Result identity is already owned by another work")
        # 已有正式发布，恢复沿原结果键，不再新建结果尝试。
        if await publication(connection, key) is not None:
            return
        # 尚未发布：登记一条 pending 结果尝试，供发布时收尾。
        await connection.execute(
            text("""
                INSERT INTO runtime.result_attempts
                (scope_id,trigger_event_id,producer,result_kind,attempt_id,outcome,created_at)
                VALUES (:scope_id,:trigger_event_id,:producer,:result_kind,:attempt,'pending',
                        clock_timestamp()) ON CONFLICT DO NOTHING
            """),
            {**key.model_dump(), "attempt": run.attempt_id},
        )

    async def publish(
        self,
        connection: AsyncConnection,
        run: RunInput,
        key: ResultKey,
        *,
        result_ref: Ref,
        event_id: UUID,
        payload: dict[str, JsonValue],
        publication_refs: list[Ref],
    ) -> Publication:
        """和所有者事实/投影同事务；响应丢失可查询原发布，异内容不能覆盖。"""
        execution = await store.lock_owned(connection, self.entries, run.execution_id)
        policy = self.policy(key)
        # 发布者归属生产方与范围须与当前执行一致。
        if execution.owner != key.producer or execution.scope_id != key.scope_id:
            raise PermissionError("Publication owner mismatch")
        await store.check(connection, self.entries, execution, "read")
        current = await store.attempt(connection, run.attempt_id)
        # 尝试归属、期限与固定工作的输入/实现/配置引用任一漂移，判输入不一致。
        if (
            current.execution_id != run.execution_id
            or current.deadline_at != run.deadline_at
            or execution.input_ref != run.input_ref
            or execution.implementation_ref != run.implementation_ref
            or execution.ai_config_ref != run.ai_config_ref
        ):
            raise ValueError("Publication input differs from the fixed work")
        old = await publication(connection, key)
        # 已有正式发布：先比对是否同一工作、同一尝试、同一内容与事件。
        if old is not None:
            # 任一要素不符，说明同键被用于异内容，拒绝覆盖。
            if (
                old.execution_id != run.execution_id
                or old.attempt_id != run.attempt_id
                or old.result_ref != result_ref
                or old.payload != payload
                or old.event_id != event_id
                or old.publication_refs != publication_refs
            ):
                raise ValueError("Published result conflict")
            return old
        await store.active(connection, self.entries, run, "step")
        owner = await connection.scalar(
            text("SELECT execution_id FROM runtime.expected_results WHERE " + key_filter()),
            key.model_dump(),
        )
        # 必须先经期待登记，工作才能发布对应结果。
        if owner != run.execution_id:
            raise ValueError("Result must be registered before publication")
        event = (
            await connection.execute(
                text(
                    "SELECT producer,scope_id,source_execution_ref FROM runtime.events "
                    "WHERE event_id=:id"
                ),
                {"id": event_id},
            )
        ).one_or_none()
        # 留痕事件须属于本生产工作：生产方、范围、来源执行三者一致。
        if event is None or tuple(event) != (key.producer, key.scope_id, run.execution_id):
            raise PermissionError("Publication event does not belong to this production work")
        saved = Publication(
            **key.model_dump(),
            execution_id=run.execution_id,
            attempt_id=run.attempt_id,
            result_ref=result_ref,
            event_id=event_id,
            payload=payload,
            publication_refs=publication_refs,
            published_at=await connection.scalar(text("SELECT clock_timestamp()")),
        )
        # 所有者按固定策略核对载荷与正式事件，不能以通知代替原文。
        await policy.check(connection, execution, saved)
        await connection.execute(
            text(
                "INSERT INTO runtime.published_results SELECT * FROM jsonb_populate_record("
                "NULL::runtime.published_results,CAST(:body AS jsonb))"
            ),
            {"body": saved.model_dump_json()},
        )
        # 发布落库后把对应结果尝试收尾为 completed。
        await connection.execute(
            text(
                "UPDATE runtime.result_attempts SET outcome='completed',"
                "finished_at=clock_timestamp() WHERE " + key_filter() + " AND attempt_id=:attempt"
            ),
            {**key.model_dump(), "attempt": run.attempt_id},
        )
        return saved

    async def read(
        self, connection: AsyncConnection, caller: Caller, scope_kind: str, key: ResultKey
    ) -> ResultView:
        """调用方身份及资源由入口核验；不触发评价、不修改生产记录。"""
        policy = self.policy(key)
        # 读取授权三重核对：可读模块、read 动作、授权范围，缺一拒绝。
        if (
            caller.owner not in policy.readers
            or "read" not in caller.actions
            or (scope_kind, key.scope_id) not in caller.scopes
        ):
            raise PermissionError("Result read is not authorized")
        trigger_scope = (
            await connection.execute(
                text("SELECT scope_kind,scope_id FROM runtime.events WHERE event_id=:id"),
                {"id": key.trigger_event_id},
            )
        ).one_or_none()
        # 触发事件必须落在调用方授权范围内。
        if trigger_scope is None or tuple(trigger_scope) != (scope_kind, key.scope_id):
            raise PermissionError("Result trigger is outside the authorized scope")
        saved = await publication(connection, key)
        # 已有正式发布，直接返回可用结果。
        if saved is not None:
            return ResultView(state="available", publication=saved)
        row = (
            await connection.execute(
                text(
                    "SELECT e.state,e.failure_ref FROM runtime.expected_results r "
                    "JOIN runtime.executions e ON e.execution_id=r.execution_id WHERE "
                    + key_filter("r.")
                ),
                key.model_dump(),
            )
        ).one_or_none()
        # 无期待记录也无发布，按未找到返回。
        if row is None:
            return ResultView(state="not_found")
        # 生产工作已到终态（失败/取消/完成但未出结果），结果判失败并附失败引用。
        if row.state in {"failed", "cancelled", "completed"}:
            return ResultView(
                state="failed",
                failure_ref=(Ref.model_validate(row.failure_ref) if row.failure_ref else None),
            )
        # 其余状态仍在等待结果发布。
        return ResultView(state="pending")


def key_filter(prefix: str = "") -> str:
    """标识符来自固定合同，不从调用参数拼SQL。"""
    return " AND ".join(f"{prefix}{name}=:{name}" for name in ResultKey.model_fields)


async def publication(connection: AsyncConnection, key: ResultKey) -> Publication | None:
    """内部读取；对外必须先由Results.read校验资源与用途。"""
    row = (
        (
            await connection.execute(
                text("SELECT * FROM runtime.published_results WHERE " + key_filter()),
                key.model_dump(),
            )
        )
        .mappings()
        .one_or_none()
    )
    return Publication.model_validate_json(json.dumps(dict(row), default=str)) if row else None
