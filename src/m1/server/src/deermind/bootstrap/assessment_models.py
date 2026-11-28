"""Wire assessment authoring to the selected textbook edition and its request receipts."""

from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.product.materials.editions import read_edition
from deermind.product.materials.receiving import MaterialReceiving
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.spaces.domain.public import TaskRef
from deermind.spaces.evaluation.assessment_models import publish_claims, read_models, store_model
from deermind.spaces.evaluation.public import AssessmentCommand, AssessmentModel, ClaimRef, ClaimRow
from sqlalchemy import text


class AssessmentAuthoring:
    def __init__(self, materials: MaterialReceiving) -> None:
        self.materials = materials

    async def list(self, book: UUID, extraction: UUID) -> list[AssessmentModel]:
        async with self.materials.engine.connect() as db:
            source = await read_edition(db, book, extraction)
            if source.kind != "extraction" or source.status != "published":
                raise RequestError(409, "invalid_reference", "请选择本教材已发布的提炼。")
            return await read_models(db, extraction)

    async def save(
        self, principal: UUID, book: UUID, extraction: UUID, model: UUID, body: AssessmentCommand
    ) -> AssessmentModel:
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.materials.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(principal),
                action="evaluation.edit_model",
                scope_id=str(model),
                request_id=body.request_id,
                normalized_input={
                    "book": str(book),
                    "extraction": str(extraction),
                    **body.model_dump(mode="json"),
                },
            )
            row = (
                await db.execute(
                    text("SELECT domain_id,import_id FROM product.textbook WHERE textbook_id=:id"),
                    {"id": book},
                )
            ).one_or_none()
            if row is None:
                raise RequestError(404, "not_found", "教材不存在。")
            await self.materials.read_import(db, row.import_id, lock=True)
            source = await read_edition(db, book, extraction)
            saved = next(
                (m for m in await read_models(db, extraction) if m.model_id == model), None
            )
            if saved is None or source.status != "published" or source.kind != "extraction":
                raise RequestError(404, "not_found", "找不到该提炼版本的评估标准。")
            if receipt.result_ref:
                event_id = UUID(receipt.result_ref.id)
                facts = await self.materials.reader.read_facts(
                    "extraction",
                    extraction,
                    event_id,
                    refs=[EventPartRef(event_id=event_id, record_id=str(model), path="")],
                    expected_event_type="AssessmentModelSaved",
                    correlation_id=receipt.request_ref,
                )
                items = facts["items"]
                if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
                    raise ValueError("评估标准回执缺少结果记录")
                return AssessmentModel.model_validate_json(canonical_json(items[0]["content"]))
            if saved.status != "draft" or saved.revision != body.revision:
                raise RequestError(409, "revision_conflict", "评估标准已发布或已被修改，请刷新。")
            if (body.action == "save") != (body.claims is not None):
                raise RequestError(422, "invalid_reference", "先保存草稿，再按保存的版本发布。")
            result = saved.model_copy(
                update={
                    "claims": body.claims if body.claims is not None else saved.claims,
                    "status": "published" if body.action == "publish" else "draft",
                    "revision": saved.revision + 1,
                }
            )
            if body.action == "publish":
                await publish_claims(
                    db,
                    self.materials.events,
                    self.materials.attachments,
                    result,
                    actor,
                    receipt.request_ref,
                    row.domain_id,
                    {entry.task_ref: entry.method_refs for entry in source.entries},
                )
            event_id = await store_model(
                db,
                self.materials.events,
                self.materials.attachments,
                actor,
                receipt.request_ref,
                result,
            )
            await complete_request(
                db, receipt, Ref(owner="runtime", type="event", id=str(event_id))
            )
            return result

    async def members(self, model: UUID) -> list[ClaimRow]:
        async with self.materials.engine.connect() as db:
            rows = await db.execute(
                text(
                    "SELECT "
                    "c.claim_id,c.head_revision,c.task_id,c.task_version,v.definition->>'title' "
                    "AS title "
                    "FROM evaluation.claim c JOIN evaluation.claim_version v ON "
                    "(v.claim_id,v.revision)=(c.claim_id,c.head_revision) "
                    "JOIN evaluation.assessment_model m USING(model_id) WHERE m.model_id=:id AND "
                    "m.status='published' ORDER BY title,c.claim_id"
                ),
                {"id": model},
            )
            return [
                ClaimRow(
                    claim_ref=ClaimRef(claim_id=row.claim_id, revision=row.head_revision),
                    task_ref=TaskRef(kind="task", object_id=row.task_id, version=row.task_version),
                    title=row.title,
                    gaps=[],
                )
                for row in rows
            ]
