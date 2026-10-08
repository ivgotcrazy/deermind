"""Opt-in fixed-activity entry restrictions; no natural-language classification."""
from dataclasses import dataclass
from .records import Ref, Space, json_value
from .runtime import ContractError
from .session import SerialSession


@dataclass(frozen=True)
class WorkingScope:
    identity: str
    revision: str
    subject: str
    scope: str
    purpose: str
    protocols: tuple[Ref, ...]
    constraints: Ref
    actions: tuple[Ref, ...]


class RestrictedEntry:
    def __init__(self, boundary, profile):
        if boundary.working_entry is not None:
            raise ContractError('WorkingScopeAlreadyRegistered')
        if (not isinstance(profile, WorkingScope)
                or any(not isinstance(v, str) or not v for v in
                       (profile.identity, profile.revision, profile.subject, profile.scope, profile.purpose))
                or type(profile.protocols) is not tuple or not profile.protocols
                or type(profile.actions) is not tuple or not profile.actions
                or len(set(profile.protocols)) != len(profile.protocols)
                or len(set(profile.actions)) != len(profile.actions)):
            raise ContractError('InvalidWorkingScope')
        for ref in profile.protocols:
            protocol = boundary._protocols.get(ref)
            if protocol is None or protocol.candidate_kind not in ('Observation', 'PolicyOutcome'):
                raise ContractError('WorkingProtocolNotRegistered')
            if (protocol.candidate_kind == 'PolicyOutcome'
                    and boundary.h.get(ref).payload.get('legality_profile') != 'policy-admission-v1'):
                raise ContractError('WorkingPolicyAdmissionRequired')
        envelope = boundary.h.get(profile.constraints)
        if (profile.constraints.space != Space.CANONICAL or envelope is None
                or envelope.kind != 'ActivityConstraints'
                or (envelope.subject, envelope.scope, envelope.purpose) !=
                   (profile.subject, profile.scope, profile.purpose)
                or not envelope.payload.get('episode')
                or not envelope.payload.get('allowed_action_refs')
                or any(value not in [json_value(r) for r in profile.actions]
                       for value in envelope.payload['allowed_action_refs'])):
            raise ContractError('WorkingActivityEnvelopeMismatch')
        for ref in profile.actions:
            action = boundary.h.get(ref)
            if (ref.space != Space.CANONICAL or action is None or action.kind != 'ActionSemantic'
                    or action.payload.get('executor_target') != 'mock-display'
                    or 'activity_transition' in action.payload
                    or not isinstance(action.payload.get('exact_payload'), str)
                    or not action.payload['exact_payload']):
                raise ContractError('WorkingLocalActionRequired')
        self.boundary, self.profile = boundary, profile
        self.session = boundary.session or SerialSession(boundary)
        boundary.working_entry = self
        self.registration = boundary.execution('WorkingScopeRegistered', profile.subject,
                                              json_value(profile))

    def check_context(self, context):
        b, p = self.boundary, self.profile
        protocol = b._protocols.get(context.protocol)
        # Scope governs the interaction entry, not independent Evaluation owners.
        if protocol is not None and protocol.candidate_kind not in ('Observation', 'PolicyOutcome'):
            return
        if b.session is not self.session:
            raise ContractError('WorkingSerialSessionRequired')
        if b._contexts.get(context.identity) != context:
            raise ContractError('RegisteredContextRequired')
        if (context.subject, context.scope, context.purpose) != (p.subject, p.scope, p.purpose):
            raise ContractError('WorkingContextScopeMismatch')
        if context.protocol not in p.protocols:
            raise ContractError('WorkingProtocolOutsideScope')
        turn = self.session.context_turn(context)
        if turn is None:
            raise ContractError('WorkingTurnBindingRequired')
        self.session.check_open(turn)
        for item in context.items:
            if item.record.kind == 'ActivityTransitionOccurred':
                raise ContractError('WorkingTransitionOutsideScope')
        if b._protocols[context.protocol].candidate_kind == 'PolicyOutcome':
            envelopes = [i for i in context.items if i.record.kind == 'ActivityConstraints']
            if (len(envelopes) != 1 or envelopes[0].record.ref != p.constraints
                    or envelopes[0].content != b.h.get(p.constraints).payload):
                raise ContractError('WorkingActivityEnvelopeMismatch')

    def check_candidate(self, candidate):
        self.check_context(self.boundary._contexts[candidate.context_id])
        if candidate.record.kind == 'PolicyOutcome' and candidate.record.payload.get('outcome') == 'Execute':
            payload = candidate.record.payload
            if (payload.get('executor_target') != 'mock-display'
                    or not any((payload.get('action_identity'), payload.get('action_revision')) ==
                               (r.identity, r.revision) for r in self.profile.actions)):
                raise ContractError('WorkingActionOutsideScope')

    def check_policy(self, policy_ref):
        b = self.boundary
        from .boundary import digest
        record = b.h.get(policy_ref)
        candidate = next((c for c in b._candidates.values() if c.record.ref == policy_ref
                          and record is not None
                          and 'candidate-sha256:' + digest(c) in record.provenance), None)
        if candidate is None:
            raise ContractError('WorkingRegisteredPolicyRequired')
        self.check_context(b._contexts[candidate.context_id])

    def check_action(self, payload):
        p = self.profile
        if (payload.get('subject'), payload.get('scope'), payload.get('purpose')) != (p.subject, p.scope, p.purpose):
            raise ContractError('WorkingActionScopeMismatch')
        if (payload.get('executor_target') != 'mock-display'
                or payload.get('action_semantic_ref') not in [json_value(r) for r in p.actions]):
            raise ContractError('WorkingActionOutsideScope')
        from .actions import exact_ref
        self.check_policy(exact_ref(payload['policy_ref']))
