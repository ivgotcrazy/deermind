"""首次使用确认：校验本人身份、保存原始决定，再保存确定性条件快照。"""

from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.reading import EventPartRef, ReadAccess
from deermind.foundation.system.events.store import EventStore, canonical_json
from deermind.product.accounts.conditions import derive_conditions
from deermind.product.accounts.save import canonical_actor
from deermind.product.accounts.transactions import (
    append_account_event,
    authorize,
    database_time,
    lock_accounts,
)
from deermind.product.accounts.usage_events import UsageConfirmed, record
from deermind.product.accounts.usage_facts import ConditionsFact, ConfirmationFact
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import AuthError, SessionView
from deermind.product.public.notice import TEST_NOTICE, TEST_NOTICE_TEXT, assent_source
from deermind.product.public.usage import (
    ConfirmationResult,
    ConfirmUsageRequest,
    ConfirmUsageResponse,
    UsageView,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


async def current_conditions(connection: AsyncConnection, student: UUID) -> ConditionsFact:
    row = (
        (
            await connection.execute(
                text(
                    "SELECT student_id,revision,confirmation_refs,eligibility,"
                    "reasons,updated_at FROM product.usage_conditions WHERE student_id=:id"
                ),
                {"id": student},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AuthError(404, "not_found", "使用确认记录不存在。")
    # PG JSONB中的UUID等由正式DTO解码，不能靠隐式Python类型转换。
    return ConditionsFact.model_validate(dict(row))


class AccountUsage:
    def __init__(self, engine: AsyncEngine, store: EventStore, reader: EventReader) -> None:
        self.engine, self.store, self.reader = engine, store, reader

    async def view(self, session: SessionView) -> UsageView:
        if session.account.role != "student":
            raise AuthError(403, "forbidden", "此入口只显示本人的使用确认。")
        async with self.engine.connect() as connection:
            condition = await current_conditions(connection, session.account.account_id)
        return UsageView.model_validate(
            {
                "student_id": condition.student_id,
                "revision": condition.revision,
                "notice_ref": TEST_NOTICE,
                "notice_text": TEST_NOTICE_TEXT,
                "source_ref": assent_source(str(condition.student_id), condition.revision),
                "allowed": condition.eligibility == "allowed",
                "gaps": [r.model_dump() for r in condition.reasons],
                "can_confirm": any(r.path == "student_assent" for r in condition.reasons),
            }
        )

    async def confirm(
        self, session: SessionView, body: ConfirmUsageRequest
    ) -> ConfirmUsageResponse:
        decision = body.confirmation
        student = decision.student_id
        actor = Ref(owner="product", type="account", id=str(session.account.account_id))
        is_student = session.account.role == "student"
        if is_student and (
            student != session.account.account_id or decision.kind != "student_assent"
        ):
            raise AuthError(403, "forbidden", "只能确认本人的使用意愿。")
        if decision.notice_ref != TEST_NOTICE:
            raise AuthError(409, "notice_changed", "告知内容已变化，请重新查看。")
        if is_student and (
            decision.source_ref != assent_source(str(student), body.expected_revision)
            or decision.occurred_at is not None
            or decision.decision == "pending"
        ):
            raise AuthError(400, "invalid_request", "请通过本人的确认页面提交。")
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=canonical_actor(actor),
                action="record_usage_confirmation",
                scope_id=str(student),
                request_id=str(body.request_id),
                normalized_input=body.model_dump(mode="json"),
            )
            await lock_accounts(connection, {student, session.account.account_id})
            await authorize(connection, session, admin=not is_student)
            if receipt.result_ref is None:
                condition = await current_conditions(connection, student)
                if condition.revision != body.expected_revision:
                    raise AuthError(409, "revision_conflict", "确认条件已变化，请刷新后重试。")
                now = await database_time(connection)
                if decision.occurred_at is not None and (
                    decision.occurred_at.tzinfo is None or decision.occurred_at > now
                ):
                    raise AuthError(400, "invalid_request", "核实时间必须明确且不能晚于现在。")
                confirmations: list[ConfirmationFact] = []
                rows = (
                    await connection.execute(
                        text(
                            "SELECT DISTINCT ON (kind) confirmation_id,student_id,kind, "
                            "notice_ref,decision,"
                            "source_ref,actor_ref,occurred_at,created_at "
                            "FROM product.usage_confirmations "
                            "WHERE student_id=:id AND notice_ref=CAST(:notice AS jsonb) "
                            "ORDER BY kind,created_at DESC,confirmation_id DESC"
                        ),
                        {"id": student, "notice": TEST_NOTICE.model_dump_json()},
                    )
                ).mappings()
                for row in rows:
                    fact = ConfirmationFact.model_validate(dict(row))
                    if fact.kind == decision.kind and fact.decision == "accepted":
                        raise AuthError(
                            409, "already_confirmed", "此项已确认；本轮不提供撤回流程。"
                        )
                    if fact.kind != decision.kind:
                        confirmations.append(fact)
                confirmation = ConfirmationFact(
                    confirmation_id=uuid4(),
                    student_id=student,
                    kind=decision.kind,
                    notice_ref=TEST_NOTICE,
                    decision=decision.decision,
                    source_ref=decision.source_ref,
                    actor_ref=actor,
                    occurred_at=now if is_student else decision.occurred_at,
                    created_at=now,
                )
                confirmations.append(confirmation)
                verified = bool(
                    await connection.scalar(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM product.student_guardian_relations r "
                            "WHERE student_id=:id AND relation_state='active' AND NOT EXISTS "
                            "(SELECT 1 FROM product.student_guardian_relations n "
                            "WHERE n.previous_relation_id=r.relation_id))"
                        ),
                        {"id": student},
                    )
                )
                updated = derive_conditions(
                    student_id=student,
                    revision=condition.revision + 1,
                    now=now,
                    notice_ref=TEST_NOTICE,
                    guardian_verified=verified,
                    confirmations=confirmations,
                )
                payload = UsageConfirmed(
                    student_id=student,
                    confirmation_ref=Ref(
                        owner="product",
                        type="usage_confirmation",
                        id=str(confirmation.confirmation_id),
                    ),
                    usage_conditions_ref=Ref(
                        owner="product",
                        type="usage_conditions",
                        id=str(student),
                        revision=updated.revision,
                    ),
                    notice_text=TEST_NOTICE_TEXT,
                    records=[
                        record("confirmation", "product.usage_confirmations", confirmation),
                        record("conditions", "product.usage_conditions", updated),
                    ],
                )
                event_id = await append_account_event(
                    connection,
                    self.store,
                    actor=actor,
                    account=student,
                    event_type="UsageConfirmationRecorded",
                    schema_version=2,
                    payload=payload,
                    request_id=str(body.request_id),
                    receipt_id=receipt.request_ref,
                )
                receipt = await complete_request(
                    connection, receipt, Ref(owner="runtime", type="event", id=str(event_id))
                )
        if receipt.result_ref is None:
            raise RuntimeError("Confirmation receipt has no result")
        # 重复提交读取原事件的快照，不把后来变化的条件伪装为原请求结果。
        facts = await self.reader.read_event_facts(
            ReadAccess(
                principal_id=str(session.account.account_id),
                handler_id="product.usage_receipt",
                module="product",
                purpose="execution_support",
                authorization_ref=str(session.session_id),
                scopes=frozenset({("account", student)}),
                execution_ref=receipt.request_ref,
            ),
            [
                EventPartRef(event_id=UUID(receipt.result_ref.id), record_id="conditions", path=""),
                EventPartRef(
                    event_id=UUID(receipt.result_ref.id), record_id="confirmation", path=""
                ),
            ],
            purpose="execution_support",
        )
        items = facts["items"]
        if not isinstance(items, list) or len(items) != 2:
            raise RuntimeError("Invalid confirmation fact result")
        first, second = items
        if not isinstance(first, dict) or not isinstance(second, dict):
            raise RuntimeError("Invalid confirmation fact shape")
        saved = ConditionsFact.model_validate_json(canonical_json(first["content"]))
        original = ConfirmationFact.model_validate_json(canonical_json(second["content"]))
        return ConfirmUsageResponse(
            request_ref=receipt.request_ref,
            result=ConfirmationResult.model_validate(
                {
                    "confirmation_ref": Ref(
                        owner="product", type="usage_confirmation", id=str(original.confirmation_id)
                    ),
                    "conditions_revision": saved.revision,
                    "allowed": saved.eligibility == "allowed",
                    "gaps": [r.model_dump() for r in saved.reasons],
                }
            ),
        )
