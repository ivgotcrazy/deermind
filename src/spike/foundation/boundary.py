"""Context, exact-candidate validation and synchronous formal commit for the Spike."""

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from uuid import uuid4

from .records import Dependency, Mode, Record, Ref, Role, Space, VersionContext, json_value
from .runtime import ContractError, CurrentResolver, Decision
from .security import AccessDenied, DataUse, Operation, parameter
from .semantic_review import check_criteria_review


def digest(value):
    return sha256(json.dumps(json_value(value), sort_keys=True, ensure_ascii=False,
                             allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Protocol:
    ref: Ref
    candidate_kind: str
    owner: str
    allowed_context_kinds: tuple[str, ...]
    # Exact structural fields; no lexical/keyword interpretation of their contents.
    fields: tuple[tuple[str, str], ...]
    semantic_rule: Ref
    destination: str = "reasoning-runtime"


@dataclass(frozen=True)
class ContextInput:
    ref: Ref
    role: Role
    required: bool = True
    current: bool = True


@dataclass(frozen=True)
class ContextItem:
    record: Record
    authority_basis: tuple[str, ...]
    data_authority_basis: tuple[str, ...]


@dataclass(frozen=True)
class ContextPackage:
    identity: str
    principal: str
    subject: str
    scope: str
    purpose: str
    protocol: Ref
    versions: VersionContext
    items: tuple[ContextItem, ...]
    dependencies: tuple[Dependency, ...]
    excluded: tuple[tuple[Ref, str], ...]
    frozen_at: int


@dataclass(frozen=True)
class Candidate:
    identity: str
    record: Record
    protocol: Ref
    context_id: str
    execution: Ref
    expected_head: Ref | None


@dataclass(frozen=True)
class SemanticValidation:
    identity: str
    candidate_digest: str
    context_id: str
    protocol: Ref
    rule: Ref
    execution: Ref
    model_ref: str
    status: str
    rationale: str
    fixture: bool
    details_json: str = "{}"


@dataclass(frozen=True)
class CommitOutcome:
    status: str
    candidate_digest: str
    committed: Ref | None
    reason: str
    audit_ref: Ref


class BoundaryRuntime:
    def __init__(self, harness, security):
        self.h, self.security = harness, security
        self._protocols = {}
        self._contexts = {}
        self._candidates = {}
        self._reviews = {}

    def register_protocol(self, protocol):
        if protocol.ref in self._protocols:
            raise ContractError("Protocol registration is immutable")
        if (protocol.ref.space != Space.CANONICAL or protocol.semantic_rule.space != Space.CANONICAL
                or self.h.get(protocol.ref) is None or self.h.get(protocol.semantic_rule) is None):
            raise ContractError("Protocol and semantic rules must have exact canonical records")
        if protocol.owner != {"Observation": "Interaction", "PolicyOutcome": "Interaction",
                              "Evidence": "Evaluation", "LearnerBelief": "Evaluation"}.get(protocol.candidate_kind):
            raise ContractError("Protocol cannot redefine semantic ownership")
        self._protocols[protocol.ref] = protocol

    def execution(self, kind, subject, payload):
        record = Record.create(ref=Ref(Space.EXECUTION, uuid4().hex, "1"), kind=kind,
                               subject=subject, owner="ReasoningRuntime", recorded_at=self.h.clock.now,
                               payload=payload, provenance=("runtime-created",))
        self.h.executions.append(record)
        return record.ref

    def _eligibility(self, token, destination):
        def check(record, scope, purpose):
            auth = self.security.authority(token, Operation(purpose, record.subject, record.ref.identity, "read"))
            if auth.decision != Decision.ALLOW:
                return "Unauthorized"
            data = self.security.data_authority(token, DataUse(purpose, record.subject, record.kind, "read", destination))
            return "" if data.decision == Decision.ALLOW else "DataAuthorityDenied"
        return check

    def assemble(self, token, protocol_ref, subject, scope, purpose, inputs, versions):
        protocol = self._protocols[protocol_ref]
        source = self.execution("ContextAssembly", subject, {"protocol": json_value(protocol_ref)})
        request = Operation(purpose, subject, protocol_ref.identity, "reason")
        authority, _ = self.security.enforce(token, request, source)
        if protocol_ref not in versions.semantic_bindings or protocol.semantic_rule not in versions.semantic_bindings:
            raise ContractError("VersionContext must bind the protocol and semantic rule")
        if self.h.canonical.check_compatibility(versions, scope, purpose, self.h.clock.now) != Decision.ALLOW:
            raise ContractError("VersionIncompatible")
        items, dependencies, excluded = [], [], []
        for requested in inputs:
            try:
                record, (auth, data) = self.security.read(token, requested.ref, purpose, protocol.destination,
                                                        source, protocol.allowed_context_kinds)
                if record.subject != subject:
                    raise ContractError("SubjectMismatch")
                if requested.current:
                    result = CurrentResolver(self.h.capture(), self._eligibility(token, protocol.destination)).resolve_exact(
                        requested.ref, scope, purpose)
                    if result.current is None:
                        raise ContractError(result.reason)
                items.append(ContextItem(record, auth.authority_basis, data.authority_basis))
                dependencies.append(Dependency(record.ref, Mode.CURRENT if requested.current else Mode.PINNED,
                                               requested.role))
            except (AccessDenied, ContractError) as exc:
                reason = exc.category if isinstance(exc, AccessDenied) else str(exc)
                excluded.append((requested.ref, reason))
                self.execution("ContextExclusion", subject, {"source": json_value(source),
                                                             "ref": json_value(requested.ref), "reason": reason})
                if requested.required:
                    raise
        for ref in versions.semantic_bindings:
            self.security.read(token, ref, purpose, protocol.destination, source)
            dependencies.append(Dependency(ref, Mode.CURRENT, Role.CANONICAL))
        package = ContextPackage(uuid4().hex, authority.principal, subject, scope, purpose, protocol_ref,
                                 versions, tuple(items), tuple(dependencies), tuple(excluded), self.h.clock.now)
        self._contexts[package.identity] = package
        # Manifest is distinct from the actual payload package and VersionContext.
        self.execution("ContextManifest", subject, {"context_id": package.identity, "protocol": json_value(protocol_ref),
                       "included": [{"ref": json_value(i.record.ref), "authority": i.authority_basis,
                                     "data_authority": i.data_authority_basis} for i in items],
                       "excluded": [{"ref": json_value(r), "reason": why} for r, why in excluded],
                       "versions": json_value(versions), "frozen_at": package.frozen_at})
        self.h.control.reach("afterContextFrozen")
        return package

    def propose(self, context, identity, revision, payload, expected_head=None):
        if self._contexts.get(context.identity) != context:
            raise ContractError("Context must originate from the assembler")
        protocol = self._protocols[context.protocol]
        execution = self.execution("CandidateGeneration", context.subject, {"context_id": context.identity,
                                   "protocol": json_value(protocol.ref), "output": payload})
        record = Record.create(ref=Ref(Space.DERIVED, identity, revision), kind=protocol.candidate_kind,
                               subject=context.subject, owner=protocol.owner, recorded_at=self.h.clock.now,
                               payload=payload, scope=context.scope, purpose=context.purpose,
                               dependencies=context.dependencies, versions=context.versions,
                               provenance=(execution.identity, context.identity))
        candidate = Candidate(uuid4().hex, record, context.protocol, context.identity, execution, expected_head)
        self._candidates[candidate.identity] = candidate
        return candidate

    def record_semantic_validation(self, token, candidate, status, rationale, model_ref, *, fixture=False):
        """Trusted validation execution boundary; never exposed as a model callable tool.

        Direct result injection is restricted to explicitly marked test fixtures.
        Real reviews originate in validate_with_llm and its provider execution.
        """
        if not fixture:
            raise ContractError("RealLLMValidationUnavailable")
        if status not in ("PASS", "FAIL", "UNRESOLVED"):
            raise ContractError("Invalid semantic validation status")
        context = self._contexts[candidate.context_id]
        protocol = self._protocols[candidate.protocol]
        source = self.execution("SemanticValidationExecution", candidate.record.subject,
                                {"candidate_digest": digest(candidate), "context_id": context.identity,
                                 "protocol": json_value(protocol.ref), "rule": json_value(protocol.semantic_rule),
                                 "model_ref": model_ref, "status": status, "fixture": True})
        use = DataUse(context.purpose, context.subject, candidate.record.kind, "validate", protocol.destination)
        self.security.enforce(token, Operation(context.purpose, context.subject, protocol.ref.identity, "validate"), source, use)
        for item in context.items:
            self.security.read(token, item.record.ref, context.purpose, protocol.destination, source,
                               protocol.allowed_context_kinds)
        result = SemanticValidation(uuid4().hex, digest(candidate), context.identity, protocol.ref,
                                    protocol.semantic_rule, source, model_ref, status, rationale, True)
        self._reviews[result.identity] = result
        return result

    def _model_context(self, token, context, source):
        protocol = self._protocols[context.protocol]
        values = []
        for item in context.items:
            record, _ = self.security.read(token, item.record.ref, context.purpose, protocol.destination,
                                           source, protocol.allowed_context_kinds)
            values.append({"ref": json_value(record.ref), "kind": record.kind, "content": record.payload})
        return values

    def generate_with_llm(self, token, context, adapter):
        if self._contexts.get(context.identity) != context:
            raise ContractError("UnregisteredContext")
        if adapter.config.base_url != self._protocols[context.protocol].destination:
            raise ContractError("ModelDestinationMismatch")
        source = self.execution("LLMGenerationStarted", context.subject, {"context_id": context.identity})
        authority, _ = self.security.enforce(token, Operation(context.purpose, context.subject, context.protocol.identity, "reason"), source)
        if authority.principal != context.principal:
            raise ContractError("ExecutionPrincipalMismatch")
        content = self._model_context(token, context, source)
        protocol_record = self.h.get(context.protocol)
        messages = [{"role": "system", "content": protocol_record.payload["generation_system"]},
                    {"role": "user", "content": json.dumps(content, ensure_ascii=False)}]
        try:
            payload, call_id = adapter.complete(messages, "ObservationGeneration")
        except Exception:
            self.execution("LLMGenerationFailed", context.subject, {"context_id": context.identity})
            raise
        candidate = self.propose(context, "O", "r1", payload)
        candidate = replace(candidate, record=replace(candidate.record,
                            provenance=candidate.record.provenance + (f"model-call:{call_id}",)))
        self._candidates[candidate.identity] = candidate
        self.execution("LLMGenerationCompleted", context.subject, {"context_id": context.identity,
                       "model_call": call_id, "candidate_digest": digest(candidate)})
        return candidate

    def validate_with_llm(self, token, candidate, adapter):
        if self._candidates.get(candidate.identity) != candidate:
            raise ContractError("UnregisteredOrAlteredCandidate")
        context = self._contexts[candidate.context_id]
        protocol = self._protocols[candidate.protocol]
        if adapter.config.base_url != protocol.destination:
            raise ContractError("ModelDestinationMismatch")
        source = self.execution("LLMValidationStarted", context.subject, {"candidate_digest": digest(candidate)})
        self.security.enforce(token, Operation(context.purpose, context.subject, protocol.ref.identity, "validate"), source,
                              DataUse(context.purpose, context.subject, candidate.record.kind, "validate", protocol.destination))
        content = self._model_context(token, context, source)
        rule = self.h.get(protocol.semantic_rule)
        # These are exact arithmetic fixture facts, not a natural-language classifier.
        arithmetic = {"42 / 6": 42 // 6, "8 * 15": 8 * 15, "42 / 6 * 15": (42 // 6) * 15}
        messages = [{"role": "system", "content": rule.payload["system"]},
                    {"role": "user", "content": json.dumps({"context": content,
                     "candidate": candidate.record.payload, "arithmetic_fixture": arithmetic,
                     "criteria": rule.payload.get("criteria", [])}, ensure_ascii=False)}]
        try:
            output, call_id = adapter.complete(messages, "ObservationSemanticValidation")
        except Exception:
            self.execution("LLMValidationFailed", context.subject, {"candidate_digest": digest(candidate)})
            raise
        try:
            if rule.payload.get("format") == "criteria-quotes-v2":
                status, rationale = check_criteria_review(output, candidate.record.payload, rule.payload["criteria"])
            elif rule.payload.get("format", "legacy-v1") == "legacy-v1":
                if (set(output) != {"status", "rationale"} or output["status"] not in ("PASS", "FAIL", "UNRESOLVED")
                        or not isinstance(output["rationale"], str) or not output["rationale"].strip()):
                    raise ContractError("InvalidSemanticValidationOutput")
                status, rationale = output["status"], output["rationale"]
            else:
                raise ContractError("UnsupportedSemanticValidationFormat")
        except ContractError as exc:
            self.execution("SemanticValidationRejected", context.subject,
                           {"candidate_digest": digest(candidate), "model_call": call_id,
                            "reason": str(exc), "output": output})
            raise
        execution = self.execution("SemanticValidationExecution", context.subject,
                                   {"candidate_digest": digest(candidate), "context_id": context.identity,
                                    "protocol": json_value(protocol.ref), "rule": json_value(protocol.semantic_rule),
                                    "model_ref": adapter.config.model, "model_call": call_id,
                                    "status": status, "fixture": False, "details": output})
        review = SemanticValidation(uuid4().hex, digest(candidate), context.identity, protocol.ref,
                                    protocol.semantic_rule, execution, adapter.config.model, status,
                                    rationale, False, json.dumps(output, ensure_ascii=False, sort_keys=True))
        self._reviews[review.identity] = review
        return review

    def validate(self, candidate, review_id):
        if self._candidates.get(candidate.identity) != candidate:
            return "UnregisteredOrAlteredCandidate"
        context = self._contexts.get(candidate.context_id)
        protocol = self._protocols.get(candidate.protocol)
        if context is None or protocol is None or context.protocol != candidate.protocol:
            return "ProtocolContextMismatch"
        r = candidate.record
        if r.ref.space != Space.DERIVED or (r.kind, r.owner) != (protocol.candidate_kind, protocol.owner):
            return "CandidateStandingMismatch"
        if (r.subject, r.scope, r.purpose, r.versions, r.dependencies) != (
                context.subject, context.scope, context.purpose, context.versions, context.dependencies):
            return "ContextBindingMismatch"
        payload = r.payload
        types = {"string": str, "array": list, "object": dict, "number": (int, float), "boolean": bool}
        if not isinstance(payload, dict) or set(payload) != {name for name, _ in protocol.fields}:
            return "SchemaMismatch"
        for name, typename in protocol.fields:
            if typename not in types or not isinstance(payload[name], types[typename]):
                return "SchemaMismatch"
            if typename == "number" and isinstance(payload[name], bool):
                return "SchemaMismatch"
        for dep in r.dependencies:
            if self.h.get(dep.target) is None:
                return "MissingGroundingReference"
        review = self._reviews.get(review_id)
        if review is None:
            return "RequiredSemanticValidationMissing"
        if (review.candidate_digest, review.context_id, review.protocol, review.rule) != (
                digest(candidate), context.identity, protocol.ref, protocol.semantic_rule):
            return "SemanticValidationBindingMismatch"
        execution = self.h.get(review.execution)
        if (execution is None or execution.kind != "SemanticValidationExecution"
                or execution.payload["candidate_digest"] != digest(candidate)):
            return "UntrustedValidationExecution"
        rule = self.h.get(protocol.semantic_rule)
        if rule.payload.get("format") == "criteria-quotes-v2":
            try:
                details = json.loads(review.details_json)
                status, _ = check_criteria_review(details, r.payload, rule.payload["criteria"])
                if status != review.status or execution.payload.get("details") != details:
                    return "SemanticValidationDetailsMismatch"
            except (ContractError, ValueError) as exc:
                return f"SemanticValidationEvidenceInvalid:{exc}"
        return "" if review.status == "PASS" else f"SemanticValidation:{review.status}"

    def commit(self, token, candidate, review_id):
        self.h.control.reach("beforeCandidateValidation")
        error = self.validate(candidate, review_id)
        self.execution("CandidateValidation", candidate.record.subject,
                       {"candidate_digest": digest(candidate), "review_id": review_id, "reason": error})
        if error:
            return self._outcome(candidate, "ValidationFailed", error)
        self.h.control.reach("beforeCommitRevalidation")
        record = candidate.record
        context = self._contexts[candidate.context_id]
        protocol = self._protocols[candidate.protocol]
        request = Operation(record.purpose, record.subject, record.ref.identity, "commit",
                            (parameter("owner", record.owner), parameter("kind", record.kind)))
        use = DataUse(record.purpose, record.subject, record.kind, "commit", "formal-state")
        try:
            authority, _ = self.security.enforce(token, request, candidate.execution, use)
            if authority.principal != context.principal:
                return self._outcome(candidate, "Unauthorized", "ExecutionPrincipalMismatch")
            # All critical reads are reauthorized even when the context was formerly legal.
            for dep in record.dependencies:
                self.security.read(token, dep.target, record.purpose, protocol.destination, candidate.execution)
        except AccessDenied as exc:
            return self._outcome(candidate, exc.category, exc.decision.reason)
        except ContractError as exc:
            return self._outcome(candidate, "CandidateStale", str(exc))
        head = self.h.states.candidate(record.ref.identity, record.scope, record.purpose, self.h.clock.now)
        if (head.ref if head else None) != candidate.expected_head or self.h.get(record.ref) is not None:
            return self._outcome(candidate, "CommitConflict", "ExpectedHeadChanged")
        if record.valid_until is not None and record.valid_until <= self.h.clock.now:
            return self._outcome(candidate, "LifecycleIneligible", "CandidateExpired")
        if self.h.canonical.check_compatibility(record.versions, record.scope, record.purpose, self.h.clock.now) != Decision.ALLOW:
            return self._outcome(candidate, "VersionIncompatible", "VersionCombinationUnavailable")
        # Validate the proposed graph in a private snapshot; it has no standing yet.
        snapshot = self.h.capture()
        proposed = replace(record, recorded_at=snapshot.clock.now)
        snapshot.states.append(proposed)
        eligibility = self._eligibility(token, protocol.destination)
        def check(upstream, scope, purpose):
            return "" if upstream.ref == proposed.ref else eligibility(upstream, scope, purpose)
        resolution = CurrentResolver(snapshot, check).resolve_exact(proposed.ref, record.scope, record.purpose)
        self.execution("CommitResolution", record.subject, json_value(resolution))
        if resolution.current is None:
            status = resolution.reason if resolution.reason in ("Unauthorized", "DataAuthorityDenied", "LifecycleIneligible") else "CandidateStale"
            return self._outcome(candidate, status, resolution.reason)
        # No await/callback between final checks and append: single-process atomic boundary.
        committed = replace(record, recorded_at=self.h.clock.now,
                            provenance=record.provenance + (f"candidate-sha256:{digest(candidate)}", review_id))
        self.h.states.append(committed)
        return self._outcome(candidate, "Committed", "", committed.ref)

    def _outcome(self, candidate, status, reason, committed=None):
        audit = Record.create(ref=Ref(Space.AUDIT, uuid4().hex, "1"), kind="CommitOutcome",
                              subject=candidate.record.subject, owner="FormalCommit",
                              recorded_at=self.h.clock.now,
                              payload={"candidate_digest": digest(candidate), "candidate_id": candidate.identity,
                                       "status": status, "reason": reason,
                                       "committed": json_value(committed) if committed else None},
                              provenance=(candidate.execution.identity,))
        self.h.audit.append(audit)
        return CommitOutcome(status, digest(candidate), committed, reason, audit.ref)
