"""Injected boundary checks; semantic validation outcomes remain explicit fixtures."""

from dataclasses import replace

from .boundary import BoundaryRuntime, ContextInput, Protocol
from .cases import correct, derived, foundation_harness, seed
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, Decision
from .security import (AccessDenied, AuthorityGrant, CredentialBinding, DataUseGrant,
                       Operation, SecurityRuntime, parameter)


def setup_boundary():
    h = foundation_harness()
    # Step 3/4 uses backend enforcement, not the Step 0–2 eligibility fixture.
    h.eligibility.clear()
    protocol_ref = seed(h, Ref(Space.CANONICAL, "ObservationProtocol", "v1"), kind="ReasoningProtocol")
    rule = seed(h, Ref(Space.CANONICAL, "ObservationRules", "v1"), kind="SemanticValidationRules")
    work = seed(h, Ref(Space.FACT, "work", "1"), kind="LearnerWorkSubmitted",
                occurrence_key="work", payload={"text": "42 / 6 = 8; 8 * 15 = 120"})
    belief = seed(h, derived("B-old"), kind="LearnerBelief", payload={"untrusted_for_observation": True})
    h.canonical.add_compatibility_fixture(Compatibility("protocol-rules-v1", (protocol_ref, rule),
                                                      "learner-A", "learning", Decision.ALLOW))
    versions = VersionContext((protocol_ref, rule), compatibility_basis="protocol-rules-v1")
    security = SecurityRuntime(h)
    resources = (work.identity, belief.identity, protocol_ref.identity, rule.identity, "O")
    security.install_authority(AuthorityGrant("read-grant", "interaction", "learning", "learner-A",
                                             resources, ("read",), 10000))
    security.install_authority(AuthorityGrant("reason-grant", "interaction", "learning", "learner-A",
                                             (protocol_ref.identity,), ("reason", "validate"), 10000))
    security.install_authority(AuthorityGrant("commit-grant", "interaction", "learning", "learner-A",
                                             ("O",), ("commit",), 10000,
                                             (("owner", (parameter("owner", "Interaction")[1],)),
                                              ("kind", (parameter("kind", "Observation")[1],)))))
    security.install_data(DataUseGrant("read-data", "interaction", "learning", "learner-A",
                                      ("LearnerWorkSubmitted", "LearnerBelief", "ReasoningProtocol",
                                       "SemanticValidationRules", "Observation"),
                                      ("read",), ("reasoning-runtime",), "run", "internal", 10000))
    security.install_data(DataUseGrant("validate-data", "interaction", "learning", "learner-A",
                                      ("Observation",), ("validate",), ("reasoning-runtime",), "run", "internal", 10000))
    security.install_data(DataUseGrant("commit-data", "interaction", "learning", "learner-A",
                                      ("Observation",), ("commit",), ("formal-state",), "run", "internal", 10000))
    token = security.issue_fixture_credential(CredentialBinding("interaction", "learning", "learner-A", 10000))
    runtime = BoundaryRuntime(h, security)
    runtime.register_protocol(Protocol(protocol_ref, "Observation", "Interaction", ("LearnerWorkSubmitted",),
                                       (("description", "string"),), rule))
    context = runtime.assemble(token, protocol_ref, "learner-A", "learner-A", "learning",
                               (ContextInput(work, Role.FACTUAL), ContextInput(belief, Role.EPISTEMIC, required=False)),
                               versions)
    candidate = runtime.propose(context, "O", "r1", {"description": "The submitted division and final answer mismatch the task."})
    review = runtime.record_semantic_validation(token, candidate, "PASS", "injected control result",
                                                 "SCRIPTED-VALIDATION-FIXTURE", fixture=True)
    return h, security, runtime, token, context, candidate, review


def boundary_case(e):
    h, security, runtime, token, context, candidate, review = setup_boundary()
    e.emit("boundary_setup", grants=security.describe_grants(), context=json_value(context),
           candidate=json_value(candidate), semantic_validation=json_value(review))
    e.check("Observation context excludes historical Belief", [i.record.kind for i in context.items], ["LearnerWorkSubmitted"])
    e.check("no derived standing before commit", h.get(candidate.record.ref), None)
    outcome = runtime.commit(token, candidate, review.identity)
    e.emit("commit", **json_value(outcome))
    e.check("authorized validated candidate commits", outcome.status, "Committed")
    e.check("duplicate candidate cannot overwrite", runtime.commit(token, candidate, review.identity).status, "CommitConflict")
    e.capture(h, "guarded commit")

    for label, mutation, expected in (
        ("upstream correction", lambda h, s, c: correct(h, c.record.dependencies[0].target), "CandidateStale"),
        ("commit authority revoked", lambda h, s, c: s.revoke("commit-grant", c.execution), "Unauthorized"),
        ("data authority revoked", lambda h, s, c: s.revoke("read-data", c.execution), "DataAuthorityDenied"),
    ):
        h, security, runtime, token, context, candidate, review = setup_boundary()
        mutation(h, security, candidate)
        outcome = runtime.commit(token, candidate, review.identity)
        e.emit("commit", label=label, **json_value(outcome))
        e.check(label, outcome.status, expected)
        e.check(f"{label}: no standing", h.get(candidate.record.ref), None)
        e.capture(h, label)


def security_case(e):
    h, security, runtime, token, context, candidate, review = setup_boundary()
    attempts = (
        Operation("learning", "learner-B", "work", "read"),
        Operation("learning", "learner-B", "O", "execute"),
        Operation("learning", "learner-A", "ObservationProtocol", "GovernanceActivateVersion"),
        Operation("unrelated-purpose", "learner-A", "work", "read"),
        Operation("learning", "learner-A", "O", "commit",
                  (parameter("owner", "Evolution"), parameter("kind", "Observation"))),
    )
    for i, attempt in enumerate(attempts):
        status = "ALLOWED"
        try:
            security.enforce(token, attempt, candidate.execution)
        except AccessDenied as exc:
            status = exc.category
        e.emit("backend_attempt", request=json_value(attempt), status=status)
        e.check(f"injected escalation {i}", status, "Unauthorized")
    signals = [r for r in h.audit.records() if r.kind == "SecuritySignal"]
    e.check("every denied attempt has a source-linked SecuritySignal", len(signals), len(attempts))
    e.check("signals retain actual execution provenance", all(r.payload["source"] == json_value(candidate.execution) for r in signals), True)
    e.check("denied calls have no semantic effect", h.get(candidate.record.ref), None)
    e.capture(h, "backend-denied attempts")


GUARDED_CASES = {"ContextCommit-foundation": boundary_case, "F2-injected-foundation": security_case}
