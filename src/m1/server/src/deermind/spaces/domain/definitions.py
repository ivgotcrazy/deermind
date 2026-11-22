"""领域根定义的查询、保存与归属校验。"""

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
    DomainContentRef,
    DomainDetail,
    DomainList,
    DomainRef,
    DomainRow,
    DomainView,
)

_RECEIPT = text(
    "SELECT receipt_id,input_hash,normalized_input,state,result_ref "
    "FROM domain.command_receipt WHERE principal_id=:principal AND action=:action "
    "AND scope_id=:scope AND request_id=:request_id"
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


def create_result(ref: DomainRef) -> CreateDomainResult:
    return CreateDomainResult(object_ref=ref, content_ref=DomainContentRef(object_ref=ref))


def saved_response(row: RowMapping) -> CreateDomainResponse:
    if row["state"] != "completed":
        raise RuntimeError("A domain create receipt must be committed with its result")
    saved = Ref.model_validate(row["result_ref"])
    if (saved.owner, saved.type, saved.version) != ("domain", "domain", 1):
        raise RuntimeError("A domain create receipt must retain the initial version")
    ref = DomainRef(object_id=UUID(saved.id), version=1)
    return CreateDomainResponse(request_ref=row["receipt_id"], result=create_result(ref))


def replay(row: RowMapping, body: str, digest: str) -> CreateDomainResponse:
    if row["input_hash"] != digest or canonical_json(row["normalized_input"]) != body:
        raise RequestError(409, "request_conflict", "请求编号已用于其他内容。")
    return saved_response(row)


async def apply_domain_event(connection: AsyncConnection, event: StoredEvent) -> None:
    """从已验证事实生成首个版本、派生头与投影收据，同事务提交。"""
    value = version_content(event.payload)
    async with application(connection, "domain.definitions.v1", 1, event.draft.event_id) as apply:
        if not apply:
            return
        await connection.execute(
            text(
                "INSERT INTO domain.object_identity "
                "(object_id,kind,head_version,catalog_revision) VALUES (:id,'domain',1,1)"
            ),
            {"id": value.object_id},
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

    async def read_domain(
        self,
        session: SessionView,
        domain_id: UUID,
        object_id: UUID,
        version: int | None = None,
    ) -> DomainDetail:
        administrator(session)
        if object_id != domain_id:
            raise RequestError(404, "not_found", "找不到指定领域。")
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT v.version,v.source_event_id,head.is_deleted "
                            "FROM domain.object_identity i "
                            "JOIN domain.object_version head ON (head.object_id,head.version)="
                            "(i.object_id,i.head_version) "
                            "JOIN domain.object_version v ON v.object_id=i.object_id "
                            "AND v.version=COALESCE(CAST(:version AS bigint),i.head_version) "
                            "WHERE i.object_id=:id AND i.kind='domain' AND i.domain_id IS NULL "
                            "AND (CAST(:version AS bigint) IS NOT NULL OR NOT head.is_deleted)"
                        ),
                        {"id": domain_id, "version": version},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise RequestError(404, "not_found", "找不到指定领域或版本。")
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
        if (value.object_id, value.version) != (domain_id, row["version"]):
            raise RuntimeError("The domain version projection points to a different fact")
        ref = DomainRef(object_id=value.object_id, version=value.version)
        return DomainDetail(
            object=DomainView(
                object_ref=ref,
                content=value.content,
                content_ref=DomainContentRef(object_ref=ref),
                is_identity_deleted=row["is_deleted"],
                source_event_id=event_id,
            )
        )

    async def create_domain(
        self, session: SessionView, body: CreateDomainRequest
    ) -> CreateDomainResponse:
        actor_id = administrator(session)
        key = receipt_key(actor_id, body.request_id)
        normalized = canonical_json(body.model_dump(mode="json", exclude={"request_id"}))
        digest = sha256(normalized.encode("utf-8")).hexdigest()
        async with self.engine.connect() as connection:
            # 重试已提交请求直接查回旧结果；大正文也不会再次准备附件。
            exists = (await connection.execute(_RECEIPT, key)).mappings().one_or_none()
            if exists is not None:
                return replay(exists, normalized, digest)
            created_at = await connection.scalar(text("SELECT clock_timestamp()"))
        assert isinstance(created_at, datetime)

        receipt_id = uuid4()
        ref = DomainRef(object_id=uuid4(), version=1)
        actor = Ref(owner="product", type="account", id=str(actor_id))
        scope = ("domain", ref.object_id)
        access = ProducerAccess("domain", actor, frozenset({scope}))
        version = DomainVersion(
            object_id=ref.object_id,
            version=1,
            content_schema_version=1,
            content=body.definition,
            is_deleted=False,
            created_at=created_at,
            created_by=actor,
            change_note=body.change_note,
        )
        payload = DomainSaved(
            object_ref=ref,
            previous_ref=None,
            action="create",
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
            (saved,) = await self.events.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=receipt_id,
                expected_seq={scope: 0},
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
        return CreateDomainResponse(request_ref=receipt_id, result=create_result(ref))

    async def read_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[CreateDomainResult]:
        """入口核验当前管理员会话，领域仅查询该管理员自己的原请求。"""
        if query.action != SAVE_ACTION or query.resource_kind != "account":
            raise RequestError(400, "invalid_request", "该领域请求入口不可查询。")
        if query.resource_id != principal_id:
            raise RequestError(404, "not_found", "找不到领域请求。")
        key = receipt_key(principal_id, query.request_id)
        async with self.engine.connect() as connection:
            row = (await connection.execute(_RECEIPT, key)).mappings().one_or_none()
        if row is None:
            return ReceiptView[CreateDomainResult](receipt_state="not_found")
        saved = saved_response(row)
        return ReceiptView[CreateDomainResult](
            receipt_state="completed",
            receipt_ref=saved.request_ref,
            business_state="committed",
            result=saved.result,
        )
