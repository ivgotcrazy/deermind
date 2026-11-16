"""多表账号事实夹具；一名学生、两段关系、两次确认，供真实PG重建验证。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.bootstrap.events import event_store
from deermind.foundation.system.events.contracts import EventDraft, ProducerAccess, Ref, StoredEvent
from deermind.product.accounts.facts import AccountFact, AccountSaved
from deermind.product.accounts.projections import apply_account_events
from deermind.product.accounts.usage_events import UsageConfirmed, record
from deermind.product.accounts.usage_facts import (
    ConditionsFact,
    ConfirmationFact,
    GuardianFact,
    RelationFact,
)
from sqlalchemy.ext.asyncio import AsyncEngine


async def student_facts(
    engine: AsyncEngine, *, guardian: UUID | None = None, project: bool = True
) -> tuple[UUID, list[StoredEvent]]:
    """提供已有监护人ID时不重复创建该人事实，用于跨范围依赖测试。"""
    student = uuid4()
    shared = guardian is not None
    guardian = guardian or uuid4()
    actor = Ref(owner="runtime", type="service", id="synthetic-fixture")
    source = Ref(owner="product", type="synthetic_verification", id=str(guardian))
    now = datetime.now(UTC)
    account = AccountFact(
        account_id=student,
        login_identifier=student.hex,
        display_name="Synthetic student",
        role="student",
        status="active",
        revision=1,
        created_at=now,
    )
    person = GuardianFact(
        guardian_id=guardian,
        verified_identity_ref=source,
        display_name="Synthetic guardian",
        created_at=now,
    )
    first = RelationFact(
        relation_id=uuid4(),
        student_id=student,
        guardian_id=guardian,
        revision=1,
        verification_ref=source,
        relation_state="ended",
        previous_relation_id=None,
        actor_ref=actor,
        created_at=now,
    )
    second = first.model_copy(
        update={
            "relation_id": uuid4(),
            "revision": 2,
            "relation_state": "active",
            "previous_relation_id": first.relation_id,
        }
    )
    condition = ConditionsFact(
        student_id=student,
        revision=1,
        confirmation_refs=[],
        eligibility="pending",
        reasons=[],
        updated_at=now,
    )
    payload = AccountSaved(
        account_id=student,
        action="create_student",
        account_revision=1,
        relation_refs=[
            Ref(owner="product", type="guardian_relation", id=str(r.relation_id))
            for r in (first, second)
        ],
        records=[record("account", "product.accounts", account)]
        + ([] if shared else [record("guardian", "product.guardian_records", person)])
        + [
            record(str(r.relation_id), "product.student_guardian_relations", r)
            for r in (first, second)
        ]
        + [record("conditions", "product.usage_conditions", condition)],
    )
    drafts = [
        EventDraft(
            uuid4(),
            "TrialAccountSaved",
            1,
            "account",
            student,
            Ref(owner="product", type="account", id=str(student), revision=1),
            payload.model_dump(mode="json"),
            str(uuid4()),
        )
    ]
    for revision, kind in enumerate(("guardian_consent", "student_assent"), start=2):
        confirmation = ConfirmationFact(
            confirmation_id=uuid4(),
            student_id=student,
            kind=kind,
            notice_ref=Ref(owner="product", type="test_notice", id="test"),
            decision="accepted",
            source_ref=source,
            actor_ref=actor,
            occurred_at=now,
            created_at=now,
        )
        ref = Ref(owner="product", type="usage_confirmation", id=str(confirmation.confirmation_id))
        condition = condition.model_copy(
            update={
                "revision": revision,
                "confirmation_refs": [*condition.confirmation_refs, ref],
                "eligibility": "allowed" if revision == 3 else "pending",
            }
        )
        confirmed = UsageConfirmed(
            student_id=student,
            confirmation_ref=ref,
            usage_conditions_ref=Ref(
                owner="product", type="usage_conditions", id=str(student), revision=revision
            ),
            notice_text="Synthetic notice only",
            records=[
                record("confirmation", "product.usage_confirmations", confirmation),
                record("conditions", "product.usage_conditions", condition),
            ],
        )
        drafts.append(
            EventDraft(
                uuid4(),
                "UsageConfirmationRecorded",
                2,
                "account",
                student,
                Ref(owner="product", type="account", id=str(student)),
                confirmed.model_dump(mode="json"),
                str(uuid4()),
            )
        )
    async with engine.begin() as connection:
        events = await event_store().append(
            connection,
            ProducerAccess("product", actor, frozenset({("account", student)})),
            drafts,
            commit_id=uuid4(),
            correlation_id=uuid4(),
            expected_seq={("account", student): 0},
        )
        if project:
            await apply_account_events(connection, events)
    return student, events
