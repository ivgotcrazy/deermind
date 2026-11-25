"""教材提交已采用的候选，领域的受理结果通过事件回写。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, EventPayload, ProducerAccess, Ref
from deermind.abstractions.material_intake import (
    REQUESTED,
    CandidateKey,
    IntakeDecided,
    IntakeRequested,
    IntakeSource,
)
from deermind.foundation.system.delivery.outbox import delivery_state
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials import intake_facts as facts
from deermind.product.materials.facts import record
from deermind.product.materials.receiving import MaterialReceiving, import_ref
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.material_intake import (
    SUBMIT_INTAKE,
    IntakeAccepted,
    IntakeSubmissionView,
    SubmitDomainIntake,
)
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class MaterialIntake:
    def __init__(self, materials: MaterialReceiving) -> None:
        self.materials = materials
        self.engine = materials.engine

    async def require_current_source(
        self, connection: AsyncConnection, import_id: UUID, source: IntakeSource
    ) -> None:
        """短事务内锁定教材，再验证领域将要使用的那条采用记录。"""
        await self.materials.read_import(connection, import_id, lock=True)
        available = await connection.scalar(
            text(
                "SELECT 1 FROM product.material_content_current v "
                "JOIN product.material_candidate c USING(candidate_id,candidate_revision) "
                "WHERE v.import_id=:scope AND v.candidate_id=:id "
                "AND v.candidate_revision=:revision "
                "AND v.adoption_ref=:adoption AND c.source_event_id=:event AND v.validity='current'"
            ),
            {
                "scope": import_id,
                "id": source.candidate_ref.candidate_id,
                "revision": source.candidate_ref.candidate_revision,
                "adoption": UUID(source.adoption_ref.id),
                "event": source.candidate_fact.event_id,
            },
        )
        if available is None:
            # 候选已退役、版本不符或采用记录不一致，引用已失效。
            raise RequestError(409, "source_changed", "所引用的教材内容已变化，请重新提交。")

    async def _read(
        self, connection: AsyncConnection, import_id: UUID, submission_id: UUID
    ) -> facts.SubmissionFact:
        row = await connection.scalar(
            text(
                "SELECT to_jsonb(s)-'source_event_id' FROM product.material_intake_submission s "
                "WHERE import_id=:scope AND submission_id=:id"
            ),
            {"scope": import_id, "id": submission_id},
        )
        if row is None:
            raise RequestError(404, "not_found", "找不到本教材的入库提交。")
        # 命中提交记录后转为事实模型。
        return facts.SubmissionFact.model_validate_json(canonical_json(row))

    async def _view(
        self, connection: AsyncConnection, row: facts.SubmissionFact
    ) -> IntakeSubmissionView:
        delivery = await delivery_state(connection, row.trigger_event_id)
        # 租约在途对外仍显示为待送达。
        visible_delivery = "pending" if delivery == "leased" else delivery
        retired = await connection.scalar(
            text("SELECT status='deleted' FROM product.material_import WHERE import_id=:id"),
            {"id": row.import_id},
        )
        return IntakeSubmissionView(
            submission_id=row.submission_id,
            trigger_event_ref=row.trigger_event_id,
            status=row.status,
            domain_receipt_ref=row.domain_receipt_ref,
            items=row.items,
            issues=[Issue.model_validate(item) for item in row.issues],
            # 导入已删除时提交等待状态视为关闭。
            wait_state="closed" if retired else row.wait_state,
            delivery_state=visible_delivery
            if visible_delivery in ("pending", "delivered", "exhausted")
            else "unknown",
        )

    async def detail(
        self, session: SessionView, import_id: UUID, submission_id: UUID
    ) -> IntakeSubmissionView:
        self.materials.administrator(session)
        async with self.engine.connect() as connection:
            return await self._view(
                connection, await self._read(connection, import_id, submission_id)
            )

    async def _sources(
        self, connection: AsyncConnection, import_id: UUID, command: SubmitDomainIntake
    ) -> list[IntakeSource]:
        selected: dict[CandidateKey, RowMapping] = {}
        sources: list[IntakeSource] = []
        # 逐条核对所采用候选是否为当前有效版本。
        for reference in command.adopted_content_refs:
            item = (
                (
                    await connection.execute(
                        text(
                            "SELECT c.kind,c.parent_ref,c.source_event_id,v.adoption_ref "
                            "FROM product.material_content_current v "
                            "JOIN product.material_candidate c "
                            "USING(candidate_id,candidate_revision) "
                            "WHERE v.import_id=:scope AND c.candidate_id=:id "
                            "AND c.candidate_revision=:rev "
                            "AND c.basis_revision=:basis AND v.validity='current'"
                        ),
                        {
                            "scope": import_id,
                            "id": reference.candidate_id,
                            "rev": reference.candidate_revision,
                            "basis": reference.basis_revision,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
            if item is None or reference.key() in selected:
                # 引用失效或同一候选重复提交。
                raise RequestError(409, "invalid_reference", "只可提交不同且当前已采用的内容。")
            selected[reference.key()] = item
            sources.append(
                IntakeSource(
                    candidate_ref=reference,
                    candidate_fact=EventPartRef(
                        event_id=item.source_event_id,
                        record_id=str(reference.candidate_id),
                        path="",
                    ),
                    adoption_ref=Ref(
                        owner="product", type="material_adoption", id=str(item["adoption_ref"])
                    ),
                )
            )

        required = {
            reference for reference, item in selected.items() if item["kind"] == "reference"
        }
        bound = {binding.candidate_ref.key() for binding in command.parent_bindings}
        if bound != required or len(bound) != len(command.parent_bindings):
            # 参考类候选与父题绑定必须一一对应，不得遗漏或重复。
            raise RequestError(400, "missing_parent", "每条题内参考都需要指定对应题目。")
        for binding in command.parent_bindings:
            if binding.parent_candidate_ref is not None:
                parent = binding.parent_candidate_ref
                expected = selected[binding.candidate_ref.key()]["parent_ref"]
                if (
                    parent.key() not in selected
                    or selected[parent.key()]["kind"] != "task_instance"
                    or expected is None
                    or expected["id"] != str(parent.candidate_id)
                    or expected["revision"] != parent.candidate_revision
                ):
                    # 父题须在本批内、类型为题目，且与候选登记的父引用一致。
                    raise RequestError(400, "missing_parent", "请同时提交题内参考所对应的题目。")
        return sources

    async def _write(
        self,
        connection: AsyncConnection,
        row: facts.SubmissionFact,
        event_type: str,
        payload: EventPayload,
        actor: Ref,
        event_id: UUID,
        correlation: UUID,
        *,
        request_id: str | None = None,
        cause: UUID | None = None,
    ) -> Ref:
        result = Ref(owner="product", type="material_intake_submission", id=str(row.submission_id))
        scope = ("material_import", row.import_id)
        sequence = await lock_scope_sequence(connection, *scope)
        (event,) = await self.materials.events.append(
            connection,
            ProducerAccess(
                "product",
                actor,
                frozenset({scope}),
                frozenset({cause}) if cause else frozenset(),
            ),
            [
                EventDraft(
                    event_id,
                    event_type,
                    1,
                    scope[0],
                    row.import_id,
                    result,
                    payload.model_dump(mode="json"),
                    request_id,
                    cause,
                    (import_ref(row.import_id),),
                )
            ],
            commit_id=uuid4(),
            correlation_id=correlation,
            expected_seq={scope: sequence},
        )
        await facts.project(connection, event)
        return result

    async def submit(
        self, session: SessionView, import_id: UUID, command: SubmitDomainIntake
    ) -> IntakeAccepted:
        principal = self.materials.administrator(session)
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=str(principal),
                action=SUBMIT_INTAKE,
                scope_id=str(import_id),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json"),
            )
            if receipt.result_ref is None:
                # 本事务抢到收据身份，持锁校验并落提交事件。
                imported = await self.materials.read_import(connection, import_id, lock=True)
                sources = await self._sources(connection, import_id, command)
                row = facts.SubmissionFact(
                    submission_id=uuid4(),
                    import_id=import_id,
                    candidate_refs=command.adopted_content_refs,
                    parent_bindings=command.parent_bindings,
                    trigger_event_id=uuid4(),
                    status="submitted",
                    domain_receipt_ref=None,
                    wait_state="waiting",
                    items=[],
                    issues=[],
                    created_at=datetime.now(UTC),
                )
                payload = IntakeRequested(
                    domain_id=imported["domain_id"],
                    intake_request_id=row.submission_id,
                    candidate_refs=row.candidate_refs,
                    sources=sources,
                    parent_bindings=row.parent_bindings,
                    records=[record(facts.SUBMISSION, row.submission_id, row)],
                )
                reference = await self._write(
                    connection,
                    row,
                    REQUESTED,
                    payload,
                    Ref(owner="product", type="account", id=str(principal)),
                    row.trigger_event_id,
                    receipt.request_ref,
                    request_id=command.request_id,
                )
                await complete_request(connection, receipt, reference)
            else:
                # 幂等重放：读回原提交事实组装结果。
                row = await self._read(connection, import_id, UUID(receipt.result_ref.id))
            return IntakeAccepted(
                request_ref=receipt.request_ref, result=await self._view(connection, row)
            )

    async def receive_result(self, connection: AsyncConnection, notice: EventNotice) -> Acceptance:
        raw = await self.materials.reader.read_facts(
            notice.scope_kind,
            notice.scope_id,
            notice.event_id,
            expected_event_type=notice.event_type,
            refs=[EventPartRef(event_id=notice.event_id, record_id=None, path="")],
        )
        parts = raw["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        content = parts[0]["content"]
        assert isinstance(content, dict)
        decision = IntakeDecided.model_validate_json(
            canonical_json(
                {
                    **content,
                    "records": [],
                }
            )
        )
        row = await self._read(connection, notice.scope_id, decision.intake_request_id)
        if row.trigger_event_id != decision.trigger_event_id:
            # 回写结果须对应原始提交触发事件，防止串单。
            raise ValueError("Intake outcome does not match the original submission")
        updated = row.model_copy(
            update={
                "status": decision.outcome,
                "wait_state": "closed",
                "domain_receipt_ref": decision.receipt_ref,
                "items": decision.items,
                "issues": decision.issues,
            }
        )
        payload = facts.IntakeStatusUpdated(
            submission_id=row.submission_id,
            domain_event_id=notice.event_id,
            domain_receipt_ref=decision.receipt_ref,
            outcome=decision.outcome,
            records=[record(facts.SUBMISSION, row.submission_id, updated)],
        )
        reference = await self._write(
            connection,
            updated,
            facts.STATUS,
            payload,
            Ref(owner="product", type="service", id="material-intake"),
            uuid4(),
            row.submission_id,
            cause=notice.event_id,
        )
        return Acceptance(disposition="accepted", arrangement_refs=[reference])

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[IntakeSubmissionView]:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT request_ref,result_ref FROM product.command_receipt "
                        "WHERE principal_id=:owner AND action=:action AND scope_id=:scope "
                        "AND request_id=:request AND state='completed'"
                    ),
                    {
                        "owner": str(principal),
                        "action": SUBMIT_INTAKE,
                        "scope": str(query.resource_id),
                        "request": query.request_id,
                    },
                )
            ).one_or_none()
            if row is None:
                # 无已完成提交收据，按未找到返回。
                return ReceiptView[IntakeSubmissionView](receipt_state="not_found")
            saved = await self._read(connection, query.resource_id, UUID(row.result_ref["id"]))
            return ReceiptView[IntakeSubmissionView](
                receipt_state="completed",
                receipt_ref=row.request_ref,
                result=await self._view(connection, saved),
            )
