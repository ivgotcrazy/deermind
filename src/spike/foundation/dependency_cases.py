"""B1/B2 state-mechanism cases: real commits, explicit scripted semantics.

These cases make no claim about Observation interpretation or A2 reliability.
Only factual/canonical setup and the correction stimulus are seeded fixtures.
"""

from .boundary import BoundaryRuntime, ContextInput, Protocol
from .cases import EvidenceRecorder, correct, derived, seed
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, CurrentResolver, Decision, Harness
from .security import AuthorityGrant, CredentialBinding, DataUseGrant, SecurityRuntime, parameter


class DependencyWorld:
    def __init__(self, evidence: EvidenceRecorder, branches=1):
        self.e = evidence
        self.h = Harness()  # No blanket EligibilityFixture: all reads use backend grants.
        self.security = SecurityRuntime(self.h)
        self.runtime = BoundaryRuntime(self.h, self.security)
        self.work = seed(self.h, Ref(Space.FACT, "work", "1"), kind="LearnerWorkSubmitted",
                         occurrence_key="work", payload={"fixture": "B-state-mechanism"})
        identities = ("O",) + tuple(f"{prefix}-{i}" for prefix in ("E", "B") for i in range(branches))
        self.protocols, self.versions, self.tokens = {}, {}, {}
        kinds = {"Observation": ("Interaction", "interaction", "LearnerWorkSubmitted"),
                 "Evidence": ("Evaluation", "evaluation", "Observation"),
                 "LearnerBelief": ("Evaluation", "evaluation", "Evidence")}
        canonical_ids = []
        for kind, (owner, principal, input_kind) in kinds.items():
            ref = seed(self.h, Ref(Space.CANONICAL, f"B-{kind}-Protocol", "v1"),
                       kind="ReasoningProtocol", payload={"semantic_source": "SCRIPTED-DEPENDENCY-FIXTURE"})
            rule = seed(self.h, Ref(Space.CANONICAL, f"B-{kind}-Rules", "v1"),
                        kind="SemanticValidationRules", payload={"format": "fixture"})
            canonical_ids.extend((ref.identity, rule.identity))
            compatibility = f"B-{kind}-compatible"
            self.h.canonical.add_compatibility_fixture(Compatibility(
                compatibility, (ref, rule), "learner-A", "learning", Decision.ALLOW))
            self.protocols[kind] = Protocol(ref, kind, owner, (input_kind,), (("description", "string"),), rule)
            self.versions[kind] = VersionContext((ref, rule), compatibility_basis=compatibility)
            self.runtime.register_protocol(self.protocols[kind])
        types = tuple(kinds) + ("LearnerWorkSubmitted", "ReasoningProtocol", "SemanticValidationRules")
        for principal in ("interaction", "evaluation"):
            self.tokens[principal] = self.security.issue_fixture_credential(
                CredentialBinding(principal, "learning", "learner-A", 100000))
            self.security.install_authority(AuthorityGrant(
                f"{principal}-read", principal, "learning", "learner-A",
                identities + ("work",) + tuple(canonical_ids), ("read",), 100000))
            self.security.install_data(DataUseGrant(
                f"{principal}-read-data", principal, "learning", "learner-A", types,
                ("read",), ("reasoning-runtime",), "run", "internal", 100000))
        for kind, (owner, principal, _) in kinds.items():
            protocol = self.protocols[kind]
            self.security.install_authority(AuthorityGrant(
                f"{kind}-reason", principal, "learning", "learner-A", (protocol.ref.identity,),
                ("reason", "validate"), 100000))
            resources = ("O",) if kind == "Observation" else tuple(
                f"{'E' if kind == 'Evidence' else 'B'}-{i}" for i in range(branches))
            self.security.install_authority(AuthorityGrant(
                f"{kind}-commit", principal, "learning", "learner-A", resources, ("commit",), 100000,
                (("owner", (parameter("owner", owner)[1],)), ("kind", (parameter("kind", kind)[1],)))))
            for operation, destination in (("validate", "reasoning-runtime"), ("commit", "formal-state")):
                self.security.install_data(DataUseGrant(
                    f"{kind}-{operation}-data", principal, "learning", "learner-A", (kind,),
                    (operation,), (destination,), "run", "internal", 100000))
        self.e.emit("setup", semantic_source="SCRIPTED-DEPENDENCY-FIXTURE",
                    correction_source="trusted factual stimulus, not a correction-authorization test",
                    grants=self.security.describe_grants())

    def prepare(self, kind, identity, revision, upstream):
        self.h.clock.advance()
        protocol = self.protocols[kind]
        token = self.tokens["interaction" if protocol.owner == "Interaction" else "evaluation"]
        context = self.runtime.assemble(token, protocol.ref, "learner-A", "learner-A", "learning",
                                        (ContextInput(upstream, Role.FACTUAL if kind == "Observation" else Role.EPISTEMIC),),
                                        self.versions[kind])
        head = self.h.states.candidate(identity, "learner-A", "learning", self.h.clock.now)
        candidate = self.runtime.propose(context, identity, revision,
                                         {"description": f"Scripted {kind} state for dependency isolation."},
                                         expected_head=head.ref if head else None)
        review = self.runtime.record_semantic_validation(
            token, candidate, "PASS", "Predeclared scripted meaning; tests state mechanisms only.",
            "SCRIPTED-DEPENDENCY-FIXTURE", fixture=True)
        self.e.emit("prepared", context=json_value(context), candidate=json_value(candidate),
                    review=json_value(review))
        return token, candidate, review

    def finish(self, prepared, expected="Committed", token=None):
        own_token, candidate, review = prepared
        outcome = self.runtime.commit(token or own_token, candidate, review.identity)
        self.e.emit("commit", candidate_ref=json_value(candidate.record.ref), outcome=json_value(outcome))
        self.e.check(f"commit {candidate.record.ref.identity}:{candidate.record.ref.revision} -> {expected}",
                     outcome.status, expected)
        self.e.check("standing agrees with commit outcome", self.h.get(candidate.record.ref) is not None,
                     outcome.status == "Committed")
        return candidate.record.ref

    def submit(self, kind, identity, revision, upstream):
        return self.finish(self.prepare(kind, identity, revision, upstream))

    def stage(self, label, expected):
        before = self.h.states.records()
        snapshot_id = self.e.capture(self.h, label)
        snapshot = self.h.capture()
        eligibility = self.runtime._eligibility(self.tokens["evaluation"], "reasoning-runtime")
        actual = {}
        for identity in expected:
            result = CurrentResolver(snapshot, eligibility).resolve(identity, "learner-A", "learning")
            self.e.emit("resolution", label=label, snapshot_id=snapshot_id, identity=identity, **json_value(result))
            actual[identity] = json_value(result.current) if result.current else None
        self.e.check(label, actual, {k: json_value(v) if v else None for k, v in expected.items()})
        self.e.check(f"{label}: reads do not mutate or recompute", self.h.states.records() == before, True)

    def preserve(self, records):
        self.e.check("all historical exact records unchanged", all(self.h.get(r.ref) == r for r in records), True)
        refs = {r.ref for r in self.h.states.records()}
        commits = {Ref(Space(v["space"]), v["identity"], v["revision"])
                   for r in self.h.audit.records() if r.kind == "CommitOutcome"
                   and (v := r.payload.get("committed")) is not None}
        self.e.check("every derived record has a successful formal commit", refs == commits, True)
        self.e.check("blanket eligibility fixture absent", self.h.eligibility, {})
        self.e.capture(self.h, "final with all execution and audit records")


def b1(e):
    w = DependencyWorld(e)
    o1 = w.submit("Observation", "O", "r1", w.work)
    e1 = w.submit("Evidence", "E-0", "r1", o1)
    b1_ref = w.submit("LearnerBelief", "B-0", "r1", e1)
    old = w.h.states.records()
    w.stage("before correction", {"O": o1, "E-0": e1, "B-0": b1_ref})
    stale_e = w.prepare("Evidence", "E-0", "stale", o1)
    stale_b = w.prepare("LearnerBelief", "B-0", "stale", e1)
    correction = correct(w.h, o1)
    e.emit("stimulus", correction=json_value(w.h.get(correction)))
    w.stage("correction without replacement", {"O": None, "E-0": None, "B-0": None})
    o2 = w.submit("Observation", "O", "r2", w.work)
    w.stage("only O recomputed", {"O": o2, "E-0": None, "B-0": None})
    w.finish(stale_e, "CandidateStale")
    w.finish(stale_b, "CandidateStale")
    e2 = w.submit("Evidence", "E-0", "r2", o2)
    w.stage("O and E recomputed", {"O": o2, "E-0": e2, "B-0": None})
    b2_ref = w.submit("LearnerBelief", "B-0", "r2", e2)
    w.stage("all recomputed", {"O": o2, "E-0": e2, "B-0": b2_ref})
    e.check("old E retains exact O:r1", w.h.get(e1).dependencies[0].target == o1, True)
    e.check("old B retains exact E:r1", w.h.get(b1_ref).dependencies[0].target == e1, True)
    w.preserve(old)


def b2(e):
    w = DependencyWorld(e, branches=100)
    root = w.submit("Observation", "O", "r1", w.work)
    expected = {"O": root}
    for i in range(100):
        evidence = w.submit("Evidence", f"E-{i}", "r1", root)
        belief = w.submit("LearnerBelief", f"B-{i}", "r1", evidence)
        expected.update({f"E-{i}": evidence, f"B-{i}": belief})
    old = w.h.states.records()
    w.stage("all 100 branches initially readable", expected)
    correction = correct(w.h, root)
    e.emit("stimulus", correction=json_value(w.h.get(correction)))
    expected = dict.fromkeys(expected)
    w.stage("all branches immediately unavailable without recompute", expected)
    new_root = w.submit("Observation", "O", "r2", w.work)
    expected["O"] = new_root
    w.stage("root alone restored", expected)
    new_e = w.submit("Evidence", "E-0", "r2", new_root)
    expected["E-0"] = new_e
    w.stage("one Evidence restored, no Belief restored", expected)
    new_b = w.submit("LearnerBelief", "B-0", "r2", new_e)
    expected["B-0"] = new_b
    w.stage("one full branch restored, other 99 remain unavailable", expected)
    e.check("only three replacements were committed", len(w.h.states.records()) - len(old), 3)
    w.preserve(old)


CASES = {"B1": b1, "B2": b2}
