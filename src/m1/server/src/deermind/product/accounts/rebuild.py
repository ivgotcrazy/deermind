"""账号业务的停写重建：固定事实范围，生成隔离副本，核对后原子发布五张查询表。"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from deermind.foundation.system.events.contracts import StoredEvent
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.reading import ReadAccess
from deermind.foundation.system.projections.contracts import CheckIssue, RebuildJob
from deermind.foundation.system.projections.records import ProjectionRecords
from deermind.product.accounts.projections import (
    EVENT_TYPES,
    PROJECTOR_ID,
    TABLES,
    apply_account_events,
    rows_for,
    stage_tables,
)
from deermind.product.accounts.usage_facts import ConditionsFact
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class AccountRebuildSpec:
    implementation_digest: str


class AccountRebuilder:
    """生成和校验均归账号业务；底座只提供事件读取及维护控制记录。"""

    def __init__(self, engine: AsyncEngine, reader: EventReader, spec: AccountRebuildSpec) -> None:
        self.engine, self.reader, self.spec = engine, reader, spec
        self.records = ProjectionRecords(engine)

    @staticmethod
    def stage_name(identity: UUID) -> str:
        return stage_tables(identity)["product.accounts"]

    @asynccontextmanager
    async def _guard(self) -> AsyncGenerator[AsyncConnection]:
        async with self.records.guard() as gate:
            await gate.execute(
                text(f"LOCK TABLE {','.join(t.name for t in TABLES)} IN SHARE MODE NOWAIT")
            )
            yield gate

    async def _job(
        self, connection: AsyncConnection, identity: UUID, operator: str, authorization: str
    ) -> RebuildJob:
        job = await self.records.get(connection, identity, operator, authorization)
        if job is None:
            raise PermissionError("Rebuild is not available to this maintenance request")
        return job

    def _current(self, job: RebuildJob) -> None:
        if (
            job.projector_id != PROJECTOR_ID
            or job.implementation_digest != self.spec.implementation_digest
            or job.target_relations != stage_tables(job.rebuild_id)
            or job.stage_relation != self.stage_name(job.rebuild_id)
            or any(bound.scope_kind != "account" for bound in job.scope_bounds)
        ):
            raise ValueError("Legacy or changed rebuild cannot resume; prepare a new generation")

    async def prepare(
        self,
        identity: UUID,
        generation: int,
        scopes: Sequence[UUID],
        *,
        operator: str,
        authorization: str,
    ) -> RebuildJob:
        """明确授权范围，重复请求沿原记录；不清理或转换旧维护记录。"""
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
            existing = await self.records.get(gate, identity, operator, authorization)
            if existing:
                self._current(existing)
                if (
                    existing.generation != generation
                    or [b.scope_id for b in existing.scope_bounds] != scopes
                ):
                    raise ValueError("Existing rebuild parameters cannot be changed")
                return existing
            bounds = await self.records.bounds(gate, "account", scopes)
            now = await gate.scalar(text("SELECT clock_timestamp()"))
            if not isinstance(now, datetime):
                raise RuntimeError("Database clock unavailable")
            targets = stage_tables(identity)
            job = RebuildJob(
                rebuild_id=identity,
                projector_id=PROJECTOR_ID,
                generation=generation,
                implementation_digest=self.spec.implementation_digest,
                scope_bounds=bounds,
                stage_relation=self.stage_name(identity),
                target_relations=targets,
                operator_id=operator,
                authorization_ref=authorization,
                state="building",
                result_event_id=None,
                error=None,
                created_at=now,
                updated_at=now,
            )
            for table in TABLES:
                # LIKE不复制外键；完整的业务关联在_verify核对，正式替换仍受真实外键约束。
                await gate.execute(
                    text(f"CREATE TABLE {targets[table.name]} (LIKE {table.name} INCLUDING ALL)")
                )
                await gate.execute(
                    text(f"REVOKE ALL ON {targets[table.name]} FROM deermind_app, PUBLIC")
                )
            await self.records.create(gate, job)
            return job

    async def status(self, identity: UUID, *, operator: str, authorization: str) -> RebuildJob:
        async with self.records.guard() as gate:
            return await self._job(gate, identity, operator, authorization)

    def _access(self, job: RebuildJob) -> ReadAccess:
        return ReadAccess(
            job.operator_id,
            "product.account_rebuild",
            "product",
            "projection_rebuild",
            job.authorization_ref,
            frozenset((b.scope_kind, b.scope_id) for b in job.scope_bounds),
            maintenance_ref=str(job.rebuild_id),
        )

    async def resume(
        self, identity: UUID, *, operator: str, authorization: str, max_events: int | None = None
    ) -> RebuildJob:
        """临时连接/锁故障保留断点；事实或完整性错误记失败，正式表不变。"""
        if max_events is not None and (type(max_events) is not int or max_events < 1):
            raise ValueError("max_events must be a positive integer")
        async with self._guard() as gate:
            job = await self._job(gate, identity, operator, authorization)
            # 旧结果可查，但不得被当作五表重建结果或继续执行。
            self._current(job)
            if job.state != "building":
                return job
            bounds = await self.records.bounds(
                gate, "account", [b.scope_id for b in job.scope_bounds]
            )
            if bounds != job.scope_bounds:
                raise ValueError("Source facts changed; prepare a new rebuild generation")
            try:
                processed = 0
                for bound in job.scope_bounds:
                    previous = await self.records.position(gate, job, bound)
                    while previous < bound.upper_seq:
                        event_id = await self.records.event_id(gate, bound, previous + 1)
                        event = await self.reader.read_projection_event(self._access(job), event_id)
                        await self._checkpoint(job, event, previous)
                        previous += 1
                        processed += 1
                        if max_events is not None and processed >= max_events:
                            return await self._job(gate, identity, operator, authorization)
                async with gate.begin_nested():
                    await self._verify(gate, job)
                    await self._finish(gate, job)
            except (PoolTimeout, TimeoutError, ConnectionError):
                raise
            except DBAPIError as error:
                code = getattr(error.orig, "sqlstate", "") or ""
                if (
                    error.connection_invalidated
                    or code[:2] in {"08", "40", "53", "57", "58"}
                    or code == "55P03"
                ):
                    raise
                await self.records.fail(gate, job, type(error).__name__)
            except (ValueError, OSError) as error:
                await self.records.fail(gate, job, type(error).__name__)
            return await self._job(gate, identity, operator, authorization)

    async def _checkpoint(self, job: RebuildJob, event: StoredEvent, previous: int) -> None:
        async with self.engine.begin() as connection:
            await apply_account_events(
                connection, [event], generation=job.generation, targets=job.target_relations
            )
            # 未被本生成器采用的事件只推进扫描位置，不冒充投影已应用。
            await self.records.advance(connection, job, event, previous)

    async def _verify(self, gate: AsyncConnection, job: RebuildJob) -> None:
        """按完整历史推导应有行集合，再逐表比较；防止漏行、多行和旧快照伪装最新值。"""
        expected: dict[str, dict[object, dict[str, object]]] = {t.name: {} for t in TABLES}
        applied: set[UUID] = set()
        for bound in job.scope_bounds:
            if await self.records.position(gate, job, bound) != bound.upper_seq:
                raise ValueError("Progress does not cover the fixed source range")
            for sequence in range(1, bound.upper_seq + 1):
                event_id = await self.records.event_id(gate, bound, sequence)
                event = await self.reader.read_projection_event(self._access(job), event_id)
                if event.draft.event_type not in EVENT_TYPES:
                    continue
                applied.add(event_id)
                rows = rows_for(event)
                for table in TABLES:
                    for row in rows[table.name]:
                        key = row[table.key]
                        if key in expected[table.name] and not table.update_columns:
                            raise ValueError("Immutable account fact identity is repeated")
                        expected[table.name][key] = row
        if await self.records.applied(gate, job) != applied:
            raise ValueError("Applied receipts differ from the account events actually handled")
        if set(expected["product.accounts"]) != {b.scope_id for b in job.scope_bounds}:
            raise ValueError("Selected account has no complete account fact")
        for table in TABLES:
            rows = (
                await gate.execute(text(f"SELECT * FROM {job.target_relations[table.name]}"))
            ).mappings()
            if {r[table.key]: dict(r) for r in rows} != expected[table.name]:
                raise ValueError(f"Account projection differs from source facts: {table.name}")
        self._check_relations(expected)

    @staticmethod
    def _check_relations(rows: dict[str, dict[object, dict[str, object]]]) -> None:
        """共享监护人的来源不在授权范围时拒绝；不依赖可能损坏的正式表补事实。"""
        accounts = rows["product.accounts"]
        guardians = rows["product.guardian_records"]
        relations = rows["product.student_guardian_relations"]
        confirmations = rows["product.usage_confirmations"]
        for row in relations.values():
            if row["student_id"] not in accounts or row["guardian_id"] not in guardians:
                raise ValueError(
                    "Guardian dependency outside selected facts; include its owning account scope"
                )
            previous = row["previous_relation_id"]
            if previous is not None:
                prior = relations.get(previous)
                if (
                    prior is None
                    or any(prior[key] != row[key] for key in ("student_id", "guardian_id"))
                    or int(str(prior["revision"])) >= int(str(row["revision"]))
                ):
                    raise ValueError("Previous guardian relationship is missing or unrelated")
        for row in confirmations.values():
            if row["student_id"] not in accounts:
                raise ValueError("Confirmation belongs to an unselected account")
        for row in rows["product.usage_conditions"].values():
            if row["student_id"] not in accounts:
                raise ValueError("Usage condition belongs to an unselected account")
            condition = ConditionsFact.model_validate(
                {key: row[key] for key in ConditionsFact.model_fields}
            )
            for ref in condition.confirmation_refs:
                referenced = confirmations.get(UUID(ref.id))
                if (
                    ref.owner != "product"
                    or ref.type != "usage_confirmation"
                    or referenced is None
                    or referenced["student_id"] != condition.student_id
                ):
                    raise ValueError("Usage condition refers to missing or unrelated confirmation")

    async def _finish(self, gate: AsyncConnection, job: RebuildJob) -> None:
        """只替换本次业务范围；控制数据不删除，共享监护人不因局部重建被清理。"""
        scopes = [b.scope_id for b in job.scope_bounds]
        # 先删除范围内不应存在的从表行；跨范围引用由外键拒绝，整批保持原样。
        for table in reversed(TABLES):
            if table.name in {"product.accounts", "product.guardian_records"}:
                continue
            await gate.execute(
                text(
                    f"DELETE FROM {table.name} t WHERE t.student_id=ANY(:scopes) AND NOT EXISTS "
                    f"(SELECT 1 FROM {job.target_relations[table.name]} s "
                    f"WHERE s.{table.key}=t.{table.key})"
                ),
                {"scopes": scopes},
            )
        for table in TABLES:
            assignments = ",".join(f"{c}=EXCLUDED.{c}" for c in table.columns if c != table.key)
            order = (
                " ORDER BY revision" if table.name == "product.student_guardian_relations" else ""
            )
            await gate.execute(
                text(
                    f"INSERT INTO {table.name} ({','.join(table.columns)}) "
                    f"SELECT {','.join(table.columns)} FROM {job.target_relations[table.name]} "
                    f"WHERE true{order} "
                    f"ON CONFLICT ({table.key}) DO UPDATE SET {assignments}"
                )
            )
            # 发布后的逐列差异必须为空；这里比较的是已修复数据，不要求旧数据原本正确。
            mismatch = await gate.scalar(
                text(
                    f"SELECT EXISTS(SELECT 1 FROM {job.target_relations[table.name]} s "
                    f"LEFT JOIN {table.name} t ON t.{table.key}=s.{table.key} "
                    "WHERE to_jsonb(s) IS DISTINCT FROM to_jsonb(t))"
                )
            )
            if mismatch:
                raise ValueError("Published account projection differs from verified copy")
        await self.records.publish(
            gate,
            job,
            [
                CheckIssue(
                    code="SOURCE_MATCH",
                    path="account_views",
                    message="账号、监护关系、确认及当前使用条件的行集合、来源和进度核对通过",
                )
            ],
        )
        for destination in reversed(list(job.target_relations.values())):
            await gate.execute(text(f"DROP TABLE {destination}"))
