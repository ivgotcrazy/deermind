"""账号业务的停写重建：固定事实范围，生成隔离副本，核对后原子发布五张查询表。"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from deermind.abstractions.events import StoredEvent
from deermind.foundation.system.events.query import EventReader
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
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class AccountRebuildSpec:
    implementation_digest: str


class AccountRebuilder:
    """生成和校验均归账号业务；底座只提供事件读取及维护控制记录。"""

    def __init__(
        self,
        reader: EventReader,
        spec: AccountRebuildSpec,
        records: ProjectionRecords,
    ) -> None:
        self.reader, self.spec = reader, spec
        self.records = records

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
            # 维护请求未授权或不存在，不能读取重建作业。
            raise PermissionError("Rebuild is not available to this maintenance request")
        return job

    async def rebuild(
        self,
        identity: UUID,
        generation: int,
        scopes: Sequence[UUID],
        *,
        operator: str,
        authorization: str,
    ) -> RebuildJob:
        """按完整范围重建；重发相同请求只查结果，重做须使用新身份和代次。"""
        if (
            type(generation) is not int
            or generation <= 1
            or not scopes
            or len(set(scopes)) != len(scopes)
            or not operator.strip()
            or not authorization.strip()
        ):
            # 重建必须显式指定代次、非空且不重复的范围及维护授权。
            raise ValueError(
                "Explicit generation, scopes and maintenance authorization are required"
            )
        scopes = sorted(scopes, key=str)
        async with self._guard() as gate:
            existing = await self.records.get(gate, identity, operator, authorization)
            if existing:
                if (
                    existing.projector_id != PROJECTOR_ID
                    or existing.generation != generation
                    or any(b.scope_kind != "account" for b in existing.scope_bounds)
                    or [b.scope_id for b in existing.scope_bounds] != scopes
                ):
                    # 同一重建身份的参数不可中途改动。
                    raise ValueError("Existing rebuild parameters cannot be changed")
                if existing.state == "building":
                    # 遗留未完成作业不能复用，须换身份与新代次重做。
                    raise ValueError("Legacy unfinished rebuild; use a new identity and generation")
                # 已结束作业直接返回既有结果，幂等重放。
                return existing
            bounds = await self.records.bounds(gate, "account", scopes)
            now = await gate.scalar(text("SELECT clock_timestamp()"))
            if not isinstance(now, datetime):
                # 取数据库时钟失败属内部环境错误。
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
            await self.records.create(gate, job)
            try:
                # 副本、生成收据、正式替换与成功事件一起回滚，外层可单独保存失败结果。
                async with gate.begin_nested():
                    await self._build(gate, job)
                    await self._verify(gate, job)
                    await self._finish(gate, job)
            except Exception as error:
                if gate.invalidated:
                    # 连接已失效，作业状态无法落库，直接上抛。
                    raise
                # 其余失败记录为 failed 结果，事务由外层回滚。
                await self.records.result(gate, job, "failed", type(error).__name__)
            return await self._job(gate, identity, operator, authorization)

    async def status(self, identity: UUID, *, operator: str, authorization: str) -> RebuildJob:
        async with self.records.guard() as gate:
            return await self._job(gate, identity, operator, authorization)

    async def _events(self, gate: AsyncConnection, job: RebuildJob) -> AsyncGenerator[StoredEvent]:
        for bound in job.scope_bounds:
            after = 0
            # 按范围分批扫描，逐事件交出。
            while after < bound.upper_seq:
                # 单个目标事实可含大附件；每次只保留一个解包后的事件。
                page = await self.reader.scan_scope(
                    gate,
                    bound.scope_kind,
                    bound.scope_id,
                    after_seq=after,
                    upper_seq=bound.upper_seq,
                    types=EVENT_TYPES,
                    limit=1,
                )
                for event in page.events:
                    yield event
                after = page.scanned_through_seq

    async def _build(self, gate: AsyncConnection, job: RebuildJob) -> None:
        """副本只在本次事务内存在；正式外键约束仍在发布时检查。"""
        for table in TABLES:
            target = job.target_relations[table.name]
            await gate.execute(text(f"CREATE TABLE {target} (LIKE {table.name} INCLUDING ALL)"))
            await gate.execute(text(f"REVOKE ALL ON {target} FROM deermind_app, PUBLIC"))
        async for event in self._events(gate, job):
            await apply_account_events(
                gate, [event], generation=job.generation, targets=job.target_relations
            )

    async def _verify(self, gate: AsyncConnection, job: RebuildJob) -> None:
        """按完整历史推导应有行集合，再逐表比较；防止漏行、多行和旧快照伪装最新值。"""
        expected: dict[str, dict[object, dict[str, object]]] = {t.name: {} for t in TABLES}
        applied: set[UUID] = set()
        async for event in self._events(gate, job):
            applied.add(event.draft.event_id)
            rows = rows_for(event)
            for table in TABLES:
                for row in rows[table.name]:
                    key = row[table.key]
                    if key in expected[table.name] and not table.update_columns:
                        # 不可变事实表不得重复同一身份。
                        raise ValueError("Immutable account fact identity is repeated")
                    expected[table.name][key] = row
        if await self.records.applied(gate, job) != applied:
            # 已应用收据集合须与实际处理过的事件一致。
            raise ValueError("Applied receipts differ from the account events actually handled")
        if set(expected["product.accounts"]) != {b.scope_id for b in job.scope_bounds}:
            # 每个被选账号都必须有完整账号事实，不能缺主记录。
            raise ValueError("Selected account has no complete account fact")
        for table in TABLES:
            rows = (
                await gate.execute(text(f"SELECT * FROM {job.target_relations[table.name]}"))
            ).mappings()
            if {r[table.key]: dict(r) for r in rows} != expected[table.name]:
                # 副本行集合与由历史推导的应有行不一致。
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
                # 依赖的学生或监护人不在所选事实范围内。
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
                    # 前序关系缺失、对象不符或版本未递增。
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
                    # 条件引用的确认记录缺失、类型不符或归属他人。
                    raise ValueError("Usage condition refers to missing or unrelated confirmation")

    async def _finish(self, gate: AsyncConnection, job: RebuildJob) -> None:
        """只替换本次业务范围；控制数据不删除，共享监护人不因局部重建被清理。"""
        scopes = [b.scope_id for b in job.scope_bounds]
        # 先删除范围内不应存在的从表行；跨范围引用由外键拒绝，整批保持原样。
        for table in reversed(TABLES):
            if table.name in {"product.accounts", "product.guardian_records"}:
                # 主表与监护人表由整表覆盖，不从表先行删除。
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
                # 发布后的正式表与已校验副本存在逐列差异，回滚本次重建。
                raise ValueError("Published account projection differs from verified copy")
        await self.records.publish(
            gate,
            job,
            [
                CheckIssue(
                    code="SOURCE_MATCH",
                    path="account_views",
                    message="账号、监护关系、确认及当前使用条件的行集合、来源和覆盖范围核对通过",
                )
            ],
        )
        # 发布核对通过后，逆序清理本次重建的隔离副本。
        for destination in reversed(list(job.target_relations.values())):
            await gate.execute(text(f"DROP TABLE {destination}"))
