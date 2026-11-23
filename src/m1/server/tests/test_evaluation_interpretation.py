"""核对同一作答的引用、帮助与逐方面资格。"""

from dataclasses import replace
from datetime import UTC, datetime
from unittest import TestCase
from uuid import uuid4

from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import Ref
from deermind.product.public.learning_targets import (
    GoalItem,
    MethodRequirement,
    TargetAspect,
    TargetAspectRef,
    TaskConditions,
)
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation import input_facts, interpretation
from deermind.spaces.evaluation.inputs import EvaluationMaterials
from deermind.spaces.evaluation.mastery import calculate_revision, evidence_record, projected_item
from deermind.spaces.evaluation.public import (
    AspectDefinition,
    AspectRule,
    ClaimDefinition,
    ClaimRef,
    ClaimView,
    MethodDefinition,
)
from deermind.spaces.interaction.public import EvaluationMaterial, EvaluationSource
from pydantic import JsonValue

ANSWER = "120 × 1/4 = 30，120 + 30 = 150。"


def bundle() -> EvaluationMaterials:
    scope, event, adoption, work = [uuid4() for _ in range(4)]
    time = datetime.now(UTC)
    fixed = Ref(owner="product", type="space_adoption", id=str(adoption))
    activity = Ref(owner="interaction", type="activity", id=str(uuid4()))
    round_ref = Ref(owner="interaction", type="round", id=str(uuid4()))
    instance = Ref(owner="domain", type="task_instance", id=str(uuid4()), version=1)
    task = TaskRef(kind="task", object_id=uuid4(), version=1)
    method = SolutionRef(kind="solution", object_id=uuid4(), version=1)
    claim = ClaimRef(claim_id=uuid4(), revision=1)

    def material(role: str, body: JsonValue) -> EvaluationMaterial:
        return EvaluationMaterial.model_validate(
            {
                "role": role,
                "ref": EventPartRef(event_id=event, record_id=str(work), path=f"/{role}"),
                "sha256": "a" * 64,
                "content": body,
            }
        )

    return EvaluationMaterials(
        record=input_facts.InputRecord(
            input_id=work,
            scope_id=scope,
            trigger_event_id=event,
            source_seq=20,
            source_kind="answer",
            source_id=work,
            created_at=time,
            input=input_facts.EvaluationInput(
                adoption_ref=fixed,
                application_ref=fixed,
                target_basis_ref=fixed,
                activity_ref=activity,
                task_use_ref=None,
                round_ref=round_ref,
                plan_ref=None,
                task_instance_ref=instance,
                occurred_at=time,
                candidate_scope=[
                    input_facts.CandidateTask(
                        task_ref=task,
                        claim_ref=claim,
                        methods=[
                            input_facts.CandidateMethod(method_ref=method, chapter_sources=[fixed])
                        ],
                        gaps=[],
                    )
                ],
                materials=[],
                domain_materials=[],
                history_basis=[],
                missing_reasons=[],
                interpretation_contract_ref="test",
                parameter_ref="test",
                algorithm_ref="test",
            ),
        ),
        source=EvaluationSource(
            scope_id=scope,
            trigger_event_id=event,
            source_seq=20,
            source_kind="answer",
            source_id=work,
            adoption_ref=fixed,
            activity_ref=activity,
            task_use_ref=None,
            round_ref=round_ref,
            plan_ref=None,
            task_instance_ref=instance,
            occurred_at=time,
            materials=[
                material("answer", {"text": ANSWER}),
                material("question", {"text": "原有120本，增加四分之一"}),
                material(
                    "help_basis",
                    {
                        "mode": "detection",
                        "help_event_ids": [],
                        "external_help": "unknown",
                        "prior_task_use_event_ids": [],
                    },
                ),
            ],
            missing_reasons=[],
        ),
        claims=[
            ClaimView(
                claim_ref=claim,
                gaps=[],
                definition=ClaimDefinition(
                    domain_id=uuid4(),
                    task_ref=task,
                    title="四分之一",
                    description="求新量",
                    aspects=[
                        AspectDefinition(code=code, label=label, description=label)
                        for code, label in (("independent", "独立"), ("retention", "保持"))
                    ],
                    criteria=[],
                    methods=[
                        MethodDefinition(
                            method_ref=method,
                            criterion_ids=[],
                            aspect_rules=[
                                AspectRule(
                                    aspect_code=code,
                                    judgement_basis="核对过程",
                                    evidence_requirements=[],
                                    condition_schema={},
                                    default_values={},
                                )
                                for code in ("independent", "retention")
                            ],
                        )
                    ],
                ),
            )
        ],
        domain=dict([(instance, {})]),
    )


def candidate(choice: int, material: int = 1) -> interpretation.Candidate:
    return interpretation.Candidate(
        choice=choice,
        execution_checks=[],
        aspect_judgement="met",
        source_spans=[interpretation.QuotedSource(material=material, quote=ANSWER)],
        method_source=interpretation.QuotedSource(material=material, quote=ANSWER),
        reason="已说明两个步骤",
        limitations=[],
    )


def assess(
    value: EvaluationMaterials, *candidates: interpretation.Candidate
) -> list[interpretation.CheckedEvidence]:
    return interpretation.check(
        value,
        interpretation.Interpretation(
            candidates=list(candidates),
            unattributed=[],
            declared_external_help=None,
        ),
    )


class InterpretationTests(TestCase):
    def test_system_facts_allow_independent_with_external_unknown(self) -> None:
        independent, retention = assess(bundle(), candidate(1), candidate(2))
        self.assertEqual((independent.qualification, independent.verdict), ("eligible", "positive"))
        self.assertEqual(independent.condition_facts[0].status, "unknown")
        self.assertEqual((retention.qualification, retention.verdict), ("unknown", None))

    def test_missing_help_is_unknown(self) -> None:
        value = bundle()
        source = value.source.model_copy(update={"materials": value.source.materials[:2]})
        (checked,) = assess(replace(value, source=source), candidate(1))
        self.assertEqual((checked.qualification, checked.verdict), ("unknown", None))

    def test_unverified_scope_keeps_independent_evidence_without_target_coverage(self) -> None:
        value = bundle()
        choice = interpretation.choices(value)[0]
        chapter = uuid4()
        item = GoalItem(
            item_id=uuid4(),
            title="验证题面范围",
            claim_ref=choice.claim,
            chapter_refs=[chapter],
            task_conditions=TaskConditions(description="增加四分之一"),
            method_mode="specified",
            methods=[
                MethodRequirement(
                    method_ref=choice.method,
                    chapter_refs=[chapter],
                    aspects=[
                        TargetAspect(
                            aspect_ref=TargetAspectRef(
                                claim_ref=choice.claim, aspect_code="independent"
                            ),
                            condition_values={},
                        )
                    ],
                )
            ],
        )
        value = replace(value, targets=(item,))
        for quote, covered in (
            ("原有120本，增加五分之一", False),
            ("原有120本，增加四分之一", True),
        ):
            with self.subTest(quote=quote):
                (checked,) = interpretation.check(
                    value,
                    interpretation.Interpretation(
                        candidates=[candidate(1)],
                        unattributed=[],
                        declared_external_help=None,
                        covered_scopes=[
                            interpretation.TestedScope(
                                item_id=item.item_id,
                                source=interpretation.QuotedSource(material=2, quote=quote),
                            )
                        ],
                    ),
                )
                self.assertEqual((checked.qualification, checked.verdict), ("eligible", "positive"))
                self.assertEqual(
                    any(fact.condition == "target_scope" for fact in checked.condition_facts),
                    covered,
                )

    def test_retention_uses_qualified_server_history(self) -> None:
        value = bundle()
        selected = interpretation.choices(value)[1]
        key = (
            selected.claim.claim_id,
            selected.claim.revision,
            selected.method.object_id,
            selected.method.version,
            selected.aspect,
        )
        parsed = interpretation.Interpretation(
            candidates=[candidate(2)],
            unattributed=[],
            declared_external_help=None,
        )
        (unknown,) = interpretation.check(value, parsed)
        self.assertEqual(unknown.reason_codes, ["retention_basis_unknown"])
        for elapsed, qualification in ((False, "ineligible"), (True, "eligible")):
            verified = interpretation.ConditionFact(
                condition="retention_window",
                status="known",
                value={"minimum_met": elapsed},
                source_refs=[value.source.materials[1].ref],
            )
            (checked,) = interpretation.check(value, parsed, {key: verified})
            self.assertEqual(checked.qualification, qualification)

    def test_unused_method_cannot_receive_a_negative_observation(self) -> None:
        item = candidate(1).model_copy(
            update={"aspect_judgement": "not_met", "method_source": None}
        )
        (checked,) = assess(bundle(), item)
        self.assertEqual((checked.qualification, checked.verdict), ("unknown", None))
        self.assertEqual(checked.reason_codes, ["method_unattributed"])

    def test_outside_scope_and_other_sources_rejected(self) -> None:
        for item in (candidate(3), candidate(1, 2)):
            with self.subTest(candidate=item), self.assertRaises(ValueError):
                assess(bundle(), item)

    def test_source_only_once_and_conflict_is_unknown(self) -> None:
        selected = candidate(1)
        (single,) = assess(bundle(), selected, selected)
        self.assertEqual(len(single.source_spans), 1)
        contrary = selected.model_copy(update={"aspect_judgement": "not_met"})
        (conflict,) = assess(bundle(), selected, contrary)
        self.assertEqual((conflict.qualification, conflict.verdict), ("unknown", None))

    def test_teaching_only_qualifies_the_explained_responsibility(self) -> None:
        value = bundle()
        original = value.source.materials[0]
        teaching = original.model_copy(update={"role": "teaching"})
        source = value.source.model_copy(
            update={"source_kind": "teaching", "materials": [teaching, teaching]}
        )
        prepared = replace(value, source=source)
        whole, retention = assess(prepared, candidate(1), candidate(1, 2), candidate(2))
        self.assertEqual((whole.qualification, whole.verdict), ("eligible", None))
        self.assertEqual(len(whole.source_spans), 1)
        self.assertEqual(retention.reason_codes, ["no_learning_transfer_for_aspect"])
        incomplete = candidate(1).model_copy(update={"aspect_judgement": "not_met"})
        (skipped,) = assess(prepared, incomplete)
        self.assertEqual(skipped.reason_codes, ["teaching_incomplete"])

    def test_numeric_update_keeps_prediction_and_observation_separate(self) -> None:
        value = bundle()
        now = value.record.created_at
        (checked,) = assess(value, candidate(1))
        evidence = evidence_record(value.record, uuid4(), checked, now)
        first = calculate_revision(evidence, None, value.record)
        self.assertIsNotNone(first)
        assert first
        current = projected_item(evidence, None, first)
        teaching = evidence.model_copy(update={"source_kind": "teaching", "verdict": None})
        second = calculate_revision(teaching, current, value.record)
        self.assertIsNotNone(second)
        assert second
        self.assertAlmostEqual(first.p_current_after, 0.7727272727)
        self.assertAlmostEqual(second.p_current_after, 0.7840909091)
        self.assertEqual(second.p_obs_after, first.p_obs_after)
        self.assertEqual(second.last_observed_at, first.last_observed_at)
        unknown = evidence.model_copy(update={"qualification": "unknown", "verdict": None})
        self.assertIsNone(calculate_revision(unknown, current, value.record))
