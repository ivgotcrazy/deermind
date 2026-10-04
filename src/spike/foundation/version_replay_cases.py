"""C1/C2 fixtures with real version/commit/replay mechanisms and scripted cognition."""

from hashlib import sha256

from .boundary import ContextInput, Protocol
from .cases import seed
from .dependency_cases import DependencyWorld
from .records import Dependency, Mode, Ref, Role, Space, json_value
from .replay import ArtifactStore, ReplayRuntime
from .runtime import Activation, Compatibility, Decision
from .security import AuthorityGrant, DataUseGrant


class VersionReplayWorld(DependencyWorld):
    def __init__(self, evidence):
        super().__init__(evidence)
        self.old_protocol = self.protocols["Observation"]
        self.h.canonical.activate_fixture(Activation("C-activate-v1", self.old_protocol.ref,
                                                   "learner-A", "learning", self.h.clock.advance()))
        self.h.canonical.activate_fixture(Activation("C-rule-v1", self.old_protocol.semantic_rule,
                                                   "learner-A", "learning", self.h.clock.advance()))
        self.artifacts = ArtifactStore()
        content = "Synthetic C fixture raw work: 42 / 6 = 8."
        self.artifact = seed(self.h, Ref(Space.FACT, "raw-work", "1"), kind="GroundingArtifact",
                             payload={"sha256": sha256(content.encode()).hexdigest()})
        self.artifacts.put_fixture(self.artifact, content)
        self.work = seed(self.h, Ref(Space.FACT, "work", "2"), kind="LearnerWorkSubmitted",
                         occurrence_key="work", corrects=self.work,
                         dependencies=(Dependency(self.artifact, Mode.PINNED, Role.FACTUAL),),
                         payload={"artifact": json_value(self.artifact), "fixture": "C-version-replay"})
        self.e.emit("C_setup", fact=json_value(self.h.get(self.work)), artifact=json_value(self.h.get(self.artifact)),
                    semantic_source="SELECTED-REINTERPRETATION-FIXTURE", provider="availability-controlled fixture")
        self.calls = 0
        def synthetic_model(raw, records):
            self.calls += 1
            return {"description": "Different scripted output from a new execution."}
        self.models = {"fixture-model:r1": synthetic_model, "fixture-model:r2": synthetic_model}
        self.replay = ReplayRuntime(self.runtime, self.artifacts, self.models)
        self.roots = []

    def reinterpret(self, factual_refs, target_version, revision):
        """Selected reinterpretation fixture logic; never a language classifier."""
        if factual_refs != (self.work,):
            raise ValueError("Unexpected factual fixture")
        protocol = self.runtime._protocols[target_version]
        compatibility = "C-v2-compatible" if target_version.revision == "v2" else "B-Observation-compatible"
        versions = self.h.canonical.bind_active((target_version.identity, protocol.semantic_rule.identity), "learner-A", "learning",
                                                self.h.clock.now, compatibility)
        if versions.semantic_bindings[0] != target_version:
            raise ValueError("TargetVersionNotActive")
        self.versions["Observation"] = versions
        self.protocols["Observation"] = protocol
        prepared = self.prepare("Observation", "O", revision, self.work)
        ref = self.finish(prepared)
        token, candidate, review = prepared
        context = self.runtime._contexts[candidate.context_id]
        context_manifest = next(r for r in self.h.executions.records()
                                if r.kind == "ContextManifest" and r.payload["context_id"] == context.identity)
        commit = next(r for r in self.h.audit.records() if r.kind == "CommitOutcome"
                      and r.payload.get("candidate_id") == candidate.identity and r.payload["status"] == "Committed")
        root = self.runtime.execution("ReplayManifest", "learner-A", {
            "semantic_source": "SELECTED-REINTERPRETATION-FIXTURE", "model_ref": "fixture-model:r1",
            "records": {"output": json_value(ref), "generation": json_value(candidate.execution),
                        "validation": json_value(review.execution), "commit": json_value(commit.ref),
                        "context": json_value(context_manifest.ref), "fact": json_value(self.work),
                        "artifact": json_value(self.artifact), "protocol": json_value(target_version),
                        "rule": json_value(protocol.semantic_rule)}})
        self._grant_replay(root)
        self.roots.append(root)
        return ref, root

    def _grant_replay(self, root):
        records = self.h.get(root).payload["records"]
        identities = (root.identity,) + tuple(r["identity"] for r in records.values())
        suffix = root.identity
        self.security.install_authority(AuthorityGrant("C-read-"+suffix, "interaction", "learning", "learner-A",
                                                       identities, ("read",), 100000))
        self.security.install_authority(AuthorityGrant("C-replay-"+suffix, "interaction", "learning", "learner-A",
                                                       (root.identity,), ("historical_reconstruct", "reexecute"), 100000))
        kinds = tuple({self.h.get(Ref(Space(r["space"]), r["identity"], r["revision"])).kind for r in records.values()}) + ("ReplayManifest",)
        self.security.install_data(DataUseGrant("C-read-data-"+suffix, "interaction", "learning", "learner-A",
                                               kinds, ("read",), ("replay-runtime",), "run", "internal", 100000))
        self.security.install_data(DataUseGrant("C-replay-data-"+suffix, "interaction", "learning", "learner-A",
                                               ("ReplayManifest",), ("historical_reconstruct", "reexecute"),
                                               ("replay-runtime",), "run", "internal", 100000))

    def install_v2(self):
        old = self.old_protocol
        ref = seed(self.h, Ref(Space.CANONICAL, old.ref.identity, "v2"), kind="ReasoningProtocol",
                   payload={"semantic_source": "SELECTED-REINTERPRETATION-FIXTURE", "version": "v2"})
        rule = seed(self.h, Ref(Space.CANONICAL, old.semantic_rule.identity, "v2"), kind="SemanticValidationRules",
                    payload={"format": "fixture", "version": "v2"})
        self.runtime.register_protocol(Protocol(ref, "Observation", "Interaction", old.allowed_context_kinds, old.fields, rule))
        self.h.canonical.add_compatibility_fixture(Compatibility("C-v2-compatible", (ref, rule), "learner-A", "learning", Decision.ALLOW))
        return ref

    def activate(self, ref):
        self.h.canonical.activate_fixture(Activation("C-activate-"+ref.revision, ref, "learner-A", "learning", self.h.clock.advance()))
        self.h.canonical.activate_fixture(Activation("C-rule-"+ref.revision, self.runtime._protocols[ref].semantic_rule,
                                                   "learner-A", "learning", self.h.clock.advance()))

    def record_replay(self, label, result, expected):
        self.e.emit("replay", label=label, result=result)
        self.e.check(label, result["capability"], expected)


def c1(e):
    w = VersionReplayWorld(e)
    o1, old_execution = w.reinterpret((w.work,), w.old_protocol.ref, "r1")
    old_record = w.h.get(o1)
    v2 = w.install_v2()
    e.check("committing v2 does not activate it", w.h.canonical.active(v2.identity, "learner-A", "learning", w.h.clock.now).target == w.old_protocol.ref, True)
    w.activate(v2)
    o2, new_execution = w.reinterpret((w.work,), v2, "r2")
    e.check("same original fact under both versions", w.h.get(o1).dependencies[0].target == w.work == w.h.get(o2).dependencies[0].target, True)
    e.check("old version and record immutable", w.h.get(o1) == old_record, True)
    e.check("new boundary binds v2", w.h.get(o2).versions.semantic_bindings[0] == v2, True)
    e.check("two revisions physically coexist", len(w.h.states.records()), 2)
    from .runtime import CurrentResolver
    resolution = CurrentResolver(w.h.capture(), w.runtime._eligibility(w.tokens["interaction"], "reasoning-runtime")).resolve_exact(o1, "learner-A", "learning")
    e.emit("exact_old_resolution", **json_value(resolution))
    e.check("activation does not blanket invalidate compatible old exact record", resolution.current == o1, True)
    old_view = w.replay.historical_reconstruct(w.tokens["interaction"], old_execution)
    new_view = w.replay.historical_reconstruct(w.tokens["interaction"], new_execution)
    w.record_replay("old history reconstructed", old_view, "FULL")
    w.record_replay("new history reconstructed", new_view, "FULL")
    e.check("old history resolves exact v1", old_view["historical_view"]["version_context"]["semantic_bindings"][0]["revision"], "v1")
    e.check("new history resolves exact v2", new_view["historical_view"]["version_context"]["semantic_bindings"][0]["revision"], "v2")
    e.check("historical reconstruction makes no model calls", w.calls, 0)
    evidence = w.submit("Evidence", "E-0", "r1", o2)
    e.check("Evidence v1 can consume Observation v2 without global generation",
            (w.h.get(evidence).versions.semantic_bindings[0].revision,
             w.h.get(evidence).dependencies[0].target == o2), ("v1", True))
    w.preserve((old_record,))


def c2(e):
    w = VersionReplayWorld(e)
    output, root = w.reinterpret((w.work,), w.old_protocol.ref, "r1")
    token = w.tokens["interaction"]
    originals = {r.ref: r for space in Space for r in w.h.history_for(space).records()}
    w.record_replay("complete history", w.replay.historical_reconstruct(token, root), "FULL")
    w.record_replay("same-environment new execution", w.replay.reexecute(token, root, "fixture-model:r1"), "FULL")
    e.check("re-execution does not overwrite historical output", w.h.get(output) == originals[output], True)
    original_model = w.models.pop("fixture-model:r1")
    e.emit("availability_change", model="fixture-model:r1", available=False)
    w.record_replay("model unavailable does not block reconstruction", w.replay.historical_reconstruct(token, root), "FULL")
    w.record_replay("exact re-execution unavailable", w.replay.reexecute(token, root, "fixture-model:r1"), "UNAVAILABLE")
    substitute = w.replay.reexecute(token, root, "fixture-model:r2")
    w.record_replay("explicit different environment has partial fidelity", substitute, "PARTIAL")
    e.check("new output has no historical standing", substitute["historical_view"], None)
    w.models["fixture-model:r1"] = original_model
    e.emit("availability_change", model="fixture-model:r1", available=True)
    w.artifacts.remove_fixture(w.artifact, "retention fixture expiry")
    e.emit("retention", ref=json_value(w.artifact), reason=w.artifacts.removals[w.artifact])
    e.check("retention removes actual fixture bytes", w.artifacts.load(w.h.get(w.artifact)), (None, "RawArtifactRemoved"))
    partial = w.replay.historical_reconstruct(token, root)
    w.record_replay("missing raw artifact yields partial history", partial, "PARTIAL")
    e.check("no replacement raw artifact invented", partial["historical_view"]["raw_artifacts"], {})
    e.check("saved output retained despite raw removal", partial["historical_view"]["historical_output"], originals[output].payload_json)
    w.record_replay("raw input missing prevents new execution", w.replay.reexecute(token, root, "fixture-model:r1"), "UNAVAILABLE")
    w.stage("raw removal does not itself invalidate saved semantics", {"O": output})
    e.check("only two explicit fixture re-executions invoked", w.calls, 2)
    e.check("all original history remains unchanged", all(w.h.get(ref) == r for ref, r in originals.items()), True)
    e.check("re-execution creates no formal derived state", len(w.h.states.records()), 1)
    w.preserve((originals[output],))


CASES = {"C1": c1, "C2": c2}
