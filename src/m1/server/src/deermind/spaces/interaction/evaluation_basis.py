"""只沿本次作答或教学收束的正式事实读取取证原文。"""

from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.events.query import EventReader
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.interaction import (
    conversation_facts,
    help_facts,
    provision_facts,
    round_facts,
    task_facts,
)
from deermind.spaces.interaction.public import (
    EvaluationMaterial,
    EvaluationMaterialRole,
    EvaluationSource,
)
from pydantic import JsonValue
from sqlalchemy import text

SCOPE = "learning_space"


class EventLocation(FactModel):
    event_type: str
    owner_ref: Ref
    scope_event_seq: int


class HelpBasis(FactModel):
    mode: Literal["practice", "detection"] | None = None
    task_use_event_id: UUID | None = None
    help_event_ids: list[UUID] | None = None
    prior_task_use_event_ids: list[UUID] | None = None
    external_help: str | None = None


class EvaluationFacts:
    def __init__(self, reader: EventReader) -> None:
        self.reader = reader

    async def _location(
        self, scope: UUID, event: UUID, types: tuple[str, ...], *, cutoff: int | None = None
    ) -> EventLocation:
        page = await self.reader.query_metadata(
            SCOPE,
            scope,
            filters=EventFilter(event_id=event, event_types=types),
            upper_seq=cutoff,
            limit=1,
        )
        items = page["items"]
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise LookupError("Evaluation source is outside the authorized facts")
        row = items[0]
        return EventLocation.model_validate_json(
            canonical_json({key: row[key] for key in EventLocation.model_fields})
        )

    async def _parts(
        self,
        scope: UUID,
        event: UUID,
        kind: str,
        selectors: list[tuple[EvaluationMaterialRole, str | None, str]],
    ) -> list[EvaluationMaterial]:
        refs = [
            EventPartRef(event_id=event, record_id=record, path=path)
            for _, record, path in selectors
        ]
        found = await self.reader.read_facts(
            SCOPE, scope, event, expected_event_type=kind, schema_version=1, refs=refs
        )
        items = found["items"]
        if not isinstance(items, list) or len(items) != len(refs):
            raise ValueError("Incomplete event reading response")
        materials: list[EvaluationMaterial] = []
        for (role, _, _), ref, value in zip(selectors, refs, items, strict=True):
            if not isinstance(value, dict) or value["completeness"] != "complete":
                raise LookupError("A recorded evaluation field is missing")
            digest = value["sha256"]
            if not isinstance(digest, str):
                raise ValueError("Invalid event fragment checksum")
            materials.append(
                EvaluationMaterial(role=role, ref=ref, sha256=digest, content=value["content"])
            )
        return materials

    async def read(self, scope: UUID, trigger: UUID) -> EvaluationSource:
        location = await self._location(
            scope, trigger, (task_facts.SUBMITTED, provision_facts.CLOSED)
        )
        if location.event_type == task_facts.SUBMITTED:
            return await self._answer(scope, trigger, location)
        return await self._teaching(scope, trigger, location)

    async def prior_questions(
        self, scope: UUID, cutoff: int, task: TaskRef, method: SolutionRef
    ) -> list[EvaluationMaterial] | None:
        """Look up earlier questions with a recorded assignment to this method."""
        async with self.reader.engine.connect() as db:
            candidates = (
                await db.scalars(
                    text("""
                SELECT u.source_event_id FROM interaction.task_uses u
                JOIN runtime.events e ON e.event_id=u.source_event_id
                WHERE u.scope_id=:scope AND e.scope_id=:scope AND e.scope_event_seq<:cutoff
                AND (
                    u.method_conditions @> CAST(:plan AS jsonb)
                    OR u.method_conditions @> CAST(:practice AS jsonb)
                )
                ORDER BY e.scope_event_seq DESC LIMIT 101
            """),
                    {
                        "scope": scope,
                        "cutoff": cutoff,
                        "plan": canonical_json(
                            {
                                "task_ref": task.model_dump(mode="json"),
                                "methods": [method.model_dump(mode="json")],
                            }
                        ),
                        "practice": canonical_json(
                            {"method_refs": [method.model_dump(mode="json")]}
                        ),
                    },
                )
            ).all()
        if len(candidates) > 100:
            return None
        return [
            question
            for event in candidates
            for _record, question in [await self._question(scope, event, cutoff, "prior_question")]
        ]

    async def _answer(
        self, scope: UUID, trigger: UUID, location: EventLocation
    ) -> EvaluationSource:
        identity = location.owner_ref.id
        selectors: list[tuple[EvaluationMaterialRole, str | None, str]] = [
            ("answer", None, ""),
            ("answer", identity, ""),
            ("answer", identity, "/answer"),
            ("help_basis", identity, "/help_basis"),
        ]
        # 动作字段保存本次采用、活动及检测轮引用。
        header, source, answer, help_material = await self._parts(
            scope, trigger, task_facts.SUBMITTED, selectors
        )
        envelope = task_facts.AnswerSubmitted.model_validate_json(
            canonical_json({"records": [], **_object(header.content)})
        )
        submission = task_facts.SubmissionFact.model_validate_json(canonical_json(source.content))
        basis = HelpBasis.model_validate_json(canonical_json(help_material.content))
        if (
            submission.scope_id != scope
            or submission.event_ref != trigger
            or str(submission.submission_id) != identity
            or envelope.submission_ref != location.owner_ref
            or envelope.adoption_ref.id != str(submission.adoption_ref)
        ):
            raise ValueError("Submission does not match its trigger")
        materials = [answer, help_material]
        missing: list[str] = []
        use: task_facts.TaskUseFact | None = None
        if basis.task_use_event_id is None:
            missing.append("task_use_missing")
        else:
            use, question = await self._question(
                scope, basis.task_use_event_id, location.scope_event_seq, "question"
            )
            if (
                use.task_use_id != submission.task_use_ref
                or use.activity_id != submission.activity_id
                or use.adoption_ref != submission.adoption_ref
                or use.round_id != submission.round_id
                or use.purpose != basis.mode
            ):
                raise ValueError("Submission does not match the original question")
            materials.append(question)
        if basis.help_event_ids is None:
            missing.append("help_history_unknown")
        for event in dict.fromkeys(basis.help_event_ids or []):
            materials.extend(await self._help(scope, event, submission, location.scope_event_seq))
        if basis.prior_task_use_event_ids is None:
            missing.append("prior_exposure_unknown")
        for event in dict.fromkeys(basis.prior_task_use_event_ids or []):
            previous, question = await self._question(
                scope, event, location.scope_event_seq, "prior_question"
            )
            if use is None or previous.instance_ref != use.instance_ref:
                raise ValueError("Exposure does not match this question instance")
            materials.append(question)
        if submission.round_id:
            rounds = await self._round(scope, submission)
            materials.extend(rounds)
            if len(rounds) != 2:
                missing.append("round_facts_missing")
        return EvaluationSource(
            scope_id=scope,
            trigger_event_id=trigger,
            source_seq=location.scope_event_seq,
            source_kind="answer",
            source_id=submission.submission_id,
            adoption_ref=envelope.adoption_ref,
            activity_ref=envelope.activity_ref,
            task_use_ref=envelope.task_use_ref,
            round_ref=envelope.round_ref,
            plan_ref=envelope.plan_ref,
            task_instance_ref=use.instance_ref if use else None,
            occurred_at=submission.accepted_at,
            materials=materials,
            missing_reasons=missing,
        )

    async def _question(
        self, scope: UUID, event: UUID, cutoff: int, role: Literal["question", "prior_question"]
    ) -> tuple[task_facts.TaskUseFact, EvaluationMaterial]:
        location = await self._location(scope, event, (task_facts.PRESENTED,), cutoff=cutoff - 1)
        (material,) = await self._parts(
            scope, event, task_facts.PRESENTED, [(role, location.owner_ref.id, "")]
        )
        question = task_facts.TaskUseFact.model_validate_json(canonical_json(material.content))
        if question.scope_id != scope or str(question.task_use_id) != location.owner_ref.id:
            raise ValueError("Question does not match its event")
        return question, material

    async def _message(
        self,
        scope: UUID,
        activity: UUID | None,
        part: Ref,
        cutoff: int,
        role: Literal["teaching", "provided_help"],
    ) -> EvaluationMaterial:
        if part.owner != "interaction" or part.type != "message" or not part.path:
            raise ValueError("Invalid teaching text reference")
        async with self.reader.engine.connect() as db:
            event = await db.scalar(
                text(
                    "SELECT m.source_event_id FROM interaction.messages m "
                    "JOIN interaction.message_assignments a USING(message_id) "
                    "WHERE m.scope_id=:scope AND m.message_id=:message "
                    "AND (CAST(:activity AS uuid) IS NULL OR a.activity_id=:activity) "
                    "AND m.role='assistant'"
                ),
                {"scope": scope, "message": UUID(part.id), "activity": activity},
            )
        if not isinstance(event, UUID):
            raise LookupError("Referenced teaching text is outside the authorized activity")
        location = await self._location(
            scope, event, (conversation_facts.RECORDED,), cutoff=cutoff - 1
        )
        if location.owner_ref.id != part.id:
            raise ValueError("Teaching text does not match its source event")
        (material,) = await self._parts(
            scope, event, conversation_facts.RECORDED, [(role, part.id, part.path)]
        )
        return material

    async def _help(
        self, scope: UUID, event: UUID, submission: task_facts.SubmissionFact, cutoff: int
    ) -> list[EvaluationMaterial]:
        await self._location(scope, event, (help_facts.HANDLED,), cutoff=cutoff - 1)
        (header,) = await self._parts(scope, event, help_facts.HANDLED, [("help", None, "")])
        action = help_facts.HelpHandled.model_validate_json(
            canonical_json({"records": [], **_object(header.content)})
        )
        key = f"{action.help_ref.id}:{action.stage}"
        materials = await self._parts(scope, event, help_facts.HANDLED, [("help", key, "")])
        help_record = help_facts.HelpFact.model_validate_json(canonical_json(materials[0].content))
        if help_record.scope_id != scope or help_record.task_use_id != submission.task_use_ref:
            raise ValueError("Help does not belong to this question use")
        for part in help_record.provided_part_refs:
            # A substantive reply may be in a child activity. Help already identifies its message.
            if action.provided_message_ref is None or action.provided_message_ref.id != part.id:
                raise ValueError("Help content is unrelated to the provided message")
            materials.append(await self._message(scope, None, part, cutoff, "provided_help"))
        return materials

    async def _round(
        self, scope: UUID, submission: task_facts.SubmissionFact
    ) -> list[EvaluationMaterial]:
        async with self.reader.engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT r.source_event_id AS opened, v.source_event_id AS closed, "
                        "v.revision "
                        "FROM interaction.detection_rounds r "
                        "JOIN interaction.activities a ON a.activity_id=r.activity_id "
                        "LEFT JOIN interaction.round_revisions v ON v.round_id=r.round_id "
                        "AND v.submission_ref=:submission AND v.reason='submitted' "
                        "WHERE r.round_id=:round AND a.scope_id=:scope AND r.task_use_ref=:use"
                    ),
                    {
                        "submission": submission.submission_id,
                        "round": submission.round_id,
                        "scope": scope,
                        "use": submission.task_use_ref,
                    },
                )
            ).one_or_none()
        if row is None:
            return []
        identity = str(submission.round_id)
        materials = await self._parts(
            scope, row.opened, round_facts.STARTED, [("round_opened", identity, "")]
        )
        if row.closed:
            materials.extend(
                await self._parts(
                    scope,
                    row.closed,
                    round_facts.CLOSED,
                    [("round_closed", f"{identity}:{row.revision}", "")],
                )
            )
        return materials

    async def _teaching(
        self, scope: UUID, trigger: UUID, location: EventLocation
    ) -> EvaluationSource:
        (header, closure) = await self._parts(
            scope,
            trigger,
            provision_facts.CLOSED,
            [("closure", None, ""), ("closure", location.owner_ref.id, "")],
        )
        action = provision_facts.OpportunityClosed.model_validate_json(
            canonical_json({"records": [], **_object(header.content)})
        )
        recorded = provision_facts.Closure.model_validate_json(canonical_json(closure.content))
        if action.closure_ref != location.owner_ref or recorded.event_ref != trigger:
            raise ValueError("Teaching closure does not match its trigger")
        materials = [closure]
        for part in action.provided_part_refs:
            materials.append(
                await self._message(
                    scope, UUID(action.activity_ref.id), part, location.scope_event_seq, "teaching"
                )
            )
        return EvaluationSource(
            scope_id=scope,
            trigger_event_id=trigger,
            source_seq=location.scope_event_seq,
            source_kind="teaching",
            source_id=recorded.opportunity_id,
            adoption_ref=action.adoption_ref,
            activity_ref=action.activity_ref,
            task_use_ref=None,
            round_ref=None,
            plan_ref=None,
            task_instance_ref=None,
            occurred_at=recorded.closed_at,
            materials=materials,
            missing_reasons=[],
        )


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("Expected an event object")
    return value
