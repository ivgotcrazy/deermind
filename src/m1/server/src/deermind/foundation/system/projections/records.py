"""通用投影维护记录；业务负责副本、生成与校验，本模块只操作 runtime 记录。

分层定位：foundation（公共运行底座 / 投影重建仓储）
对外契约：ProjectionRecords 提供重建作业的授权核对、上界取材、登记、防重收据与结果事件落定。
边界约束：不调用生成器、不解释副本元数据；维护作业须使用 migrator 身份且库版本与维护包一致。
"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.projections.contracts import (
    REBUILD_FINISHED,
    CheckIssue,
    RebuildFinished,
    RebuildJob,
    ScopeBound,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class ProjectionRecords:
    """维护授权、固定上界和批次结果；不调用生成器，不解释副本元数据。"""

    def __init__(
        self, engine: AsyncEngine, *, expected_revision: str, maintenance_lock: int
    ) -> None:
        self.engine = engine
        self.expected_revision = expected_revision
        self.maintenance_lock = maintenance_lock

    @asynccontextmanager
    async def guard(self) -> AsyncGenerator[AsyncConnection]:
        """先停写再调用。NOWAIT只检查取锁当时，后来的应用写入受锁超时约束。"""
        async with self.engine.begin() as connection:
            # 重建必须使用 migrator 维护身份，普通业务库账号无权执行。
            if await connection.scalar(text("SELECT current_user")) != "deermind_migrator":
                raise PermissionError("Rebuild requires the maintenance database identity")
            # 库版本须与维护包一致，避免在迁移中途的库上重建投影。
            revision = await connection.scalar(
                text("SELECT version_num FROM public.alembic_version")
            )
            if revision != self.expected_revision:
                raise RuntimeError("Database revision differs from the maintenance package")
            # 咨询事务锁互斥：同一时刻只允许一个迁移或投影维护作业。
            if not await connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": self.maintenance_lock}
            ):
                raise RuntimeError("Another migration or projection maintenance is running")
            # 缩短锁等待超时，并以共享模式锁住事件表，阻止维护期间写入。
            await connection.execute(text("SET LOCAL lock_timeout='3s'"))
            await connection.execute(text("LOCK TABLE runtime.events IN SHARE MODE NOWAIT"))
            yield connection

    async def get(
        self, connection: AsyncConnection, identity: UUID, operator: str, authorization: str
    ) -> RebuildJob | None:
        """按重建编号读取作业，并核对操作者与授权是否匹配。"""
        raw = await connection.scalar(
            text("SELECT to_jsonb(r) FROM runtime.projection_rebuilds r WHERE rebuild_id=:id"),
            {"id": identity},
        )
        # 作业不存在，按无作业返回，交由调用方判 404。
        if raw is None:
            return None
        job = RebuildJob.model_validate_json(canonical_json(raw))
        # 操作者与授权引用任一不符，拒绝本次维护请求接管该作业。
        if job.operator_id != operator or job.authorization_ref != authorization:
            raise PermissionError("Rebuild is not available to this maintenance request")
        return job

    async def bounds(
        self, connection: AsyncConnection, kind: str, scopes: Sequence[UUID]
    ) -> list[ScopeBound]:
        """按范围集合取当前已封上界序号；无来源事实则拒绝重建。"""
        result: list[ScopeBound] = []
        # 逐范围取当前已封上界序号，作为本次重建的取材上限。
        for scope in scopes:
            upper = await connection.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind=:kind AND scope_id=:scope"
                ),
                {"kind": kind, "scope": scope},
            )
            # 范围无来源事实（无上界或上界为 0），不允许用空数据替换投影。
            if upper is None or upper < 1:
                raise ValueError("Cannot replace a projection without source facts")
            result.append(ScopeBound(scope_kind=kind, scope_id=scope, upper_seq=upper))
        return result

    async def create(self, connection: AsyncConnection, job: RebuildJob) -> None:
        """登记一条 building 状态的重建作业。"""
        await connection.execute(
            text(
                "INSERT INTO runtime.projection_rebuilds "
                "(rebuild_id,projector_id,generation,implementation_digest,scope_bounds,"
                "stage_relation,target_relations,operator_id,authorization_ref,"
                "state,created_at,updated_at) "
                "VALUES (:id,:projector,:generation,:digest,CAST(:bounds AS jsonb),:stage,"
                "CAST(:targets AS jsonb),:operator,:authorization,'building',:created,:created)"
            ),
            {
                "id": job.rebuild_id,
                "projector": job.projector_id,
                "generation": job.generation,
                "digest": job.implementation_digest,
                "bounds": canonical_json([b.model_dump(mode="json") for b in job.scope_bounds]),
                "stage": job.stage_relation,
                "targets": canonical_json(job.target_relations),
                "operator": job.operator_id,
                "authorization": job.authorization_ref,
                "created": job.created_at,
            },
        )

    async def applied(self, connection: AsyncConnection, job: RebuildJob) -> set[UUID]:
        """返回该投影器当前生成号已应用过的事件编号集合。"""
        # 按投影器+生成号汇总已落收据的事件，供比对哪些事件需要重放。
        return set(
            await connection.scalars(
                text(
                    "SELECT event_id FROM runtime.projection_receipts WHERE "
                    "projector_id=:projector AND generation=:generation"
                ),
                {"projector": job.projector_id, "generation": job.generation},
            )
        )

    async def publish(
        self, connection: AsyncConnection, job: RebuildJob, checks: list[CheckIssue]
    ) -> None:
        """业务完成替换后同事务登记；不能先登记完成再写业务数据。"""
        parameters = {"projector": job.projector_id, "generation": job.generation}
        # 跨代复制既有应用收据到新生成号，避免已应用事件被重复处理。
        await connection.execute(
            text(
                "INSERT INTO runtime.projection_receipts"
                "(projector_id,generation,event_id,applied_at) "
                "SELECT projector_id,1,event_id,applied_at FROM runtime.projection_receipts "
                "WHERE projector_id=:projector AND generation=:generation ON CONFLICT DO NOTHING"
            ),
            parameters,
        )
        # 只登记校验通过的完整范围；不持久化逐事件的维护断点。
        await connection.execute(
            text(
                "INSERT INTO runtime.projection_offsets "
                "(projector_id,generation,scope_kind,scope_id,scanned_through_seq,"
                "history_upper_seq,state,updated_at) VALUES (:projector,:generation,:kind,:scope,"
                ":upper,:upper,'completed',clock_timestamp())"
            ),
            # 逐范围写入本次重建封定的上界偏移。
            [
                {
                    **parameters,
                    "kind": bound.scope_kind,
                    "scope": bound.scope_id,
                    "upper": bound.upper_seq,
                }
                for bound in job.scope_bounds
            ],
        )
        # 旧代历史偏移转入 live 态继续增量跟踪，清除上次错误标记。
        await connection.execute(
            text(
                "INSERT INTO runtime.projection_offsets "
                "(projector_id,generation,scope_kind,scope_id,scanned_through_seq,"
                "history_upper_seq,state,updated_at) SELECT projector_id,1,scope_kind,scope_id,"
                "history_upper_seq,history_upper_seq,'live',clock_timestamp() "
                "FROM runtime.projection_offsets WHERE projector_id=:projector "
                "AND generation=:generation "
                "ON CONFLICT (projector_id,generation,scope_kind,scope_id) DO UPDATE SET "
                "scanned_through_seq=EXCLUDED.scanned_through_seq,history_upper_seq=EXCLUDED.history_upper_seq,"
                "state='live',error=NULL,updated_at=EXCLUDED.updated_at"
            ),
            parameters,
        )
        # 偏移落定后同事务登记重建完成结果事件。
        await self.result(connection, job, "completed", None, checks=checks)

    async def result(
        self,
        gate: AsyncConnection,
        job: RebuildJob,
        outcome: str,
        error_type: str | None,
        *,
        checks: list[CheckIssue] | None = None,
    ) -> None:
        """落定重建结果事件，并把作业更新为对应终态。"""
        owner = Ref(owner="runtime", type="projection_rebuild", id=str(job.rebuild_id))
        # 有失败类型才记失败原因码；未显式给校验项时按成败补一条默认核对说明。
        payload = RebuildFinished.model_validate(
            {
                "records": [],
                "subject_ref": owner,
                "outcome": outcome,
                "reason_code": "REBUILD_FAILED" if error_type else None,
                "projector_id": job.projector_id,
                "generation": job.generation,
                "scope_bounds": job.scope_bounds,
                "checks": checks
                if checks is not None
                else [
                    CheckIssue(
                        code="REBUILD_FAILED" if error_type else "SOURCE_MATCH",
                        path="scope_bounds",
                        message="核对未通过，正式查询数据未替换"
                        if error_type
                        else "调用方已确认维护结果",
                    )
                ],
            }
        )
        # 由重建编号派生确定性事件编号，同一作业重复收尾不会产生不同 finished 事件。
        event_id = uuid5(NAMESPACE_URL, f"deermind/rebuild/{job.rebuild_id}/finished")
        draft = EventDraft(
            event_id,
            "ProjectionRebuildFinished",
            1,
            "maintenance",
            job.rebuild_id,
            owner,
            payload.model_dump(mode="json"),
            f"rebuild:{job.rebuild_id}",
        )
        access = ProducerAccess(
            "runtime",
            Ref(owner="runtime", type="operator", id=job.operator_id),
            frozenset({("maintenance", job.rebuild_id)}),
        )
        await EventStore([REBUILD_FINISHED]).append(
            gate,
            access,
            [draft],
            commit_id=uuid4(),
            correlation_id=job.rebuild_id,
            expected_seq={("maintenance", job.rebuild_id): 0},
        )
        # 事件留痕后把作业更新为对应终态，并回填结果事件编号与失败明细。
        await gate.execute(
            text(
                "UPDATE runtime.projection_rebuilds SET state=:state,result_event_id=:event,"
                "error=CAST(:error AS jsonb),updated_at=clock_timestamp() WHERE rebuild_id=:id"
            ),
            {
                "state": outcome,
                "event": event_id,
                "id": job.rebuild_id,
                "error": canonical_json({"code": "REBUILD_FAILED", "message": error_type})
                if error_type
                else None,
            },
        )
