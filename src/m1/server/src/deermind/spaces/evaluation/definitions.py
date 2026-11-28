"""读取、修订和保存 Task 的完整评价定义快照。"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.command_receipts import CommandReceipt, ReceiptCommands
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.domain.public import SolutionRef, TaskDefinition, TaskRef
from deermind.spaces.evaluation import definition_facts as facts
from deermind.spaces.evaluation.conditions import verify_schema
from deermind.spaces.evaluation.public import (
    MANAGE_CLAIM,
    STANDARD_ASPECTS,
    AspectDefinition,
    ClaimCommand,
    ClaimDefinition,
    ClaimDetail,
    ClaimList,
    ClaimReceipt,
    ClaimRef,
    ClaimResult,
    ClaimRow,
    ClaimView,
    CreateClaim,
    ExecutionCriterion,
    MethodDefinition,
    RemoveCriterion,
    SaveAspectRule,
    SaveClaim,
    SaveCriterion,
    SetMethodCriteria,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def _invalid(message: str, *, code: str = "invalid_reference") -> RequestError:
    return RequestError(409, code, message)


def _check_aspects(aspects: list[AspectDefinition]) -> None:
    codes = {a.code for a in aspects}
    # 方面代码去重后数量减少，说明存在重复定义。
    if len(codes) != len(aspects):
        raise _invalid("评价方面代码不能重复。")
    # 偏离默认方面集合时，至少一处要给变更理由，且新增非标准方面必须各自说明理由。
    if codes != STANDARD_ASPECTS.keys() and (
        not any(a.change_reason for a in aspects)
        or any(not a.change_reason for a in aspects if a.code not in STANDARD_ASPECTS)
    ):
        raise _invalid("调整默认评价方面时需要说明理由。")


def _gaps(definition: ClaimDefinition) -> list[Issue]:
    result: list[Issue] = []
    # 任务缺少任何直接方法，记整体缺口。
    if not definition.methods:
        result.append(Issue(code="missing_methods", path="/methods", message="任务没有直接方法。"))
    for index, method in enumerate(definition.methods):
        path = f"/methods/{index}"
        # 方法尚未挂任何执行判据。
        if not method.criterion_ids:
            result.append(
                Issue(
                    code="missing_criteria", path=path + "/criterion_ids", message="尚无执行判据。"
                )
            )
        rules = {rule.aspect_code for rule in method.aspect_rules}
        for aspect in definition.aspects:
            # 规则缺失或方面本身不受支持，分别记不同缺口码。
            if aspect.code not in rules or aspect.code not in STANDARD_ASPECTS:
                result.append(
                    Issue(
                        code="missing_aspect_rule"
                        if aspect.code not in rules
                        else "unsupported_aspect",
                        path=f"{path}/aspect_rules/{aspect.code}",
                        message=f"{aspect.label}尚未具备可用的评价规则。",
                    )
                )
    return result


def _revise(
    prior: ClaimDefinition,
    command: SaveClaim | SaveCriterion | SetMethodCriteria | SaveAspectRule | RemoveCriterion,
) -> tuple[ClaimDefinition, list[SolutionRef], list[UUID]]:
    """只修改新快照，保留 Task、方法顺序和已有判据身份。"""
    if isinstance(command, SaveClaim):
        _check_aspects(command.aspects)
        codes = {aspect.code for aspect in command.aspects}
        # 方面集合相对旧版有变化时，必须给出变更理由。
        if codes != {aspect.code for aspect in prior.aspects} and not any(
            aspect.change_reason for aspect in command.aspects
        ):
            raise _invalid("调整评价方面时需要说明理由。")
        methods = [
            method.model_copy(
                update={
                    "aspect_rules": [r for r in method.aspect_rules if r.aspect_code in codes],
                }
            )
            for method in prior.methods
        ]
        return (
            prior.model_copy(
                update={
                    "title": command.title,
                    "description": command.description,
                    "aspects": command.aspects,
                    "methods": methods,
                }
            ),
            [m.method_ref for m in methods if command.aspects != prior.aspects],
            [],
        )

    criteria = {c.criterion_id: c for c in prior.criteria}
    if isinstance(command, SaveCriterion | RemoveCriterion):
        identity = (
            command.criterion.criterion_id
            if isinstance(command, SaveCriterion)
            else command.criterion_id
        )
        # 已有判据必须归属于本主张，不得跨主张改动。
        if identity is not None and identity not in criteria:
            raise _invalid("判据不属于本 Claim。")
        identity = identity or uuid4()
        affected = [m.method_ref for m in prior.methods if identity in m.criterion_ids]
        if isinstance(command, RemoveCriterion):
            # 仍被方法引用的判据不能直接删除。
            if affected:
                raise _invalid("请先取消方法对该判据的引用。", code="criterion_in_use")
            del criteria[identity]
        else:
            criteria[identity] = ExecutionCriterion(
                **command.criterion.model_dump(exclude={"criterion_id"}),
                criterion_id=identity,
            )
        return prior.model_copy(update={"criteria": list(criteria.values())}), affected, [identity]

    existing = next((m for m in prior.methods if m.method_ref == command.method_ref), None)
    # 目标方法必须是该任务版本下的直接方法。
    if existing is None:
        raise _invalid("所选方法不是此版本任务的直接方法。")
    if isinstance(command, SetMethodCriteria):
        # 所选判据不得重复，且必须全部属于本主张。
        if (
            len(set(command.criterion_ids)) != len(command.criterion_ids)
            or not set(command.criterion_ids) <= criteria.keys()
        ):
            raise _invalid("请只选择本 Claim 的不同判据。")
        changed = existing.model_copy(update={"criterion_ids": command.criterion_ids})
    else:
        rule = command.rule
        # 规则挂接的方面必须是本主张已定义的方面。
        if rule.aspect_code not in {a.code for a in prior.aspects}:
            raise _invalid("所选评价方面不属于本 Claim。")
        try:
            verify_schema(rule.condition_schema, rule.default_values)
        except ValueError as error:
            # 条件模式与默认值不合法，转为 400 条件错误。
            raise RequestError(400, "invalid_condition", str(error)) from error
        rules = {item.aspect_code: item for item in existing.aspect_rules}
        rules[rule.aspect_code] = rule
        changed = existing.model_copy(update={"aspect_rules": list(rules.values())})
    return (
        prior.model_copy(
            update={
                "methods": [
                    changed if m.method_ref == changed.method_ref else m for m in prior.methods
                ],
            }
        ),
        [changed.method_ref],
        [],
    )


class ClaimDefinitions:
    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        reader: EventReader,
        attachments: FactAttachments,
        receipts: ReceiptCommands[AsyncConnection],
        task_guard: Callable[[AsyncConnection, UUID, TaskRef], Awaitable[TaskDefinition]],
    ) -> None:
        self.engine = engine
        self.events = events
        self.reader = reader
        self.attachments = attachments
        self.receipts = receipts
        self.task_guard = task_guard

    async def list_claims(
        self,
        principal: UUID,
        domain_id: UUID,
        task_id: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> ClaimList:
        token = sha256(
            canonical_json([str(principal), str(domain_id), str(task_id), name]).encode()
        ).hexdigest()
        after = None
        if cursor:
            prefix, _, position = cursor.partition(".")
            try:
                after = UUID(position)
            except ValueError as error:
                raise RequestError(400, "invalid_cursor", "续页位置无效。") from error
            # 游标前缀须与当前查询条件摘要一致，防止沿用旧条件翻页。
            if prefix != token:
                raise RequestError(400, "invalid_cursor", "查询条件变化，请重新读取列表。")
        async with self.engine.connect() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT c.claim_id,c.head_revision,c.task_id,c.task_version,"
                        "v.definition->>'title' AS title,v.gaps FROM evaluation.claim c "
                        "JOIN evaluation.claim_version v "
                        "ON (v.claim_id,v.revision)=(c.claim_id,c.head_revision) "
                        "WHERE c.domain_id=:domain "
                        "AND (CAST(:task AS uuid) IS NULL OR c.task_id=:task) "
                        "AND (CAST(:after AS uuid) IS NULL OR c.claim_id>:after) "
                        "AND strpos(lower(v.definition->>'title'),lower(:name))>0 "
                        "ORDER BY c.claim_id LIMIT :limit"
                    ),
                    {
                        "domain": domain_id,
                        "task": task_id,
                        "after": after,
                        "name": name,
                        "limit": limit + 1,
                    },
                )
            ).all()
        return ClaimList(
            items=[
                ClaimRow(
                    claim_ref=ClaimRef(claim_id=r.claim_id, revision=r.head_revision),
                    task_ref=TaskRef(kind="task", object_id=r.task_id, version=r.task_version),
                    title=r.title,
                    gaps=[Issue.model_validate(issue) for issue in r.gaps],
                )
                for r in rows[:limit]
            ],
            next_cursor=f"{token}.{rows[limit - 1].claim_id}" if len(rows) > limit else None,
        )

    async def _version(
        self, claim_id: UUID, revision: int | None
    ) -> tuple[facts.ClaimVersion, facts.ClaimChanged]:
        async with self.engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT c.domain_id,v.source_event_id FROM evaluation.claim c "
                        "JOIN evaluation.claim_version v USING(claim_id) "
                        "WHERE c.claim_id=:id "
                        "AND v.revision=COALESCE(CAST(:revision AS bigint),c.head_revision)"
                    ),
                    {"id": claim_id, "revision": revision},
                )
            ).one_or_none()
        # 未命中对应主张修订记录，返回 404。
        if row is None:
            raise RequestError(404, "not_found", "找不到指定 Claim 修订。")
        event_id = row.source_event_id
        raw = await self.reader.read_facts(
            "domain",
            row.domain_id,
            event_id,
            expected_event_type=facts.EVENT,
            refs=[
                EventPartRef(event_id=event_id, record_id=facts.RECORD_ID, path=""),
                EventPartRef(event_id=event_id, record_id=None, path=""),
            ],
        )
        items = raw["items"]
        assert isinstance(items, list) and isinstance(items[0], dict) and isinstance(items[1], dict)
        version = facts.ClaimVersion.model_validate_json(canonical_json(items[0]["content"]))
        payload = items[1]["content"]
        assert isinstance(payload, dict)
        event = facts.ClaimChanged.model_validate_json(canonical_json({**payload, "records": []}))
        return version, event

    async def detail(self, claim_id: UUID, revision: int | None) -> ClaimDetail:
        version, change = await self._version(claim_id, revision)
        return ClaimDetail(
            claim=ClaimView(
                claim_ref=change.claim_ref,
                definition=version.definition,
                gaps=version.gaps,
            )
        )

    async def _read_receipt(self, receipt: CommandReceipt) -> ClaimReceipt:
        reference = receipt.result_ref
        assert reference is not None and reference.revision is not None
        version, change = await self._version(UUID(reference.id), reference.revision)
        changed = version.request_ref == str(receipt.request_ref)
        return ClaimReceipt(
            request_ref=receipt.request_ref,
            result=ClaimResult(
                claim_ref=change.claim_ref,
                changed=changed,
                gaps=version.gaps,
                affected_method_refs=change.affected_method_refs if changed else [],
            ),
        )

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[ClaimResult]:
        async with self.engine.connect() as db:
            receipt = await self.receipts.find_completed_request(
                db,
                principal,
                MANAGE_CLAIM,
                query.resource_id,
                query.request_id,
            )
        # 找不到已完成的管理请求，回执记为未找到。
        if receipt is None:
            return ReceiptView[ClaimResult](receipt_state="not_found")
        saved = await self._read_receipt(receipt)
        return ReceiptView[ClaimResult](
            receipt_state="completed", receipt_ref=saved.request_ref, result=saved.result
        )

    async def save(self, principal: UUID, command: ClaimCommand) -> ClaimReceipt:
        normalized = command.model_dump(mode="json")
        async with self.engine.begin() as db:
            saved = await self.receipts.find_completed_request(
                db,
                principal,
                MANAGE_CLAIM,
                command.domain_id,
                command.request_id,
                normalized,
            )
            # 仅在无既有回执时才校验任务；已有回执直接复用其结果。
            task = (
                await self.task_guard(db, command.domain_id, command.task_ref)
                if saved is None
                else None
            )
        if saved is not None:
            # 同一请求已完成，幂等返回既有回执结果。
            return await self._read_receipt(saved)
        assert task is not None
        previous = None
        # 新建分支：以任务下已有方法构造初始空定义。
        if isinstance(command, CreateClaim):
            _check_aspects(command.aspects)
            reference = ClaimRef(claim_id=uuid4(), revision=1)
            definition = ClaimDefinition(
                domain_id=command.domain_id,
                task_ref=command.task_ref,
                title=command.title,
                description=command.description,
                aspects=command.aspects,
                criteria=[],
                methods=[
                    MethodDefinition(method_ref=m, criterion_ids=[], aspect_rules=[])
                    for m in task.method_refs
                ],
            )
            affected, criteria = task.method_refs, []
        else:
            prior, _ = await self._version(command.claim_id, command.expected_revision)
            # 旧定义的领域与任务版本必须与命令指定的一致。
            if (prior.definition.domain_id, prior.definition.task_ref) != (
                command.domain_id,
                command.task_ref,
            ):
                raise _invalid("Claim 与指定 Task 版本不一致。")
            previous = ClaimRef(claim_id=prior.claim_id, revision=prior.revision)
            definition, affected, criteria = _revise(prior.definition, command)
            reference = ClaimRef(
                claim_id=prior.claim_id,
                revision=prior.revision + int(definition != prior.definition),
            )

        gaps, request_ref = _gaps(definition), uuid4()
        result_ref = Ref(
            owner="evaluation",
            type="claim",
            id=str(reference.claim_id),
            revision=reference.revision,
        )
        changed = reference != previous
        scope = ("domain", command.domain_id)
        actor = Ref(owner="product", type="account", id=str(principal))
        access = ProducerAccess("evaluation", actor, frozenset({scope}))
        prepared = None
        # 仅当定义确有变更时才构造待落库事件。
        if changed:
            version = facts.ClaimVersion(
                claim_id=reference.claim_id,
                revision=reference.revision,
                definition=definition,
                gaps=gaps,
                request_ref=str(request_ref),
                actor_ref=actor,
                created_at=datetime.now(UTC),
            )
            change = facts.ClaimChanged(
                domain_id=command.domain_id,
                task_ref=command.task_ref,
                previous_claim_ref=previous,
                claim_ref=reference,
                action=command.action,
                affected_method_refs=affected,
                affected_criterion_ids=criteria,
                request_ref=request_ref,
                records=[
                    FactRecord(
                        record_id=facts.RECORD_ID,
                        record_type=facts.RECORD,
                        schema_version=1,
                        content=InlineContent(
                            storage="inline", value=version.model_dump(mode="json")
                        ),
                    )
                ],
            )
            draft = EventDraft(
                uuid4(),
                facts.EVENT,
                1,
                *scope,
                result_ref,
                change.model_dump(mode="json"),
                command.request_id,
            )
            prepared = await self.attachments.prepare(self.events, access, (draft,))

        async with self.engine.begin() as db:
            receipt = await self.receipts.claim_request(
                db,
                principal_id=str(principal),
                action=MANAGE_CLAIM,
                scope_id=str(command.domain_id),
                request_id=command.request_id,
                normalized_input=normalized,
                reserved_ref=request_ref,
            )
            # 回执尚无结果引用，才进入本次落库流程。
            if receipt.result_ref is None:
                await self.task_guard(db, command.domain_id, command.task_ref)
                await self._guard_head(db, command, previous)
                if prepared is not None:
                    sequence = await lock_scope_sequence(db, *scope)
                    (stored,) = await self.events.append(
                        db,
                        access,
                        prepared,
                        commit_id=uuid4(),
                        correlation_id=request_ref,
                        expected_seq={scope: sequence},
                    )
                    await facts.project(db, stored)
                await self.receipts.complete_request(db, receipt, result_ref)
                return ClaimReceipt(
                    request_ref=request_ref,
                    result=ClaimResult(
                        claim_ref=reference,
                        changed=changed,
                        gaps=gaps,
                        affected_method_refs=affected if changed else [],
                    ),
                )
        return await self._read_receipt(receipt)

    async def _guard_head(
        self, db: AsyncConnection, command: ClaimCommand, previous: ClaimRef | None
    ) -> None:
        row = (
            await db.execute(
                text(
                    "SELECT claim_id,head_revision FROM evaluation.claim WHERE domain_id=:domain "
                    "AND task_id=:task AND task_version=:version AND model_id IS NULL FOR UPDATE"
                ),
                {
                    "domain": command.domain_id,
                    "task": command.task_ref.object_id,
                    "version": command.task_ref.version,
                },
            )
        ).one_or_none()
        # 新建主张时该任务版本已存在 Claim，拒绝重复创建。
        if previous is None and row is not None:
            raise RequestError(
                409,
                "claim_exists",
                "此 Task 版本已有 Claim。",
                issues=[
                    Issue(
                        code="claim_exists",
                        path="/task_ref",
                        message="请选择现有 Claim。",
                        related_ref=Ref(
                            owner="evaluation",
                            type="claim",
                            id=str(row.claim_id),
                            revision=row.head_revision,
                        ),
                    )
                ],
            )
        # 修订时头指针已被改动（缺失或编号不一致），判修订冲突。
        if previous is not None and (
            row is None
            or (row.claim_id, row.head_revision) != (previous.claim_id, previous.revision)
        ):
            raise _invalid("Claim 已有新的修订，请重新读取。", code="revision_conflict")
