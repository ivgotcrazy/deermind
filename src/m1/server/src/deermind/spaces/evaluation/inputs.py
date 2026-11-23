"""以当时的采用版本和原始事实生成有限的评价材料。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.abstractions.hashing import digest
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.product.public.courses import AdoptionView, CourseSnapshot
from deermind.product.public.learning_targets import GoalItem
from deermind.spaces.domain.public import SolutionRef, TaskInstance, TaskRef
from deermind.spaces.evaluation import belief, input_facts
from deermind.spaces.evaluation.public import ClaimDetail, ClaimRef, ClaimView
from deermind.spaces.interaction.public import EvaluationMaterial, EvaluationSource
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

SCOPE = "learning_space"
INTERPRETATION_REF = "M1-EVIDENCE-01"
ACTOR = Ref(owner="evaluation", type="handler", id="evaluation.prepare_input")

type ReadSource = Callable[[UUID, UUID], Awaitable[EvaluationSource]]
type ReadPriorQuestions = Callable[
    [UUID, int, TaskRef, SolutionRef], Awaitable[list[EvaluationMaterial] | None]
]
type ReadAdoption = Callable[[AsyncConnection, UUID, UUID], Awaitable[AdoptionView]]
type ReadClaim = Callable[[UUID, int], Awaitable[ClaimDetail]]
type ReadDomain = Callable[
    [AsyncConnection, UUID, Ref], Awaitable[tuple[dict[str, JsonValue], UUID] | None]
]


@dataclass(frozen=True)
class EvaluationMaterials:
    record: input_facts.InputRecord
    source: EvaluationSource
    claims: list[ClaimView]
    domain: dict[Ref, dict[str, JsonValue]]
    targets: tuple[GoalItem, ...] = ()


def candidate_scope(
    snapshot: CourseSnapshot, claims: dict[ClaimRef, ClaimView]
) -> list[input_facts.CandidateTask]:
    """取得目标采用的 Task，并按教材保留每种方法的独立出处。"""
    selected: dict[TaskRef, dict[SolutionRef, list[Ref]]] = {}
    for chapter in snapshot.chapters:
        for association in chapter.associations:
            if association.active:
                methods = selected.setdefault(association.task_ref, {})
                for method in association.method_refs:
                    methods.setdefault(method, []).append(association.association_ref)
    result: list[input_facts.CandidateTask] = []
    for claim in dict.fromkeys(item.claim_ref for item in snapshot.items):
        definition = claims[claim].definition
        adopted = selected.get(definition.task_ref, {})
        choices = [
            input_facts.CandidateMethod(method_ref=item.method_ref, chapter_sources=sources)
            for item in definition.methods
            if (sources := adopted.get(item.method_ref))
        ]
        result.append(
            input_facts.CandidateTask(
                task_ref=definition.task_ref,
                claim_ref=claim,
                methods=choices,
                gaps=[] if choices else ["adopted_method_missing"],
            )
        )
    return result


def _domain_ref(reference: TaskRef | SolutionRef) -> Ref:
    return Ref(
        owner="domain", type=reference.kind, id=str(reference.object_id), version=reference.version
    )


async def find_prepared(
    db: AsyncConnection, scope: UUID, trigger: UUID
) -> input_facts.InputRecord | None:
    row = await db.scalar(
        text(
            "SELECT to_jsonb(i)-'source_event_id' FROM evaluation.evaluation_input i "
            "WHERE scope_id=:scope AND trigger_event_id=:trigger"
        ),
        {"scope": scope, "trigger": trigger},
    )
    if row is None:
        return None
    return input_facts.InputRecord.model_validate_json(canonical_json(row))


class EvaluationInputs:
    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        attachments: FactAttachments,
        sources: ReadSource,
        adoptions: ReadAdoption,
        claims: ReadClaim,
        domain: ReadDomain,
        prior_questions: ReadPriorQuestions | None = None,
    ) -> None:
        self.engine, self.events, self.attachments = engine, events, attachments
        self.sources, self.adoptions, self.claims, self.domain = sources, adoptions, claims, domain
        self.prior_questions = prior_questions

    async def prepare(self, scope: UUID, trigger: UUID) -> EvaluationMaterials:
        source = await self.sources(scope, trigger)
        if source.scope_id != scope or source.trigger_event_id != trigger:
            raise ValueError("Evaluation source does not match the requested scope")
        async with self.engine.connect() as db:
            adopted = await self.adoptions(db, scope, UUID(source.adoption_ref.id))
        actual, fixed = source.adoption_ref, adopted.adoption_ref
        # 采用记录的 UUID 已唯一固定该次采用；Product 另返回空间内的采用序号。
        if fixed.model_copy(
            update={"revision": actual.revision}
        ) != actual or actual.revision not in (None, fixed.revision):
            raise ValueError("Evaluation requires the adoption recorded by the source")
        claims = {
            claim: (await self.claims(claim.claim_id, claim.revision)).claim
            for claim in dict.fromkeys(item.claim_ref for item in adopted.snapshot.items)
        }
        if any(key != value.claim_ref for key, value in claims.items()):
            raise ValueError("Claim lookup returned a different revision")
        candidates = candidate_scope(adopted.snapshot, claims)
        domain, domain_locators, domain_gaps = await self._read_domain(source, candidates, claims)
        saved = await self._save(
            source,
            input_facts.EvaluationInput(
                adoption_ref=fixed,
                application_ref=adopted.application_ref,
                target_basis_ref=adopted.target_basis_ref,
                activity_ref=source.activity_ref,
                task_use_ref=source.task_use_ref,
                round_ref=source.round_ref,
                plan_ref=source.plan_ref,
                task_instance_ref=source.task_instance_ref,
                occurred_at=source.occurred_at,
                candidate_scope=candidates,
                materials=[
                    input_facts.MaterialLocator(role=item.role, ref=item.ref, sha256=item.sha256)
                    for item in source.materials
                ],
                domain_materials=domain_locators,
                history_basis=[
                    item.ref for item in source.materials if item.role == "prior_question"
                ],
                missing_reasons=[*source.missing_reasons, *domain_gaps],
                interpretation_contract_ref=INTERPRETATION_REF,
                parameter_ref=belief.PARAMETER_REF,
                algorithm_ref=belief.ALGORITHM_REF,
            ),
        )
        return EvaluationMaterials(
            saved, source, list(claims.values()), domain, tuple(adopted.snapshot.items)
        )

    async def _read_domain(
        self,
        source: EvaluationSource,
        candidates: list[input_facts.CandidateTask],
        claims: dict[ClaimRef, ClaimView],
    ) -> tuple[dict[Ref, dict[str, JsonValue]], list[input_facts.DomainLocator], list[str]]:
        needed: dict[Ref, UUID] = {}
        domains: set[UUID] = set()
        for candidate in candidates:
            domain = claims[candidate.claim_ref].definition.domain_id
            domains.add(domain)
            needed[_domain_ref(candidate.task_ref)] = domain
            for method in candidate.methods:
                needed[_domain_ref(method.method_ref)] = domain
        contents: dict[Ref, dict[str, JsonValue]] = {}
        locators: list[input_facts.DomainLocator] = []
        gaps: list[str] = []
        allowed_tasks = [item.task_ref for item in candidates]
        async with self.engine.connect() as db:
            if source.source_kind == "answer":
                fixed = source.task_instance_ref
                if fixed is None:
                    gaps.append("task_instance_missing")
                elif len(domains) == 1:
                    task = await self.domain(db, next(iter(domains)), fixed)
                    if task is None:
                        gaps.append("task_instance_not_found")
                    elif (
                        TaskInstance.model_validate_json(canonical_json(task[0])).task_ref
                        not in allowed_tasks
                    ):
                        gaps.append("task_outside_evaluation_scope")
                    else:
                        contents[fixed], event_id = task
                        locators.append(
                            input_facts.DomainLocator(
                                ref=fixed,
                                source_event_id=event_id,
                                sha256=digest(contents[fixed]),
                            )
                        )
                else:
                    gaps.append("evaluation_domain_unknown")
            for reference, domain in needed.items():
                found = await self.domain(db, domain, reference)
                if found is None:
                    gaps.append(f"{reference.type}_missing:{reference.id}")
                    continue
                contents[reference], event_id = found
                locators.append(
                    input_facts.DomainLocator(
                        ref=reference,
                        source_event_id=event_id,
                        sha256=digest(contents[reference]),
                    )
                )
        return contents, locators, gaps

    async def _save(
        self, source: EvaluationSource, basis: input_facts.EvaluationInput
    ) -> input_facts.InputRecord:
        scope, trigger = source.scope_id, source.trigger_event_id
        async with self.engine.connect() as db:
            previous = await find_prepared(db, scope, trigger)
        if previous:
            if previous.input != basis:
                raise ValueError("A fixed evaluation source returned different material")
            return previous
        saved = input_facts.InputRecord(
            input_id=uuid4(),
            scope_id=scope,
            trigger_event_id=trigger,
            source_seq=source.source_seq,
            source_kind=source.source_kind,
            source_id=source.source_id,
            input=basis,
            created_at=datetime.now(UTC),
        )
        reference = Ref(owner="evaluation", type="evaluation_input", id=str(saved.input_id))
        payload = input_facts.InputPrepared(
            evaluation_input_ref=reference,
            trigger_event_id=trigger,
            records=[
                FactRecord(
                    record_id=reference.id,
                    record_type=input_facts.INPUT,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=saved.model_dump(mode="json")),
                )
            ],
        )
        fact_scope = (SCOPE, scope)
        draft = EventDraft(
            uuid4(),
            input_facts.PREPARED,
            1,
            *fact_scope,
            reference,
            payload.model_dump(mode="json"),
            None,
            causation_event_id=trigger,
        )
        access = ProducerAccess("evaluation", ACTOR, frozenset({fact_scope}), frozenset({trigger}))
        prepared = await self.attachments.prepare(self.events, access, (draft,))
        async with self.engine.begin() as db:
            sequence = await lock_scope_sequence(db, *fact_scope)
            previous = await find_prepared(db, scope, trigger)
            if previous:
                if previous.input != basis:
                    raise ValueError("A fixed evaluation source returned different material")
                return previous
            (event,) = await self.events.append(
                db,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=trigger,
                expected_seq={fact_scope: sequence},
            )
            await input_facts.project(db, event)
        return saved
