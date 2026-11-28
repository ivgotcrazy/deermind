"""Generate, revise and publish a complete set of task criteria for one book model."""

from uuid import UUID, uuid4, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.projections.receipts import application
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation import definition_facts as facts
from deermind.spaces.evaluation.public import (
    STANDARD_ASPECTS,
    AspectDefinition,
    AspectRule,
    AssessmentModel,
    ClaimDefinition,
    ClaimRef,
    ExecutionCriterion,
    MethodDefinition,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def item(kind: str, identifier: str, model: FactModel) -> FactRecord:
    return FactRecord(
        record_id=identifier,
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=model.model_dump(mode="json")),
    )


RECORD = "evaluation.assessment_model"
EVENT = "AssessmentModelSaved"


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if len(payload.records) != 1:
        raise ValueError("Expected one assessment model snapshot")
    rec = payload.records[0]
    if (
        rec.record_type != RECORD
        or not isinstance(rec.content, InlineContent)
        or (rec.content.value.get("model_id"), rec.content.value.get("extraction_id"))
        != (rec.record_id, str(draft.scope_id))
    ):
        raise ValueError("Assessment snapshot does not belong to its source edition")


REGISTRATION = EventRegistration(
    EVENT, 1, "evaluation", "extraction", EventPayload, validate, {(RECORD, 1): AssessmentModel}
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    rec = event.payload.records[0]
    assert isinstance(rec.content, InlineContent)
    async with application(db, "evaluation.assessment_models", 1, event.draft.event_id) as needed:
        if needed:
            await db.execute(
                text(
                    "INSERT INTO evaluation.assessment_model SELECT * FROM jsonb_populate_record("
                    "NULL::evaluation.assessment_model,CAST(:body AS jsonb)) ON "
                    "CONFLICT(model_id) DO UPDATE SET "
                    "revision=excluded.revision,status=excluded.status,claims=excluded.claims,source_event_id=excluded.source_event_id"
                ),
                {
                    "body": canonical_json(
                        {**rec.content.value, "source_event_id": str(event.draft.event_id)}
                    )
                },
            )


async def save_fact(
    db: AsyncConnection,
    events: EventStore,
    files: FactAttachments,
    actor: Ref,
    request: UUID,
    kind: str,
    scope_id: UUID,
    event_type: str,
    owner: Ref,
    payload: EventPayload,
) -> StoredEvent:
    scope = (kind, scope_id)
    access = ProducerAccess("evaluation", actor, frozenset({scope}))
    draft = EventDraft(
        uuid4(), event_type, 1, *scope, owner, payload.model_dump(mode="json"), str(request)
    )
    prepared = await files.prepare(events, access, (draft,))
    seq = await lock_scope_sequence(db, *scope)
    (saved,) = await events.append(
        db, access, prepared, commit_id=uuid4(), correlation_id=request, expected_seq={scope: seq}
    )
    return saved


async def store_model(
    db: AsyncConnection,
    events: EventStore,
    files: FactAttachments,
    actor: Ref,
    request: UUID,
    model: AssessmentModel,
) -> UUID:
    payload = EventPayload(records=[item(RECORD, str(model.model_id), model)])
    event = await save_fact(
        db,
        events,
        files,
        actor,
        request,
        "extraction",
        model.extraction_id,
        EVENT,
        Ref(
            owner="evaluation",
            type="assessment_model",
            id=str(model.model_id),
            revision=model.revision,
        ),
        payload,
    )
    await project(db, event)
    return event.draft.event_id


def definitions(
    model: AssessmentModel, domain: UUID, expected: dict[TaskRef, list[SolutionRef]]
) -> list[tuple[ClaimRef, ClaimDefinition]]:
    by_task = {entry.task_id: entry for entry in model.claims}
    if (
        len(by_task) != len(model.claims)
        or set(by_task) != {task.object_id for task in expected}
        or not expected
    ):
        raise RequestError(422, "incomplete", "每个教学任务都需要且只能有一项 Claim。")
    result: list[tuple[ClaimRef, ClaimDefinition]] = []
    for task, methods in expected.items():
        standard = by_task[task.object_id]
        rules = {m.method_id: m for m in standard.methods}
        if (
            not methods
            or len(rules) != len(standard.methods)
            or set(rules) != {m.object_id for m in methods}
        ):
            raise RequestError(
                422, "incomplete", f"《{standard.title}》的判据须覆盖本任务的全部方法。"
            )
        claim_id = uuid5(model.model_id, str(task.object_id))
        criteria: list[ExecutionCriterion] = []
        method_defs: list[MethodDefinition] = []
        for method in methods:
            rule = rules[method.object_id]
            if (
                len(rule.aspects) != len(STANDARD_ASPECTS)
                or {a.aspect for a in rule.aspects} != STANDARD_ASPECTS.keys()
            ):
                raise RequestError(
                    422, "incomplete", f"《{standard.title}》的方法缺少四方面证据判据。"
                )
            cid = uuid5(claim_id, str(method.object_id))
            criteria.append(
                ExecutionCriterion(
                    criterion_id=cid,
                    title=standard.title,
                    required_inputs=["学生作答原文及实际帮助记录"],
                    judgement_basis=standard.description,
                    pass_description=rule.pass_description,
                    fail_description=rule.fail_description,
                    unknown_description=rule.unknown_description,
                )
            )
            method_defs.append(
                MethodDefinition(
                    method_ref=method,
                    criterion_ids=[cid],
                    aspect_rules=[
                        AspectRule(
                            aspect_code=a.aspect,
                            judgement_basis=a.evidence,
                            evidence_requirements=[a.evidence],
                            condition_schema={"type": "object", "additionalProperties": False},
                            default_values={},
                        )
                        for a in rule.aspects
                    ],
                )
            )
        result.append(
            (
                ClaimRef(claim_id=claim_id, revision=1),
                ClaimDefinition(
                    domain_id=domain,
                    task_ref=task,
                    title=standard.title,
                    description=standard.description,
                    aspects=[
                        AspectDefinition(code=k, label=v, description=v)
                        for k, v in STANDARD_ASPECTS.items()
                    ],
                    criteria=criteria,
                    methods=method_defs,
                ),
            )
        )
    return result


async def publish_claims(
    db: AsyncConnection,
    events: EventStore,
    files: FactAttachments,
    model: AssessmentModel,
    actor: Ref,
    request: UUID,
    domain: UUID,
    expected: dict[TaskRef, list[SolutionRef]],
) -> None:
    for ref, definition in definitions(model, domain, expected):
        version = facts.ClaimVersion(
            model_id=model.model_id,
            claim_id=ref.claim_id,
            revision=1,
            definition=definition,
            gaps=[],
            request_ref=str(request),
            actor_ref=actor,
            created_at=await db.scalar(text("SELECT clock_timestamp()")),
        )
        payload = facts.ClaimChanged(
            domain_id=domain,
            task_ref=definition.task_ref,
            previous_claim_ref=None,
            claim_ref=ref,
            action="publish_model",
            affected_method_refs=[m.method_ref for m in definition.methods],
            affected_criterion_ids=[c.criterion_id for c in definition.criteria],
            request_ref=request,
            records=[item(facts.RECORD, facts.RECORD_ID, version)],
        )
        event = await save_fact(
            db,
            events,
            files,
            actor,
            request,
            "domain",
            domain,
            facts.EVENT,
            Ref(owner="evaluation", type="claim", id=str(ref.claim_id), revision=1),
            payload,
        )
        await facts.project(db, event)


async def read_models(db: AsyncConnection, extraction: UUID) -> list[AssessmentModel]:
    rows = await db.scalars(
        text(
            "SELECT to_jsonb(m)-'source_event_id' FROM evaluation.assessment_model m WHERE "
            "extraction_id=:id ORDER BY number DESC"
        ),
        {"id": extraction},
    )
    return [AssessmentModel.model_validate_json(canonical_json(row)) for row in rows]


async def require_members(
    db: AsyncConnection, extraction: UUID, model: UUID, claims: set[ClaimRef]
) -> None:
    rows = await db.execute(
        text(
            "SELECT c.claim_id,c.head_revision FROM evaluation.assessment_model m "
            "JOIN evaluation.claim c USING(model_id) WHERE m.extraction_id=:extraction AND "
            "m.model_id=:model AND m.status='published'"
        ),
        {"extraction": extraction, "model": model},
    )
    members = {(row.claim_id, row.head_revision) for row in rows}
    if not claims or not {(c.claim_id, c.revision) for c in claims} <= members:
        raise RequestError(
            409, "invalid_reference", "所选 Claim 必须属于这版提炼下同一套已发布评估标准。"
        )
