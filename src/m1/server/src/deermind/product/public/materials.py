"""教材登记、原件清单与上传用途的公开输入输出。"""

from datetime import datetime
from typing import Annotated, BinaryIO, Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import FileReceipt, JsonUUID, OriginalMedia
from deermind.foundation.system.public.errors import Issue
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import SessionView
from pydantic import Field, StringConstraints, model_validator

RECEIVE_MATERIAL = "product.receive_material"
type RequestId = Annotated[str, Field(min_length=1, max_length=128)]
type Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
type Revision = Annotated[int, Field(ge=1, le=2**63 - 1)]


class MaterialDomainRef(FactModel):
    kind: Literal["domain"]
    object_id: JsonUUID
    version: Revision


class RegisterMaterialFile(FactModel):
    request_id: RequestId
    purpose: Literal["material_source"]
    original_name: Name
    declared_media_type: OriginalMedia
    declared_byte_size: Annotated[int, Field(gt=0, le=2**63 - 1)]
    domain_ref: MaterialDomainRef
    import_id: JsonUUID | None = None


class MaterialFile(FactModel):
    receipt: FileReceipt
    original_name: Name
    order: Revision


class ReceiveFiles(FactModel):
    request_id: RequestId
    files: list[MaterialFile] = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def unique_files(self) -> "ReceiveFiles":
        if len({file.order for file in self.files}) != len(self.files):
            raise ValueError("File order must be unique")
        if len({file.receipt.storage_ref for file in self.files}) != len(self.files):
            raise ValueError("File receipts must be unique")
        return self


class NewMaterial(ReceiveFiles):
    domain_ref: MaterialDomainRef
    title: Name
    source: Name
    edition: Name | None = None


class AppendMaterial(ReceiveFiles):
    expected_revision: Revision


class MaterialResult(FactModel):
    textbook_id: JsonUUID
    import_id: JsonUUID
    received: list[Ref]
    failed: list[Issue]
    source_revision: Revision


class MaterialReceipt(FactModel):
    request_ref: UUID
    result: MaterialResult


class TextbookMetadata(FactModel):
    title: Name
    source: Name
    edition: Name | None
    copyright_page_ref: Ref | None


class TextbookRow(FactModel):
    textbook_id: UUID
    domain_id: UUID
    import_id: UUID
    metadata: TextbookMetadata
    metadata_revision: Revision
    created_at: datetime


class TextbookList(FactModel):
    items: list[TextbookRow]
    next_cursor: str | None


class MaterialSourceView(FactModel):
    source_ref: Ref
    receipt: FileReceipt
    original_name: str
    order: Revision
    page_count: Revision


class MaterialView(FactModel):
    textbook: TextbookRow
    revision: Revision
    source_revision: Revision
    content_revision: int
    sources: list[MaterialSourceView]
    next_source_cursor: str | None
    deletion_scope_ref: Ref


class MaterialDetail(FactModel):
    material: MaterialView = Field(serialization_alias="import")


DELETE_MATERIAL = "product.delete_material_import"


class DeleteMaterial(FactModel):
    request_id: RequestId
    expected_revision: Revision
    confirmed_scope_ref: Ref


class MaterialDeletionResult(FactModel):
    import_id: UUID
    deleted: bool


class MaterialDeletionReceipt(FactModel):
    request_ref: UUID
    result: MaterialDeletionResult


class MaterialDeletionService(Protocol):
    async def delete(
        self,
        session: SessionView,
        import_id: UUID,
        command: DeleteMaterial,
    ) -> MaterialDeletionReceipt: ...


class MaterialService(Protocol):
    async def authorize_upload(
        self, session: SessionView, domain: MaterialDomainRef, identity: UUID | None
    ) -> None: ...

    async def receive(
        self, session: SessionView, body: NewMaterial | AppendMaterial, identity: UUID | None = None
    ) -> MaterialReceipt: ...

    async def list_books(
        self,
        session: SessionView,
        domain_id: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> TextbookList: ...

    async def detail(
        self, session: SessionView, textbook_id: UUID, cursor: str | None, limit: int
    ) -> MaterialDetail: ...

    async def download(
        self, session: SessionView, source_id: UUID, file_id: UUID
    ) -> tuple[BinaryIO, str, int, str]: ...

    async def read_receipt(
        self, principal: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[MaterialResult]: ...
