"""领域、知识成分及其固定版本的读写。"""

from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.projections.receipts import application
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import SessionView
from deermind.spaces.domain.facts import (
    EVENT_TYPE,
    RECORD_ID,
    RECORD_TYPE,
    DomainSaved,
    DomainVersion,
    version_content,
    version_ref,
)
from deermind.spaces.domain.public import (
    SAVE_ACTION,
    CreateDomainRequest,
    CreateDomainResponse,
    CreateDomainResult,
    CreateKnowledgeRequest,
    CreateTaskRequest,
    DeleteKnowledgeRequest,
    DeleteTaskRequest,
    DomainContentRef,
    DomainDefinition,
    DomainDetail,
    DomainList,
    DomainRef,
    DomainRow,
    DomainView,
    KnowledgeComponent,
    KnowledgeContentRef,
    KnowledgeDetail,
    KnowledgeRef,
    KnowledgeView,
    MemberKind,
    MemberList,
    MemberRef,
    MemberRow,
    ObjectDetail,
    ObjectRef,
    SaveKnowledgeResult,
    SaveRequest,
    SaveResult,
    SaveTaskResult,
    TaskContentRef,
    TaskDefinition,
    TaskDetail,
    TaskRef,
    TaskView,
    UpdateKnowledgeRequest,
    UpdateTaskRequest,
    task_gaps,
)

_RECEIPT = text(
    "SELECT r.receipt_id,r.input_hash,r.normalized_input,r.state,r.result_ref,v.content "
    "FROM domain.command_receipt r LEFT JOIN domain.object_version v "
    "ON r.result_ref->>'type'='task' AND v.object_id=CAST(r.result_ref->>'id' AS uuid) "
    "AND v.version=CAST(r.result_ref->>'version' AS bigint) "
    "WHERE r.principal_id=:principal AND r.action=:action "
    "AND r.scope_id=:scope AND r.request_id=:request_id"
)
_ROOT = (
    "SELECT i.catalog_revision FROM domain.object_identity i "
    "JOIN domain.object_version v ON (v.object_id,v.version)=(i.object_id,i.head_version) "
    "WHERE i.object_id=:id AND i.kind='domain' AND NOT v.is_deleted"
)
_VERSION = text(
    "SELECT i.kind,i.domain_id,v.version,v.source_event_id,head.is_deleted "
    "FROM domain.object_identity i "
    "JOIN domain.object_version head ON (head.object_id,head.version)=(i.object_id,i.head_version) "
    "JOIN domain.object_version v ON v.object_id=i.object_id "
    "AND v.version=COALESCE(CAST(:version AS bigint),i.head_version) "
    "WHERE i.object_id=:id AND i.kind IN ('domain','kc','task') "
    "AND (CAST(:version AS bigint) IS NOT NULL OR NOT head.is_deleted)"
)


def administrator(session: SessionView) -> UUID:
    if session.account.role != "admin":
        raise RequestError(403, "forbidden", "当前账号无领域管理权限。")
    return session.account.account_id


def receipt_key(principal_id: UUID, request_id: str) -> dict[str, str]:
    return {
        "principal": canonical_json(["product", "account", str(principal_id)]),
        "action": SAVE_ACTION,
        "scope": str(principal_id),
        "request_id": request_id,
    }


def save_result(
    ref: ObjectRef, content: DomainDefinition | KnowledgeComponent | TaskDefinition | None = None
) -> SaveResult:
    if isinstance(ref, KnowledgeRef):
        return SaveKnowledgeResult(object_ref=ref, content_ref=KnowledgeContentRef(object_ref=ref))
    if isinstance(ref, TaskRef):
        if not isinstance(content, TaskDefinition):
            raise RuntimeError("A Task receipt must reference its fixed definition")
        return SaveTaskResult(
            object_ref=ref, content_ref=TaskContentRef(object_ref=ref), gaps=task_gaps(content)
        )
    return CreateDomainResult(object_ref=ref, content_ref=DomainContentRef(object_ref=ref))


def saved_response(row: RowMapping) -> CreateDomainResponse:
    if row["state"] != "completed":
        raise RuntimeError("A domain save receipt must be committed with its result")
    saved = Ref.model_validate(row["result_ref"])
    task = None
    if saved.owner == "domain" and saved.type == "domain" and saved.version == 1:
        ref = DomainRef(object_id=UUID(saved.id), version=1)
    elif saved.owner == "domain" and saved.type == "kc" and saved.version is not None:
        ref = KnowledgeRef(kind="kc", object_id=UUID(saved.id), version=saved.version)
    elif saved.owner == "domain" and saved.type == "task" and saved.version is not None:
        ref = TaskRef(kind="task", object_id=UUID(saved.id), version=saved.version)
        task = TaskDefinition.model_validate(row["content"])
    else:
        raise RuntimeError("A domain receipt must reference a saved definition version")
    return CreateDomainResponse(request_ref=row["receipt_id"], result=save_result(ref, task))


def replay(row: RowMapping, body: str, digest: str) -> CreateDomainResponse:
    if row["input_hash"] != digest or canonical_json(row["normalized_input"]) != body:
        raise RequestError(409, "request_conflict", "请求编号已用于其他内容。")
    return saved_response(row)


async def apply_domain_event(connection: AsyncConnection, event: StoredEvent) -> None:
    """由事实追加版本，推进对应对象的头和所属领域的目录。"""
    value = version_content(event.payload)
    assert isinstance(event.payload, DomainSaved)
    ref = event.payload.object_ref
    root = isinstance(ref, DomainRef)
    async with application(connection, "domain.definitions.v1", 1, event.draft.event_id) as apply:
        if not apply:
            return
        if event.payload.action == "create":
            await connection.execute(
                text(
                    "INSERT INTO domain.object_identity "
                    "(object_id,kind,domain_id,head_version,catalog_revision) "
                    "VALUES (:id,:kind,:domain_id,1,:catalog)"
                ),
                {
                    "id": value.object_id,
                    "kind": ref.kind,
                    "domain_id": None if root else event.draft.scope_id,
                    "catalog": 1 if root else None,
                },
            )
        await connection.execute(
            text(
                "INSERT INTO domain.object_version "
                "(object_id,version,content_schema_version,content,is_deleted,created_at,"
                "created_by,change_note,source_event_id) VALUES "
                "(:id,:version,:schema,CAST(:content AS jsonb),:deleted,:created_at,"
                "CAST(:created_by AS jsonb),:note,:event_id)"
            ),
            {
                "id": value.object_id,
                "version": value.version,
                "schema": value.content_schema_version,
                "content": value.content.model_dump_json(),
                "deleted": value.is_deleted,
                "created_at": value.created_at,
                "created_by": value.created_by.model_dump_json(),
                "note": value.change_note,
                "event_id": event.draft.event_id,
            },
        )
        if event.payload.action != "create":
            await connection.execute(
                text("UPDATE domain.object_identity SET head_version=:version WHERE object_id=:id"),
                {"id": ref.object_id, "version": ref.version},
            )
        if not root:
            await connection.execute(
                text(
                    "UPDATE domain.object_identity SET catalog_revision=catalog_revision+1 "
                    "WHERE object_id=:id"
                ),
                {"id": event.draft.scope_id},
            )


class DomainDefinitions:
    """围绕领域边界提供管理端所需的最小读写服务。"""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        reader: EventReader,
        attachments: FactAttachments,
    ) -> None:
        self.engine = engine
        self.events = events
        self.reader = reader
        self.attachments = attachments

    async def list_domains(self, session: SessionView) -> DomainList:
        administrator(session)
        async with self.engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT i.object_id,v.version,v.content->>'name' AS name,"
                            "v.is_deleted,v.source_event_id FROM domain.object_identity i "
                            "JOIN domain.object_version v ON (v.object_id,v.version)="
                            "(i.object_id,i.head_version) "
                            "WHERE i.kind='domain' AND i.domain_id IS NULL AND NOT v.is_deleted "
                            "ORDER BY i.object_id"
                        )
                    )
                )
                .mappings()
                .all()
            )
        return DomainList(
            items=[
                DomainRow(
                    object_ref=DomainRef(object_id=row["object_id"], version=row["version"]),
                    name=row["name"],
                    is_deleted=row["is_deleted"],
                    source_event_id=row["source_event_id"],
                )
                for row in rows
            ]
        )

    async def list_members(
        self,
        session: SessionView,
        domain_id: UUID,
        name: str,
        cursor: str | None,
        limit: int,
        kinds: list[MemberKind] | None,
    ) -> MemberList:
        actor = administrator(session)
        name = name.strip()
        selected = sorted(set(kinds or ["kc", "task"]))
        async with self.engine.begin() as connection:
            # 目录基准和列表来自同一快照；后续页不跨目录修订混读。
            await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            catalog = await connection.scalar(text(_ROOT), {"id": domain_id})
            if catalog is None:
                raise RequestError(404, "not_found", "找不到指定领域。")
            token = sha256(
                canonical_json([str(actor), str(domain_id), name, selected, catalog]).encode()
            ).hexdigest()
            after = None
            if cursor is not None:
                prefix, _, position = cursor.partition(".")
                try:
                    after = UUID(position)
                except ValueError as error:
                    raise RequestError(400, "invalid_request", "续页位置无效。") from error
                if prefix != token:
                    raise RequestError(409, "read_range_changed", "领域目录已变化，请重新读取。")
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT i.kind,i.object_id,v.version,v.content->>'name' AS name,"
                            "v.source_event_id "
                            "FROM domain.object_identity i JOIN domain.object_version v "
                            "ON (v.object_id,v.version)=(i.object_id,i.head_version) "
                            "WHERE i.domain_id=:domain AND i.kind=ANY(CAST(:kinds AS text[])) "
                            "AND NOT v.is_deleted "
                            "AND strpos(lower(v.content->>'name'),lower(:name))>0 "
                            "AND (CAST(:after AS uuid) IS NULL OR i.object_id>:after) "
                            "ORDER BY i.object_id LIMIT :limit"
                        ),
                        {
                            "domain": domain_id,
                            "name": name,
                            "after": after,
                            "kinds": selected,
                            "limit": limit + 1,
                        },
                    )
                )
                .mappings()
                .all()
            )
        return MemberList(
            items=[
                MemberRow(
                    object_ref=TaskRef(
                        kind="task", object_id=row["object_id"], version=row["version"]
                    )
                    if row["kind"] == "task"
                    else KnowledgeRef(
                        kind="kc", object_id=row["object_id"], version=row["version"]
                    ),
                    name=row["name"],
                    is_deleted=False,
                    source_event_id=row["source_event_id"],
                )
                for row in rows[:limit]
            ],
            next_cursor=f"{token}.{rows[limit - 1]['object_id']}" if len(rows) > limit else None,
            read_token=token,
        )

    async def read_object(
        self,
        session: SessionView,
        domain_id: UUID,
        object_id: UUID,
        version: int | None = None,
    ) -> ObjectDetail:
        administrator(session)
        async with self.engine.connect() as connection:
            row = await self._version_row(connection, object_id, version)
        owner = object_id if row["kind"] == "domain" else row["domain_id"]
        if owner != domain_id:
            raise RequestError(404, "not_found", "找不到指定领域对象或版本。")
        value = await self._read_version(row, owner, object_id)
        if row["kind"] == "task":
            if not isinstance(value.content, TaskDefinition):
                raise RuntimeError("A Task must reference its own content model")
            task_ref = TaskRef(kind="task", object_id=value.object_id, version=value.version)
            return TaskDetail(
                object=TaskView(
                    object_ref=task_ref,
                    content=value.content,
                    content_ref=TaskContentRef(object_ref=task_ref),
                    is_identity_deleted=row["is_deleted"],
                    source_event_id=row["source_event_id"],
                    gaps=task_gaps(value.content),
                )
            )
        if row["kind"] == "kc":
            if not isinstance(value.content, KnowledgeComponent):
                raise RuntimeError("A knowledge component must reference its own content model")
            ref = KnowledgeRef(kind="kc", object_id=value.object_id, version=value.version)
            return KnowledgeDetail(
                object=KnowledgeView(
                    object_ref=ref,
                    content=value.content,
                    content_ref=KnowledgeContentRef(object_ref=ref),
                    is_identity_deleted=row["is_deleted"],
                    source_event_id=row["source_event_id"],
                )
            )
        if not isinstance(value.content, DomainDefinition):
            raise RuntimeError("A domain root must reference its own content model")
        domain_ref = DomainRef(object_id=value.object_id, version=value.version)
        return DomainDetail(
            object=DomainView(
                object_ref=domain_ref,
                content=value.content,
                content_ref=DomainContentRef(object_ref=domain_ref),
                is_identity_deleted=row["is_deleted"],
                source_event_id=row["source_event_id"],
            )
        )

    async def _version_row(
        self, connection: AsyncConnection, object_id: UUID, version: int | None
    ) -> RowMapping:
        row = (
            (await connection.execute(_VERSION, {"id": object_id, "version": version}))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RequestError(404, "not_found", "找不到指定领域对象或版本。")
        return row

    async def _read_version(
        self, row: RowMapping, domain_id: UUID, object_id: UUID
    ) -> DomainVersion:
        event_id: UUID = row["source_event_id"]
        facts = await self.reader.read_facts(
            "domain",
            domain_id,
            event_id,
            refs=[EventPartRef(event_id=event_id, record_id=RECORD_ID, path="")],
            expected_event_type=EVENT_TYPE,
            schema_version=1,
        )
        items = facts["items"]
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise RuntimeError("A domain version must load exactly one fact record")
        value = DomainVersion.model_validate_json(canonical_json(items[0]["content"]))
        if (value.object_id, value.version) != (object_id, row["version"]):
            raise RuntimeError("The domain version projection points to a different fact")
        return value

    async def save_definition(
        self, session: SessionView, body: SaveRequest
    ) -> CreateDomainResponse:
        actor_id = administrator(session)
        key = receipt_key(actor_id, body.request_id)
        normalized = canonical_json(body.model_dump(mode="json", exclude={"request_id"}))
        digest = sha256(normalized.encode("utf-8")).hexdigest()
        row = None
        async with self.engine.connect() as connection:
            # 重试已提交请求直接查回旧结果；大正文也不会再次准备附件。
            exists = (await connection.execute(_RECEIPT, key)).mappings().one_or_none()
            if exists is not None:
                return replay(exists, normalized, digest)
            created_at = await connection.scalar(text("SELECT clock_timestamp()"))
            if isinstance(
                body,
                (
                    UpdateKnowledgeRequest,
                    DeleteKnowledgeRequest,
                    UpdateTaskRequest,
                    DeleteTaskRequest,
                ),
            ):
                row = await self._version_row(
                    connection, body.object_ref.object_id, body.object_ref.version
                )
        assert isinstance(created_at, datetime)

        previous = None
        if isinstance(body, CreateDomainRequest):
            ref = DomainRef(object_id=uuid4(), version=1)
            domain_id = ref.object_id
            content = body.definition
        elif isinstance(body, CreateKnowledgeRequest):
            ref = KnowledgeRef(kind="kc", object_id=uuid4(), version=1)
            domain_id = body.domain_id
            content = body.definition
        elif isinstance(body, CreateTaskRequest):
            ref = TaskRef(kind="task", object_id=uuid4(), version=1)
            domain_id = body.domain_id
            content = body.definition
        else:
            assert row is not None
            domain_id = row["domain_id"]
            if row["kind"] != body.object_ref.kind or not isinstance(domain_id, UUID):
                raise RequestError(404, "not_found", "找不到指定领域对象。")
            previous = body.object_ref
            if previous.version != body.expected_version:
                raise RequestError(409, "version_conflict", "编辑版本不一致，请检查原稿。")
            ref = previous.model_copy(update={"version": previous.version + 1})
            if isinstance(body, DeleteKnowledgeRequest | DeleteTaskRequest):
                content = (await self._read_version(row, domain_id, ref.object_id)).content
            else:
                content = body.definition

        receipt_id = uuid4()
        actor = Ref(owner="product", type="account", id=str(actor_id))
        scope = ("domain", domain_id)
        access = ProducerAccess("domain", actor, frozenset({scope}))
        version = DomainVersion(
            object_id=ref.object_id,
            version=ref.version,
            content_schema_version=1,
            content=content,
            is_deleted=body.action == "soft_delete",
            created_at=created_at,
            created_by=actor,
            change_note=body.change_note,
        )
        payload = DomainSaved(
            object_ref=ref,
            previous_ref=previous,
            action=body.action,
            request_ref=receipt_id,
            records=[
                FactRecord(
                    record_id=RECORD_ID,
                    record_type=RECORD_TYPE,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=version.model_dump(mode="json")),
                )
            ],
        )
        draft = EventDraft(
            event_id=uuid4(),
            event_type=EVENT_TYPE,
            schema_version=1,
            scope_kind=scope[0],
            scope_id=scope[1],
            owner_ref=version_ref(ref),
            payload=payload.model_dump(mode="json"),
            source_request_id=body.request_id,
        )
        try:
            prepared = await self.attachments.prepare(self.events, access, (draft,))
        except OSError as error:
            raise RequestError(503, "temporarily_unavailable", "暂时无法保存领域内容。") from error

        async with self.engine.begin() as connection:
            claimed = await connection.scalar(
                text(
                    "INSERT INTO domain.command_receipt "
                    "(receipt_id,principal_id,action,scope_id,request_id,"
                    "normalized_input,input_hash,"
                    "state,created_at,updated_at) VALUES "
                    "(:receipt,:principal,:action,:scope,:request_id,CAST(:body AS jsonb),:digest,"
                    "'accepted',clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT (principal_id,action,scope_id,request_id) DO NOTHING "
                    "RETURNING receipt_id"
                ),
                {**key, "receipt": receipt_id, "body": normalized, "digest": digest},
            )
            if claimed is None:
                # 唯一键等到另一事务提交后，本次查询读取其完整收据。
                existing = (await connection.execute(_RECEIPT, key)).mappings().one()
                return replay(existing, normalized, digest)
            sequence = 0
            if not isinstance(ref, DomainRef):
                sequence = await self._lock_member_save(connection, domain_id, previous)
            (saved,) = await self.events.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=receipt_id,
                expected_seq={scope: sequence},
            )
            await apply_domain_event(connection, saved)
            await connection.execute(
                text(
                    "UPDATE domain.command_receipt SET state='completed',"
                    "result_ref=CAST(:result AS jsonb),updated_at=clock_timestamp() "
                    "WHERE receipt_id=:receipt"
                ),
                {
                    "receipt": receipt_id,
                    "result": version_ref(ref).model_dump_json(exclude_none=True),
                },
            )
        return CreateDomainResponse(request_ref=receipt_id, result=save_result(ref, content))

    async def _lock_member_save(
        self, connection: AsyncConnection, domain_id: UUID, previous: MemberRef | None
    ) -> int:
        # 所有领域成员保存先锁所属领域，再核对成员的当前版本。
        root = await connection.scalar(text(_ROOT + " FOR UPDATE OF i"), {"id": domain_id})
        if root is None:
            raise RequestError(404, "not_found", "找不到指定领域。")
        if previous is not None:
            head = (
                await connection.execute(
                    text(
                        "SELECT i.head_version,v.is_deleted FROM domain.object_identity i "
                        "JOIN domain.object_version v ON (v.object_id,v.version)="
                        "(i.object_id,i.head_version) WHERE i.object_id=:id "
                        "AND i.kind=:kind AND i.domain_id=:domain FOR UPDATE OF i"
                    ),
                    {"id": previous.object_id, "kind": previous.kind, "domain": domain_id},
                )
            ).one_or_none()
            if head is None or head.is_deleted or head.head_version != previous.version:
                raise RequestError(409, "version_conflict", "领域对象已变更，请核对最新版本。")
        sequence = await connection.scalar(
            text(
                "SELECT last_seq FROM runtime.scope_event_heads "
                "WHERE scope_kind='domain' AND scope_id=:id"
            ),
            {"id": domain_id},
        )
        if not isinstance(sequence, int):
            raise RuntimeError("A domain catalog must have a committed root event")
        return sequence

    async def read_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[SaveResult]:
        """入口核验当前管理员会话，领域仅查询该管理员自己的原请求。"""
        if query.action != SAVE_ACTION or query.resource_kind != "account":
            raise RequestError(400, "invalid_request", "该领域请求入口不可查询。")
        if query.resource_id != principal_id:
            raise RequestError(404, "not_found", "找不到领域请求。")
        key = receipt_key(principal_id, query.request_id)
        async with self.engine.connect() as connection:
            row = (await connection.execute(_RECEIPT, key)).mappings().one_or_none()
        if row is None:
            return ReceiptView[SaveResult](receipt_state="not_found")
        saved = saved_response(row)
        return ReceiptView[SaveResult](
            receipt_state="completed",
            receipt_ref=saved.request_ref,
            business_state="committed",
            result=saved.result,
        )
