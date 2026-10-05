"""A1: active shared semantics, structurally excluded history, real cognition."""
import json
from .boundary import BoundaryRuntime, ContextInput, Protocol
from .cases import seed
from .llm import ModelFailure
from .records import Ref, Role, Space, json_value
from .runtime import Activation, Compatibility, ContractError, Decision, Harness
from .security import AccessDenied, AuthorityGrant, CredentialBinding, DataUseGrant, SecurityRuntime, parameter


class FormationWorld:
    def __init__(self,definition,variant):
        self.h=Harness();self.security=SecurityRuntime(self.h);self.runtime=BoundaryRuntime(self.h,self.security)
        self.definition=definition
        self.protocol=seed(self.h,Ref(Space.CANONICAL,definition['identity'],definition['version']),kind='ReasoningProtocol',payload=definition)
        self.rule=seed(self.h,Ref(Space.CANONICAL,'A1ValidationRules','v1'),kind='SemanticValidationRules',payload={
            'system':definition['validation_system'],'format':definition['validation_format'],'criteria':definition['criteria']})
        self.semantics=seed(self.h,Ref(Space.CANONICAL,'ObservationSemantics','v1'),kind='ObservationSemantics',payload=definition['semantics_v1'])
        self.work=seed(self.h,Ref(Space.FACT,'A1-work','1'),kind='LearnerWorkSubmitted',occurrence_key='A1-work',payload={
            'task':'6kg apples cost 42 yuan. What do 15kg cost?','text':variant['text']})
        self.forbidden=tuple(seed(self.h,Ref(Space.DERIVED,name,'r1'),kind=kind,payload={'excluded_history_marker':marker})
            for name,kind,marker in [('B-old','LearnerBelief','BELIEF_PRIVATE_FIXTURE_617'),
                ('A-old','TargetAssessment','ASSESSMENT_PRIVATE_FIXTURE_731'),('P-old','PolicyOutcome','POLICY_PRIVATE_FIXTURE_829')])
        records=[r for space in Space for r in self.h.history_for(space).records()]
        self.security.install_authority(AuthorityGrant('A1-read','interaction','learning','learner-A',tuple(r.ref.identity for r in records),('read',),10000))
        self.security.install_authority(AuthorityGrant('A1-reason','interaction','learning','learner-A',(self.protocol.identity,),('reason','validate'),10000))
        self.security.install_authority(AuthorityGrant('A1-commit','interaction','learning','learner-A',('O',),('commit',),10000,
            tuple((k,(parameter(k,v)[1],)) for k,v in {'owner':'Interaction','kind':'Observation'}.items())))
        self.security.install_data(DataUseGrant('A1-read-data','interaction','learning','learner-A',tuple({r.kind for r in records}),('read',),
            (definition['provider_endpoint'],),'run','internal',10000))
        self.security.install_data(DataUseGrant('A1-validate-data','interaction','learning','learner-A',('Observation',),('validate',),
            (definition['provider_endpoint'],),'run','internal',10000))
        self.security.install_data(DataUseGrant('A1-commit-data','interaction','learning','learner-A',('Observation',),('commit',),('formal-state',),'run','internal',10000))
        self.token=self.security.issue_fixture_credential(CredentialBinding('interaction','learning','learner-A',10000))
        self.runtime.register_protocol(Protocol(self.protocol,'Observation','Interaction',('LearnerWorkSubmitted','ObservationSemantics'),
            (('description','string'),),self.rule,definition['provider_endpoint']))
        bindings=(self.protocol,self.rule,self.semantics)
        self.h.canonical.add_compatibility_fixture(Compatibility('A1-compatible',bindings,'learner-A','learning',Decision.ALLOW))
        for ref in bindings:self.h.canonical.activate_fixture(Activation('A1-active-'+ref.identity,ref,'learner-A','learning',self.h.clock.advance()))
        self.versions=self.h.canonical.bind_active(tuple(r.identity for r in bindings),'learner-A','learning',self.h.clock.now,'A1-compatible')
        self.inputs=(ContextInput(self.work,Role.FACTUAL),ContextInput(self.semantics,Role.CANONICAL))+tuple(
            ContextInput(ref,Role.EPISTEMIC,required=False) for ref in self.forbidden)
        self.context=self.runtime.assemble(self.token,self.protocol,'learner-A','learner-A','learning',self.inputs,self.versions)

    def check_exclusion(self,e):
        e.check('allowed Context kinds only',[i.record.kind for i in self.context.items],['LearnerWorkSubmitted','ObservationSemantics'])
        e.check('all prohibited inputs structurally excluded',set(ref for ref,_ in self.context.excluded)==set(self.forbidden),True)
        e.check('prohibited inputs absent from exact dependencies',not set(self.forbidden).intersection(d.target for d in self.context.dependencies),True)
        e.check('same semantics and protocol active',len(self.context.versions.activation_basis),3)
        # Prove the prohibition is not just a cooperative optional read request.
        for ref in self.forbidden:
            try:
                self.runtime.assemble(self.token,self.protocol,'learner-A','learner-A','learning',
                    (ContextInput(ref,Role.EPISTEMIC),),self.versions)
            except (ContractError,AccessDenied):e.check('required forbidden read rejected:'+ref.identity,True,True)
            else:e.check('required forbidden read rejected:'+ref.identity,False,True)


def run_case(e,definition,variant,repetition,adapter):
    w=FormationWorld(definition,variant);start=len(adapter.records)
    row={'variant':variant['id'],'repetition':repetition,'result':'NON_SUCCESS','commit_status':None,'semantic_status':None}
    w.check_exclusion(e)
    e.emit('A1_context',context=json_value(w.context),grants=w.security.describe_grants(),expected=variant['expected'])
    e.capture(w.h,'initial')
    try:
        candidate=w.runtime.generate_with_llm(w.token,w.context,adapter,identity='O')
        e.emit('A1_candidate',candidate=json_value(candidate))
        row['candidate']=candidate.record.payload
        review=w.runtime.validate_with_llm(w.token,candidate,adapter)
        e.emit('A1_review',review=json_value(review))
        row['semantic_status']=review.status
        outcome=w.runtime.commit(w.token,candidate,review.identity)
        e.emit('A1_commit',outcome=json_value(outcome))
        row.update(commit_status=outcome.status,commit_reason=outcome.reason,
            criterion_statuses={c['id']:c['status'] for c in json.loads(review.details_json).get('criteria',[])})
        e.check('standing agrees with required review',w.h.get(candidate.record.ref) is not None,review.status=='PASS')
        if outcome.status=='Committed':row['result']='PASS'
    except (ModelFailure,ContractError,AccessDenied) as exc:row.update(failure_type=type(exc).__name__,reason=str(exc))
    finally:
        calls=adapter.records[start:]
        # Exact synthetic marker checks audit byte leakage, not language meaning.
        wire=json.dumps([c['messages'] for c in calls],ensure_ascii=False)
        for ref in w.forbidden:
            e.check('forbidden history bytes absent from all provider messages:'+ref.identity,
                    w.h.get(ref).payload['excluded_history_marker'] in wire,False)
        for call in calls:e.emit('model_execution',**call)
        e.capture(w.h,'final')
        row.update(model_calls=len(calls),checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']])
        if row['failed_checks']:row['result']='FAIL'
        e.emit('case_result',**row)
    return row
