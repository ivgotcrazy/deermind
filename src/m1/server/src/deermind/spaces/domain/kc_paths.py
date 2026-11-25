"""确认固定 Task、Solution 和 KC 能组成直接检验路径。"""

from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.projections.receipts import application
from deermind.foundation.system.public.errors import ErrorDetail, Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.domain.facts import version_ref
from deermind.spaces.domain.kc_path_facts import (
    ARTIFACT_TYPE,
    CONFIRMED,
    NOT_READY,
    PATH_TYPE,
    KCPathEvent,
    PathArtifact,
    PathBasis,
    PathRecord,
    basis_ref,
    path_records,
    path_ref,
)
from deermind.spaces.domain.public import (
    CONFIRM_PATH_ACTION,
    ConfirmKCPathRequest,
    ConfirmKCPathResponse,
    ConfirmKCPathResult,
    KCPathView,
    KnowledgeRef,
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
    TaskRef,
    solution_gaps,
    task_gaps,
)
from deermind.spaces.domain.relationships import relationship_error

_RECEIPT = text(
    "SELECT receipt_id,input_hash,normalized_input,state,result_ref,error,input_artifact_id "
    "FROM domain.command_receipt WHERE principal_id=:principal AND action=:action "
    "AND scope_id=:scope AND request_id=:request_id"
)
_EXISTING = text(
    "SELECT confirmation_id,basis_artifact_id FROM domain.kc_test_path "
    "WHERE (task_id,task_version,solution_id,solution_version,kc_id,kc_version)="
    "(:task_id,:task_version,:solution_id,:solution_version,:kc_id,:kc_version)"
)
_VERSIONS = text(
    "SELECT i.object_id,v.version,i.kind,v.content FROM "
    "unnest(CAST(:ids AS uuid[]),CAST(:versions AS bigint[])) AS selected(object_id,version) "
    "JOIN domain.object_identity i ON i.object_id=selected.object_id "
    "JOIN domain.object_version v ON (v.object_id,v.version)=(i.object_id,selected.version) "
    "JOIN domain.object_version h ON (h.object_id,h.version)=(i.object_id,i.head_version) "
    "WHERE i.domain_id=:domain AND NOT v.is_deleted AND NOT h.is_deleted"
)


def _key(principal: UUID, domain: UUID, request_id: str) -> dict[str, str]:
    return {
        "principal": canonical_json(["product", "account", str(principal)]),
        "action": CONFIRM_PATH_ACTION,
        "scope": str(domain),
        "request_id": request_id,
    }


def _ref_keys(body: ConfirmKCPathRequest) -> dict[str, UUID | int]:
    return {
        "kc_id": body.kc_ref.object_id,
        "kc_version": body.kc_ref.version,
        "task_id": body.task_ref.object_id,
        "task_version": body.task_ref.version,
        "solution_id": body.solution_ref.object_id,
        "solution_version": body.solution_ref.version,
    }


def _receipt(row: RowMapping) -> ReceiptView[ConfirmKCPathResult]:
    if row["state"] == "failed":
        # 失败回执转为拒绝视图，带回依据产物引用。
        error = ErrorDetail.model_validate(row["error"])
        return ReceiptView[ConfirmKCPathResult](
            receipt_state="rejected",
            receipt_ref=row["receipt_id"],
            business_state="not_ready",
            error=error,
            result_refs=[basis_ref(row["input_artifact_id"])],
        )
    if row["state"] != "completed":
        raise RuntimeError("A KC path receipt must commit with its outcome")
    return ReceiptView[ConfirmKCPathResult](
        receipt_state="completed",
        receipt_ref=row["receipt_id"],
        business_state="committed",
        result=ConfirmKCPathResult(confirmation_ref=Ref.model_validate(row["result_ref"])),
    )


def _response(receipt: ReceiptView[ConfirmKCPathResult]) -> ConfirmKCPathResponse:
    if receipt.error is not None:
        # 回执带业务错误，转成 409 抛出。
        raise RequestError(
            409, receipt.error.code, receipt.error.message, issues=receipt.error.issues
        )
    assert receipt.receipt_ref is not None and receipt.result is not None
    return ConfirmKCPathResponse(request_ref=receipt.receipt_ref, result=receipt.result)


def _replay(row: RowMapping, normalized: str, digest: str) -> ConfirmKCPathResponse:
    if row["input_hash"] != digest or canonical_json(row["normalized_input"]) != normalized:
        # 同编号对应不同输入，幂等键冲突。
        raise RequestError(409, "request_conflict", "请求编号已用于其他内容。")
    return _response(_receipt(row))


async def _check_path(
    connection: AsyncConnection, domain: UUID, body: ConfirmKCPathRequest
) -> list[Issue]:
    named_refs = (
        ("kc_ref", body.kc_ref),
        ("task_ref", body.task_ref),
        ("solution_ref", body.solution_ref),
    )
    rows = await connection.execute(
        _VERSIONS,
        {
            "domain": domain,
            "ids": [ref.object_id for _, ref in named_refs],
            "versions": [ref.version for _, ref in named_refs],
        },
    )
    by_ref = {(row.kind, row.object_id, row.version): row.content for row in rows}
    for field, ref in named_refs:
        if (ref.kind, ref.object_id, ref.version) not in by_ref:
            # 版本已删、不存在或跨领域，按引用错误抛出。
            raise relationship_error(f"/{field}", "引用的版本不存在、已移除或不属于本领域。")
    task = TaskDefinition.model_validate(
        by_ref["task", body.task_ref.object_id, body.task_ref.version]
    )
    method = SolutionDefinition.model_validate(
        by_ref["solution", body.solution_ref.object_id, body.solution_ref.version]
    )
    if body.solution_ref not in task.method_refs:
        # 任务→方法须为直接采用关系。
        raise relationship_error("/solution_ref", "指定版本的方法必须由该任务版本直接采用。")
    if body.kc_ref not in method.kc_refs:
        # 方法→KC 须为直接引用关系。
        raise relationship_error("/kc_ref", "指定版本的知识成分必须由该方法版本直接引用。")
    issues = [
        issue.model_copy(update={"path": f"/task_ref{issue.path}"})
        for issue in task_gaps(task)
        if issue.path in {"/responsibility", "/expected_output", "/completion_conditions"}
    ] + [
        issue.model_copy(update={"path": f"/solution_ref{issue.path}"})
        for issue in solution_gaps(method)
        if issue.path in {"/rationale", "/applicability", "/key_process"}
    ]
    if body.not_direct_reason is not None:
        # 人工说明路径不直接的原因，作为补充问题留档。
        issues.append(
            Issue(code="not_direct", path="/not_direct_reason", message=body.not_direct_reason)
        )
    return issues


def _record(record_type: str, identity: UUID, body: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=record_type,
        schema_version=1,
        content=InlineContent(storage="inline", value=body.model_dump(mode="json")),
    )


async def _project(connection: AsyncConnection, event: StoredEvent) -> None:
    assert isinstance(event.payload, KCPathEvent)
    artifact, path = path_records(event.payload)
    async with application(connection, "domain.kc_test_paths.v1", 1, event.draft.event_id) as apply:
        if not apply:
            # 已被回执投影处理过，跳过落表。
            return
        await connection.execute(
            text(
                "INSERT INTO domain.artifact "
                "(artifact_id,domain_id,kind,definition_refs,payload,"
                "command_ref,created_at,source_event_id) "
                "VALUES (:artifact_id,:domain_id,:kind,CAST(:definitions AS jsonb),"
                "CAST(:basis AS jsonb),CAST(:command AS jsonb),:created_at,:event)"
            ),
            {
                "artifact_id": artifact.artifact_id,
                "domain_id": artifact.domain_id,
                "kind": artifact.kind,
                "definitions": canonical_json(
                    [ref.model_dump(mode="json") for ref in artifact.definition_refs]
                ),
                "basis": artifact.payload.model_dump_json(),
                "command": artifact.command_ref.model_dump_json(),
                "created_at": artifact.created_at,
                "event": event.draft.event_id,
            },
        )
        if path is not None:
            # 仅确认通过的记录落 kc_test_path 表；不足依据只落 artifact。
            await connection.execute(
                text(
                    "INSERT INTO domain.kc_test_path "
                    "(confirmation_id,kc_id,kc_version,task_id,task_version,solution_id,"
                    "solution_version,basis_artifact_id,confirmed_by,confirmed_at,source_event_id) "
                    "VALUES (:confirmation_id,:kc_id,:kc_version,:task_id,:task_version,"
                    ":solution_id,:solution_version,:basis_artifact_id,"
                    "CAST(:confirmed_by AS jsonb),:confirmed_at,:event)"
                ),
                {
                    **path.model_dump(mode="python"),
                    "confirmed_by": path.confirmed_by.model_dump_json(),
                    "event": event.draft.event_id,
                },
            )


async def read_task_paths(
    connection: AsyncConnection, task: TaskRef, methods: list[SolutionRef]
) -> list[KCPathView]:
    """读取所选方法和固定任务版本的确认，包含历史依据。"""
    if not methods:
        # 未指定方法时无路径可读。
        return []
    methods_by_key = {(ref.object_id, ref.version): ref for ref in methods}
    rows = await connection.execute(
        text(
            "SELECT p.*,a.payload FROM domain.kc_test_path p "
            "JOIN domain.artifact a ON a.artifact_id=p.basis_artifact_id "
            "WHERE p.task_id=:id AND p.task_version=:version "
            "ORDER BY p.confirmed_at,p.confirmation_id"
        ),
        {"id": task.object_id, "version": task.version},
    )
    result: list[KCPathView] = []
    for row in rows:
        method = methods_by_key.get((row.solution_id, row.solution_version))
        if method is None:
            # 路径关联的方法不在本次所选范围内，跳过。
            continue
        basis = PathBasis.model_validate(row.payload)
        result.append(
            KCPathView(
                confirmation_ref=path_ref(row.confirmation_id),
                basis_ref=basis_ref(row.basis_artifact_id),
                kc_ref=KnowledgeRef(kind="kc", object_id=row.kc_id, version=row.kc_version),
                task_ref=task,
                solution_ref=method,
                observable_behavior=basis.observable_behavior,
                insufficient_examples=basis.insufficient_examples,
                confirmed_by=Ref.model_validate(row.confirmed_by),
                confirmed_at=row.confirmed_at,
                source_event_id=row.source_event_id,
            )
        )
    return result


class KCTestPaths:
    def __init__(
        self, engine: AsyncEngine, events: EventStore, attachments: FactAttachments
    ) -> None:
        self.engine = engine
        self.events = events
        self.attachments = attachments

    async def confirm(
        self, actor_id: UUID, domain: UUID, body: ConfirmKCPathRequest
    ) -> ConfirmKCPathResponse:
        key = _key(actor_id, domain, body.request_id)
        normalized = canonical_json(body.model_dump(mode="json", exclude={"request_id"}))
        digest = sha256(normalized.encode()).hexdigest()
        async with self.engine.connect() as connection:
            previous = (await connection.execute(_RECEIPT, key)).mappings().one_or_none()
            if previous is not None:
                # 同请求编号已有回执，按幂等重放校验后返回。
                return _replay(previous, normalized, digest)
            issues = await _check_path(connection, domain, body)
            now = await connection.scalar(text("SELECT clock_timestamp()"))
        assert isinstance(now, datetime)

        request_id, artifact_id, confirmation_id = uuid4(), uuid4(), uuid4()
        actor = Ref(owner="product", type="account", id=str(actor_id))
        refs = [version_ref(ref) for ref in (body.kc_ref, body.task_ref, body.solution_ref)]
        basis = PathBasis(
            outcome="not_ready" if issues else "confirmed",
            responsibility_ref=refs[1].model_copy(update={"path": "/responsibility"}),
            observable_behavior=body.observable_behavior,
            insufficient_examples=body.insufficient_examples,
            issues=issues,
        )
        artifact = PathArtifact(
            artifact_id=artifact_id,
            domain_id=domain,
            definition_refs=refs,
            payload=basis,
            command_ref=Ref(owner="domain", type="command_receipt", id=str(request_id)),
            created_at=now,
        )
        rows = [_record(ARTIFACT_TYPE, artifact_id, artifact)]
        related = None
        if not issues:
            # 校验无缺口才生成确认记录；有缺口只落依据产物。
            keys = _ref_keys(body)
            path = PathRecord.model_validate(
                {
                    **keys,
                    "confirmation_id": confirmation_id,
                    "basis_artifact_id": artifact_id,
                    "confirmed_by": actor,
                    "confirmed_at": now,
                }
            )
            rows.append(_record(PATH_TYPE, confirmation_id, path))
            related = path_ref(confirmation_id)

        check_ref = basis_ref(artifact_id)
        event = KCPathEvent(
            records=rows,
            confirmation_ref=related,
            basis_ref=check_ref,
            kc_ref=body.kc_ref,
            task_ref=body.task_ref,
            solution_ref=body.solution_ref,
            request_ref=request_id,
        )
        scope = ("domain", domain)
        access = ProducerAccess("domain", actor, frozenset({scope}))
        draft = EventDraft(
            event_id=uuid4(),
            event_type=NOT_READY if issues else CONFIRMED,
            schema_version=1,
            scope_kind="domain",
            scope_id=domain,
            owner_ref=related or check_ref,
            payload=event.model_dump(mode="json"),
            source_request_id=body.request_id,
        )
        try:
            prepared = await self.attachments.prepare(self.events, access, (draft,))
        except OSError as error:
            # 附件落盘失败按临时不可用返回，不污染业务状态。
            raise RequestError(503, "temporarily_unavailable", "暂时无法保存检验依据。") from error

        async with self.engine.begin() as connection:
            claimed = await connection.scalar(
                text(
                    "INSERT INTO domain.command_receipt "
                    "(receipt_id,principal_id,action,scope_id,request_id,"
                    "normalized_input,input_hash,state,created_at,updated_at) VALUES "
                    "(:id,:principal,:action,:scope,:request_id,CAST(:body AS jsonb),:digest,"
                    "'accepted',clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT (principal_id,action,scope_id,request_id) DO NOTHING "
                    "RETURNING receipt_id"
                ),
                {**key, "id": request_id, "body": normalized, "digest": digest},
            )
            if claimed is None:
                # 并发下回执被他方插入，转走幂等重放分支。
                row = (await connection.execute(_RECEIPT, key)).mappings().one()
                return _replay(row, normalized, digest)

            root = await connection.scalar(
                text(
                    "SELECT i.object_id FROM domain.object_identity i "
                    "JOIN domain.object_version v ON "
                    "(v.object_id,v.version)=(i.object_id,i.head_version) "
                    "WHERE i.object_id=:id AND i.kind='domain' AND NOT v.is_deleted FOR UPDATE OF i"
                ),
                {"id": domain},
            )
            if root is None:
                # 领域身份已删除或不存在，拒绝写入。
                raise RequestError(404, "not_found", "找不到指定领域。")
            # 条件正文来自固定版本，锁内重查活动身份和固定关系。
            await _check_path(connection, domain, body)
            existing = (
                (await connection.execute(_EXISTING, _ref_keys(body))).one_or_none()
                if not issues
                else None
            )
            if existing is not None:
                # 同一三元组已有确认记录，复用原依据，避免重复投影。
                related = path_ref(existing.confirmation_id)
                artifact_id = existing.basis_artifact_id
            else:
                sequence = await connection.scalar(
                    text(
                        "SELECT last_seq FROM runtime.scope_event_heads "
                        "WHERE scope_kind='domain' AND scope_id=:id"
                    ),
                    {"id": domain},
                )
                assert isinstance(sequence, int)
                (stored,) = await self.events.append(
                    connection,
                    access,
                    prepared,
                    commit_id=uuid4(),
                    correlation_id=request_id,
                    expected_seq={scope: sequence},
                )
                await _project(connection, stored)
            rejection = (
                ErrorDetail(
                    code="not_ready",
                    message="已记录检验依据不足。",
                    issues=[
                        *issues,
                        Issue(
                            code="basis", path="/basis", message="不足记录", related_ref=check_ref
                        ),
                    ],
                    retryable=False,
                )
                if issues
                else None
            )
            await connection.execute(
                text(
                    "UPDATE domain.command_receipt SET state=:state,"
                    "result_ref=CAST(:result AS jsonb),"
                    "input_artifact_id=:artifact,error=CAST(:error AS jsonb),"
                    "updated_at=clock_timestamp() WHERE receipt_id=:receipt"
                ),
                {
                    "receipt": request_id,
                    "state": "failed" if issues else "completed",
                    "result": related.model_dump_json(exclude_none=True) if related else None,
                    "artifact": artifact_id,
                    "error": rejection.model_dump_json() if rejection else None,
                },
            )
            row = (await connection.execute(_RECEIPT, key)).mappings().one()
        return _response(_receipt(row))

    async def read_receipt(
        self, principal: UUID, query: ReceiptQuery
    ) -> ReceiptView[ConfirmKCPathResult]:
        if query.action != CONFIRM_PATH_ACTION or query.resource_kind != "domain":
            # 收据只对本动作、本领域开放查询。
            raise RequestError(400, "invalid_request", "该路径确认收据不可查询。")
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        _RECEIPT, _key(principal, query.resource_id, query.request_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            # 无对应回执，返回未找到视图。
            return ReceiptView[ConfirmKCPathResult](receipt_state="not_found")
        return _receipt(row)
