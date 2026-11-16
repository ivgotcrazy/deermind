"""维护窗口中的隔离重建；副本及进度可续做，正式替换与结果留痕同事务。"""

import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from deermind.foundation.system.events.contracts import EventDraft, ProducerAccess, Ref, StoredEvent
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.reading import ReadAccess
from deermind.foundation.system.events.store import EventStore, canonical_json
from deermind.foundation.system.projections.contracts import (
    REBUILD_FINISHED,
    CheckIssue,
    RebuildFinished,
    RebuildJob,
    RebuildSpec,
    ScopeBound,
)
from deermind.infrastructure.database.connection import EXPECTED_REVISION, MAINTENANCE_LOCK
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class ProjectionRebuilder:
    """只装配已实现的单行查询投影；不接受浏览器或Agent提供的执行逻辑。"""

    def __init__(self, engine: AsyncEngine, reader: EventReader, spec: RebuildSpec) -> None:
        if (
            not re.fullmatch(r"[a-z_]+\.[a-z_]+", spec.target)
            or any(not re.fullmatch(r"[a-z_]+", column) for column in spec.columns)
            or spec.key not in spec.columns
            or "source_event_id" not in spec.columns
            or not re.fullmatch(r"[0-9a-f]{64}", spec.implementation_digest)
        ):
            raise ValueError("Invalid registered rebuild specification")
        self.engine, self.reader, self.spec = engine, reader, spec

    @staticmethod
    def stage_name(identity: UUID) -> str:
        return f"runtime.rebuild_{identity.hex}"

    @asynccontextmanager
    async def _guard(self) -> AsyncGenerator[AsyncConnection]:
        """维护账号与迁移共用互斥锁；SHARE锁阻止漏停的写入，不静默等待。"""
        async with self.engine.begin() as gate:
            if await gate.scalar(text("SELECT current_user")) != "deermind_migrator":
                raise PermissionError("Rebuild requires the maintenance database identity")
            if (
                await gate.scalar(text("SELECT version_num FROM public.alembic_version"))
                != EXPECTED_REVISION
            ):
                raise RuntimeError("Database revision differs from the maintenance package")
            if not await gate.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": MAINTENANCE_LOCK}
            ):
                raise RuntimeError("Another migration or projection maintenance is running")
            # 此连接只保护维护窗口；逐事件的副本/收据在独立短事务中提交。
            await gate.execute(
                text(f"LOCK TABLE runtime.events, {self.spec.target} IN SHARE MODE NOWAIT")
            )
            yield gate

    async def _job(
        self, connection: AsyncConnection, identity: UUID, operator: str, authorization: str
    ) -> RebuildJob:
        raw = await connection.scalar(
            text("SELECT to_jsonb(r) FROM runtime.projection_rebuilds r WHERE rebuild_id=:id"),
            {"id": identity},
        )
        if raw is None:
            raise PermissionError("Rebuild is not available to this maintenance request")
        job = RebuildJob.model_validate_json(canonical_json(raw))
        if job.operator_id != operator or job.authorization_ref != authorization:
            raise PermissionError("Rebuild is not available to this maintenance request")
        if job.projector_id != self.spec.projector_id or job.stage_relation != self.stage_name(
            identity
        ):
            raise ValueError("Rebuild does not match the registered projector")
        return job

    async def prepare(
        self,
        identity: UUID,
        generation: int,
        scopes: Sequence[UUID],
        *,
        operator: str,
        authorization: str,
    ) -> RebuildJob:
        """固定完整范围和上界；重复同一请求返回原记录，不重建或清空副本。"""
        if (
            type(generation) is not int
            or generation <= 1
            or not scopes
            or len(set(scopes)) != len(scopes)
            or not operator.strip()
            or not authorization.strip()
        ):
            raise ValueError(
                "Explicit generation, scopes and maintenance authorization are required"
            )
        scopes = sorted(scopes, key=str)
        async with self._guard() as gate:
            exists = await gate.scalar(
                text("SELECT 1 FROM runtime.projection_rebuilds WHERE rebuild_id=:id"),
                {"id": identity},
            )
            if exists:
                job = await self._job(gate, identity, operator, authorization)
                if (
                    job.generation != generation
                    or [b.scope_id for b in job.scope_bounds] != list(scopes)
                    or job.implementation_digest != self.spec.implementation_digest
                ):
                    raise ValueError("Existing rebuild parameters cannot be changed")
                return job
            bounds: list[ScopeBound] = []
            for scope in scopes:
                upper = await gate.scalar(
                    text(
                        "SELECT last_seq FROM runtime.scope_event_heads WHERE scope_kind=:kind "
                        "AND scope_id=:scope"
                    ),
                    {"kind": self.spec.scope_kind, "scope": scope},
                )
                if upper is None or upper < 1:
                    raise ValueError("Cannot replace a projection without source facts")
                bounds.append(
                    ScopeBound(scope_kind=self.spec.scope_kind, scope_id=scope, upper_seq=upper)
                )
            stage = self.stage_name(identity)
            await gate.execute(
                text(f"CREATE TABLE {stage} (LIKE {self.spec.target} INCLUDING ALL)")
            )
            await gate.execute(
                text(
                    "INSERT INTO runtime.projection_rebuilds "
                    "(rebuild_id,projector_id,generation,implementation_digest,scope_bounds,"
                    "stage_relation,"
                    "operator_id,authorization_ref,state,created_at,updated_at) "
                    "VALUES (:id,:projector,:generation,:digest,CAST(:bounds AS jsonb),:stage,"
                    ":operator,:authorization,'building',clock_timestamp(),clock_timestamp())"
                ),
                {
                    "id": identity,
                    "projector": self.spec.projector_id,
                    "generation": generation,
                    "digest": self.spec.implementation_digest,
                    "bounds": canonical_json([b.model_dump(mode="json") for b in bounds]),
                    "stage": stage,
                    "operator": operator,
                    "authorization": authorization,
                },
            )
            for bound in bounds:
                await gate.execute(
                    text(
                        "INSERT INTO runtime.projection_offsets "
                        "(projector_id,generation,scope_kind,scope_id,history_upper_seq,state,"
                        "updated_at) "
                        "VALUES "
                        "(:projector,:generation,:kind,:scope,:upper,'catching_up',"
                        "clock_timestamp())"
                    ),
                    {
                        "projector": self.spec.projector_id,
                        "generation": generation,
                        "kind": bound.scope_kind,
                        "scope": bound.scope_id,
                        "upper": bound.upper_seq,
                    },
                )
            return await self._job(gate, identity, operator, authorization)

    async def status(self, identity: UUID, *, operator: str, authorization: str) -> RebuildJob:
        async with self._guard() as gate:
            return await self._job(gate, identity, operator, authorization)

    def _access(self, job: RebuildJob) -> ReadAccess:
        return ReadAccess(
            job.operator_id,
            "runtime.projection_read",
            "runtime",
            "projection_rebuild",
            job.authorization_ref,
            frozenset((b.scope_kind, b.scope_id) for b in job.scope_bounds),
            maintenance_ref=str(job.rebuild_id),
        )

    def _values(self, event: StoredEvent) -> dict[str, object] | None:
        values = self.spec.values(event)
        if values is None:
            return None
        if (
            set(values) != set(self.spec.columns)
            or values[self.spec.key] != event.draft.scope_id
            or values["source_event_id"] != event.draft.event_id
            or event.draft.scope_kind != self.spec.scope_kind
        ):
            raise ValueError("Projection row identity or columns differ from its fact")
        return values

    async def _check_bounds(self, gate: AsyncConnection, job: RebuildJob) -> None:
        if job.implementation_digest != self.spec.implementation_digest:
            raise ValueError("Resume must use the original projector implementation")
        for bound in job.scope_bounds:
            if bound.scope_kind != self.spec.scope_kind:
                raise ValueError("Rebuild scope differs from its registered projector")
            current = await gate.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads WHERE scope_kind=:kind AND "
                    "scope_id=:scope"
                ),
                {"kind": bound.scope_kind, "scope": bound.scope_id},
            )
            if current != bound.upper_seq:
                raise ValueError("Source facts changed; prepare a new rebuild generation")

    async def resume(
        self, identity: UUID, *, operator: str, authorization: str, max_events: int | None = None
    ) -> RebuildJob:
        """中断保留已提交副本；已完成只返回原结果。明确失败须修复后新建代次。"""
        if max_events is not None and (type(max_events) is not int or max_events < 1):
            raise ValueError("max_events must be a positive integer")
        async with self._guard() as gate:
            job = await self._job(gate, identity, operator, authorization)
            if job.state != "building":
                return job
            # 范围或代码不符不消耗原工作，也不修改原副本；操作人必须明确重新准备。
            await self._check_bounds(gate, job)
            try:
                processed = 0
                for bound in job.scope_bounds:
                    while True:
                        previous = await gate.scalar(
                            text(
                                "SELECT scanned_through_seq FROM runtime.projection_offsets "
                                "WHERE projector_id=:projector AND generation=:generation "
                                "AND scope_kind=:kind AND scope_id=:scope"
                            ),
                            {
                                "projector": job.projector_id,
                                "generation": job.generation,
                                "kind": bound.scope_kind,
                                "scope": bound.scope_id,
                            },
                        )
                        if previous is None:
                            raise ValueError("Rebuild progress is missing")
                        if previous == bound.upper_seq:
                            break
                        event_id = await gate.scalar(
                            text(
                                "SELECT event_id FROM runtime.events WHERE scope_kind=:kind "
                                "AND scope_id=:scope AND scope_event_seq=:seq"
                            ),
                            {
                                "kind": bound.scope_kind,
                                "scope": bound.scope_id,
                                "seq": previous + 1,
                            },
                        )
                        if event_id is None:
                            raise ValueError("A source sequence is missing")
                        event = await self.reader.read_projection_event(self._access(job), event_id)
                        await self._checkpoint(job, event, previous)
                        processed += 1
                        if max_events is not None and processed >= max_events:
                            return await self._job(gate, identity, operator, authorization)
                # 替换前再逐行核对来源及结果，不能仅凭“收据齐了”信任维护副本。
                async with gate.begin_nested():
                    await self._verify(gate, job)
                    await self._finish(gate, job)
            except Exception as error:
                # 不把原文、SQL参数或异常输入写入维护事实；错误类型留在受控记录中。
                await self._failed(gate, job, type(error).__name__)
            return await self._job(gate, identity, operator, authorization)

    async def _checkpoint(self, job: RebuildJob, event: StoredEvent, previous: int) -> None:
        values = self._values(event)
        columns = ",".join(self.spec.columns)
        parameters = ",".join(":" + column for column in self.spec.columns)
        async with self.engine.begin() as connection:
            if values is not None:
                await connection.execute(
                    text(
                        f"INSERT INTO {job.stage_relation} ({columns}) VALUES ({parameters}) "
                        f"ON CONFLICT ({self.spec.key}) DO UPDATE SET "
                        + ",".join(
                            f"{column}=EXCLUDED.{column}"
                            for column in self.spec.columns
                            if column != self.spec.key
                        )
                    ),
                    values,
                )
            await connection.execute(
                text(
                    "INSERT INTO "
                    "runtime.projection_receipts(projector_id,generation,event_id,applied_at) "
                    "VALUES (:projector,:generation,:event,clock_timestamp())"
                ),
                {
                    "projector": job.projector_id,
                    "generation": job.generation,
                    "event": event.draft.event_id,
                },
            )
            result = await connection.execute(
                text(
                    "UPDATE runtime.projection_offsets SET "
                    "scanned_through_seq=:next,updated_at=clock_timestamp() "
                    "WHERE projector_id=:projector AND generation=:generation AND scope_kind=:kind "
                    "AND scope_id=:scope AND scanned_through_seq=:previous AND state='catching_up'"
                ),
                {
                    "projector": job.projector_id,
                    "generation": job.generation,
                    "kind": event.draft.scope_kind,
                    "scope": event.draft.scope_id,
                    "previous": previous,
                    "next": event.scope_event_seq,
                },
            )
            if result.rowcount != 1:
                raise ValueError("Projection progress no longer matches its checkpoint")

    async def _verify(self, gate: AsyncConnection, job: RebuildJob) -> None:
        expected = sum(bound.upper_seq for bound in job.scope_bounds)
        rows = list(await gate.scalars(text(f"SELECT {self.spec.key} FROM {job.stage_relation}")))
        receipts = await gate.scalar(
            text(
                "SELECT count(*) FROM runtime.projection_receipts WHERE "
                "projector_id=:projector AND generation=:generation"
            ),
            {"projector": job.projector_id, "generation": job.generation},
        )
        if len(rows) != len(job.scope_bounds) or receipts != expected:
            raise ValueError("Staged rows and receipts do not cover the fixed source range")
        covered = await gate.scalar(
            text(
                f"SELECT count(*) FROM {job.stage_relation} s JOIN runtime.projection_receipts r "
                "ON r.event_id=s.source_event_id WHERE r.projector_id=:projector AND "
                "r.generation=:generation"
            ),
            {"projector": job.projector_id, "generation": job.generation},
        )
        if covered != len(rows):
            raise ValueError("Receipts do not match the staged source events")
        for bound in job.scope_bounds:
            progress = (
                await gate.execute(
                    text(
                        "SELECT scanned_through_seq,history_upper_seq,state FROM "
                        "runtime.projection_offsets "
                        "WHERE projector_id=:projector AND generation=:generation AND "
                        "scope_kind=:kind AND scope_id=:scope"
                    ),
                    {
                        "projector": job.projector_id,
                        "generation": job.generation,
                        "kind": bound.scope_kind,
                        "scope": bound.scope_id,
                    },
                )
            ).one()
            if tuple(progress) != (bound.upper_seq, bound.upper_seq, "catching_up"):
                raise ValueError("Progress does not cover the fixed source range")
        for identity in rows:
            row = (
                (
                    await gate.execute(
                        text(f"SELECT * FROM {job.stage_relation} WHERE {self.spec.key}=:id"),
                        {"id": identity},
                    )
                )
                .mappings()
                .one()
            )
            event = await self.reader.read_projection_event(
                self._access(job), row["source_event_id"]
            )
            bound = next((b for b in job.scope_bounds if b.scope_id == identity), None)
            if (
                bound is None
                or event.scope_event_seq > bound.upper_seq
                or dict(row) != self._values(event)
            ):
                raise ValueError("Staged row differs from its original fact")

    async def _finish(self, gate: AsyncConnection, job: RebuildJob) -> None:
        columns = ",".join(self.spec.columns)
        assignments = ",".join(
            f"{column}=EXCLUDED.{column}" for column in self.spec.columns if column != self.spec.key
        )
        # 保留业务主键，更新完整查询行；不删除凭据或请求收据等控制数据。
        await gate.execute(
            text(
                f"INSERT INTO {self.spec.target} ({columns}) SELECT {columns} FROM "
                f"{job.stage_relation} WHERE true "
                f"ON CONFLICT ({self.spec.key}) DO UPDATE SET {assignments}"
            )
        )
        await gate.execute(
            text(
                "INSERT INTO "
                "runtime.projection_receipts(projector_id,generation,event_id,applied_at) "
                "SELECT projector_id,1,event_id,applied_at FROM runtime.projection_receipts "
                "WHERE projector_id=:projector AND generation=:generation ON CONFLICT DO NOTHING"
            ),
            {"projector": job.projector_id, "generation": job.generation},
        )
        await gate.execute(
            text(
                "INSERT INTO runtime.projection_offsets "
                "(projector_id,generation,scope_kind,scope_id,scanned_through_seq,"
                "history_upper_seq,state,updated_at) "
                "SELECT "
                "projector_id,1,scope_kind,scope_id,history_upper_seq,history_upper_seq,'live',"
                "clock_timestamp() "
                "FROM runtime.projection_offsets WHERE projector_id=:projector AND "
                "generation=:generation "
                "ON CONFLICT (projector_id,generation,scope_kind,scope_id) DO UPDATE SET "
                "scanned_through_seq=EXCLUDED.scanned_through_seq,"
                "history_upper_seq=EXCLUDED.history_upper_seq,"
                "state='live',error=NULL,updated_at=EXCLUDED.updated_at"
            ),
            {"projector": job.projector_id, "generation": job.generation},
        )
        await gate.execute(
            text(
                "UPDATE runtime.projection_offsets SET "
                "state='completed',updated_at=clock_timestamp() "
                "WHERE projector_id=:projector AND generation=:generation"
            ),
            {"projector": job.projector_id, "generation": job.generation},
        )
        await self._result(gate, job, "completed", None)
        await gate.execute(text(f"DROP TABLE {job.stage_relation}"))

    async def _failed(self, gate: AsyncConnection, job: RebuildJob, error_type: str) -> None:
        await gate.execute(
            text(
                "UPDATE runtime.projection_offsets SET state='blocked',error=CAST(:error AS jsonb),"
                "updated_at=clock_timestamp() WHERE projector_id=:projector AND "
                "generation=:generation"
            ),
            {
                "projector": job.projector_id,
                "generation": job.generation,
                "error": canonical_json(
                    {"code": "REBUILD_FAILED", "message": error_type, "event_id": None}
                ),
            },
        )
        await self._result(gate, job, "failed", error_type)

    async def _result(
        self, gate: AsyncConnection, job: RebuildJob, outcome: str, error_type: str | None
    ) -> None:
        owner = Ref(owner="runtime", type="projection_rebuild", id=str(job.rebuild_id))
        payload = RebuildFinished.model_validate(
            {
                "records": [],
                "subject_ref": owner,
                "outcome": outcome,
                "reason_code": "REBUILD_FAILED" if error_type else None,
                "projector_id": job.projector_id,
                "generation": job.generation,
                "scope_bounds": job.scope_bounds,
                "checks": [
                    CheckIssue(
                        code="REBUILD_FAILED" if error_type else "SOURCE_MATCH",
                        path="scope_bounds",
                        message="核对未通过，正式查询数据未替换"
                        if error_type
                        else "范围、正文、来源、收据和进度核对通过",
                    )
                ],
            }
        )
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
        await EventStore([REBUILD_FINISHED]).append_and_project(
            gate,
            access,
            [draft],
            commit_id=uuid4(),
            correlation_id=job.rebuild_id,
            expected_seq={("maintenance", job.rebuild_id): 0},
        )
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
