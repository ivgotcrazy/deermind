from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import CASES, correct, current, derived, foundation_harness, run_case, seed
from foundation.records import Dependency, Mode, Record, Ref, Role, Space, VersionContext
from foundation.runtime import (Activation, Compatibility, ContractError, Decision,
                                EligibilityFixture, Harness, InjectedFailure, TestControl)


class HistoryTests(unittest.TestCase):
    def test_nested_payload_is_immutable_and_exact_record_cannot_be_overwritten(self):
        h = foundation_harness()
        payload = {"steps": [{"answer": 120}]}
        ref = seed(h, derived("O"), payload=payload)
        payload["steps"][0]["answer"] = 105
        read = h.get(ref).payload
        read["steps"].clear()
        self.assertEqual(h.get(ref).payload, {"steps": [{"answer": 120}]})
        with self.assertRaises(FrozenInstanceError):
            h.get(ref).owner = "someone else"
        with self.assertRaises(ContractError):
            h.seed_committed_fixture(replace(h.get(ref), payload_json='{"answer": 105}'))

    def test_correction_preserves_fact_and_changes_effective_occurrence(self):
        h = foundation_harness()
        ref = seed(h, Ref(Space.FACT, "submission", "1"), kind="LearnerWorkSubmitted",
                   occurrence_key="work", payload={"text": "old"})
        old_time = h.clock.now
        correction = correct(h, ref)
        self.assertEqual(h.facts.get(ref).payload, {"text": "old"})
        self.assertEqual(h.facts.resolve_effective_occurrence("work", "learner-A", old_time).ref, ref)
        self.assertEqual(h.facts.resolve_effective_occurrence("work", "learner-A", h.clock.now).ref, correction)
        self.assertIsNone(h.facts.resolve_effective_occurrence("work", "other-learner", h.clock.now))
        with self.assertRaises(ContractError):
            seed(h, Ref(Space.FACT, "silent-replacement", "1"), occurrence_key="work")

    def test_histories_do_not_promote_execution_to_fact_or_current_semantics(self):
        h = foundation_harness()
        execution = seed(h, Ref(Space.EXECUTION, "run", "1"), kind="ReasoningExecution")
        self.assertEqual(len(h.facts.records()), 0)
        with self.assertRaises(ContractError):
            h.facts.append(h.get(execution))
        seed(h, derived("O"), dependencies=(current(execution),))
        self.assertEqual(h.resolve("O").reason, "NonSemanticStanding")
        seed(h, Ref(Space.AUDIT, "audit", "1"), kind="AuditEntry")
        self.assertEqual(len(h.audit.records()), 1)
        self.assertEqual(len(h.executions.records()), 1)

    def test_snapshot_branches_are_independent_including_clock_and_failures(self):
        h = foundation_harness()
        ref = seed(h, derived("O"))
        h.control.fail_once("beforeActionEffect", "injected")
        snapshot = h.capture()
        left, right = Harness.branch(snapshot), Harness.branch(snapshot)
        correct(left, ref)
        self.assertIsNone(left.resolve("O").current)
        self.assertEqual(right.resolve("O").current, ref)
        self.assertEqual(h.resolve("O").current, ref)
        self.assertGreater(left.clock.now, right.clock.now)
        with self.assertRaises(InjectedFailure):
            left.control.reach("beforeActionEffect")
        left.control.reach("beforeActionEffect")
        with self.assertRaises(InjectedFailure):
            right.control.reach("beforeActionEffect")
        with self.assertRaises(ValueError):
            h.clock.advance(-1)
        with self.assertRaises(ValueError):
            TestControl().fail_once("undeclared", "failure")


class CurrentTests(unittest.TestCase):
    def setUp(self):
        self.h = foundation_harness()

    def test_exact_dependency_never_rebinds_during_staged_recompute(self):
        h = self.h
        o1 = seed(h, derived("O"))
        e1 = seed(h, derived("E"), kind="Evidence", dependencies=(current(o1),))
        b1 = seed(h, derived("B"), kind="LearnerBelief", dependencies=(current(e1),))
        self.assertEqual(h.resolve("B").current, b1)
        correct(h, o1)
        o2 = seed(h, derived("O", "r2"))
        self.assertEqual(h.resolve("O").current, o2)
        self.assertIsNone(h.resolve("E").current)
        self.assertIsNone(h.resolve("B").current)
        self.assertTrue(any(c.ref == o1 and c.result == "Corrected" for c in h.resolve("B").checks))
        e2 = seed(h, derived("E", "r2"), kind="Evidence", dependencies=(current(o2),))
        self.assertEqual(h.resolve("E").current, e2)
        self.assertIsNone(h.resolve("B").current)
        b2 = seed(h, derived("B", "r2"), kind="LearnerBelief", dependencies=(current(e2),))
        self.assertEqual(h.resolve("B").current, b2)
        self.assertEqual(h.get(e1).dependencies[0].target, o1)
        self.assertEqual(h.get(b1).dependencies[0].target, e1)

    def test_new_upstream_alone_does_not_invalidate_exact_usable_basis(self):
        o1 = seed(self.h, derived("O"))
        evidence = seed(self.h, derived("E"), dependencies=(current(o1),))
        seed(self.h, derived("O", "r2"))
        self.assertEqual(self.h.resolve("E").current, evidence)

    def test_declared_head_requirement_is_checked_without_rebinding(self):
        o1 = seed(self.h, derived("O"))
        evidence = seed(self.h, derived("E"), dependencies=(current(o1, require_head=True),))
        seed(self.h, derived("O", "r2"))
        self.assertEqual(self.h.resolve("E").reason, "RequiredHeadChanged")
        self.assertEqual(self.h.get(evidence).dependencies[0].target, o1)

    def test_invalid_latest_candidate_does_not_fall_back_to_older_usable_revision(self):
        old = seed(self.h, derived("O"))
        new = seed(self.h, derived("O", "r2"))
        correct(self.h, new)
        result = self.h.resolve("O")
        self.assertEqual(result.candidate, new)
        self.assertIsNone(result.current)
        self.assertIsNotNone(self.h.get(old))

    def test_pinned_history_survives_correction_but_missing_pinned_is_not_silently_ignored(self):
        old = seed(self.h, derived("O"))
        pinned = Dependency(old, Mode.PINNED, Role.EPISTEMIC)
        evidence = seed(self.h, derived("E"), dependencies=(pinned,))
        correct(self.h, old)
        self.assertEqual(self.h.resolve("E").current, evidence)
        seed(self.h, derived("missing"), dependencies=(replace(pinned, target=derived("absent")),))
        self.assertEqual(self.h.resolve("missing").reason, "MissingExactReference")

    def test_validity_cycle_returns_non_resolution(self):
        a, b = derived("A"), derived("B")
        seed(self.h, a, dependencies=(current(b),))
        seed(self.h, b, dependencies=(current(a),))
        self.assertEqual(self.h.resolve("A").reason, "ValidityCycle")

    def test_incoherent_transitive_revisions_are_rejected(self):
        old = seed(self.h, derived("O"))
        new = seed(self.h, derived("O", "r2"))
        e1 = seed(self.h, derived("E-1"), dependencies=(current(old),))
        e2 = seed(self.h, derived("E-2"), dependencies=(current(new),))
        seed(self.h, derived("B"), dependencies=(current(e1), current(e2)))
        self.assertEqual(self.h.resolve("B").reason, "DependencyIncoherent")

    def test_purpose_scope_and_unknown_eligibility_are_fail_closed(self):
        ref = seed(self.h, derived("O"))
        self.assertEqual(self.h.resolve("O", purpose="audit").reason, "MissingCandidate")
        self.assertEqual(self.h.resolve("O", scope="learner-B").reason, "MissingCandidate")
        for field in ("authority", "data_authority", "security"):
            for outcome in (Decision.DENY, Decision.UNKNOWN):
                with self.subTest(field=field, outcome=outcome):
                    self.h.eligibility[("learner-A", "learning")] = replace(
                        EligibilityFixture(Decision.ALLOW, Decision.ALLOW, Decision.ALLOW), **{field: outcome})
                    result = self.h.resolve("O")
                    self.assertIsNone(result.current)
                    self.assertEqual(result.reason, f"{field}:{outcome}")
                    self.assertEqual(result.candidate, ref)

    def test_declared_dependency_use_context_is_honored(self):
        other = seed(self.h, derived("audit-source"), purpose="audit")
        seed(self.h, derived("O"), dependencies=(current(other, purpose="audit"),))
        self.assertEqual(self.h.resolve("O").reason, "authority:UNKNOWN")
        self.h.eligibility[("learner-A", "audit")] = EligibilityFixture(
            Decision.ALLOW, Decision.ALLOW, Decision.ALLOW)
        self.assertIsNotNone(self.h.resolve("O").current)

    def test_clock_expiry_is_checked_on_each_fresh_resolution(self):
        ref = seed(self.h, derived("O"), valid_until=5)
        self.assertEqual(self.h.resolve("O").current, ref)
        self.h.clock.advance(4)
        self.assertEqual(self.h.resolve("O").reason, "LifecycleIneligible")


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.h = foundation_harness()
        self.v1 = seed(self.h, Ref(Space.CANONICAL, "Semantics", "v1"), kind="ObservationSemantics")
        self.v2 = seed(self.h, Ref(Space.CANONICAL, "Semantics", "v2"), kind="ObservationSemantics")

    def activate(self, target, scope="learner-A", purpose="learning"):
        a = Activation(f"activation-{self.h.clock.advance()}", target, scope, purpose, self.h.clock.now)
        self.h.canonical.activate_fixture(a)
        return a

    def test_commit_activation_scope_and_rollback_are_separate(self):
        registry = self.h.canonical
        self.assertIsNone(registry.active("Semantics", "learner-A", "learning", self.h.clock.now))
        first = self.activate(self.v1)
        self.activate(self.v2, scope="learner-B")
        self.activate(self.v2, purpose="audit")
        self.assertEqual(registry.active("Semantics", "learner-A", "learning", self.h.clock.now), first)
        self.activate(self.v2)
        self.activate(self.v1)
        self.assertEqual(registry.active("Semantics", "learner-A", "learning", self.h.clock.now).target, self.v1)
        self.assertEqual(len(registry.activations()), 5)
        self.assertIsNotNone(registry.get(self.v2))
        with self.assertRaises(ContractError):
            registry.activate_fixture(first)
        with self.assertRaises(ContractError):
            self.activate(Ref(Space.CANONICAL, "Semantics", "absent"))

    def test_required_active_dependency_detects_activation_change(self):
        self.activate(self.v1)
        dep = Dependency(self.v1, Mode.CURRENT, Role.CANONICAL, require_active=True)
        observation = seed(self.h, derived("O"), dependencies=(dep,))
        self.assertEqual(self.h.resolve("O").current, observation)
        self.activate(self.v2)
        self.assertEqual(self.h.resolve("O").reason, "RequiredActivationChanged")
        self.assertEqual(self.h.get(observation).dependencies[0].target, self.v1)

    def test_unknown_incompatible_and_mismatched_version_sets_do_not_pass(self):
        registry = self.h.canonical
        for name, decision in (("yes", Decision.ALLOW), ("no", Decision.DENY)):
            registry.add_compatibility_fixture(Compatibility(name, (self.v1,), "learner-A", "learning", decision))
        for identity, binding, basis, reason in (
            ("missing", self.v1, "unknown", "VersionCompatibility:UNKNOWN"),
            ("denied", self.v1, "no", "VersionCompatibility:DENY"),
            ("mismatch", self.v2, "yes", "VersionCompatibility:UNKNOWN"),
        ):
            seed(self.h, derived(identity), versions=VersionContext((binding,), compatibility_basis=basis))
            self.assertEqual(self.h.resolve(identity).reason, reason)
        with self.assertRaises(ContractError):
            registry.add_compatibility_fixture(Compatibility("yes", (self.v2,), "learner-A", "learning", Decision.ALLOW))

    def test_binding_is_frozen_and_execution_version_is_not_semantic_dependency(self):
        self.activate(self.v1)
        self.h.canonical.add_compatibility_fixture(Compatibility("v1-ok", (self.v1,), "learner-A", "learning", Decision.ALLOW))
        context = self.h.canonical.bind_active(("Semantics",), "learner-A", "learning", self.h.clock.now,
                                             "v1-ok", (("model", "fixture-model-old"),))
        observation = seed(self.h, derived("O"), versions=context)
        self.activate(self.v2)
        self.assertEqual(self.h.get(observation).versions.semantic_bindings, (self.v1,))
        self.assertEqual(self.h.resolve("O").current, observation)
        with self.assertRaises(ValueError):
            VersionContext((self.v1, self.v2))
        with self.assertRaises(ValueError):
            VersionContext(execution_bindings=(["model", "mutable"],))


class RunnerTests(unittest.TestCase):
    def test_foundation_cases_emit_evidence_without_claiming_assumption_support(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, case in CASES.items():
                with self.subTest(case=name):
                    summary = run_case(name, case, Path(directory))
                    self.assertEqual(summary["foundation_result"], "PASS", summary)
                    self.assertEqual(summary["assumption_status"], "UNVALIDATED")
                    rows = [json.loads(line) for line in (Path(directory) / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]
                    self.assertTrue(any(r["kind"] == "snapshot" for r in rows))
                    self.assertTrue(any(r["kind"] == "resolution" and r["checks"] for r in rows))
                    self.assertEqual(rows[-1]["kind"], "case_end")

    def test_exception_and_failed_assertion_are_retained_and_runs_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            def failed(e):
                e.check("wrong result", 1, 2)
                raise InjectedFailure("test interruption")
            summary = run_case("failure", failed, Path(directory))
            self.assertEqual(summary["foundation_result"], "FAIL")
            self.assertEqual(summary["error"]["type"], "InjectedFailure")
            rows = [json.loads(line) for line in (Path(directory) / "failure.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertFalse(next(r for r in rows if r["kind"] == "check")["passed"])
            self.assertTrue(any(r["kind"] == "execution_failure" for r in rows))
            with self.assertRaises(FileExistsError):
                run_case("failure", failed, Path(directory))


if __name__ == "__main__":
    unittest.main()
