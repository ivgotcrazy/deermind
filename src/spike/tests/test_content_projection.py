"""Declared-use wire boundaries with explicit local semantic fixtures."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from foundation.boundary import BoundaryRuntime,ContextInput,ContextItem,Protocol
from foundation.policy import policy_legality
from types import SimpleNamespace
from foundation.cases import EvidenceRecorder,seed,correct
from foundation.content_projection import fingerprint
from foundation.llm import DeepSeekAdapter,LLMConfig
from foundation.records import Ref,Space,Role,VersionContext,json_value
from foundation.runtime import Harness,Compatibility,Decision,ContractError
from foundation.security import SecurityRuntime,CredentialBinding,AuthorityGrant,DataUseGrant,AccessDenied,parameter
from foundation.source_handles import source_registry

URL='https://api.deepseek.com'
MARKER='AUDIT_ONLY_FORBIDDEN_WIRE_68129'


class World:
    def __init__(self):
        self.h=Harness();self.s=SecurityRuntime(self.h);self.r=BoundaryRuntime(self.h,self.s)
        self.tokens={p:self.s.issue_fixture_credential(CredentialBinding(p,'learning','learner-A',100000)) for p in ('interaction','evaluation')}
        self.read_grants=[]
        self.work=seed(self.h,Ref(Space.FACT,'work','1'),kind='LearnerWorkSubmitted',payload={'text':'42÷6=?','audit_note':MARKER})
        self.producer=self.protocol('Producer','Observation',('LearnerWorkSubmitted',),(('description','string'),('audit_note','string')),
            {'output_field_uses':{'description':['observation'],'audit_note':['audit']}})
        self.source_contract=seed(self.h,Ref(Space.CANONICAL,'WorkUse','v1'),kind='ContentUseContract',payload={
            'record_space':'fact','record_kind':'LearnerWorkSubmitted','field_uses':{'text':['raw-material'],'audit_note':['audit']}})
        self.producer_versions=self.versions(self.producer)
        self.allow()
        self.ctx=self.r.assemble(self.tokens['interaction'],self.producer.ref,'learner-A','learner-A','learning',
            (ContextInput(self.work,Role.FACTUAL),),self.producer_versions)

    def protocol(self,name,kind,inputs,fields,extra):
        ref=seed(self.h,Ref(Space.CANONICAL,name,'v1'),kind='ReasoningProtocol',payload={
            'generation_system':'Explicit local fixture generation.', 'validation_system':'Explicit local fixture review.',**extra})
        rule=seed(self.h,Ref(Space.CANONICAL,name+'-rules','v1'),kind='SemanticValidationRules',payload={
            'format':extra.get('validation_format','legacy-v1'),'system':'Fixture','criteria':extra.get('criteria',[])})
        protocol=Protocol(ref,kind,'Evaluation' if kind=='Evidence' else 'Interaction',inputs,fields,rule,URL)
        self.r.register_protocol(protocol)
        return protocol

    def versions(self,protocol,*refs):
        bindings=(protocol.ref,protocol.semantic_rule,*refs);identity=uuid4().hex
        self.h.canonical.add_compatibility_fixture(Compatibility(identity,bindings,'learner-A','learning',Decision.ALLOW))
        return VersionContext(bindings,compatibility_basis=identity)

    def allow(self):
        records=[r for space in Space for r in self.h.history_for(space).records()]
        for p,kind,owner in (('interaction','Observation','Interaction'),('evaluation','Evidence','Evaluation')):
            tag=uuid4().hex
            self.s.install_authority(AuthorityGrant('read-'+tag,p,'learning','learner-A',tuple({r.ref.identity for r in records}),('read','reason','validate'),100000))
            self.s.install_authority(AuthorityGrant('commit-'+tag,p,'learning','learner-A',('O','E'),('commit',),100000,
                tuple((k,(parameter(k,v)[1],)) for k,v in {'owner':owner,'kind':kind}.items())))
            grant='data-'+tag;self.read_grants.append(grant)
            self.s.install_data(DataUseGrant(grant,p,'learning','learner-A',tuple({r.kind for r in records})+(kind,),
                ('read','validate','commit'),(URL,'formal-state'),'run','internal',100000))

    def observation(self,status='PASS',description='学习者写了42÷6=?，商尚未给出。'):
        candidate=self.r.propose(self.ctx,'O','r1',{'description':description,'audit_note':MARKER})
        review=self.r.record_semantic_validation(self.tokens['interaction'],candidate,status,'LOCAL fixture','LOCAL',fixture=True)
        outcome=self.r.commit(self.tokens['interaction'],candidate,review.identity)
        self.candidate,self.review=candidate,review
        self.allow()
        return outcome

    def consumer(self,*,fields=None,use='observation',mode='formal',kind='Observation',contract=None,version_bound=True):
        contract=contract or self.producer.ref
        profile={'format':'declared-fields-v1','inputs':[{'kind':kind,'mode':mode,'contract':json_value(contract),
            'fields':fields or ['description'],'use':use}]}
        self.consumer_protocol=self.protocol('Consumer-'+uuid4().hex,'Evidence',(kind,),(('description','string'),),{'context_projection':profile})
        self.consumer_versions=self.versions(self.consumer_protocol,*((contract,) if version_bound else ()))
        self.allow()
        return self.consumer_protocol

    def assemble(self,ref=None,**kwargs):
        return self.r.assemble(self.tokens['evaluation'],self.consumer_protocol.ref,'learner-A','learner-A','learning',
            (ContextInput(ref or self.candidate.record.ref,Role.EPISTEMIC,**kwargs),),self.consumer_versions)


class ContentProjectionTests(unittest.TestCase):
    artifact_directory=None

    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        path=Path(self.artifact_directory or directory.name);path.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(path/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.worlds=[];self.adapters=[];self.addCleanup(self.capture)

    def capture(self):
        for a in self.adapters:
            for row in a.records:self.e.emit('scripted_model_execution',**row)
        for n,w in enumerate(self.worlds):self.e.capture(w.h,'final:'+str(n))

    def world(self):
        w=World();self.worlds.append(w);return w

    def adapter(self):
        def transport(url,key,wire,timeout):
            # Negative byte assertion concerns this fixed synthetic marker, not text meaning.
            self.assertNotIn(MARKER,json.dumps(wire,ensure_ascii=False))
            value={'status':'PASS','rationale':'LOCAL semantic fixture'} if isinstance(json.loads(wire['messages'][1]['content']),dict) else {'description':'LOCAL evidence fixture'}
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
        a=DeepSeekAdapter(LLMConfig('LOCAL-ONLY',max_calls=3),transport);self.adapters.append(a);return a

    def test_actual_generation_validation_and_manifest_use_projected_fields(self):
        w=self.world();self.assertEqual(w.observation().status,'Committed');w.consumer();ctx=w.assemble()
        llm=self.adapter();candidate=w.r.generate_with_llm(w.tokens['evaluation'],ctx,llm,identity='E')
        review=w.r.validate_with_llm(w.tokens['evaluation'],candidate,llm)
        self.assertEqual(w.r.commit(w.tokens['evaluation'],candidate,review.identity).status,'Committed')
        for call in llm.records:self.assertNotIn(MARKER,json.dumps(call['messages'],ensure_ascii=False))
        content=json.loads(llm.records[0]['messages'][1]['content'])[0]
        self.assertEqual(set(content['content']),{'description'});self.assertEqual(content['content_use'],'observation')
        manifest=next(r for r in w.h.executions.records() if r.kind=='ContextManifest' and r.payload['context_id']==ctx.identity)
        projection=manifest.payload['included'][0]['projection']
        self.assertEqual(projection['projected_payload_sha256'],fingerprint(content['content']))
        self.assertEqual(projection['source_payload_sha256'],fingerprint(w.h.get(w.candidate.record.ref).payload))
        self.assertEqual(projection['formal_proof']['validation_ref'],json_value(w.review.execution))
        self.assertIn(MARKER,w.h.get(w.candidate.record.ref).payload['audit_note'])

    def test_audit_field_cannot_be_promoted_by_consumer_field_request(self):
        w=self.world();w.observation();w.consumer(fields=['description','audit_note'])
        with self.assertRaisesRegex(ContractError,'FieldUseNotAdmitted'):w.assemble()

    def test_optional_rejection_records_exclusion_without_field_fallback(self):
        w=self.world();w.observation();w.consumer(fields=['audit_note'])
        ctx=w.assemble(required=False)
        self.assertEqual(ctx.items,());self.assertEqual(ctx.excluded[0][1],'FieldUseNotAdmitted')

    def test_failed_unresolved_and_unsubmitted_candidates_have_no_formal_input(self):
        for status in ('FAIL','UNRESOLVED'):
            w=self.world();self.assertEqual(w.observation(status).status,'ValidationFailed');w.consumer()
            with self.assertRaises((ContractError,AccessDenied)):w.assemble()
        w=self.world();w.consumer();ref=Ref(Space.DERIVED,'not-committed','r1')
        with self.assertRaises((ContractError,AccessDenied)):w.assemble(ref)

    def test_seeded_derived_label_without_real_commit_proof_is_rejected(self):
        w=self.world();fake=seed(w.h,Ref(Space.DERIVED,'fake','r1'),kind='Observation',payload={'description':'Typed label only.'})
        w.consumer()
        with self.assertRaisesRegex(ContractError,'CommitProofMissing'):w.assemble(fake)

    def test_missing_validation_proof_blocks_formally_committed_source(self):
        w=self.world();w.observation();w.consumer();w.r._reviews.pop(w.review.identity)
        with self.assertRaisesRegex(ContractError,'CommitProofMissing'):w.assemble()

    def test_source_fact_has_separate_contract_and_no_formal_proof(self):
        w=self.world();w.consumer(kind='LearnerWorkSubmitted',mode='source',contract=w.source_contract,fields=['text'],use='raw-material')
        ctx=w.assemble(w.work)
        self.assertEqual(ctx.items[0].content,{'text':'42÷6=?'})
        self.assertIsNone(json.loads(ctx.items[0].projection_json)['formal_proof'])
        llm=self.adapter();w.r.generate_with_llm(w.tokens['evaluation'],ctx,llm,identity='E')

    def test_derived_record_cannot_fall_back_to_source_material_contract(self):
        w=self.world();w.observation();w.consumer(mode='source',contract=w.source_contract)
        with self.assertRaisesRegex(ContractError,'SourceContractMismatch'):w.assemble()

    def test_contract_version_must_be_explicitly_bound(self):
        w=self.world();w.observation();w.consumer(version_bound=False)
        with self.assertRaisesRegex(ContractError,'NotVersionBound'):w.assemble()

    def test_correction_refuses_current_but_preserves_explicit_historical_reference(self):
        w=self.world();w.observation();w.consumer();correct(w.h,w.candidate.record.ref);w.allow()
        with self.assertRaises(ContractError):w.assemble()
        ctx=w.assemble(current=False)
        self.assertEqual(ctx.dependencies[0].mode.value,'PINNED')
        self.assertEqual(ctx.items[0].content['description'],w.candidate.record.payload['description'])

    def test_revocation_before_model_send_rechecks_data_authority(self):
        w=self.world();w.observation();w.consumer();ctx=w.assemble()
        for grant in w.read_grants:w.s.revoke(grant,w.candidate.execution)
        llm=self.adapter()
        with self.assertRaises(AccessDenied):w.r.generate_with_llm(w.tokens['evaluation'],ctx,llm,identity='E')
        self.assertEqual(llm.calls,0)

    def test_changed_context_projection_cannot_register_or_send(self):
        w=self.world();w.observation();w.consumer();ctx=w.assemble()
        item=replace(ctx.items[0],content_json=json.dumps(w.candidate.record.payload))
        altered=replace(ctx,items=(item,));llm=self.adapter()
        with self.assertRaisesRegex(ContractError,'UnregisteredContext'):w.r.generate_with_llm(w.tokens['evaluation'],altered,llm,identity='E')
        self.assertEqual(llm.calls,0)

    def test_source_registry_cannot_cite_dropped_audit_field(self):
        w=self.world();w.observation();w.consumer();ctx=w.assemble()
        registry=source_registry([i.model_value() for i in ctx.items])
        self.assertEqual([r['field'] for r in registry],['description'])
        self.assertNotIn(MARKER,json.dumps(registry,ensure_ascii=False))

    def test_commit_rechecks_producer_validation_instead_of_trusting_frozen_projection(self):
        w=self.world();w.observation();w.consumer();ctx=w.assemble();llm=self.adapter()
        c=w.r.generate_with_llm(w.tokens['evaluation'],ctx,llm,identity='E');review=w.r.validate_with_llm(w.tokens['evaluation'],c,llm)
        w.r._reviews.pop(w.review.identity)
        outcome=w.r.commit(w.tokens['evaluation'],c,review.identity)
        self.assertEqual(outcome.status,'CandidateStale');self.assertEqual(outcome.reason,'ProjectionFormalCommitProofMissing')

    def test_wrong_meaning_inside_allowed_description_is_not_lexically_removed(self):
        w=self.world();w.observation(description='现在应该完整讲解。');w.consumer();ctx=w.assemble()
        self.assertEqual(ctx.items[0].content['description'],'现在应该完整讲解。')
        # Deliberate false semantic PASS remains visible: field projection is not A2 semantic support.

    def test_semantic_source_check_cannot_reach_unprojected_record_bytes(self):
        w=self.world();w.observation();old=w.consumer()
        definition=w.h.get(old.ref).payload
        definition.update(validation_format='source-linked-v3',criteria=[{'id':'grounding','evidence_mode':'whole_candidate','requirement':'Fixture grounding.'}])
        w.consumer_protocol=w.protocol('SourceChecked','Evidence',('Observation',),(('description','string'),),definition)
        w.consumer_versions=w.versions(w.consumer_protocol,w.producer.ref);w.allow();ctx=w.assemble()
        candidate=w.r.propose(ctx,'E','r1',{'description':'Audit candidate'})
        raw={'reviewed_fields':['description'],'criteria':[{'id':'grounding','status':'PASS','quotes':[],'rationale':'Fixture'}],
            'claims':[{'field':'description','text':'Audit candidate','kind':'paraphrase','reported_quote':None,'status':'PASS',
                'sources':[{'ref':json_value(w.candidate.record.ref),'field':'audit_note','text':MARKER}],'rationale':'Injected bad citation'}]}
        def transport(url,key,wire,timeout):
            self.assertNotIn(MARKER,json.dumps(wire,ensure_ascii=False))
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(raw)}}]}
        llm=DeepSeekAdapter(LLMConfig('LOCAL-ONLY'),transport);self.adapters.append(llm)
        with self.assertRaisesRegex(ContractError,'QuoteNotInExactSource'):w.r.validate_with_llm(w.tokens['evaluation'],candidate,llm)
        self.assertIsNone(w.h.get(candidate.record.ref));self.assertEqual(llm.calls,1)

    def test_policy_legality_cannot_restore_omitted_action_parameters(self):
        w=self.world()
        action=seed(w.h,Ref(Space.CANONICAL,'hint','v1'),kind='ActionSemantic',payload={'exact_payload':'hint text','executor_target':'mock-display'})
        envelope=seed(w.h,Ref(Space.CANONICAL,'envelope','v1'),kind='ActivityConstraints',payload={'episode':'episode','allowed_action_refs':[json_value(action)]})
        ctx=SimpleNamespace(items=(ContextItem(w.h.get(action),(),(),json.dumps({'executor_target':'mock-display'})),ContextItem(w.h.get(envelope),(),())))
        payload={'context_refs':[json_value(action)],'episode':'episode','outcome':'Execute','defer_condition':'',
            'action_identity':'hint','action_revision':'v1','exact_payload':'hint text','executor_target':'mock-display'}
        self.assertEqual(policy_legality(payload,ctx),'ExactActionParametersMismatch')


if __name__=='__main__':unittest.main()
