"""教材登记、补件与回读，文件核验在教材提交事务外完成。"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID, uuid4, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.abstractions.files import FileBytes
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.files.uploads import MAX_BYTES, FileUploads, file_view
from deermind.foundation.system.public.errors import ErrorDetail, Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials.facts import (
    IMPORT,
    RECEIVED,
    SOURCE,
    TEXTBOOK,
    MaterialImportFact,
    MaterialReceived,
    MaterialSourceFact,
    SourcePage,
    project,
    record,
)
from deermind.product.persistence.receipts import claim_request, complete_request, reject_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.errors import RequestConflict
from deermind.product.public.materials import (
    RECEIVE_MATERIAL,
    AppendMaterial,
    MaterialDetail,
    MaterialDomainRef,
    MaterialReceipt,
    MaterialResult,
    MaterialSourceView,
    MaterialView,
    NewMaterial,
    TextbookList,
    TextbookListItem,
    TextbookMetadata,
    TextbookRow,
)
from deermind.spaces.domain.public import DomainDetail, DomainService
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_IMPORT = (
    "SELECT i.*,t.domain_id FROM product.material_import i "
    "JOIN product.textbook t USING(import_id) "
    "WHERE i.import_id=:id AND i.status='active'"
)
_RECEIPT = text(
    "SELECT request_ref,normalized_input,state,result_ref,error FROM product.command_receipt "
    "WHERE principal_id=:principal AND action=:action AND scope_id=:scope AND request_id=:request"
)
_SOURCE_VIEW = (
    "SELECT s.source_id,s.original_name,s.source_order,jsonb_array_length(s.pages) AS page_count,"
    "s.file_id,s.sha256 FROM product.material_source s WHERE s.import_id=:id"
)


def import_ref(identity: UUID) -> Ref:
    return Ref(owner="product", type="material_import", id=str(identity))


def cursor_position(cursor: str | None, token: str) -> UUID | None:
    if cursor is None:
        return None
    prefix, _, value = cursor.partition(".")
    if prefix != token:
        # 游标前缀须与当前读取范围的指纹一致，防止跨范围翻页。
        raise RequestError(400, "invalid_request", "续页位置与当前读取范围不符，请重新读取。")
    try:
        return UUID(value)
    except ValueError as error:
        raise RequestError(400, "invalid_request", "续页位置无效。") from error


class MaterialReceiving:
    def __init__(
        self,
        engine: AsyncEngine,
        domain: DomainService,
        uploads: FileUploads,
        events: EventStore,
        reader: EventReader,
        attachments: FactAttachments,
        open_file: Callable[[FileBytes, int], BinaryIO],
    ) -> None:
        self.engine = engine
        self.domain = domain
        self.uploads = uploads
        self.events = events
        self.reader = reader
        self.attachments = attachments
        self.open_file = open_file

    @staticmethod
    def administrator(session: SessionView) -> UUID:
        if session.account.role != "admin":
            # 教材管理仅限管理员。
            raise RequestError(403, "forbidden", "只有管理员可以管理教材。")
        return session.account.account_id

    async def read_import(
        self, connection: AsyncConnection, identity: UUID, *, lock: bool = False
    ) -> RowMapping:
        statement = _IMPORT + (" FOR UPDATE OF i" if lock else "")
        row = (await connection.execute(text(statement), {"id": identity})).mappings().one_or_none()
        if row is None:
            # 仅返回 active 导入；缺失或已删除均按未找到处理。
            raise RequestError(404, "not_found", "找不到此教材导入。")
        return row

    async def authorize_upload(
        self, session: SessionView, domain: MaterialDomainRef, identity: UUID | None
    ) -> None:
        self.administrator(session)
        try:
            detail = await self.domain.read_object(
                session, domain.object_id, domain.object_id, domain.version
            )
        except RequestError as error:
            if error.status != 404:
                # 非 404 错误原样上抛，仅把领域不存在转为引用无效。
                raise
            raise RequestError(400, "invalid_reference", "请选择有效领域。") from error
        if not isinstance(detail, DomainDetail) or detail.object.is_identity_deleted:
            raise RequestError(400, "invalid_reference", "请选择有效领域。")
        if identity is not None:
            # 补件场景：核对既有导入与所选领域一致。
            async with self.engine.connect() as connection:
                imported = await self.read_import(connection, identity)
            if imported["domain_id"] != domain.object_id:
                raise RequestError(400, "invalid_reference", "补页必须沿用教材所属领域。")

    async def _receipt_row(
        self, principal: UUID, scope: UUID, request_id: str
    ) -> RowMapping | None:
        async with self.engine.connect() as connection:
            result = await connection.execute(
                _RECEIPT,
                {
                    "principal": str(principal),
                    "action": RECEIVE_MATERIAL,
                    "scope": str(scope),
                    "request": request_id,
                },
            )
            return result.mappings().one_or_none()

    async def _original(self, reference: Ref, request_ref: UUID) -> MaterialResult:
        import_id = UUID(reference.id)
        found = await self.reader.query_metadata(
            "material_import",
            import_id,
            filters=EventFilter(event_types=(RECEIVED,), correlation_id=request_ref),
            limit=1,
        )
        items = found["items"]
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            # 收据对应的受理事件必须恰好一条，属内部一致性错误。
            raise RuntimeError("Material receipt source event does not exist")
        event_id = UUID(str(items[0]["event_id"]))
        facts = await self.reader.read_facts(
            "material_import",
            import_id,
            event_id,
            refs=[EventPartRef(event_id=event_id, record_id=None, path="")],
            expected_event_type=RECEIVED,
            schema_version=1,
            correlation_id=request_ref,
        )
        records = facts["items"]
        if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
            raise RuntimeError("Material receipt has no action fields")
        result = records[0]["content"]
        if not isinstance(result, dict):
            raise RuntimeError("Invalid MaterialReceived action fields")
        # 把 source_refs 还原为公开结果的 received 列表。
        return MaterialResult.model_validate(
            {
                **{key: value for key, value in result.items() if key != "source_refs"},
                "received": result["source_refs"],
            }
        )

    @staticmethod
    def _failure(error: ErrorDetail) -> RequestError:
        status = 409 if error.code == "revision_conflict" else 422
        return RequestError(status, error.code, error.message, issues=error.issues)

    async def read_receipt(
        self, principal: UUID, _session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[MaterialResult]:
        row = await self._receipt_row(principal, query.resource_id, query.request_id)
        if row is None:
            # 无收据记录，按未找到返回。
            return ReceiptView[MaterialResult](receipt_state="not_found")
        if row["state"] == "failed":
            # 永久失败收据直接回传错误，不重复执行。
            return ReceiptView[MaterialResult](
                receipt_state="rejected",
                receipt_ref=row["request_ref"],
                error=ErrorDetail.model_validate(row["error"]),
            )
        reference = Ref.model_validate(row["result_ref"])
        return ReceiptView[MaterialResult](
            receipt_state="completed",
            receipt_ref=row["request_ref"],
            result_refs=[reference],
            result=await self._original(reference, row["request_ref"]),
        )

    async def receive(
        self, session: SessionView, body: NewMaterial | AppendMaterial, identity: UUID | None = None
    ) -> MaterialReceipt:
        principal = self.administrator(session)
        normalized = body.model_dump(mode="json")
        creating = isinstance(body, NewMaterial)
        scope = body.domain_ref.object_id if creating else identity
        assert scope is not None
        prior = await self._receipt_row(principal, scope, body.request_id)
        if prior is not None:
            if normalized != prior["normalized_input"]:
                # 同一请求键被不同输入复用，属冲突。
                raise RequestConflict("Material request reused with different input")
            if prior["error"] is not None:
                # 原请求已永久失败，回传其错误结果。
                raise self._failure(ErrorDetail.model_validate(prior["error"]))
            return MaterialReceipt(
                request_ref=prior["request_ref"],
                result=await self._original(
                    Ref.model_validate(prior["result_ref"]), prior["request_ref"]
                ),
            )

        current = None
        if creating:
            # 新建：校验所选领域有效。
            await self.authorize_upload(session, body.domain_ref, None)
        else:
            # 补件：载入既有导入作为修订基线。
            async with self.engine.connect() as connection:
                current = await self.read_import(connection, scope)
        import_id = uuid4() if creating else scope
        uploads = await self.uploads.completed(
            principal, [file.receipt.storage_ref for file in body.files]
        )
        sources, failed = await self._sources(body, import_id, current, uploads)
        now = datetime.now(UTC)
        imported = MaterialImportFact(
            import_id=import_id,
            textbook_id=uuid4() if current is None else current["textbook_id"],
            status="active",
            revision=1 if current is None else current["revision"] + 1,
            source_revision=1 if current is None else current["source_revision"] + 1,
            content_revision=0 if current is None else current["content_revision"],
            created_at=now if current is None else current["created_at"],
            updated_at=now,
        )
        actor = Ref(owner="product", type="account", id=str(principal))
        access = ProducerAccess("product", actor, frozenset({("material_import", import_id)}))
        prepared = None
        if sources:
            # 存在可登记原件时组装受理事件；无原件则只落失败收据。
            rows = [record(IMPORT, import_id, imported)]
            if isinstance(body, NewMaterial):
                book = TextbookRow(
                    textbook_id=imported.textbook_id,
                    domain_id=body.domain_ref.object_id,
                    import_id=import_id,
                    metadata_revision=1,
                    created_at=now,
                    metadata=TextbookMetadata(
                        title=body.title,
                        source=body.source,
                        edition=body.edition,
                        copyright_page_ref=None,
                    ),
                )
                rows.append(record(TEXTBOOK, book.textbook_id, book))
            rows.extend(record(SOURCE, source.source_id, source) for source in sources)
            payload = MaterialReceived(
                records=rows,
                import_id=import_id,
                textbook_id=imported.textbook_id,
                source_refs=[source.ref() for source in sources],
                source_revision=imported.source_revision,
                failed=failed,
            )
            draft = EventDraft(
                event_id=uuid4(),
                event_type=RECEIVED,
                schema_version=1,
                scope_kind="material_import",
                scope_id=import_id,
                owner_ref=import_ref(import_id),
                payload=payload.model_dump(mode="json"),
                source_request_id=body.request_id,
            )
            prepared = await self.attachments.prepare(self.events, access, (draft,))

        error = None
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=str(principal),
                action=RECEIVE_MATERIAL,
                scope_id=str(scope),
                request_id=body.request_id,
                normalized_input=normalized,
            )
            reference = receipt.result_ref
            if receipt.error is not None:
                # 收据本身已带错误（如冲突占用），直接沿用。
                error = receipt.error
            elif reference is None:
                if isinstance(body, AppendMaterial):
                    locked = await self.read_import(connection, import_id, lock=True)
                    if (
                        body.expected_revision != locked["source_revision"]
                        or current is None
                        or locked["revision"] != current["revision"]
                    ):
                        # 补件基线与持锁后现状不一致，记修订冲突。
                        error = ErrorDetail(
                            code="revision_conflict",
                            message="原件清单已变化，请刷新后重试。",
                            issues=[],
                            retryable=False,
                        )
                if error is None and prepared is None:
                    # 无有效原件可登记，记来源不可用。
                    error = ErrorDetail(
                        code="source_unavailable",
                        message="没有可登记的原件。",
                        issues=failed,
                        retryable=False,
                    )
                if error:
                    # 永久失败落定拒绝收据并回滚事务。
                    await reject_request(connection, receipt, error)
                elif prepared is not None:
                    # 校验通过：锁序号、追加事件并投影。
                    event_scope = ("material_import", import_id)
                    sequence = await lock_scope_sequence(connection, *event_scope)
                    (stored,) = await self.events.append(
                        connection,
                        access,
                        prepared,
                        commit_id=uuid4(),
                        correlation_id=receipt.request_ref,
                        expected_seq={event_scope: sequence},
                    )
                    await project(connection, stored)
                    reference = import_ref(import_id)
                    await complete_request(connection, receipt, reference)
        if error:
            # 事务内落定的失败错误按对应状态码抛出。
            raise self._failure(error)
        assert reference is not None
        return MaterialReceipt(
            request_ref=receipt.request_ref,
            result=await self._original(reference, receipt.request_ref),
        )

    async def _sources(
        self,
        body: NewMaterial | AppendMaterial,
        import_id: UUID,
        current: RowMapping | None,
        uploads: dict[UUID, RowMapping],
    ) -> tuple[list[MaterialSourceFact], list[Issue]]:
        existing_files: set[UUID] = set()
        existing_orders: set[int] = set()
        if current is not None:
            # 补件：载入既有文件与序号，避免重复登记。
            async with self.engine.connect() as connection:
                rows = await connection.execute(
                    text(
                        "SELECT file_id,source_order FROM product.material_source "
                        "WHERE import_id=:id"
                    ),
                    {"id": import_id},
                )
                for row in rows:
                    existing_files.add(row.file_id)
                    existing_orders.add(row.source_order)
        if sum(item.receipt.byte_size for item in body.files) > 2 * 1024**3:
            raise RequestError(413, "payload_too_large", "一次登记合计最多 2 GiB 原件。")
        sources: list[MaterialSourceFact] = []
        issues: list[Issue] = []
        # 按局部序号排序逐件核验收据与归属。
        for index, item in sorted(enumerate(body.files), key=lambda entry: entry[1].order):
            file_id = item.receipt.storage_ref
            row = uploads.get(file_id)
            allowed = (
                row is not None
                and row["original_name"] == item.original_name
                and item.receipt == file_view(row)
                and file_id not in existing_files
                and item.order not in existing_orders
            )
            if allowed and row is not None:
                domain = MaterialDomainRef.model_validate(row["domain_ref"])
                allowed = (
                    row["resource_ref"] is None and domain == body.domain_ref
                    if isinstance(body, NewMaterial)
                    else current is not None
                    and domain.object_id == current["domain_id"]
                    and row["resource_ref"] == import_ref(import_id).model_dump(exclude_none=True)
                )
                # 新建要求文件未绑定其他资源；补件要求文件归属本导入且领域一致。
            if not allowed or row is None:
                issues.append(
                    Issue(
                        code="source_unavailable",
                        path=f"/files/{index}",
                        message="文件收据无效、超出导入范围或已登记。",
                    )
                )
                continue
            identity = uuid4()
            sources.append(
                MaterialSourceFact(
                    source_id=identity,
                    import_id=import_id,
                    file_id=file_id,
                    original_name=item.original_name,
                    source_order=item.order,
                    sha256=item.receipt.sha256,
                    created_at=datetime.now(UTC),
                    pages=[
                        SourcePage(
                            page_id=uuid5(identity, str(page)),
                            file_page_index=page,
                            printed_page_label=None,
                            derived_file_ref=None,
                        )
                        for page in range(1, row["page_count"] + 1)
                    ],
                )
            )
        return sources, issues

    async def list_books(
        self,
        session: SessionView,
        domain_id: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> TextbookList:
        principal = self.administrator(session)
        token = sha256(canonical_json([str(principal), str(domain_id), name]).encode()).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as connection:
            rows = (
                await connection.scalars(
                    text(
                        "SELECT (to_jsonb(t)-'source_event_id') || jsonb_build_object("
                        "'processing', CASE WHEN i.active_request_ref IS NOT NULL "
                        "THEN 'processing' "
                        "WHEN last_turn.state IN ('failed','needs_input') THEN last_turn.state "
                        "WHEN EXISTS (SELECT 1 FROM product.material_candidate_batch b "
                        "JOIN product.material_turn mt ON mt.request_ref=b.turn_ref "
                        "WHERE mt.import_id=i.import_id AND "
                        "b.decision_state='pending') THEN 'review' "
                        "WHEN i.content_revision>0 THEN 'adopted' ELSE 'ready' END) "
                        "FROM product.textbook t JOIN product.material_import i USING(import_id) "
                        "LEFT JOIN LATERAL (SELECT state FROM product.material_turn "
                        "WHERE import_id=i.import_id ORDER BY created_at DESC LIMIT 1) "
                        "last_turn ON true WHERE i.status='active' "
                        "AND (CAST(:domain AS uuid) IS NULL OR t.domain_id=:domain) "
                        "AND strpos(lower(t.metadata->>'title'),lower(:name))>0 "
                        "AND (CAST(:after AS uuid) IS NULL OR t.textbook_id>:after) "
                        "ORDER BY t.textbook_id LIMIT :limit"
                    ),
                    {"domain": domain_id, "name": name, "after": after, "limit": limit + 1},
                )
            ).all()
        books = [TextbookListItem.model_validate_json(canonical_json(row)) for row in rows[:limit]]
        return TextbookList(
            items=books,
            next_cursor=f"{token}.{books[-1].textbook_id}" if len(rows) > limit else None,
        )

    async def detail(
        self, session: SessionView, textbook_id: UUID, cursor: str | None, limit: int
    ) -> MaterialDetail:
        principal = self.administrator(session)
        token = sha256(canonical_json([str(principal), str(textbook_id)]).encode()).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT to_jsonb(t)-'source_event_id' AS book, "
                            "i.revision,i.source_revision,i.content_revision "
                            "FROM product.textbook t "
                            "JOIN product.material_import i USING(import_id) "
                            "WHERE t.textbook_id=:id AND i.status='active'"
                        ),
                        {"id": textbook_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RequestError(404, "not_found", "找不到此教材。")
            # 命中教材后分页读取其原件清单。
            book = TextbookRow.model_validate_json(canonical_json(row["book"]))
            result = await connection.execute(
                text(
                    _SOURCE_VIEW + " AND (CAST(:after AS uuid) IS NULL OR s.source_order>("
                    "SELECT source_order FROM product.material_source "
                    "WHERE source_id=:after AND import_id=:id)) "
                    "ORDER BY s.source_order LIMIT :limit"
                ),
                {"id": book.import_id, "after": after, "limit": limit + 1},
            )
            sources = result.mappings().all()
        views: list[MaterialSourceView] = []
        for source in sources[:limit]:
            file = await self.uploads.registry.by_id(source["file_id"])
            if file is None or file.sha256 != source["sha256"] or file.category != "original":
                # 文件缺失、摘要不符或非原件类别，登记不完整。
                raise RequestError(503, "source_unavailable", "教材原件登记不完整。")
            views.append(
                MaterialSourceView(
                    source_ref=Ref(
                        owner="product", type="material_source", id=str(source["source_id"])
                    ),
                    receipt=file_view(
                        {
                            "file_id": file.file_id,
                            "declared_media_type": file.media_type,
                            "byte_size": file.byte_size,
                            "sha256": file.sha256,
                        }
                    ),
                    original_name=source["original_name"],
                    order=source["source_order"],
                    page_count=source["page_count"],
                )
            )
        return MaterialDetail(
            material=MaterialView(
                textbook=book,
                revision=row["revision"],
                source_revision=row["source_revision"],
                content_revision=row["content_revision"],
                sources=views,
                next_source_cursor=f"{token}.{views[-1].source_ref.id}"
                if len(sources) > limit
                else None,
                deletion_scope_ref=Ref(
                    owner="product",
                    type="deletion_scope",
                    id=str(book.import_id),
                    revision=row["revision"],
                ),
            )
        )

    async def download(
        self, session: SessionView, source_id: UUID, file_id: UUID
    ) -> tuple[BinaryIO, str, int, str]:
        self.administrator(session)
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT s.sha256,s.original_name FROM product.material_source s "
                        "JOIN product.material_import i USING(import_id) "
                        "WHERE s.source_id=:source AND s.file_id=:file"
                    ),
                    {"source": source_id, "file": file_id},
                )
            ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "找不到此教材原件。")
        file = await self.uploads.registry.by_id(file_id)
        if (
            file is None
            or file.sha256 != row.sha256
            or file.category != "original"
            or file.media_type not in MAX_BYTES
        ):
            # 摘要、类别或类型校验任一不符均视为原件不可用。
            raise RequestError(503, "source_unavailable", "教材原件登记不完整。")
        try:
            source = await asyncio.to_thread(
                self.open_file, file.bytes_ref(), MAX_BYTES[file.media_type]
            )
        except (ValueError, OSError) as error:
            # 读文件或完整性校验失败，转为来源不可用错误。
            raise RequestError(
                503, "source_unavailable", "教材原件缺失或完整性检查失败。"
            ) from error
        return source, file.media_type, file.byte_size, row.original_name
