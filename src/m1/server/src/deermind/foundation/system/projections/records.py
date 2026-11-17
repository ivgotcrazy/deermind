"""通用投影维护记录；业务负责副本、生成与校验，本模块只操作runtime记录。"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref, StoredEvent
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
    """维护授权、固定上界、进度和结果；不调用生成器，不解释副本元数据。"""

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
            if await connection.scalar(text("SELECT current_user")) != "deermind_migrator":
                raise PermissionError("Rebuild requires the maintenance database identity")
            revision = await connection.scalar(
                text("SELECT version_num FROM public.alembic_version")
            )
            if revision != self.expected_revision:
                raise RuntimeError("Database revision differs from the maintenance package")
            if not await connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": self.maintenance_lock}
            ):
                raise RuntimeError("Another migration or projection maintenance is running")
            await connection.execute(text("SET LOCAL lock_timeout='3s'"))
            await connection.execute(text("LOCK TABLE runtime.events IN SHARE MODE NOWAIT"))
            yield connection

    async def get(
        self, connection: AsyncConnection, identity: UUID, operator: str, authorization: str
    ) -> RebuildJob | None:
        raw = await connection.scalar(
            text("SELECT to_jsonb(r) FROM runtime.projection_rebuilds r WHERE rebuild_id=:id"),
            {"id": identity},
        )
        if raw is None:
            return None
        job = RebuildJob.model_validate_json(canonical_json(raw))
        if job.operator_id != operator or job.authorization_ref != authorization:
            raise PermissionError("Rebuild is not available to this maintenance request")
        return job

    async def bounds(
        self, connection: AsyncConnection, kind: str, scopes: Sequence[UUID]
    ) -> list[ScopeBound]:
        result: list[ScopeBound] = []
        for scope in scopes:
            upper = await connection.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind=:kind AND scope_id=:scope"
                ),
                {"kind": kind, "scope": scope},
            )
            if upper is None or upper < 1:
                raise ValueError("Cannot replace a projection without source facts")
            result.append(ScopeBound(scope_kind=kind, scope_id=scope, upper_seq=upper))
        return result

    async def create(self, connection: AsyncConnection, job: RebuildJob) -> None:
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
        for bound in job.scope_bounds:
            await connection.execute(
                text(
                    "INSERT INTO runtime.projection_offsets "
                    "(projector_id,generation,scope_kind,scope_id,history_upper_seq,"
                    "state,updated_at) VALUES (:projector,:generation,:kind,:scope,"
                    ":upper,'catching_up',clock_timestamp())"
                ),
                {
                    "projector": job.projector_id,
                    "generation": job.generation,
                    "kind": bound.scope_kind,
                    "scope": bound.scope_id,
                    "upper": bound.upper_seq,
                },
            )

    async def position(
        self, connection: AsyncConnection, job: RebuildJob, bound: ScopeBound
    ) -> int:
        value = await connection.scalar(
            text(
                "SELECT scanned_through_seq FROM runtime.projection_offsets WHERE "
                "projector_id=:projector AND generation=:generation "
                "AND scope_kind=:kind AND scope_id=:scope"
            ),
            {
                "projector": job.projector_id,
                "generation": job.generation,
                "kind": bound.scope_kind,
                "scope": bound.scope_id,
            },
        )
        if not isinstance(value, int):
            raise ValueError("Rebuild progress is missing")
        return value

    async def event_id(self, connection: AsyncConnection, bound: ScopeBound, sequence: int) -> UUID:
        if not 1 <= sequence <= bound.upper_seq:
            raise ValueError("Sequence exceeds fixed history")
        identity = await connection.scalar(
            text(
                "SELECT event_id FROM runtime.events WHERE scope_kind=:kind "
                "AND scope_id=:scope AND scope_event_seq=:seq"
            ),
            {"kind": bound.scope_kind, "scope": bound.scope_id, "seq": sequence},
        )
        if not isinstance(identity, UUID):
            raise ValueError("A source sequence is missing")
        return identity

    async def advance(
        self, connection: AsyncConnection, job: RebuildJob, event: StoredEvent, previous: int
    ) -> None:
        result = await connection.execute(
            text(
                "UPDATE runtime.projection_offsets SET scanned_through_seq=:next,"
                "updated_at=clock_timestamp() "
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

    async def applied(self, connection: AsyncConnection, job: RebuildJob) -> set[UUID]:
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
        await connection.execute(
            text(
                "INSERT INTO runtime.projection_receipts"
                "(projector_id,generation,event_id,applied_at) "
                "SELECT projector_id,1,event_id,applied_at FROM runtime.projection_receipts "
                "WHERE projector_id=:projector AND generation=:generation ON CONFLICT DO NOTHING"
            ),
            parameters,
        )
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
        await connection.execute(
            text(
                "UPDATE runtime.projection_offsets SET state='completed',"
                "updated_at=clock_timestamp() "
                "WHERE projector_id=:projector AND generation=:generation"
            ),
            parameters,
        )
        await self.result(connection, job, "completed", None, checks=checks)

    async def fail(self, gate: AsyncConnection, job: RebuildJob, error_type: str) -> None:
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
        await self.result(gate, job, "failed", error_type)

    async def result(
        self,
        gate: AsyncConnection,
        job: RebuildJob,
        outcome: str,
        error_type: str | None,
        *,
        checks: list[CheckIssue] | None = None,
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
