"""Deterministic backend enforcement. Text and model fields never grant authority."""

from dataclasses import dataclass
import json
from uuid import uuid4

from .records import Record, Ref, Space, json_value
from .runtime import ContractError, Decision


@dataclass(frozen=True)
class AuthorityGrant:
    identity: str
    principal: str
    purpose: str
    subject: str
    resources: tuple[str, ...]
    operations: tuple[str, ...]
    expires_at: int
    # Parameter values are canonical JSON, so 1, true and "1" stay distinct.
    parameter_constraints: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class DataUseGrant:
    identity: str
    principal: str
    purpose: str
    subject: str
    data_types: tuple[str, ...]
    operations: tuple[str, ...]
    destinations: tuple[str, ...]
    retention: str
    disclosure: str
    expires_at: int


@dataclass(frozen=True)
class CredentialBinding:
    principal: str
    purpose: str
    subject: str
    expires_at: int


@dataclass(frozen=True)
class Operation:
    purpose: str
    subject: str
    resource: str
    operation: str
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DataUse:
    purpose: str
    subject: str
    data_type: str
    operation: str
    destination: str
    retention: str = "run"
    disclosure: str = "internal"


@dataclass(frozen=True)
class AccessDecision:
    decision: Decision
    reason: str
    principal: str | None
    authority_basis: tuple[str, ...] = ()


class AccessDenied(RuntimeError):
    def __init__(self, category, decision):
        self.category, self.decision = category, decision
        super().__init__(f"{category}: {decision.reason}")


def parameter(name, value):
    return name, json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


class SecurityRuntime:
    """Grant installation is a trusted fixture/admin operation, never a model tool."""

    def __init__(self, harness):
        self.h = harness
        self._authority = {}
        self._data = {}
        self._credentials = {}
        self._revocations = set()
        self.payload_reads = []

    def install_authority(self, grant: AuthorityGrant):
        if grant.identity in self._authority or grant.identity in self._data:
            raise ContractError("Grant identities are immutable and unique")
        if (not isinstance(grant.resources, tuple) or not isinstance(grant.operations, tuple)
                or not isinstance(grant.parameter_constraints, tuple)
                or any(not isinstance(v, tuple) for _, v in grant.parameter_constraints)):
            raise ContractError("Grant scope must be immutable")
        self._authority[grant.identity] = grant

    def install_data(self, grant: DataUseGrant):
        if grant.identity in self._authority or grant.identity in self._data:
            raise ContractError("Grant identities are immutable and unique")
        if any(not isinstance(v, tuple) for v in (grant.data_types, grant.operations, grant.destinations)):
            raise ContractError("Data grant scope must be immutable")
        self._data[grant.identity] = grant

    def issue_fixture_credential(self, binding: CredentialBinding):
        token = uuid4().hex
        self._credentials[token] = binding
        return token

    def revoke(self, identity: str, source: Ref):
        if identity not in self._authority and identity not in self._data and identity not in self._credentials:
            raise ContractError("Cannot revoke an unknown grant or credential")
        self._require_source(source)
        self._revocations.add(identity)
        # Never emit credential tokens into histories.
        self._audit("Revocation", source, {"target": "credential" if identity in self._credentials else identity})

    def _require_source(self, source):
        if source.space not in (Space.FACT, Space.EXECUTION) or self.h.get(source) is None:
            raise ContractError("Authorization attempts require an existing occurrence/execution source")

    def _binding(self, token, purpose, subject):
        binding = self._credentials.get(token)
        if binding is None:
            return AccessDecision(Decision.UNKNOWN, "UnknownCredential", None)
        if token in self._revocations or self.h.clock.now >= binding.expires_at:
            return AccessDecision(Decision.DENY, "CredentialRevokedOrExpired", binding.principal)
        if (binding.purpose, binding.subject) != (purpose, subject):
            return AccessDecision(Decision.DENY, "CredentialScopeMismatch", binding.principal)
        return AccessDecision(Decision.ALLOW, "CredentialBound", binding.principal)

    def authority(self, token, request: Operation):
        bound = self._binding(token, request.purpose, request.subject)
        if bound.decision != Decision.ALLOW:
            return bound
        considered = []
        for grant in self._authority.values():
            if grant.principal != bound.principal:
                continue
            considered.append(grant.identity)
            if grant.identity in self._revocations or self.h.clock.now >= grant.expires_at:
                continue
            if ((grant.purpose, grant.subject) != (request.purpose, request.subject)
                    or request.resource not in grant.resources or request.operation not in grant.operations):
                continue
            constraints = dict(grant.parameter_constraints)
            values = dict(request.parameters)
            # Missing required fields, extra fields and altered values all fail.
            if len(values) != len(request.parameters) or set(values) != set(constraints):
                continue
            if any(values[name] not in allowed for name, allowed in constraints.items()):
                continue
            return AccessDecision(Decision.ALLOW, "Granted", bound.principal, (grant.identity,))
        return AccessDecision(Decision.DENY, "NoMatchingAuthorityGrant", bound.principal, tuple(considered))

    def data_authority(self, token, use: DataUse):
        bound = self._binding(token, use.purpose, use.subject)
        if bound.decision != Decision.ALLOW:
            return bound
        considered = []
        for grant in self._data.values():
            if grant.principal != bound.principal:
                continue
            considered.append(grant.identity)
            if grant.identity in self._revocations or self.h.clock.now >= grant.expires_at:
                continue
            if ((grant.purpose, grant.subject, grant.retention, grant.disclosure)
                    == (use.purpose, use.subject, use.retention, use.disclosure)
                    and use.data_type in grant.data_types and use.operation in grant.operations
                    and use.destination in grant.destinations):
                return AccessDecision(Decision.ALLOW, "Granted", bound.principal, (grant.identity,))
        return AccessDecision(Decision.DENY, "NoMatchingDataUseGrant", bound.principal, tuple(considered))

    def _audit(self, kind, source, payload):
        record = Record.create(ref=Ref(Space.AUDIT, uuid4().hex, "1"), kind=kind,
                               subject=self.h.get(source).subject, owner="SecurityRuntime",
                               recorded_at=self.h.clock.now,
                               payload={"source": json_value(source), **payload},
                               provenance=("deterministic-backend",))
        self.h.audit.append(record)
        return record.ref

    def enforce(self, token, request, source, use=None):
        self._require_source(source)
        authority = self.authority(token, request)
        if authority.decision != Decision.ALLOW:
            self._audit("SecuritySignal", source, {"request": json_value(request), **json_value(authority)})
            raise AccessDenied("Unauthorized", authority)
        if use is not None:
            if (use.purpose, use.subject) != (request.purpose, request.subject):
                raise ContractError("Operation and data use must describe one boundary")
            data = self.data_authority(token, use)
            if data.decision != Decision.ALLOW:
                self._audit("SecuritySignal", source, {"request": json_value(request),
                                                       "data_use": json_value(use), **json_value(data)})
                raise AccessDenied("DataAuthorityDenied", data)
        else:
            data = None
        return authority, data

    def read(self, token, ref, purpose, destination, source, allowed_kinds=None):
        # Metadata comes from the backend record, never from a caller's claimed type/subject.
        record = self.h.get(ref)
        if record is None:
            raise ContractError("MissingExactReference")
        request = Operation(purpose, record.subject, ref.identity, "read")
        use = DataUse(purpose, record.subject, record.kind, "read", destination)
        decisions = self.enforce(token, request, source, use)
        if allowed_kinds is not None and record.kind not in allowed_kinds:
            raise ContractError("EpistemicallyInadmissible")
        self.payload_reads.append(ref)
        return record, decisions

    def describe_grants(self):
        return {"authority": [json_value(g) for g in self._authority.values()],
                "data": [json_value(g) for g in self._data.values()],
                "revoked_grants": sorted(g for g in self._revocations if g not in self._credentials)}
