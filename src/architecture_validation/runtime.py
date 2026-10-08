"""Strict serial observation/evaluation/policy pipeline with fallible semantic review."""
from __future__ import annotations
from copy import deepcopy
import threading
import time

from .common import Rejected, digest, now
from .contracts import WIRE, FORMAL_EVIDENCE, FORMAL_BELIEF, COMPLETION, validate
from .protocols import RULES, system, review_system
from .references import Bindings
from .review import aggregate_review


def compact(value):
    if isinstance(value,dict):
        if set(value)=={'kind','id','version','revision','content_hash'}:
            return {'kind':value['kind'],'id':value['id'],'version':value['version'],'revision':value['revision']}
        return {k:compact(v) for k,v in value.items()}
    if isinstance(value,list):return [compact(v) for v in value]
    return value


def view(r):
    return {'id':r['id'],'kind':r['kind'],'object_id':r['obj'].split(':',2)[2] if r['version'] else r['obj'],
            'version':r['version'],'revision':r['revision'],'standing':'current-valid admitted by ContextAssembler',
            'created':r['created'],'body':compact(r['body'])}


def source_ids(store,provided,values):
    """Resolve only explicitly supplied, unambiguous record/object identities."""
    aliases={}
    for rid in provided:
        for alias in (rid,store.ref(rid)['id']):aliases.setdefault(alias,set()).add(rid)
    resolved=[]
    for value in values:
        matches=aliases.get(value,set())
        if len(matches)!=1:raise Rejected('UnknownOrAmbiguousSource')
        resolved.append(next(iter(matches)))
    return resolved


class Engine:
    def __init__(self,store,model,*,effect_timeout=15,test_mode=False,hooks=None):
        self.store=store;self.model=model;self.effect_timeout=effect_timeout;self.test_mode=test_mode;self.hooks=hooks or {}
        if getattr(model,'mode',None)!='real' and not test_mode:raise Rejected('ScriptedAdapterRequiresTestMode')
        self.worker_epoch=store.recover();self.stopped=threading.Event();self.thread=None
        self.repair_used={};self.executions={};self.reviews={};self.passed_reviews={}

    def start(self):
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()

    def stop(self):
        self.stopped.set()
        if self.thread:self.thread.join(timeout=2)

    def loop(self):
        while not self.stopped.is_set():
            t=self.store.claim_turn(self.worker_epoch)
            if t:
                self.process(t['id'])
            else:
                # On restart, preserve and settle dispatched/pending effects without
                # pretending to resume a lost reasoning execution.
                for sid in [r[0] for r in self.store.db.execute('SELECT id FROM sessions WHERE active_turn IS NOT NULL').fetchall()]:
                    s=self.store.session(sid);t=self.store.turn(s['active_turn'])
                    if t['worker_epoch']!=self.worker_epoch and not s['isolated']:
                        intents=self.store.db.execute('SELECT id,status FROM intents WHERE turn_id=?',(t['id'],)).fetchall()
                        if intents and all(i['status'] in ('OCCURRED','NOT_OCCURRED','ISOLATED_UNKNOWN') for i in intents):self.store.finish(t['id'],'RecoveredPriorEffect')
                self.stopped.wait(.05)

    def context(self,tid,purpose,obs_id=None,completion=None):
        st=self.store;t=st.turn(tid);sid=t['sid'];s=st.session(sid);event=st.get(t['event_id']);task=st.resolve(event['body']['task_ref'])
        sources=[r for r in st.rows('Event',sid) if r['seq']<=event['seq']]
        assistance=st.rows('ActionOccurrence',sid)
        unknown=st.rows('EffectIndeterminate',sid)
        claims=st.rows('Claim',current=True);norm=[];refs=[]
        def use(rows):
            refs.extend(r['id'] for r in rows);return [view(r) for r in rows]
        sem={'purpose':purpose,'current_activity':s['purpose'],'current_input_id':event['id'],
             'task':view(task),'sources':use(sources),'assistance':use(assistance),
             'assistance_coverage':'UNKNOWN' if unknown else 'COMPLETE',
             'source_contract':{
                 'activity':'current_activity is confirmed runtime state; purpose is the processing stage. activity_at_observation describes the historical observation and cannot override current_activity.',
                 'events':'LearnerInput is learner text, including unverified self-reports of help.',
                 'display':'Only assistance entries confirm this system rendered their listed blocks; rendering does not prove reading or comprehension.',
                 'coverage_scope':'This session, controlled application channel, before current evaluation. External help remains unknown.',
                 'partial':'PARTIAL occurrence contains only rendered blocks; omitted blocks are not assistance.'}}
        refs.append(task['id'])
        sem['domain']=use(st.rows('TaskFamily',current=True)+st.rows('KC',current=True))
        historical_tasks={st.resolve(r['body']['task_ref'])['id'] for r in sources}
        sem['prior_tasks']=use([st.get(rid) for rid in sorted(historical_tasks) if rid!=task['id']])
        if purpose=='Observation':sem['strategy']=use(st.rows('SolutionStrategy',current=True))
        else:
            sem['claims']=use(claims)
            if obs_id:sem['observations']=use([st.get(obs_id)])
        if purpose=='Evidence':sem['evidence_semantics']=use(st.rows('EvidenceSemantics',current=True))
        if purpose=='Belief':
            sem['inference_semantics']=use(st.rows('InferenceSemantics',current=True))
            sem['evidence']=use(st.rows('Evidence',sid,current=True))
            sem['beliefs']=use(st.rows('Belief',sid,current=True))
        if purpose=='Policy':
            if not completion or not st.current(completion):raise Rejected('RequiredEvaluationUnavailable')
            cr=st.get(completion)
            if cr['body']['execution_status']!='SUCCEEDED' or cr['body']['turn_id']!=tid:raise Rejected('RequiredEvaluationUnavailable')
            sem['beliefs']=use(st.rows('Belief',sid,current=True));refs.append(completion)
            sem['evaluation_completion_id']=completion
            sem['admissible_actions']=['Hint','Explanation'] if s['purpose']=='Teaching' else ['Hint','Control']
        if not s['authorized']:raise Rejected('Unauthorized')
        heads={}
        for rid in refs:
            r=st.get(rid)
            if r['revision'] or r['version']:heads[r['obj']]=rid
        # Expected target heads protect concurrent first writes as well as updates.
        if purpose=='Belief':
            for c in claims:
                obj=f"belief:{sid}:{c['obj']}";prior=st.head(obj,False);heads[obj]=prior['id'] if prior else None
        return st.make_context(sid,tid,purpose,sem,list(dict.fromkeys(refs)),heads)

    def call(self,tid,purpose,context,schema,review=False,category='base',feedback=None):
        st=self.store;ctx=st.get(context);sem=ctx['body']['semantic']
        bindings=Bindings(st,ctx)
        sem=bindings.project(sem)
        schema=bindings.schema('Review' if review else purpose,schema)
        if purpose=='Belief':
            sem['claim_evidence_index']=[{
                'claim_id':bindings.encode[c['id']],
                'evidence_ids':[bindings.encode[e['id']] for e in bindings.rows.values() if e['kind']=='Evidence' and e['body']['claim_ref']==st.ref(c['id'])],
                'prior_belief_id':next((bindings.encode[b['id']] for b in bindings.rows.values() if b['kind']=='Belief' and b['body']['claim_ref']==st.ref(c['id'])),None)
                } for c in bindings.rows.values() if c['kind']=='Claim']
        if review:
            check=schema['properties']['checks']['items'];ordered=[]
            for name in RULES[purpose]:
                bound=deepcopy(check);bound['properties']['rule_id']={'const':name};ordered.append(bound)
            schema['properties']['checks']={'type':'array','prefixItems':ordered,'items':False,'minItems':len(ordered),'maxItems':len(ordered)}
        prompt=review_system(purpose) if review else system(purpose)
        if review:sem=deepcopy(sem)|{'candidate':self.review_wire}
        elif feedback:sem=deepcopy(sem)|{'previous_attempt_feedback':feedback}
        try:
            output,record=self.model.complete(prompt,sem,schema,('Review:'+purpose) if review else purpose,category)
            eid=st.record('ReasoningExecution',{'purpose':purpose,'role':'review' if review else 'generation','mode':self.model.mode,
                 'context_id':context,'output':output,'model_record':record,'status':'COMPLETED',
                 'model_reference_bindings':bindings.manifest()},sid=ctx['sid'],turn=tid,dependencies=[(context,'PINNED','input')])
            self.executions.setdefault(tid,[]).append(eid)
            validate(schema,output)
            return output,eid
        except Rejected as e:
            eid=st.record('ReasoningExecutionFailure',{'purpose':purpose,'role':'review' if review else 'generation','mode':self.model.mode,
                 'context_id':context,'reason':str(e)},sid=ctx['sid'],turn=tid,dependencies=[(context,'PINNED','input')])
            self.executions.setdefault(tid,[]).append(eid);raise

    def materialize(self,tid,purpose,wire,ctx_id):
        # Preserve the exact raw wire in the execution/candidate; materialization
        # performs only unambiguous identity normalization within admitted inputs.
        wire=deepcopy(wire)
        st=self.store;ctx=st.get(ctx_id);sem=ctx['body']['semantic'];sid=ctx['sid']
        registry={rid:st.get(rid) for rid in ctx['body']['control']['refs']}
        bindings=Bindings(st,ctx)
        def ids(values,kinds=None):
            values[:]=[bindings.resolve(value,kinds) for value in values]
            if len(values)!=len(set(values)):raise Rejected('DuplicateSourceReference')
            for rid in values:
                if rid not in registry or kinds and registry[rid]['kind'] not in kinds:raise Rejected('UnknownOrWrongSource')
            return values
        deps=[(rid,'CURRENT' if registry[rid]['revision'] or registry[rid]['version'] else 'PINNED','input') for rid in registry]
        if purpose=='Observation':
            if 'current_purpose' in wire:raise Rejected('RuntimeOwnedField')
            wire['current_purpose']=sem['current_activity']
            validate(WIRE['Observation'],wire)
            ids(wire['source_ids'],['Event'])
            for step in wire['work_steps']:step['source_id']=ids([step['source_id']],['Event'])[0]
            if not wire['source_ids']:raise Rejected('MissingGrounding')
            event=st.get(st.turn(tid)['event_id']);correction=event['body']['correction_of']
            with st.lock:recompute=st.db.execute('SELECT target_observation FROM recompute_requests WHERE turn_id=?',(tid,)).fetchone()
            if recompute:correction=recompute[0]
            obj=st.get(correction)['obj'] if correction else 'observation:'+event['id']
            return 'Observation',[(obj,wire,deps)],[]
        if purpose=='Policy':
            ids(wire['source_ids']);outcome=wire['outcome'];action=wire['action_type']
            if outcome=='Execute':
                if action not in sem['admissible_actions']:raise Rejected('ActionNotAdmissible')
                if action=='Control':
                    if wire['blocks'] or wire['transition']!='Teaching':raise Rejected('InvalidControl')
                elif not wire['blocks'] or len(wire['blocks'])>3 or wire['transition']!='None':raise Rejected('InvalidDisplayAction')
                blockids=[b['block_id'] for b in wire['blocks']]
                if len(blockids)!=len(set(blockids)) or any(not b['text'] for b in wire['blocks']):raise Rejected('InvalidBlockIdentity')
            elif action!='None' or wire['blocks'] or wire['transition']!='None':raise Rejected('UnexpectedAction')
            if outcome=='Defer' and not wire['reevaluation_condition']:raise Rejected('MissingReevaluationCondition')
            return 'Decision',[(f'decision:{tid}:{st.session(sid)["activity_rev"]}',wire,deps)],[]
        claims={r['id']:r for r in st.rows('Claim',current=True)}
        claim_ids=[bindings.resolve(i['claim_id'],['Claim']) for i in wire['items']]
        if any(i is None for i in claim_ids) or sorted(claim_ids)!=sorted(claims):raise Rejected('ClaimCoverageMismatch')
        items=[];unchanged=[]
        for item,claim_id in zip(wire['items'],claim_ids):
            claim=claims[claim_id];claimref=st.ref(claim['id'])
            if purpose=='Evidence':
                ids(item['source_ids'],['Event']);ids(item['observation_ids'],['Observation']);ids(item['assistance_ids'],['ActionOccurrence'])
                if not item['source_ids'] or not item['observation_ids']:raise Rejected('MissingEvidenceGrounding')
                rule=st.rows('EvidenceSemantics',current=True)[0]
                body={'claim_ref':claimref,'observation_refs':[st.ref(i) for i in item['observation_ids']],
                    'grounding':[{'record_ref':st.ref(i),'content_path':'/body/text'} for i in item['source_ids']],
                    'relation':item['relation'],'interpretation':item['interpretation'],
                    'epistemic_context':{'conditions':['本 Task Family'],'assistance_refs':[st.ref(i) for i in item['assistance_ids']],
                         'coverage':item['coverage'],'observation_interval':[registry[item['source_ids'][0]]['created'],st.get(st.turn(tid)['event_id'])['created']],
                         'assistance_relevance':item['assistance_relevance'],'dependencies_explanation':item['dependencies_explanation']},'evidence_semantics_ref':st.ref(rule['id'])}
                validate(FORMAL_EVIDENCE,body)
                obs=registry[item['observation_ids'][0]]
                items.append((f'evidence:{sid}:{obs["obj"]}:{claim["obj"]}',body,deps))
            else:
                ids(item['evidence_ids'],['Evidence'])
                for conflict in item['conflicts']:ids(conflict['evidence_ids'],['Evidence'])
                obj=f'belief:{sid}:{claim["obj"]}';prior=st.head(obj,False)
                if item['disposition']=='UNCHANGED':
                    if not prior:raise Rejected('UnchangedWithoutPrior')
                    # UNCHANGED is a result referencing existing content, never a new belief.
                    if prior['body']['assessment']!={'kind':item['assessment_kind'],'statement':item['assessment']}:raise Rejected('UnchangedAssessmentMismatch')
                    unchanged.append({'claim_ref':claimref,'disposition':'UNCHANGED','belief_ref':st.ref(prior['id']),'reason':item['rationale']});continue
                if not item['evidence_ids'] and item['assessment_kind']!='UNKNOWN':raise Rejected('BeliefWithoutEvidence')
                rule=st.rows('InferenceSemantics',current=True)[0]
                body={'claim_ref':claimref,'assessment':{'kind':item['assessment_kind'],'statement':item['assessment']},
                    'epistemic_uncertainty':item['uncertainty'],'epistemic_status':item['epistemic_status'],'evidence_basis':[st.ref(i) for i in item['evidence_ids']],
                    'conflicts':[{'evidence_refs':[st.ref(i) for i in c['evidence_ids']],'explanation':c['explanation']} for c in item['conflicts']],
                    'prior_belief_ref':st.ref(prior['id']) if prior else None,'inference_semantics_ref':st.ref(rule['id']),'inference_rationale':item['rationale']}
                validate(FORMAL_BELIEF,body)
                beliefdeps=[(rid,'PINNED' if registry[rid]['kind']=='Belief' else mode,use) for rid,mode,use in deps]
                items.append((obj,body,beliefdeps))
        return purpose,items,unchanged

    def step(self,tid,purpose,obs=None,completion=None):
        feedback=None
        for attempt in range(2):
            started=time.perf_counter();category='repair' if attempt else 'base';ctx=self.context(tid,purpose,obs,completion)
            context_seconds=time.perf_counter()-started
            try:
                generation_start=time.perf_counter()
                wire,eid=self.call(tid,purpose,ctx,WIRE[purpose],category=category,feedback=feedback)
                generation_seconds=time.perf_counter()-generation_start
                kind,items,unchanged=self.materialize(tid,purpose,wire,ctx)
                candidate=self.store.record('Candidate',{'context_id':ctx,'target_kind':kind,'wire':wire,'formal_payload_hash':digest([b for _,b,_ in items]),
                    'formal_payloads':[b for _,b,_ in items],'unchanged':unchanged,'generation_execution':eid},sid=self.store.turn(tid)['sid'],turn=tid,dependencies=[(ctx,'PINNED','input'),(eid,'PINNED','generation')])
                hook=self.hooks.get('candidate_created')
                if hook:hook(self,purpose,candidate)
                self.review_wire=wire;self.review_candidate=candidate
                review_start=time.perf_counter()
                review,rid=self.call(tid,purpose,ctx,WIRE['Review'],review=True,category=category)
                review_seconds=time.perf_counter()-review_start
                checks=review['checks'];required=set(RULES[purpose]);complete=(len(checks)==len(required) and {c['rule_id'] for c in checks}==required)
                complete=complete and all(c['verdict']=='PASS' and c['reason'] for c in checks)
                bindings=Bindings(self.store,self.store.get(ctx))
                try:
                    for check in checks:check['source_ids']=[bindings.resolve(i) for i in check['source_ids']]
                except Rejected:raise Rejected('ReviewUnknownSource')
                vr=self.store.record('Validation',{'context_id':ctx,'candidate_id':candidate,'candidate_hash':self.store.get(candidate)['hash'],
                    'verdict':aggregate_review(review),'model_verdict':review['verdict'],'verdict_aggregation':'required-checks-v1',
                    'required_checks_complete':bool(complete),'rule_hash':digest(RULES[purpose]),'checks':checks,'review_execution':rid},
                    sid=self.store.turn(tid)['sid'],turn=tid,dependencies=[(candidate,'PINNED','reviewed'),(rid,'PINNED','review execution')])
                self.reviews.setdefault(tid,[]).append(vr)
                hook=self.hooks.get('before_commit')
                if hook:hook(self,purpose,candidate,vr)
                commit_start=time.perf_counter()
                outputs=self.store.commit(kind,'Interaction' if purpose in ('Observation','Policy') else 'Evaluation',ctx,candidate,vr,items)
                commit_seconds=time.perf_counter()-commit_start
                self.passed_reviews.setdefault(tid,[]).append(vr)
                self.store.record('StageTiming',{'purpose':purpose,'attempt':attempt,'context_seconds':context_seconds,'generation_seconds':generation_seconds,'review_seconds':review_seconds,'commit_seconds':commit_seconds,'total_seconds':time.perf_counter()-started},sid=self.store.turn(tid)['sid'],turn=tid)
                self.store.checkpoint(tid,purpose.upper()+'_COMMITTED')
                return outputs,unchanged,ctx
            except Rejected as e:
                feedback={'failure':str(e),'checks':[]}
                if str(e)=='RequiredValidationNotPassed':feedback['checks']=[{'rule_id':c['rule_id'],'verdict':c['verdict'],'reason':c['reason']} for c in review['checks'] if c['verdict']!='PASS']
                self.store.record('AttemptFailure',{'purpose':purpose,'context':ctx,'attempt':attempt,'reason':str(e)},sid=self.store.turn(tid)['sid'],turn=tid)
                allowed=str(e).startswith(('SchemaMismatch','InvalidStructuredOutput','IncompleteModelOutput','RequiredValidationNotPassed','UnknownOrWrongSource','ClaimCoverageMismatch','ReviewUnknownSource','UnchangedAssessmentMismatch'))
                if attempt or self.repair_used.get(tid) or not allowed:raise
                transport=getattr(self.model,'model',self.model);budget=getattr(transport,'budget',None)
                if budget is not None:
                    category='B2' if transport.phase=='B2' else 'repair'
                    if budget.data['counts'][category]+2>budget.limits[category] or budget.data['total_attempts']+2>getattr(budget,'total_limit',340):
                        self.store.record('RecoveryOmitted',{'purpose':purpose,'reason':'RecoveryPairReserveUnavailable','original_failure':str(e)},sid=self.store.turn(tid)['sid'],turn=tid)
                        raise
                self.repair_used[tid]=True
        raise Rejected('AttemptBudgetExhausted')

    def evaluation_completion(self,tid,evidence,beliefs,unchanged,ctx,obs):
        st=self.store;t=st.turn(tid)
        results=unchanged+[{'claim_ref':st.get(i)['body']['claim_ref'],'disposition':'REVISE','belief_ref':st.ref(i),'reason':st.get(i)['body']['inference_rationale']} for i in beliefs]
        body={'turn_id':tid,'input_context_ref':st.ref(ctx),'execution_refs':[st.ref(i) for i in self.executions[tid]],
              'validation_refs':[st.ref(i) for i in self.passed_reviews[tid] if st.get(st.get(i)['body']['candidate_id'])['body']['target_kind'] in ('Evidence','Belief')],'execution_status':'SUCCEEDED',
              'evidence_refs':[st.ref(i) for i in evidence],'belief_results':results,'failure_reason':''}
        validate(COMPLETION,body)
        with st.tx():
            current=st.session(t['sid']);turn=st.turn(tid)
            if not current['authorized'] or turn['status']!='RUNNING' or turn['error']:raise Rejected('EvaluationCompletionUnauthorized')
            dependencies=[obs]+evidence+beliefs+[st.resolve(i['belief_ref'])['id'] for i in unchanged]
            if any(not st.current(i) for i in dependencies):raise Rejected('NoCurrentValidState')
            return st._insert('EvaluationCompletion',body,'Evaluation',t['sid'],tid,dependencies=[(i,'CURRENT','evaluation input') for i in dependencies]+[(ctx,'PINNED','context')])

    def wait_effect(self,iid):
        st=self.store;i=st.intent(iid)
        if st.get(iid)['body']['action_type']=='Control':st.dispatch(i['sid'],st.session(i['sid'])['epoch'])
        start=time.monotonic()
        while not self.stopped.is_set():
            i=st.intent(iid)
            if i['status'] in ('OCCURRED','NOT_OCCURRED','ISOLATED_UNKNOWN'):return i['status']
            if i['status']=='INDETERMINATE':raise Rejected('EffectIndeterminate')
            if time.monotonic()-start>self.effect_timeout:
                if i['status']=='PENDING':
                    with st.tx():st._not_occurred(iid,'NoClientDispatch')
                    return 'NOT_OCCURRED'
                st.isolate(iid);raise Rejected('EffectIndeterminate')
            self.stopped.wait(.03)
        raise Rejected('WorkerStopped')

    def process(self,tid):
        st=self.store;start=time.perf_counter();obs=None;completion=None
        try:
            obs=self.step(tid,'Observation')[0][0]
            evidence=self.step(tid,'Evidence',obs)[0]
            beliefs,unchanged,ctx=self.step(tid,'Belief',obs)
            completion=self.evaluation_completion(tid,evidence,beliefs,unchanged,ctx,obs)
            for cycle in range(2):
                decision=self.step(tid,'Policy',obs,completion)[0][0];body=st.get(decision)['body']
                if body['outcome']!='Execute':break
                if cycle and body['action_type']=='Control':raise Rejected('ControlCycleLimit')
                iid=st.create_intent(decision);st.checkpoint(tid,'INTENT_COMMITTED')
                hook=self.hooks.get('intent_created')
                if hook:hook(self,iid)
                result=self.wait_effect(iid)
                if body['action_type']=='Control' and result=='OCCURRED':continue
                break
            st.finish(tid)
        except Rejected as e:
            t=st.turn(tid)
            if obs and not completion:
                contexts=[r for r in st.rows('Context',t['sid']) if r['turn_id']==tid and r['body']['control']['purpose'] in ('Evidence','Belief')]
                if contexts:
                    body={'turn_id':tid,'input_context_ref':st.ref(contexts[-1]['id']),
                          'execution_refs':[st.ref(i) for i in self.executions.get(tid,[])],
                          'validation_refs':[st.ref(i) for i in self.reviews.get(tid,[])],
                          'execution_status':'FAILED','evidence_refs':[st.ref(r['id']) for r in st.rows('Evidence',t['sid']) if r['turn_id']==tid],
                          'belief_results':[],'failure_reason':str(e)}
                    validate(COMPLETION,body)
                    st.record('EvaluationCompletion',body,'Evaluation',t['sid'],tid)
            st.record('RuntimeFailure',{'reason':str(e),'observation':obs,'phase':t['phase']},sid=t['sid'],turn=tid)
            st.finish(tid,str(e))
        except Exception as e:
            # Record only exception type; arbitrary provider content never enters errors.
            st.record('RuntimeFailure',{'reason':'ImplementationError:'+type(e).__name__},sid=st.turn(tid)['sid'],turn=tid)
            st.finish(tid,'ImplementationError:'+type(e).__name__)
            if self.test_mode:raise
        finally:
            st.record('TurnTiming',{'seconds':time.perf_counter()-start,'model_mode':self.model.mode},sid=st.turn(tid)['sid'],turn=tid)
