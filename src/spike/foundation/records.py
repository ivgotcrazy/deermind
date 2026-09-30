"""Immutable records and exact references used by the foundation fixtures."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import json


class Space(StrEnum):
    FACT = "fact"
    CANONICAL = "canonical"
    DERIVED = "derived"
    EXECUTION = "execution"
    AUDIT = "audit"


@dataclass(frozen=True, order=True)
class Ref:
    space: Space
    identity: str
    revision: str

    def __post_init__(self):
        if (not isinstance(self.space, Space) or not isinstance(self.identity, str)
                or not isinstance(self.revision, str) or not self.identity or not self.revision):
            raise ValueError("An exact reference requires space, identity and revision")


class Mode(StrEnum):
    PINNED = "PINNED"
    CURRENT = "CURRENT"


class Role(StrEnum):
    FACTUAL = "FACTUAL_GROUNDING"
    CANONICAL = "CANONICAL_SEMANTIC"
    EPISTEMIC = "EPISTEMIC"
    AUTHORITY = "AUTHORITY"
    DATA_AUTHORITY = "DATA_AUTHORITY"
    OPERATIONAL = "OPERATIONAL"


@dataclass(frozen=True)
class Dependency:
    target: Ref
    mode: Mode
    role: Role
    purpose: str | None = None
    scope: str | None = None
    require_head: bool = False
    require_active: bool = False

    def __post_init__(self):
        if not isinstance(self.mode, Mode) or not isinstance(self.role, Role):
            raise ValueError("Dependency mode and role must be typed")
        if self.require_head and self.target.space != Space.DERIVED:
            raise ValueError("require_head applies only to derived revisions")
        if self.require_active and self.target.space != Space.CANONICAL:
            raise ValueError("require_active applies only to canonical versions")
        if self.mode == Mode.PINNED and (self.require_head or self.require_active):
            raise ValueError("PINNED is historical provenance, not current eligibility")


@dataclass(frozen=True)
class VersionContext:
    semantic_bindings: tuple[Ref, ...] = ()
    execution_bindings: tuple[tuple[str, str], ...] = ()
    compatibility_basis: str | None = None
    activation_basis: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.semantic_bindings, tuple) or not isinstance(self.execution_bindings, tuple)
                or not isinstance(self.activation_basis, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or any(not isinstance(item, str) for item in pair) for pair in self.execution_bindings)
                or any(not isinstance(item, str) for item in self.activation_basis)):
            raise ValueError("Version metadata must use immutable typed tuples")
        if any(ref.space != Space.CANONICAL for ref in self.semantic_bindings):
            raise ValueError("Semantic bindings must name canonical versions")
        identities = [ref.identity for ref in self.semantic_bindings]
        if len(identities) != len(set(identities)):
            raise ValueError("A boundary cannot bind two versions of one identity")


@dataclass(frozen=True)
class Record:
    ref: Ref
    kind: str
    subject: str
    recorded_at: int
    payload_json: str
    owner: str
    scope: str = "learner-A"
    purpose: str = "learning"
    dependencies: tuple[Dependency, ...] = ()
    versions: VersionContext = field(default_factory=VersionContext)
    provenance: tuple[str, ...] = ()
    valid_until: int | None = None
    corrects: Ref | None = None
    occurrence_key: str | None = None

    @classmethod
    def create(cls, *, payload=None, **kwargs):
        # JSON text detaches nested caller-owned dictionaries/lists permanently.
        return cls(payload_json=json.dumps(payload if payload is not None else {},
                                          ensure_ascii=False, sort_keys=True,
                                          allow_nan=False), **kwargs)

    def __post_init__(self):
        json.loads(self.payload_json)
        if not self.owner or not self.kind or self.recorded_at < 0:
            raise ValueError("Record needs owner, kind and nonnegative clock time")
        if self.corrects is not None and self.ref.space != Space.FACT:
            raise ValueError("Corrections must be new factual records")
        if not isinstance(self.dependencies, tuple) or not isinstance(self.provenance, tuple):
            raise ValueError("Record metadata must be immutable tuples")
        if (any(not isinstance(d, Dependency) for d in self.dependencies)
                or any(not isinstance(p, str) for p in self.provenance)
                or not isinstance(self.versions, VersionContext)):
            raise ValueError("Record metadata has an invalid type")

    @property
    def payload(self):
        return json.loads(self.payload_json)


def json_value(value):
    """Detach dataclasses into a JSON-compatible evidence value."""
    return json.loads(json.dumps(asdict(value), ensure_ascii=False, allow_nan=False))
