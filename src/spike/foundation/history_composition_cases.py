"""X3/X4: factual assistance survives corrected interpretation; replay needs current permission."""
from copy import deepcopy
from dataclasses import replace

from .action_cases import ActionWorld
from .actions import exact_ref
from .boundary import ContextInput
from .cases import seed
from .records import Ref, Role, Space, json_value
from .replay import ArtifactStore, ReplayRuntime
from .runtime import CurrentResolver
from .security import AuthorityGrant, CredentialBinding
from .version_replay_cases import VersionReplayWorld


class CorrectionWorld(ActionWorld):
    def revision(self, kind, identity, payload, inputs):
        self.h.clock.advance()
        self.allow_reads()
        p=self.protocols[kind];token=self.tokens[p.owner.lower()]
        context=self.runtime.assemble(token,p.ref,'learner-A','learner-A','learning',
            tuple(ContextInput(r,Role.CANONICAL if r.space==Space.CANONICAL else
                               Role.FACTUAL if r.space==Space.FACT else Role.EPISTEMIC) for r in inputs),self.versions[kind])
        old=self.h.states.candidate(identity,'learner-A','learning',self.h.clock.now)
        c=self.runtime.propose(context,identity,'r2',payload,expected_head=old.ref)
        review=self.runtime.record_semantic_validation(token,c,'PASS','Explicit X3 fixture interpretation.',
            'SCRIPTED-X3',fixture=True)
        self.e.emit('X3_revision_prepared',context=json_value(context),candidate=json_value(c),review=json_value(review))
        return token,c,review


def x3(e):
    w=CorrectionWorld(e)
    w.prepare_action()
    result=w.execute('OCCUR_FULL')
    occurrence=exact_ref(result['occurrence_ref'])
    response=w.response('X3-after')
    old_o=w.commit_scripted('Observation','X3-O',{'description':'The later work writes quotient 7 and total 105.'},(response,))
    claim=seed(w.h,Ref(Space.CANONICAL,'X3-C1','v1'),kind='Claim',payload={'meaning':'Independent task proficiency'})
    ep={'description':'Post-hint performance is retained as assisted evidence for this claim.',
        'claim_ref':json_value(claim),'independence':'NOT_INDEPENDENT','impact':'POST_HINT_LOCAL_PERFORMANCE'}
    old_e=w.commit_scripted('Evidence','X3-E',ep,(old_o,occurrence,claim))
    old_b=w.commit_scripted('LearnerBelief','X3-B',{'description':'Fixture belief based on the post-hint evidence.'},(old_e,))
    historical=tuple(w.h.get(r) for r in (w.intent,w.result_ref,occurrence,exact_ref(w.h.get(occurrence).payload['acknowledgement_ref'])))
    original_states=w.h.states.records()
    before=w.exposure(response)
    e.emit('X3_lineage',observation=json_value(old_o),evidence=json_value(old_e),belief=json_value(old_b),
           occurrence=json_value(occurrence),response=json_value(response))
    w.stage('X3 before correction',{'X3-O':old_o,'X3-E':old_e,'X3-B':old_b})
    # Prepare against the old basis first; a later correction cannot silently rebase it.
    stale=w.revision('Evidence','X3-E',ep,(old_o,occurrence,claim))
    source=seed(w.h,Ref(Space.FACT,'X3-owner-input','1'),kind='ExternalOwnerInput',
        payload={'owner':'Interaction','source':'TRUSTED-REINTERPRETATION-FIXTURE'})
    correction=seed(w.h,Ref(Space.FACT,'X3-correction','1'),kind='CorrectionOccurred',corrects=old_o,
        payload={'source':json_value(source),'reason':'Owner withdraws the old annotation to add precise visible step detail.'})
    e.emit('X3_correction',record=json_value(w.h.get(correction)))
    w.stage('X3 corrected before recomputation',{'X3-O':None,'X3-E':None,'X3-B':None})
    stale_out=w.runtime.commit(stale[0],stale[1],stale[2].identity)
    e.emit('X3_stale_commit',outcome=json_value(stale_out))
    e.check('old-basis evidence candidate rejected',stale_out.status,'CandidateStale')
    e.check('old-basis rejection is correction',stale_out.reason,'Corrected')
    new_o=w.finish(w.revision('Observation','X3-O',
        {'description':'The later work explicitly writes 42 / 6 = 7 followed by 7 * 15 = 105.'},(response,)))
    w.stage('X3 only Observation restored',{'X3-O':new_o,'X3-E':None,'X3-B':None})
    new_e=w.finish(w.revision('Evidence','X3-E',{**ep,'description':'Reinterpreted visible steps remain linked to the same pre-response hint.'},
        (new_o,occurrence,claim)))
    w.stage('X3 Evidence restored',{'X3-O':new_o,'X3-E':new_e,'X3-B':None})
    new_b=w.finish(w.revision('LearnerBelief','X3-B',
        {'description':'Updated fixture interpretation preserves the same historical assistance basis.'},(new_e,)))
    w.stage('X3 chain restored',{'X3-O':new_o,'X3-E':new_e,'X3-B':new_b})
    for ref in (old_o,old_e,old_b):
        resolved=CurrentResolver(w.h.capture(),w.runtime._eligibility(w.tokens['evaluation'],'reasoning-runtime')).resolve_exact(ref,'learner-A','learning')
        e.emit('X3_old_exact_resolution',result=json_value(resolved))
        e.check('old exact '+ref.identity+' does not regain current eligibility',resolved.reason,'Corrected')
    after=w.exposure(response)
    e.check('actual exposure unchanged by interpretation correction',after,before)
    e.check('hint actually preceded the same response',after['exposures'][0]['before_response'],True)
    e.check('all original effect history immutable',all(w.h.get(r.ref)==r for r in historical),True)
    e.check('new evidence retains exact original occurrence',occurrence in {d.target for d in w.h.get(new_e).dependencies},True)
    e.check('new belief binds new evidence only',[json_value(d.target) for d in w.h.get(new_b).dependencies if d.target.space==Space.DERIVED],[json_value(new_e)])
    w.allow_reads()
    terminal=w.actions.execute(w.tokens['interaction'],w.intent)
    e.check('completed intent returns original terminal',json_value(terminal),json_value(w.result_ref))
    e.check('no duplicated disclosure',sum(r.kind=='ActionOccurrence' for r in w.h.facts.records()),1)
    e.check('no durable exposure model',any(r.kind=='AssistanceExposureModel' for r in w.h.states.records()),False)
    w.preserve(original_states)
    return {'coverage':'COMPLETE','old_chain':[json_value(r) for r in (old_o,old_e,old_b)],
            'new_chain':[json_value(r) for r in (new_o,new_e,new_b)],'occurrence':json_value(occurrence)}


class TrackedArtifacts(ArtifactStore):
    def __init__(self):
        super().__init__();self.loads=[]

    def load(self,record):
        self.loads.append(json_value(record.ref))
        return super().load(record)


class ReplayAuthorityWorld(VersionReplayWorld):
    def __init__(self,e):
        super().__init__(e)
        tracked=TrackedArtifacts()
        tracked._values=dict(self.artifacts._values)
        self.artifacts=tracked;self.replay.artifacts=tracked
        self.model_inputs=[]
        self.models['fixture-model:r1']=self.provider
        self.models['fixture-model:r2']=self.provider
        self.output,self.root=self.reinterpret((self.work,),self.old_protocol.ref,'r1')

    def provider(self,raw,records):
        self.calls+=1
        self.model_inputs.append({'raw_refs':sorted(raw),'record_refs':{k:v['ref'] for k,v in records.items()}})
        return {'description':'Explicitly new X4 fixture provider output, not historical standing.'}

    def branch(self,e):return deepcopy(self,{id(self.e):e})

    def replay_pair(self,label,*,token=None,replay=None,expected='FULL',zero_reads=False):
        token=token or self.tokens['interaction'];replay=replay or self.replay
        for operation in ('historical_reconstruct','reexecute'):
            reads=len(self.security.payload_reads);loads=len(self.artifacts.loads);calls=self.calls
            result=(replay.historical_reconstruct(token,self.root) if operation=='historical_reconstruct'
                    else replay.reexecute(token,self.root,'fixture-model:r1'))
            self.e.emit('X4_operation',label=label,operation=operation,result=result,
                payload_reads=[json_value(r) for r in self.security.payload_reads[reads:]],
                artifact_loads=self.artifacts.loads[loads:],provider_inputs=self.model_inputs[calls:])
            self.e.check(label+': '+operation+' capability',result['capability'],expected)
            if expected=='UNAVAILABLE':
                self.e.check(label+': explicit data denial',result['reasons'],['DataAuthorityDenied'])
                self.e.check(label+': no returned historical view',result['historical_view'],None)
                self.e.check(label+': no generated output',result['generated_output'],None)
                self.e.check(label+': no provider context',self.calls,calls)
                self.e.check(label+': no raw bytes loaded',len(self.artifacts.loads),loads)
                if zero_reads:self.e.check(label+': denied before any payload read',len(self.security.payload_reads),reads)
            elif operation=='reexecute':
                self.e.check(label+': provider invoked exactly once',self.calls,calls+1)
                self.e.check(label+': new output is not historical view',result['historical_view'],None)
            else:
                self.e.check(label+': exact historical output',result['historical_view']['historical_output'],self.h.get(self.output).payload_json)
                self.e.check(label+': historical reconstruction does not invoke provider',self.calls,calls)


def x4(e):
    base=ReplayAuthorityWorld(e)
    e.capture(base.h,'X4 shared baseline')
    for branch in ('replay-data-revoked','raw-data-denied','purpose-data-denied'):
        w=base.branch(e)
        e.emit('X4_branch',branch=branch,root=json_value(w.root))
        e.capture(w.h,'X4 initial '+branch)
        originals=tuple(r for space in Space for r in w.h.history_for(space).records())
        raw=dict(w.artifacts._values)
        w.replay_pair(branch+' positive')
        token=w.tokens['interaction'];replay=w.replay
        if branch=='replay-data-revoked':
            grant=w.security._data['C-replay-data-'+w.root.identity]
            w.security.revoke(grant.identity,w.root)
        elif branch=='raw-data-denied':
            grant=w.security._data['C-read-data-'+w.root.identity]
            w.security.revoke(grant.identity,w.root)
            w.security.install_data(replace(grant,identity='X4-read-except-raw',
                data_types=tuple(k for k in grant.data_types if k!='GroundingArtifact')))
        else:
            refs=[w.root.identity]+[r['identity'] for r in w.h.get(w.root).payload['records'].values()]
            token=w.security.issue_fixture_credential(CredentialBinding('interaction','research','learner-A',100000))
            w.security.install_authority(AuthorityGrant('X4-research-operation','interaction','research','learner-A',
                tuple(refs),('read','historical_reconstruct','reexecute'),100000))
            replay=ReplayRuntime(w.runtime,w.artifacts,w.models,purpose='research')
        e.emit('X4_current_grants',branch=branch,grants=w.security.describe_grants())
        signal_start=len(w.h.audit.records())
        w.replay_pair(branch+' denied',token=token,replay=replay,expected='UNAVAILABLE',zero_reads=branch!='raw-data-denied')
        signals=[r for r in w.h.audit.records()[signal_start:] if r.kind=='SecuritySignal']
        e.check(branch+': two source-linked denials',len(signals),2)
        for signal in signals:
            source=w.h.get(exact_ref(signal.payload['source']))
            e.check(branch+': denied source is this replay request',source.kind,'ReplayRequested')
            e.check(branch+': source exact historical root',source.payload['root'],json_value(w.root))
            e.check(branch+': actual data denial reason',signal.payload['reason'],'NoMatchingDataUseGrant')
        e.check(branch+': original raw bytes retained',w.artifacts._values==raw,True)
        e.check(branch+': all original records retained',all(w.h.get(r.ref)==r for r in originals),True)
        e.check(branch+': no new formal state',len(w.h.states.records()),1)
        if branch=='replay-data-revoked':
            w.security.install_data(replace(grant,identity='X4-restored-data-grant'))
            w.replay_pair(branch+' restored')
        e.capture(w.h,'X4 final '+branch)
    e.check('X4 branch provider calls do not mutate baseline',base.calls,0)
    e.check('X4 baseline raw store unread',base.artifacts.loads,[])
    return {'coverage':'COMPLETE','branches':3,'denied_operations':6,'external_model_calls':0}


CASES={'X3':x3,'X4':x4}
