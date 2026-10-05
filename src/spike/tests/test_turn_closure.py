"""Closure mechanisms only: scripted cognition and synchronous mock effects."""
import json
from pathlib import Path
import tempfile
import unittest

from foundation.action_cases import ActionWorld
from foundation.boundary import ContextInput
from foundation.cases import EvidenceRecorder, seed
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.records import Ref, Role, Space, json_value
from foundation.runtime import ContractError
from foundation.serial_cases import SerialWorld
from foundation.session import SerialSession
from run_serial_validation import load_design
from test_activity_composition import LocalWorld, transport as activity_transport
from run_activity_composition_validation import execute_path


def local_transport(url,key,wire,timeout):
    name=wire['tool_choice']['function']['name']
    if name=='submit_policy':
        context=json.loads(wire['messages'][1]['content'])
        output={'outcome':'Execute','action_identity':'HintCheckStep','action_revision':'e1-v1',
            'exact_payload':'再检查一下 42÷6。','executor_target':'mock-display','episode':'apple-episode',
            'rationale':'SCRIPTED CLOSURE FIXTURE','context_refs':[context[0]['ref']],
            'expected_disclosure':'Local cue','uncertainty':'Fixture','defer_condition':''}
    else:output={'status':'PASS','rationale':'SCRIPTED CLOSURE FIXTURE'}
    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
        {'type':'function','function':{'name':name,'arguments':json.dumps(output)}}]}}]}


class TurnClosureTests(unittest.TestCase):
    artifact_directory=None

    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.directory=Path(self.artifact_directory or directory.name)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(self.directory/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.worlds=[]
        self.addCleanup(self.capture)

    def capture(self):
        for index,w in enumerate(self.worlds):self.e.capture(w.h,'final:'+str(index))

    def world(self):
        _,fixture,definition=load_design()
        w=SerialWorld(self.e,definition,fixture);self.worlds.append(w)
        return w

    def adapter(self,transport=local_transport):
        return DeepSeekAdapter(LLMConfig('LOCAL-ONLY',base_url='https://api.deepseek.com/beta',max_calls=4),transport)

    def failure(self,w,turn=None):
        return w.runtime.execution('TurnFailure','learner-A',{'turn_ref':json_value(turn or w.turn),
            'code':'INJECTED-MECHANISM-FAILURE','source':'TRUSTED-TEST-CONTROL'})

    def candidate(self,w):
        return w.generate_and_validate(self.adapter(),w.turn,w.context)

    def intent(self,w,bind=True):
        candidate,review=self.candidate(w)
        outcome=w.commit_and_record(w.turn,candidate,review)
        self.assertEqual(outcome.status,'Committed')
        w.allow_reads()
        intent=w.actions.create_intent(w.tokens['interaction'],candidate.record.ref,
            expires_at=w.h.clock.now+1000,idempotency_key='closure-effect')
        if bind:w.sessions.bind_intent(w.turn,intent)
        return candidate,intent

    def test_observation_failure_releases_next_request_without_failed_standing(self):
        w=ActionWorld(self.e);self.worlds.append(w)
        w.add_protocol('Observation','Interaction',('CurrentInteractionInput',),(('description','string'),))
        session=SerialSession(w.runtime)
        first=seed(w.h,Ref(Space.FACT,'first','1'),kind='CurrentInteractionInput',payload={'text':'42 / 6 = 8'})
        second=seed(w.h,Ref(Space.FACT,'second','1'),kind='CurrentInteractionInput',payload={'text':'请完整讲解这道题'})
        session.enqueue('C',first);turn=session.start('C');session.enqueue('C',second)
        # Use normal owner commit machinery; semantic FAIL is explicitly scripted.
        w.allow_reads();protocol=w.protocols['Observation']
        context=w.runtime.assemble(w.tokens['interaction'],protocol.ref,'learner-A','learner-A','learning',
            (ContextInput(first,Role.FACTUAL),),w.versions['Observation'])
        session.bind_reasoning_context(turn,context)
        candidate=w.runtime.propose(context,'O','r1',{'description':'Injected incomplete interpretation.'})
        review=w.runtime.record_semantic_validation(w.tokens['interaction'],candidate,'FAIL','Injected missing required content.',
            'SCRIPTED-CLOSURE-REVIEW',fixture=True)
        outcome=w.runtime.commit(w.tokens['interaction'],candidate,review.identity)
        self.assertEqual(outcome.status,'ValidationFailed')
        with self.assertRaisesRegex(ContractError,'ConversationTurnActive'):session.start('C')
        session.begin_close(turn,outcome.audit_ref);session.finish_close(turn)
        next_turn=session.start('C')
        self.assertEqual(session.turns[next_turn]['input'],second)
        new=w.commit_scripted('Observation','O-next',{'description':'Scripted fixture: learner requests an explanation.'},(second,))
        self.assertIsNotNone(w.h.get(new));self.assertIsNone(w.h.get(candidate.record.ref))
        self.assertEqual({d.target for d in w.h.get(new).dependencies if d.role==Role.FACTUAL},{second})
        self.assertFalse(any(r.kind=='PolicyOutcome' for r in w.h.states.records()))
        self.assertEqual(session.turns[turn]['termination_reason'],'FAILED')

    def test_queued_input_cannot_generate_before_previous_turn_closes(self):
        w=self.world();w.queue_second()
        # Assembly alone supplies no permission to reason on the queued input.
        w.allow_reads()
        protocol=w.protocols['Observation']
        context=w.runtime.assemble(w.tokens['interaction'],protocol.ref,'learner-A','learner-A','learning',
            (ContextInput(w.second_input,Role.FACTUAL),),w.versions['Observation'])
        with self.assertRaisesRegex(ContractError,'QueuedInputInActiveContext'):
            w.runtime.propose(context,'queued-O','r1',{'description':'Cannot reason ahead.'})

    def test_late_generation_is_audit_only_and_cannot_create_candidate(self):
        w=self.world();w.queue_second()
        def closes(url,key,wire,timeout):
            w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn)
            return local_transport(url,key,wire,timeout)
        adapter=self.adapter(closes)
        before=len(w.runtime._candidates)
        with self.assertRaisesRegex(ContractError,'TurnClosed'):
            w.runtime.generate_with_llm(w.tokens['interaction'],w.context,adapter,identity='P')
        self.assertEqual(len(w.runtime._candidates),before)
        self.assertEqual(adapter.calls,1)
        discarded=[r for r in w.h.executions.records() if r.kind=='LateGenerationDiscarded']
        self.assertEqual(len(discarded),1);self.assertTrue(discarded[0].payload['audit_only'])
        w.sessions.start('C')

    def test_close_immediately_before_commit_append_blocks_formal_standing(self):
        w=self.world();candidate,review=self.candidate(w)
        original=w.h.control.reach
        def closes(point):
            if point=='beforeCommitRevalidation':w.sessions.begin_close(w.turn,self.failure(w))
            original(point)
        w.h.control.reach=closes
        result=w.runtime.commit(w.tokens['interaction'],candidate,review.identity)
        self.assertEqual((result.status,result.reason),('CandidateStale','TurnClosed'))
        self.assertIsNone(w.h.get(candidate.record.ref));w.sessions.finish_close(w.turn)

    def test_close_after_policy_commit_blocks_new_intent_but_preserves_policy(self):
        w=self.world();candidate,review=self.candidate(w)
        outcome=w.commit_and_record(w.turn,candidate,review);self.assertEqual(outcome.status,'Committed')
        record=w.h.get(candidate.record.ref)
        w.sessions.begin_close(w.turn,self.failure(w));w.allow_reads()
        with self.assertRaisesRegex(ContractError,'TurnClosed'):
            w.actions.create_intent(w.tokens['interaction'],candidate.record.ref,expires_at=w.h.clock.now+100,idempotency_key='late')
        w.sessions.finish_close(w.turn)
        self.assertEqual(w.h.get(candidate.record.ref),record)

    def test_admitted_intent_before_session_binding_is_closed_as_not_dispatched(self):
        w=self.world();candidate,intent=self.intent(w,bind=False)
        w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn);w.allow_reads()
        result=w.actions.execute(w.tokens['interaction'],intent)
        self.assertEqual(w.h.get(result).payload['status'],'NotOccurred')
        self.assertEqual(w.h.get(result).payload['reason'],'TurnClosedBeforeDispatch')
        self.assertFalse(any(r.kind=='ActionOccurrence' for r in w.h.facts.records()))

    def test_close_before_dispatch_rejects_effect(self):
        w=self.world();_,intent=self.intent(w)
        w.sessions.begin_close(w.turn,self.failure(w))
        result=w.actions.execute(w.tokens['interaction'],intent)
        self.assertEqual(w.h.get(result).payload['reason'],'TurnClosed')
        self.assertEqual(w.h.get(result).payload['status'],'NotOccurred')
        w.sessions.finish_close(w.turn)

    def test_existing_full_partial_and_unknown_results_survive_closure(self):
        for mode in ('OCCUR_FULL','OCCUR_PARTIAL','INDETERMINATE'):
            with self.subTest(mode=mode):
                w=self.world();_,intent=self.intent(w)
                result=w.actions.execute(w.tokens['interaction'],intent,mode=mode,partial_characters=4 if mode=='OCCUR_PARTIAL' else None)
                prior=w.h.get(result);facts=w.h.facts.records()
                w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn);w.allow_reads()
                self.assertEqual(w.actions.execute(w.tokens['interaction'],intent),result)
                self.assertEqual(w.h.get(result),prior);self.assertEqual(w.h.facts.records(),facts)
                self.assertIn(result,w.sessions.processed_results)
                response=w.response('closure-'+mode);view=w.exposure(response)
                if mode=='INDETERMINATE':
                    self.assertEqual(view['exposures'],[]);self.assertEqual(view['unconfirmed'][0]['status'],'Indeterminate')
                else:self.assertEqual(view['exposures'][0]['completeness'],'PARTIAL' if mode=='OCCUR_PARTIAL' else 'FULL')

    def test_close_during_ack_waits_until_synchronous_executor_returns(self):
        w=self.world();_,intent=self.intent(w);original=w.actions._event
        def closes(kind,subject,payload):
            ref=original(kind,subject,payload)
            if kind=='DisplayAcknowledgement':
                w.sessions.begin_close(w.turn,self.failure(w))
                with self.assertRaisesRegex(ContractError,'EffectQuiescenceNotConfirmed'):w.sessions.finish_close(w.turn)
            return ref
        w.actions._event=closes
        result=w.actions.execute(w.tokens['interaction'],intent)
        self.assertEqual(w.h.get(result).payload['status'],'Occurred')
        w.sessions.finish_close(w.turn)
        self.assertEqual(sum(r.kind=='ActionOccurrence' for r in w.h.facts.records()),1)

    def test_unconfirmed_dispatch_blocks_release_and_duplicate_execution(self):
        w=self.world();_,intent=self.intent(w);w.queue_second()
        # Trusted fault injection models a dispatched executor without a return.
        w.sessions.before_effect(intent)
        w.sessions.begin_close(w.turn,self.failure(w))
        with self.assertRaisesRegex(ContractError,'EffectQuiescenceNotConfirmed'):w.sessions.finish_close(w.turn)
        with self.assertRaisesRegex(ContractError,'ConversationTurnActive'):w.sessions.start('C')
        with self.assertRaisesRegex(ContractError,'EffectAlreadyInFlight'):w.actions.execute(w.tokens['interaction'],intent)
        self.assertIn(intent,w.sessions.in_flight)
        self.assertFalse(any(r.kind=='ActionExecutionResult' for r in w.h.executions.records()))

    def test_new_context_from_closed_input_and_new_coordinator_cannot_bypass_guard(self):
        w=self.world();w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn)
        with self.assertRaisesRegex(ContractError,'SessionCoordinatorAlreadyRegistered'):SerialSession(w.runtime)
        w.allow_reads()
        context=w.runtime.assemble(w.tokens['interaction'],w.context.protocol,'learner-A','learner-A','learning',
            tuple(ContextInput(i.record.ref,Role.FACTUAL if i.record.ref.space==Space.FACT else Role.CANONICAL if i.record.ref.space==Space.CANONICAL else Role.EPISTEMIC) for i in w.context.items),w.context.versions)
        adapter=self.adapter()
        with self.assertRaisesRegex(ContractError,'TurnClosed'):w.runtime.generate_with_llm(w.tokens['interaction'],context,adapter,identity='P')
        self.assertEqual(adapter.calls,0)

    def test_late_validation_cannot_start_another_model_call(self):
        w=self.world();candidate,review=self.candidate(w)
        w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn)
        adapter=self.adapter()
        with self.assertRaisesRegex(ContractError,'TurnClosed'):w.runtime.validate_with_llm(w.tokens['interaction'],candidate,adapter)
        self.assertEqual(adapter.calls,0)

    def test_validation_returning_after_close_is_audit_only(self):
        w=self.world()
        candidate=w.runtime.generate_with_llm(w.tokens['interaction'],w.context,self.adapter(),identity='P')
        def closes(url,key,wire,timeout):
            w.sessions.begin_close(w.turn,self.failure(w));w.sessions.finish_close(w.turn)
            return local_transport(url,key,wire,timeout)
        adapter=self.adapter(closes)
        with self.assertRaisesRegex(ContractError,'TurnClosed'):
            w.runtime.validate_with_llm(w.tokens['interaction'],candidate,adapter)
        discarded=[r for r in w.h.executions.records() if r.kind=='LateValidationDiscarded']
        self.assertEqual(len(discarded),1);self.assertTrue(discarded[0].payload['audit_only'])
        self.assertEqual(adapter.calls,1);self.assertIsNone(w.h.get(candidate.record.ref))

    def control_world(self):
        config=LLMConfig('LOCAL-ONLY',base_url='https://api.deepseek.com/beta',max_calls=28,max_output_tokens=3072)
        row,snapshots=execute_path(self.e,1,config,activity_transport,LocalWorld)
        self.assertEqual(row['result'],'PASS',row)
        w=snapshots['switch-teaching'];w.e=self.e;self.worlds.append(w)
        return w

    def test_close_before_control_preserves_independent_activity(self):
        w=self.control_world();old=w.h.get(w.activity)
        w.sessions.begin_close(w.current_turn,self.failure(w,w.current_turn))
        result=w.control.execute(w.tokens['interaction'],w.current_intent)
        self.assertEqual(w.h.get(result).payload['status'],'NotOccurred')
        self.assertEqual(w.h.get(result).payload['reason'],'TurnClosed')
        w.sessions.finish_close(w.current_turn)
        self.assertEqual(w.h.get(w.activity),old)
        self.assertFalse(any(r.kind=='ActivityTransitionOccurred' for r in w.h.facts.records()))

    def test_successful_control_survives_later_failure(self):
        w=self.control_world();old=w.h.get(w.activity)
        result=w.effect(w.current_turn,w.current_intent)
        self.assertEqual(result['status'],'Occurred')
        teaching=w.h.get(w.activity);w.sessions.continue_cycle(w.current_turn)
        w.sessions.begin_close(w.current_turn,self.failure(w,w.current_turn))
        w.sessions.finish_close(w.current_turn)
        self.assertEqual(w.h.get(w.activity),teaching)
        self.assertEqual(teaching.payload['activity_purpose'],'Teaching')
        self.assertEqual(w.h.get(old.ref),old)
        self.assertEqual(sum(r.kind=='ActivityTransitionOccurred' for r in w.h.facts.records()),1)
        self.assertFalse(any(r.kind=='ActionOccurrence' for r in w.h.facts.records()))

    def test_failed_policy_commit_enters_failure_closure(self):
        w=self.world();candidate,review=self.candidate(w);w.external_update()
        outcome=w.commit_and_record(w.turn,candidate,review)
        self.assertEqual(outcome.status,'CandidateStale')
        self.assertEqual(w.sessions.turns[w.turn]['phase'],'CLOSING')
        w.sessions.settle(w.turn)
        self.assertEqual(w.sessions.turns[w.turn]['termination_reason'],'FAILED')
        self.assertIsNone(w.h.get(candidate.record.ref))

    def test_failure_source_must_belong_to_exact_turn(self):
        w=self.world();w.queue_second()
        with self.assertRaisesRegex(ContractError,'TurnFailureReferenceRequired'):w.sessions.begin_close(w.turn,w.second_input)
        foreign=w.runtime.execution('TurnFailure','learner-A',{'turn_ref':json_value(Ref(Space.EXECUTION,'another-turn','1'))})
        with self.assertRaisesRegex(ContractError,'TurnFailureReferenceRequired'):w.sessions.begin_close(w.turn,foreign)
        self.assertEqual(w.sessions.turns[w.turn]['phase'],'POLICY')

    def test_other_conversation_can_continue_while_one_turn_closes(self):
        w=self.world();w.sessions.begin_close(w.turn,self.failure(w))
        ref=seed(w.h,Ref(Space.FACT,'other-input','1'),kind='CurrentInteractionInput',payload={'text':'independent conversation'})
        w.sessions.enqueue('other',ref);other=w.sessions.start('other')
        self.assertNotEqual(other,w.turn);self.assertEqual(w.sessions.turns[w.turn]['phase'],'CLOSING')


if __name__=='__main__':unittest.main()
