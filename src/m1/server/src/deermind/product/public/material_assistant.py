"""教材助手的浏览器输入、原请求结果和候选核对视图。"""

from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.authentication import SessionView
from deermind.product.public.materials import RequestId, Revision
from pydantic import Field, JsonValue, StringConstraints

CONVERSE = "product.converse_material_assistant"
DECIDE = "product.decide_material_candidate"
type TurnOutcome = Literal["completed", "needs_input", "failed", "cancelled"]


class OriginalRange(FactModel):
    source_id: JsonUUID
    first_page: Revision
    last_page: Revision


class MaterialSelection(FactModel):
    import_id: JsonUUID
    scope: Literal["batch"]
    basis_revision: Annotated[int, Field(ge=0)]
    source_refs: list[OriginalRange] = Field(min_length=1, max_length=32)


class PreviousMaterialBatch(FactModel):
    batch_id: JsonUUID
    batch_revision: Revision


class MaterialMessageInput(FactModel):
    request_id: RequestId
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
    selection: MaterialSelection | None = None
    previous_batch_ref: PreviousMaterialBatch | None = None


class MaterialMessagePart(FactModel):
    part_id: str
    type: Literal["text"]
    text: str


class MaterialMessageView(FactModel):
    message_id: UUID
    import_id: UUID
    seq: Revision
    role: Literal["user", "assistant"]
    body: list[MaterialMessagePart]
    explicit_refs: list[Ref]
    turn_ref: UUID
    created_at: datetime


class MaterialHistory(FactModel):
    items: list[MaterialMessageView]
    upper_seq: int
    last_seq: int
    next_cursor: str | None
    active_request_ref: UUID | None


class MaterialTurnAcceptance(FactModel):
    request_ref: UUID
    execution_ref: UUID


class MaterialTurnResult(FactModel):
    message_ref: JsonUUID
    reply_ref: JsonUUID | None
    outcome: TurnOutcome
    candidate_batch_refs: list[Ref]
    issues: list[Issue]


class MaterialBatchView(FactModel):
    batch: dict[str, JsonValue]
    items: list[dict[str, JsonValue]]


class DecideMaterialBatch(FactModel):
    request_id: RequestId
    batch_ref: PreviousMaterialBatch
    decision: Literal["adopt", "decline"]
    expected_revision: Revision


class AdoptedMaterialResult(FactModel):
    decision_ref: Ref
    batch_ref: PreviousMaterialBatch
    decision: Literal["adopt", "decline"]
    adopted_content_refs: list[Ref]
    affected_source_refs: list[Ref]
    content_revision: Annotated[int, Field(ge=0)]


class MaterialAdoptionReceipt(FactModel):
    request_ref: UUID
    result: AdoptedMaterialResult


class MaterialCurrentContents(FactModel):
    content_revision: Annotated[int, Field(ge=0)]
    items: list[dict[str, JsonValue]]
    chapters: list[dict[str, JsonValue]]
    read_token: str


class MaterialAdoptionService(Protocol):
    async def decide(
        self, session: SessionView, import_id: UUID, command: DecideMaterialBatch
    ) -> MaterialAdoptionReceipt: ...

    async def contents(
        self, session: SessionView, import_id: UUID, chapter_id: UUID | None
    ) -> MaterialCurrentContents: ...


class MaterialAssistantService(Protocol):
    async def accept(
        self, session: SessionView, identity: UUID, command: MaterialMessageInput
    ) -> MaterialTurnAcceptance: ...

    async def history(
        self, session: SessionView, import_id: UUID, after: int, upper: int | None, limit: int
    ) -> MaterialHistory: ...

    async def read_batch(
        self, session: SessionView, import_id: UUID, batch_id: UUID
    ) -> MaterialBatchView: ...
