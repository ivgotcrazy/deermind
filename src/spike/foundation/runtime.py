"""Steps 0–2 mechanisms. Loading fixture standing is NOT FormalCommit."""

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum

from .records import Dependency, Mode, Record, Ref, Space, VersionContext, json_value


class ContractError(ValueError):
    pass


@dataclass
class FakeClock:
    now: int = 0

    def advance(self, duration: int = 1):
        if type(duration) is not int or duration < 0:
            raise ValueError("Clock cannot move backwards")
        self.now += duration
        return self.now


class History:
    def __init__(self, space: Space):
        self.space = space
        self._records: dict[Ref, Record] = {}

    def append(self, record: Record):
        if record.ref.space != self.space:
            raise ContractError("History standing mismatch")
        if record.ref in self._records:
            raise ContractError("Committed exact records cannot be overwritten")
        if self._records and record.recorded_at < next(reversed(self._records.values())).recorded_at:
            raise ContractError("Append time must be monotonic")
        self._records[record.ref] = record
        return record.ref

    def get(self, ref: Ref):
        return self._records.get(ref)

    def records(self, subject: str | None = None):
        return tuple(r for r in self._records.values() if subject is None or r.subject == subject)

    def candidate(self, identity: str, scope: str, purpose: str, time: int):
        # Select once, then validate. Never search backwards after validation fails.
        return next((r for r in reversed(self.records()) if r.ref.identity == identity
                     and r.scope == scope and r.purpose == purpose and r.recorded_at <= time), None)


class FactualHistory(History):
    def __init__(self):
        super().__init__(Space.FACT)

    def corrected(self, ref: Ref, time: int):
        return next((r for r in reversed(self.records())
                     if r.corrects == ref and r.recorded_at <= time), None)

    def version_revocation(self, ref: Ref, scope: str, purpose: str, time: int):
        return next((r for r in reversed(self.records())
                     if r.kind == 'VersionRevocationOccurred' and r.recorded_at <= time
                     and (r.scope, r.purpose) == (scope, purpose)
                     and r.payload.get('target') == json_value(ref)), None)

    def resolve_effective_occurrence(self, occurrence_key: str, subject: str, time: int):
        return next((r for r in reversed(self.records(subject))
                     if r.occurrence_key == occurrence_key and r.recorded_at <= time), None)


@dataclass(frozen=True)
class Activation:
    identity: str
    target: Ref
    scope: str
    purpose: str
    recorded_at: int


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Compatibility:
    identity: str
    bindings: tuple[Ref, ...]
    scope: str
    purpose: str
    decision: Decision


class CanonicalRegistry(History):
    def __init__(self):
        super().__init__(Space.CANONICAL)
        self._activations: dict[str, Activation] = {}
        self._compatibility: dict[str, Compatibility] = {}

    def activate_fixture(self, activation: Activation):
        record = self.get(activation.target)
        if record is None or record.recorded_at > activation.recorded_at:
            raise ContractError("Only an existing committed version can be activated")
        if activation.identity in self._activations:
            raise ContractError("Activation records are immutable")
        if self._activations and activation.recorded_at < next(reversed(self._activations.values())).recorded_at:
            raise ContractError("Activation time must be monotonic")
        self._activations[activation.identity] = activation

    def active(self, identity: str, scope: str, purpose: str, time: int):
        return next((a for a in reversed(tuple(self._activations.values()))
                     if a.target.identity == identity and a.scope == scope
                     and a.purpose == purpose and a.recorded_at <= time), None)

    def add_compatibility_fixture(self, fixture: Compatibility):
        if fixture.identity in self._compatibility:
            raise ContractError("Compatibility evidence cannot be overwritten")
        if not isinstance(fixture.decision, Decision):
            raise ContractError("Compatibility decision must be typed")
        self._compatibility[fixture.identity] = fixture

    def check_compatibility(self, versions: VersionContext, scope: str, purpose: str, time: int):
        if not versions.semantic_bindings:
            return Decision.ALLOW if versions.compatibility_basis is None else Decision.UNKNOWN
        if any(self.get(r) is None or self.get(r).recorded_at > time for r in versions.semantic_bindings):
            return Decision.UNKNOWN
        fixture = self._compatibility.get(versions.compatibility_basis)
        if fixture is None or set(fixture.bindings) != set(versions.semantic_bindings):
            return Decision.UNKNOWN
        if (fixture.scope, fixture.purpose) != (scope, purpose):
            return Decision.UNKNOWN
        return fixture.decision

    def bind_active(self, identities: tuple[str, ...], scope: str, purpose: str, time: int,
                    compatibility_basis: str, execution_bindings=()):
        active = tuple(self.active(i, scope, purpose, time) for i in identities)
        if any(a is None for a in active):
            raise ContractError("No active version for the requested boundary")
        context = VersionContext(tuple(a.target for a in active), tuple(execution_bindings),
                                 compatibility_basis, tuple(a.identity for a in active))
        if self.check_compatibility(context, scope, purpose, time) != Decision.ALLOW:
            raise ContractError("Version combination lacks compatible fixture evidence")
        return context

    def activations(self):
        return tuple(self._activations.values())

    def compatibilities(self):
        return tuple(self._compatibility.values())


@dataclass(frozen=True)
class EligibilityFixture:
    authority: Decision = Decision.UNKNOWN
    data_authority: Decision = Decision.UNKNOWN
    security: Decision = Decision.UNKNOWN


@dataclass
class Harness:
    clock: FakeClock = field(default_factory=FakeClock)
    facts: FactualHistory = field(default_factory=FactualHistory)
    canonical: CanonicalRegistry = field(default_factory=CanonicalRegistry)
    states: History = field(default_factory=lambda: History(Space.DERIVED))
    executions: History = field(default_factory=lambda: History(Space.EXECUTION))
    audit: History = field(default_factory=lambda: History(Space.AUDIT))
    eligibility: dict[tuple[str, str], EligibilityFixture] = field(default_factory=dict)
    control: "TestControl" = field(default_factory=lambda: TestControl())

    def history_for(self, space: Space):
        return {Space.FACT: self.facts, Space.CANONICAL: self.canonical,
                Space.DERIVED: self.states, Space.EXECUTION: self.executions,
                Space.AUDIT: self.audit}[space]

    def get(self, ref: Ref):
        return self.history_for(ref.space).get(ref)

    def seed_committed_fixture(self, record: Record):
        """Install owner-authored test data; deliberately not a public commit gate."""
        if record.recorded_at > self.clock.now:
            raise ContractError("Cannot seed a future committed record")
        if record.kind == 'VersionRevocationOccurred':
            try:
                value = record.payload['target']
                target = self.get(Ref(Space(value['space']), value['identity'], value['revision']))
                value = record.payload['source']
                source = self.get(Ref(Space(value['space']), value['identity'], value['revision']))
            except (KeyError, TypeError, ValueError):
                raise ContractError('InvalidVersionRevocationFixture') from None
            if (record.ref.space != Space.FACT or record.owner != 'Evolution' or target is None
                    or target.ref.space != Space.CANONICAL or source is None
                    or source.ref.space not in (Space.FACT, Space.EXECUTION)
                    or target.subject != record.subject or source.subject != record.subject
                    or source.recorded_at > record.recorded_at or target.recorded_at > record.recorded_at):
                raise ContractError('InvalidVersionRevocationFixture')
        if record.corrects is not None:
            target = self.get(record.corrects)
            if target is None or target.subject != record.subject:
                raise ContractError("Correction requires an existing same-subject target")
            if target.ref.space == Space.FACT and target.occurrence_key != record.occurrence_key:
                raise ContractError("Factual correction must retain occurrence identity")
        if record.ref.space == Space.FACT and record.occurrence_key is not None:
            previous = self.facts.resolve_effective_occurrence(record.occurrence_key, record.subject, self.clock.now)
            if previous is not None and record.corrects != previous.ref:
                raise ContractError("An occurrence update must explicitly correct its latest fact")
        return self.history_for(record.ref.space).append(record)

    def capture(self):
        return deepcopy(self)

    @staticmethod
    def branch(snapshot):
        return deepcopy(snapshot)

    def resolve(self, identity: str, scope="learner-A", purpose="learning"):
        # One detached, synchronous read basis; never reuse it for a later effect.
        return CurrentResolver(self.capture()).resolve(identity, scope, purpose)


@dataclass(frozen=True)
class Check:
    ref: Ref
    purpose: str
    scope: str
    result: str
    detail: str = ""


@dataclass(frozen=True)
class Resolution:
    status: str
    candidate: Ref | None
    current: Ref | None
    reason: str
    checked_at: int
    checks: tuple[Check, ...]


class CurrentResolver:
    """Pull-only exact dependency traversal over one frozen foundation snapshot."""

    def __init__(self, snapshot: Harness, eligibility_check=None):
        self.snapshot = snapshot
        self.eligibility_check = eligibility_check
        self.time = snapshot.clock.now
        self.checks: list[Check] = []
        self.visiting = set()
        self.verified = set()
        self.current_basis = {}

    def resolve(self, identity: str, scope: str, purpose: str):
        self.checks.clear()
        self.visiting.clear()
        self.verified.clear()
        self.current_basis.clear()
        candidate = self.snapshot.states.candidate(identity, scope, purpose, self.time)
        reason = "MissingCandidate" if candidate is None else self._validate(candidate.ref, scope, purpose)
        return Resolution("Current" if not reason else "NoCurrentValidState",
                          candidate.ref if candidate else None,
                          candidate.ref if candidate and not reason else None,
                          reason, self.time, tuple(self.checks))

    def resolve_exact(self, ref: Ref, scope: str, purpose: str):
        self.checks.clear()
        self.visiting.clear()
        self.verified.clear()
        self.current_basis.clear()
        reason = self._validate(ref, scope, purpose)
        return Resolution("Current" if not reason else "NoCurrentValidState", ref,
                          None if reason else ref, reason, self.time, tuple(self.checks))

    def _validate(self, ref: Ref, scope: str, purpose: str):
        key = (ref, scope, purpose)
        if key in self.visiting:
            self.checks.append(Check(ref, purpose, scope, "ValidityCycle"))
            return "ValidityCycle"
        if key in self.verified:
            self.checks.append(Check(ref, purpose, scope, "AlreadyCheckedExact"))
            return ""
        identity = (ref.space, ref.identity, scope, purpose)
        if identity in self.current_basis and self.current_basis[identity] != ref:
            self.checks.append(Check(ref, purpose, scope, "DependencyIncoherent"))
            return "DependencyIncoherent"
        self.current_basis[identity] = ref
        self.visiting.add(key)
        reason = self._check_record(ref, scope, purpose)
        self.visiting.remove(key)
        self.checks.append(Check(ref, purpose, scope, reason or "Eligible"))
        if not reason:
            self.verified.add(key)
        return reason

    def _check_record(self, ref: Ref, scope: str, purpose: str):
        h = self.snapshot
        record = h.get(ref)
        if record is None or record.recorded_at > self.time:
            return "MissingExactReference"
        if ref.space not in (Space.FACT, Space.CANONICAL, Space.DERIVED):
            return "NonSemanticStanding"
        if ref.space == Space.DERIVED and (record.scope, record.purpose) != (scope, purpose):
            return "UseContextMismatch"
        if record.valid_until is not None and self.time >= record.valid_until:
            return "LifecycleIneligible"
        if ref.space == Space.CANONICAL and h.facts.version_revocation(ref, scope, purpose, self.time):
            return 'VersionIneligible'
        correction = h.facts.corrected(ref, self.time)
        if correction:
            self.checks.append(Check(ref, purpose, scope, "Corrected", str(correction.ref)))
            return "Corrected"
        if self.eligibility_check is not None:
            reason = self.eligibility_check(record, scope, purpose)
            if reason:
                return reason
        else:
            eligibility = h.eligibility.get((scope, purpose), EligibilityFixture())
            for name in ("authority", "data_authority", "security"):
                outcome = getattr(eligibility, name)
                if outcome != Decision.ALLOW:
                    return f"{name}:{outcome}"
        compatibility = h.canonical.check_compatibility(record.versions, scope, purpose, self.time)
        if compatibility != Decision.ALLOW:
            return f"VersionCompatibility:{compatibility}"
        for binding in record.versions.semantic_bindings:
            reason = self._validate(binding, scope, purpose)
            if reason:
                return reason
        # Different CURRENT revisions for one identity/use are an incoherent basis.
        targets = {}
        for dep in record.dependencies:
            dep_scope, dep_purpose = dep.scope or scope, dep.purpose or purpose
            target = h.get(dep.target)
            if target is None or target.recorded_at > self.time:
                self.checks.append(Check(dep.target, dep_purpose, dep_scope, "MissingExactReference"))
                return "MissingExactReference"
            if dep.mode == Mode.PINNED:
                self.checks.append(Check(dep.target, dep_purpose, dep_scope, "HistoricalPinned"))
                continue
            identity = (dep.target.space, dep.target.identity, dep_scope, dep_purpose)
            if identity in targets and targets[identity] != dep.target:
                return "DependencyIncoherent"
            targets[identity] = dep.target
            if dep.require_head:
                head = h.states.candidate(dep.target.identity, dep_scope, dep_purpose, self.time)
                if head is None or head.ref != dep.target:
                    self.checks.append(Check(dep.target, dep_purpose, dep_scope, "RequiredHeadChanged"))
                    return "RequiredHeadChanged"
            if dep.require_active:
                active = h.canonical.active(dep.target.identity, dep_scope, dep_purpose, self.time)
                if active is None or active.target != dep.target:
                    self.checks.append(Check(dep.target, dep_purpose, dep_scope, "RequiredActivationChanged"))
                    return "RequiredActivationChanged"
            reason = self._validate(dep.target, dep_scope, dep_purpose)
            if reason:
                return reason
        return ""


class InjectedFailure(RuntimeError):
    pass


class TestControl:
    POINTS = frozenset({"afterContextFrozen", "beforeCandidateValidation", "beforeCommitRevalidation",
                        "afterActionIntent", "beforeActionEffect", "beforeReplay"})

    def __init__(self):
        self._failures: dict[str, str] = {}

    def fail_once(self, point: str, message: str):
        if point not in self.POINTS:
            raise ValueError("Undeclared failure injection point")
        self._failures[point] = message

    def reach(self, point: str):
        if point not in self.POINTS:
            raise ValueError("Undeclared failure injection point")
        if point in self._failures:
            raise InjectedFailure(self._failures.pop(point))
