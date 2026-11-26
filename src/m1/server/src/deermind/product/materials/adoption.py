"""管理员决定候选去留，相关来源的冲突在同一短事务校验。"""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials import adoption_facts as facts
from deermind.product.materials.assistant_facts import BATCH, CandidateBatchFact
from deermind.product.materials.facts import IMPORT, MaterialImportFact, record
from deermind.product.materials.receiving import MaterialReceiving, import_ref
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.material_assistant import (
    DECIDE,
    AdoptedMaterialResult,
    DecideMaterialBatch,
    MaterialAdoptionReceipt,
    MaterialCurrentContents,
    PreviousMaterialBatch,
)
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


def _candidate_ref(id_: UUID, revision: int) -> Ref:
    return Ref(owner="product", type="material_candidate", id=str(id_), revision=revision)


def _result(decision: facts.MaterialDecision) -> AdoptedMaterialResult:
    return AdoptedMaterialResult.model_validate(
        {
            "decision_ref": {
                "owner": "product",
                "type": "material_adoption",
                "id": str(decision.decision_id),
            },
            "batch_ref": {
                "batch_id": str(decision.batch_id),
                "batch_revision": decision.batch_revision,
            },
            "decision": decision.decision,
            "adopted_content_refs": decision.after_refs,
            "affected_source_refs": decision.before_refs,
            "content_revision": decision.impact["content_revision"],
        }
    )


class MaterialAdoptions:
    def __init__(self, materials: MaterialReceiving) -> None:
        self.materials = materials
        self.engine = materials.engine

    async def _saved(
        self, connection: AsyncConnection, import_id: UUID, identity: str
    ) -> facts.MaterialDecision:
        row = await connection.scalar(
            text(
                "SELECT to_jsonb(d)-'source_event_id' FROM product.material_adoption d "
                "JOIN product.material_candidate_batch b USING(batch_id) "
                "JOIN product.material_turn t ON b.turn_ref=t.request_ref "
                "WHERE d.decision_id=:id AND t.import_id=:scope"
            ),
            {"id": UUID(identity), "scope": import_id},
        )
        if row is None:
            raise LookupError("Missing adoption result")
        # 命中决定记录后转为事实模型。
        return facts.MaterialDecision.model_validate_json(canonical_json(row))

    async def decide(
        self, session: SessionView, import_id: UUID, command: DecideMaterialBatch
    ) -> MaterialAdoptionReceipt:
        principal = self.materials.administrator(session)
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=str(principal),
                action=DECIDE,
                scope_id=str(import_id),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json"),
            )
            if receipt.result_ref is not None:
                # 幂等重放：读回原决定事实。
                result = await self._saved(connection, import_id, receipt.result_ref.id)
            else:
                imported = await self.materials.read_import(connection, import_id, lock=True)
                batch = await self._batch(connection, import_id, command.batch_ref)
                if (
                    batch.decision_state != "pending"
                    or batch.decision_revision != command.expected_revision
                ):
                    # 批次已被决定或版本已变，不能重复决策。
                    raise RequestError(409, "already_decided", "这批候选已有决定，请刷新详情。")
                result = await self._save(
                    connection, import_id, imported, command, batch, receipt.request_ref, principal
                )
                await complete_request(connection, receipt, _result(result).decision_ref)
        return MaterialAdoptionReceipt(request_ref=receipt.request_ref, result=_result(result))

    async def _batch(
        self, connection: AsyncConnection, import_id: UUID, reference: PreviousMaterialBatch
    ) -> CandidateBatchFact:
        row = await connection.scalar(
            text(
                "SELECT to_jsonb(b)-'source_event_id' FROM product.material_candidate_batch b "
                "JOIN product.material_turn t ON b.turn_ref=t.request_ref "
                "WHERE b.batch_id=:id AND b.batch_revision=:rev AND t.import_id=:scope"
            ),
            {"id": reference.batch_id, "rev": reference.batch_revision, "scope": import_id},
        )
        if row is None:
            raise RequestError(404, "not_found", "找不到本教材的候选批次。")
        # 命中批次记录后转为事实模型。
        return CandidateBatchFact.model_validate_json(canonical_json(row))

    async def _check_overlap(
        self,
        connection: AsyncConnection,
        import_id: UUID,
        batch: CandidateBatchFact,
        pages: list[str],
    ) -> None:
        previous = batch.diff_summary.get("previous_batch")
        targets = [
            str(item["candidate_id"])
            for item in batch.write_set
            if item.get("action") in ("replace", "retire")
        ]
        if previous is not None and targets:
            expected = {
                str(w["candidate_id"]): w["adopted_basis"]
                for w in batch.write_set
                if "adopted_basis" in w and str(w["candidate_id"]) in targets
            }
            if expected:
                changed = await connection.scalar(
                    text(
                        "SELECT 1 FROM jsonb_each_text(CAST(:expected AS jsonb)) e "
                        "LEFT JOIN product.material_content_current c "
                        "ON c.import_id=:id AND c.candidate_id=CAST(e.key AS uuid) "
                        "WHERE c.candidate_revision IS DISTINCT FROM CAST(e.value AS bigint) "
                        "OR c.validity<>'current' LIMIT 1"
                    ),
                    {"id": import_id, "expected": canonical_json(expected)},
                )
                if changed:
                    raise RequestError(
                        409, "candidate_basis_changed", "要修正的内容已变化，请重新核对。"
                    )
                targets = [target for target in targets if target not in expected]
            # 先核对修订/退役目标相对前序批次是否仍在当前版本。
            prior = PreviousMaterialBatch.model_validate(previous)
            changed = await connection.scalar(
                text(
                    "SELECT 1 FROM product.material_candidate c "
                    "JOIN product.material_candidate_batch b USING(batch_id) "
                    "LEFT JOIN product.material_content_current v USING(import_id,candidate_id) "
                    "WHERE c.import_id=:id AND c.batch_id=:prior "
                    "AND c.candidate_id::text=ANY(CAST(:targets AS text[])) AND ("
                    "(v.candidate_id IS NOT NULL AND (v.candidate_revision<>c.candidate_revision "
                    "OR v.validity<>'current')) OR "
                    "(b.decision_state='adopted' AND v.candidate_id IS NULL)) LIMIT 1"
                ),
                {"id": import_id, "prior": prior.batch_id, "targets": targets},
            )
            if changed:
                raise RequestError(
                    409, "candidate_basis_changed", "要修正的内容已变化，请重新核对。"
                )
            if all(item.get("action") != "add" for item in batch.write_set):
                # 纯修订/退役无需再按新页占用基准查重。
                return

        # 尚无候选身份的新内容使用所读原页作为占用基准。
        collision = await connection.scalar(
            text(
                "SELECT 1 FROM product.material_adoption a "
                "JOIN product.material_candidate_batch b USING(batch_id) "
                "JOIN product.material_turn t ON b.turn_ref=t.request_ref "
                "WHERE t.import_id=:id AND a.decision='adopt' "
                "AND (a.impact->>'content_revision')::bigint>:basis "
                "AND (a.impact->'pages') ?| CAST(:pages AS text[]) LIMIT 1"
            ),
            {"id": import_id, "basis": batch.scope["basis_revision"], "pages": pages},
        )
        if collision is not None:
            # 同一原页已有更新的采用结果，新内容存在覆盖冲突。
            raise RequestError(
                409, "candidate_basis_changed", "相关原页的内容已采用新结果，请重新核对。"
            )

    async def _save(
        self,
        connection: AsyncConnection,
        import_id: UUID,
        imported: RowMapping,
        command: DecideMaterialBatch,
        batch: CandidateBatchFact,
        request_ref: UUID,
        principal: UUID,
    ) -> facts.MaterialDecision:
        adopting = command.decision == "adopt"
        timestamp = datetime.now(UTC)
        identity = uuid4()
        reference = Ref(owner="product", type="material_adoption", id=str(identity))
        actor = Ref(owner="product", type="account", id=str(principal))
        revision: int = imported["content_revision"] + int(adopting)
        before: list[Ref] = []
        after: list[Ref] = []
        chapters: list[FactRecord] = []
        pages = [str(source["source_id"]) for source in batch.read_set]
        if adopting:
            # 采用前先确认候选取材完整，并查重后再组装新旧引用。
            if batch.coverage["complete"] is not True:
                raise RequestError(
                    409, "incomplete_candidate", "候选仍缺原页或关键信息，请补充后再采用。"
                )
            await self._check_overlap(connection, import_id, batch, pages)
            before, after, chapters = await self._contents(
                connection, import_id, imported["textbook_id"], batch, reference, timestamp
            )
        result = facts.MaterialDecision(
            decision_id=identity,
            batch_id=batch.batch_id,
            batch_revision=batch.batch_revision,
            decision=command.decision,
            actor_ref=actor,
            before_refs=before,
            after_refs=after,
            impact={"content_revision": revision, "pages": [page for page in pages]},
            request_ref=request_ref,
            created_at=timestamp,
        )
        changed = batch.model_copy(
            update={
                "decision_state": "adopted" if adopting else "declined",
                "decision_revision": batch.decision_revision + 1,
            }
        )
        updated = MaterialImportFact(
            import_id=import_id,
            textbook_id=imported["textbook_id"],
            status="active",
            revision=imported["revision"] + 1,
            source_revision=imported["source_revision"],
            content_revision=revision,
            created_at=imported["created_at"],
            updated_at=timestamp,
        )
        records = [
            record(facts.DECISION, identity, result),
            record(BATCH, batch.batch_id, changed),
            record(IMPORT, import_id, updated),
            *chapters,
        ]
        payload = (
            facts.MaterialAdopted(
                records=records,
                import_id=import_id,
                adoption_ref=reference,
                adopted_refs=after,
                replaced_refs=before,
                affected_submission_refs=[],
            )
            if adopting
            else facts.MaterialDeclined(
                records=records,
                import_id=import_id,
                batch_ref=command.batch_ref,
                decision_ref=reference,
                request_ref=request_ref,
            )
        )
        scope = ("material_import", import_id)
        sequence = await lock_scope_sequence(connection, *scope)
        (event,) = await self.materials.events.append(
            connection,
            ProducerAccess("product", actor, frozenset({scope})),
            [
                EventDraft(
                    uuid4(),
                    facts.ADOPTED if adopting else facts.DECLINED,
                    1,
                    scope[0],
                    import_id,
                    reference,
                    payload.model_dump(mode="json"),
                    command.request_id,
                    subject_refs=(import_ref(import_id),),
                )
            ],
            commit_id=uuid4(),
            correlation_id=request_ref,
            expected_seq={scope: sequence},
        )
        await facts.project(connection, event)
        return result

    async def _contents(
        self,
        connection: AsyncConnection,
        import_id: UUID,
        textbook_id: UUID,
        batch: CandidateBatchFact,
        decision: Ref,
        now: datetime,
    ) -> tuple[list[Ref], list[Ref], list[FactRecord]]:
        before: list[Ref] = []
        older = batch.diff_summary.get("previous_batch")
        affected = [
            str(item["candidate_id"])
            for item in batch.write_set
            if item.get("action") in ("replace", "retire")
        ]
        if older is not None and affected:
            # 取本次被替换/退役的旧候选作为 before 引用。
            prior = PreviousMaterialBatch.model_validate(older)
            before = [
                _candidate_ref(row.candidate_id, row.candidate_revision)
                for row in await connection.execute(
                    text(
                        "SELECT v.candidate_id,v.candidate_revision "
                        "FROM product.material_content_current v "
                        "JOIN product.material_candidate c USING(candidate_id,candidate_revision) "
                        "WHERE v.import_id=:id AND c.batch_id=:prior AND v.validity='current' "
                        "AND v.candidate_id::text=ANY(CAST(:affected AS text[]))"
                    ),
                    {"id": import_id, "prior": prior.batch_id, "affected": affected},
                )
            ]
            before_ids = [ref.id for ref in before]
            dependent = await connection.scalar(
                text(
                    "SELECT 1 FROM product.material_content_current v "
                    "JOIN product.material_candidate c USING(candidate_id,candidate_revision) "
                    "WHERE v.import_id=:id AND v.validity='current' AND c.parent_ref->>'id' "
                    "=ANY(CAST(:parents AS text[])) "
                    "AND NOT(c.candidate_id::text=ANY(CAST(:parents AS text[]))) LIMIT 1"
                ),
                {"id": import_id, "parents": before_ids},
            )
            if dependent:
                # 仍有题内参考挂在被退役题目上，须一并核对。
                raise RequestError(
                    409, "candidate_dependency_changed", "请同时核对受影响的题内参考。"
                )
        after = [
            _candidate_ref(row.candidate_id, row.candidate_revision)
            for row in await connection.execute(
                text(
                    "SELECT candidate_id,candidate_revision FROM product.material_candidate "
                    "WHERE batch_id=:id AND import_id=:import ORDER BY local_key"
                ),
                {"id": batch.batch_id, "import": import_id},
            )
        ]
        proposed = batch.diff_summary["chapters"]
        assert isinstance(proposed, list)
        chapters: list[FactRecord] = []
        # 逐章组装章节记录，版本接前序章节递增。
        for item in proposed:
            assert isinstance(item, dict)
            identity = UUID(str(item["chapter_id"]))
            prior_revision = (
                await connection.scalar(
                    text(
                        "SELECT revision FROM product.material_chapter "
                        "WHERE chapter_id=:id AND textbook_id=:book"
                    ),
                    {"id": identity, "book": textbook_id},
                )
                or 0
            )
            source_ids = item["source_ids"]
            order = item["order"]
            assert isinstance(source_ids, list) and isinstance(order, int)
            chapter = facts.MaterialChapter(
                chapter_id=identity,
                textbook_id=textbook_id,
                parent_id=None,
                title=str(item["name"]),
                sort_order=order,
                revision=prior_revision + 1,
                page_refs=[
                    Ref(owner="product", type="material_page", id=str(page)) for page in source_ids
                ],
                catalog_basis_ref=decision,
                updated_at=now,
            )
            chapters.append(record(facts.CHAPTER, identity, chapter))
        return before, after, chapters

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[AdoptedMaterialResult]:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT request_ref,result_ref FROM product.command_receipt "
                            "WHERE principal_id=:owner AND action=:action AND scope_id=:scope "
                            "AND request_id=:request AND state='completed'"
                        ),
                        {
                            "owner": str(principal),
                            "action": DECIDE,
                            "scope": str(query.resource_id),
                            "request": query.request_id,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                # 无已完成决定收据，按未找到返回。
                return ReceiptView[AdoptedMaterialResult](receipt_state="not_found")
            result = await self._saved(connection, query.resource_id, row["result_ref"]["id"])
        return ReceiptView[AdoptedMaterialResult](
            receipt_state="completed", receipt_ref=row["request_ref"], result=_result(result)
        )

    async def contents(
        self,
        session: SessionView,
        import_id: UUID,
        chapter_id: UUID | None,
        *,
        catalog_only: bool = False,
    ) -> MaterialCurrentContents:
        self.materials.administrator(session)
        async with self.engine.connect() as connection:
            imported = await self.materials.read_import(connection, import_id, lock=True)
            keys = {"id": import_id, "chapter": chapter_id, "book": imported["textbook_id"]}
            items = (
                []
                if catalog_only
                else list(
                    (
                        await connection.scalars(
                            text(
                                "SELECT (to_jsonb(c)-'source_event_id') || "
                                "jsonb_build_object('validity',v.validity,"
                                "'intake_status',s.status,'intake_ref',s.submission_id) "
                                "FROM product.material_content_current v "
                                "JOIN product.material_candidate c "
                                "USING(candidate_id,candidate_revision) "
                                "LEFT JOIN LATERAL (SELECT status,submission_id FROM "
                                "product.material_intake_submission sub "
                                "WHERE sub.import_id=v.import_id "
                                "AND sub.candidate_refs @> jsonb_build_array(jsonb_build_object("
                                "'candidate_id',v.candidate_id,"
                                "'candidate_revision',v.candidate_revision)) "
                                "ORDER BY sub.created_at DESC LIMIT 1) s ON true "
                                "WHERE v.import_id=:id AND v.validity<>'retired' "
                                "AND (CAST(:chapter AS uuid) IS NULL OR v.chapter_id=:chapter) "
                                "ORDER BY v.chapter_id,c.local_key LIMIT 101"
                            ),
                            keys,
                        )
                    ).all()
                )
            )
            chapters = list(
                (
                    await connection.scalars(
                        text(
                            "SELECT to_jsonb(c)-'source_event_id' FROM product.material_chapter c "
                            "WHERE c.textbook_id=:book ORDER BY c.sort_order,c.chapter_id"
                        ),
                        keys,
                    )
                ).all()
            )
        content_revision: int = imported["content_revision"]
        view: dict[str, JsonValue] = {
            "content_revision": content_revision,
            "items": items,
            "chapters": chapters,
        }
        if len(items) > 100 or len(canonical_json(view).encode()) > 4 * 1024**2:
            # 条目数或体积超限，提示收窄到单章查看。
            raise RequestError(413, "payload_too_large", "内容太多，请选择一个章节。")
        return MaterialCurrentContents.model_validate(
            {
                **view,
                "read_token": sha256(
                    f"{import_id}:{content_revision}:{chapter_id}".encode()
                ).hexdigest(),
            }
        )
