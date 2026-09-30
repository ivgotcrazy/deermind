"""Deterministic B/C foundation scenarios; not complete assumption validations."""

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import traceback

from .records import Dependency, Mode, Record, Ref, Role, Space, VersionContext, json_value
from .runtime import Activation, Compatibility, Decision, EligibilityFixture, Harness


def derived(identity, revision="r1"):
    return Ref(Space.DERIVED, identity, revision)


def current(ref, **kwargs):
    return Dependency(ref, Mode.CURRENT, Role.EPISTEMIC, **kwargs)


def foundation_harness():
    h = Harness()
    h.eligibility[("learner-A", "learning")] = EligibilityFixture(
        Decision.ALLOW, Decision.ALLOW, Decision.ALLOW)
    return h


def seed(h, ref, *, kind="Observation", dependencies=(), versions=None, payload=None, **kwargs):
    owner = "Evaluation" if kind in ("Evidence", "LearnerBelief") else "Interaction"
    record = Record.create(ref=ref, kind=kind, subject="learner-A", owner=owner,
                           recorded_at=h.clock.advance(), payload=payload,
                           dependencies=tuple(dependencies), versions=versions or VersionContext(),
                           provenance=("owner-authored-scripted-fixture",), **kwargs)
    h.seed_committed_fixture(record)
    return ref


def correct(h, target, identity="correction-1"):
    source = h.get(target)
    return seed(h, Ref(Space.FACT, identity, "1"), kind="CorrectionOccurred",
                corrects=target, occurrence_key=source.occurrence_key,
                payload={"reason": "fixture owner retracts exact current basis"})


class EvidenceRecorder:
    def __init__(self, path: Path):
        self.path = path
        self._file = path.open("x", encoding="utf-8")
        self.checks = []

    def emit(self, kind, **data):
        self._file.write(json.dumps({"kind": kind, **data}, ensure_ascii=False, allow_nan=False) + "\n")
        self._file.flush()

    def check(self, name, actual, expected):
        result = {"name": name, "actual": actual, "expected": expected, "passed": actual == expected}
        self.checks.append(result)
        self.emit("check", **result)

    def capture(self, h, label):
        records = [json_value(r) for space in Space for r in h.history_for(space).records()]
        activations = [json_value(a) for a in h.canonical.activations()]
        body = {"clock": h.clock.now, "records": records, "activations": activations,
                "eligibility_fixtures": [dict(scope=k[0], purpose=k[1], **asdict(v))
                                         for k, v in sorted(h.eligibility.items())],
                "compatibility_fixtures": [json_value(c) for c in h.canonical.compatibilities()]}
        digest = sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.emit("snapshot", label=label, snapshot_id=digest, **body)
        return digest

    def resolve(self, h, identity, label):
        result = h.resolve(identity)
        self.emit("resolution", label=label, identity=identity, **json_value(result))
        return result.current

    def close(self):
        self._file.close()


def b1(e):
    h = foundation_harness()
    work = seed(h, Ref(Space.FACT, "work", "1"), kind="LearnerWorkSubmitted",
                occurrence_key="work", payload={"text": "42 / 6 = 8; 8 * 15 = 120"})
    o1 = seed(h, derived("O"), dependencies=(Dependency(work, Mode.CURRENT, Role.FACTUAL),))
    e1 = seed(h, derived("E"), kind="Evidence", dependencies=(current(o1),))
    b1_ref = seed(h, derived("B"), kind="LearnerBelief", dependencies=(current(e1),))
    e.capture(h, "initial")

    def stage(label, expected):
        e.capture(h, label)
        actual = [e.resolve(h, identity, label) for identity in ("O", "E", "B")]
        e.check(label, [asdict(r) if r else None for r in actual],
                [asdict(r) if r else None for r in expected])

    stage("before correction", (o1, e1, b1_ref))
    correct(h, o1)
    stage("correction without replacement", (None, None, None))
    o2 = seed(h, derived("O", "r2"), dependencies=(Dependency(work, Mode.CURRENT, Role.FACTUAL),))
    stage("only O recomputed", (o2, None, None))
    e2 = seed(h, derived("E", "r2"), kind="Evidence", dependencies=(current(o2),))
    stage("O and E recomputed", (o2, e2, None))
    b2_ref = seed(h, derived("B", "r2"), kind="LearnerBelief", dependencies=(current(e2),))
    stage("all recomputed", (o2, e2, b2_ref))
    e.check("old E retains exact O:r1", asdict(h.get(e1).dependencies[0].target), asdict(o1))
    e.check("old B retains exact E:r1", asdict(h.get(b1_ref).dependencies[0].target), asdict(e1))


def b2(e):
    h = foundation_harness()
    root = seed(h, derived("O-root"))
    for i in range(100):
        evidence = seed(h, derived(f"E-{i}"), kind="Evidence", dependencies=(current(root),))
        seed(h, derived(f"B-{i}"), kind="LearnerBelief", dependencies=(current(evidence),))
    e.capture(h, "fan-out before correction")
    e.check("100 branches initially readable",
            sum(e.resolve(h, f"B-{i}", "before correction") is not None for i in range(100)), 100)
    before = h.states.records()
    correct(h, root)
    e.capture(h, "fan-out corrected without recompute")
    for prefix in ("E", "B"):
        e.check(f"all 100 {prefix} reads refuse invalid basis",
                sum(e.resolve(h, f"{prefix}-{i}", "after correction") is None for i in range(100)), 100)
    e.check("reads preserve all old records without push or recompute", h.states.records() == before, True)
    new_root = seed(h, derived("O-root", "r2"))
    new_e = seed(h, derived("E-0", "r2"), kind="Evidence", dependencies=(current(new_root),))
    new_b = seed(h, derived("B-0", "r2"), kind="LearnerBelief", dependencies=(current(new_e),))
    e.capture(h, "one branch recomputed")
    e.check("first branch recovers", e.resolve(h, "B-0", "partial recompute") == new_b, True)
    e.check("other 99 branches remain unavailable",
            sum(e.resolve(h, f"B-{i}", "partial recompute") is None for i in range(1, 100)), 99)


def c1(e):
    h = foundation_harness()
    v1 = Ref(Space.CANONICAL, "ObservationSemantics", "v1")
    v2 = Ref(Space.CANONICAL, "ObservationSemantics", "v2")
    seed(h, v1, kind="ObservationSemantics", payload={"fixture": "v1"})
    h.canonical.activate_fixture(Activation("activate-v1", v1, "learner-A", "learning", h.clock.advance()))
    h.canonical.add_compatibility_fixture(Compatibility("compatible-v1", (v1,), "learner-A", "learning", Decision.ALLOW))
    old_context = h.canonical.bind_active((v1.identity,), "learner-A", "learning", h.clock.now, "compatible-v1")
    o1 = seed(h, derived("O-under-v1"), versions=old_context)
    seed(h, v2, kind="ObservationSemantics", payload={"fixture": "v2"})
    e.check("commit v2 does not activate", h.canonical.active(v1.identity, "learner-A", "learning", h.clock.now).target == v1, True)
    h.canonical.activate_fixture(Activation("activate-v2", v2, "learner-A", "learning", h.clock.advance()))
    h.canonical.add_compatibility_fixture(Compatibility("compatible-v2", (v2,), "learner-A", "learning", Decision.ALLOW))
    new_context = h.canonical.bind_active((v1.identity,), "learner-A", "learning", h.clock.now, "compatible-v2")
    o2 = seed(h, derived("O-under-v2"), versions=new_context)
    e.capture(h, "coexisting boundary versions")
    e.check("old result retains v1", json_value(h.get(o1).versions), json_value(old_context))
    e.check("new boundary binds v2", list(new_context.semantic_bindings) == [v2], True)
    e.check("old exact version still resolves", h.canonical.get(v1).payload, {"fixture": "v1"})
    e.check("activation does not blanket invalidate old compatible result", e.resolve(h, o1.identity, "after activation") == o1, True)
    e.check("new result is readable", e.resolve(h, o2.identity, "after activation") == o2, True)


CASES = {"B1-foundation": b1, "B2-foundation": b2, "C1-foundation": c1}


def run_case(case_id, case, directory):
    recorder = EvidenceRecorder(directory / f"{case_id}.jsonl")
    error = None
    try:
        guarded = case_id in ("ContextCommit-foundation", "F2-injected-foundation")
        recorder.emit("case_start", case_id=case_id, implementation_scope="Step 3–4" if guarded else "Step 0–2",
                      standing_source="backend-enforced commit with scripted semantic review" if guarded else "scripted fixture",
                      assumption_status="UNVALIDATED")
        case(recorder)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        recorder.emit("execution_failure", **error)
    finally:
        summary = {"case_id": case_id,
                   "foundation_result": "PASS" if error is None and recorder.checks
                   and all(c["passed"] for c in recorder.checks) else "FAIL",
                   "check_count": len(recorder.checks), "error": error,
                   "assumption_status": "UNVALIDATED"}
        recorder.emit("case_end", **summary)
        recorder.close()
    return summary
