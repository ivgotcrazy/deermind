"""Explicit local judgments verify audit/commit mechanics, not semantic competence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.cases import EvidenceRecorder,seed
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter,LLMConfig,ModelFailure
from foundation.protocol_preflight import check_observation_contract
from foundation.records import Ref,Space,json_value
from foundation.runtime import ContractError
from foundation.session import SerialSession
from test_expressions import CASES,review_for
from test_responsibility import classification
from test_structured_output import response

ROOT=Path(__file__).parents[1]
PROTOCOL=json.loads((ROOT/'protocols/observation-validation-v13.json').read_text(encoding='utf-8'))


class ValidationDimensionTests(unittest.TestCase):
    artifact_directory=None

    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        path=Path(self.artifact_directory or directory.name);path.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(path/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.worlds=[];self.adapters=[];self.addCleanup(self.capture)

    def capture(self):
        for adapter in self.adapters:
            for record in adapter.records:self.e.emit('scripted_model_execution',**record)
        for index,h in enumerate(self.worlds):self.e.capture(h,'final:'+str(index))

    def world(self):
        case=deepcopy(CASES[0])
        h,s,r,t,ctx,_,_=setup_boundary(prepare_candidate=False,protocol_payload=PROTOCOL,
            destination='https://api.deepseek.com/beta',work_payload={'task':'6kg cost 42 yuan. What do 15kg cost?','text':'42÷6=?'})
        self.worlds.append(h)
        return case,h,s,r,t,ctx,r.propose(ctx,'O','r1',case['candidate'])

    def adapter(self,case,*,raw=None,role='attributed_report',failure=None):
        outputs=[response(classification(role,payload=case['candidate']),'submit_responsibility'),
                 response(case['extraction'],'submit_extraction'),response(raw or review_for(case['candidate']))]
        if failure is not None:outputs[failure]=TimeoutError()
        llm=DeepSeekAdapter(LLMConfig('LOCAL-ONLY',base_url='https://api.deepseek.com/beta',max_calls=4),Mock(side_effect=outputs))
        self.adapters.append(llm)
        return llm

    def test_not_run_is_null_and_completed_pass_retains_exact_evidence(self):
        case,h,s,r,t,ctx,c=self.world()
        before=r.validation_assessment(c)
        self.assertTrue(all(row['execution_status']=='NOT_RUN' and row['conclusion'] is None for row in before['checks']))
        llm=self.adapter(case);review=r.validate_with_llm(t,c,llm);after=r.validation_assessment(c)
        self.assertTrue(after['all_required_checks_passed']);self.assertTrue(after['audit_only'])
        self.assertEqual(after['execution_status'],'COMPLETED');self.assertEqual(llm.calls,3)
        self.assertTrue(all(row['source_ref'] for row in after['checks']))
        records=[v for v in h.executions.records() if v.kind=='ValidationAssessment']
        self.assertEqual(len(records),1)
        self.assertEqual(records[0].payload['context_id'],ctx.identity)
        self.assertEqual(r.commit(t,c,review.identity).status,'Committed')

    def test_content_pass_and_missing_required_meaning_are_distinct(self):
        case,h,s,r,t,ctx,c=self.world();raw=review_for(case['candidate'])
        next(row for row in raw['criteria'] if row['id']=='final_result').update(status='FAIL',quotes=[])
        review=r.validate_with_llm(t,c,self.adapter(case,raw=raw));a=r.validation_assessment(c)
        self.assertEqual(a['dimensions']['content_validity']['conclusion'],'PASS')
        self.assertEqual(a['dimensions']['required_meaning']['conclusion'],'FAIL')
        self.assertEqual(a['execution_status'],'COMPLETED');self.assertFalse(a['all_required_checks_passed'])
        self.assertEqual(r.commit(t,c,review.identity).status,'ValidationFailed')

    def test_necessary_meaning_pass_does_not_hide_responsibility_failure(self):
        case,h,s,r,t,ctx,c=self.world()
        review=r.validate_with_llm(t,c,self.adapter(case,role='ability_inference'))
        a=r.validation_assessment(c)
        self.assertEqual(a['dimensions']['content_validity']['conclusion'],'FAIL')
        self.assertEqual(a['dimensions']['required_meaning']['conclusion'],'PASS')
        self.assertEqual(a['execution_status'],'COMPLETED')
        self.assertEqual(r.commit(t,c,review.identity).status,'ValidationFailed')

    def test_completed_unresolved_is_not_execution_failure(self):
        case,h,s,r,t,ctx,c=self.world()
        review=r.validate_with_llm(t,c,self.adapter(case,role='uncertain'))
        a=r.validation_assessment(c)
        self.assertEqual(a['execution_status'],'COMPLETED')
        self.assertEqual(a['dimensions']['content_validity']['conclusion'],'UNRESOLVED')
        self.assertEqual(r.commit(t,c,review.identity).status,'ValidationFailed')

    def test_failure_at_each_stage_preserves_completed_checks_and_unrun_tail(self):
        for failure in (0,1,2):
            with self.subTest(stage=failure):
                case,h,s,r,t,ctx,c=self.world();llm=self.adapter(case,failure=failure)
                with self.assertRaises(ModelFailure):r.validate_with_llm(t,c,llm)
                a=r.validation_assessment(c);self.assertEqual(a['execution_status'],'FAILED')
                rows={row['id']:row for row in a['checks']}
                ids=['responsibility','arithmetic','grounding']
                self.assertEqual([rows[i]['execution_status'] for i in ids],
                    ['COMPLETED']*failure+['FAILED']+['NOT_RUN']*(2-failure))
                self.assertIsNone(rows[ids[failure]]['conclusion'])
                self.assertIsNone(a['review_status']);self.assertFalse(a['all_required_checks_passed'])
                self.assertEqual(llm.calls,failure+1);self.assertIsNone(h.get(c.record.ref))
                with self.assertRaisesRegex(ContractError,'AlreadyAttempted'):r.validate_with_llm(t,c,llm)
                self.assertEqual(len([v for v in h.executions.records() if v.kind=='ValidationAssessment']),1)

    def test_wrong_field_is_failed_execution_not_completed_semantic_fail(self):
        case,h,s,r,t,ctx,c=self.world();raw=review_for(case['candidate'])
        raw['claims'][0]['field']='candidate.description'
        with self.assertRaises(ModelFailure):r.validate_with_llm(t,c,self.adapter(case,raw=raw))
        a=r.validation_assessment(c)
        self.assertEqual(a['dimensions']['required_meaning'],{'execution_status':'FAILED','conclusion':None})
        self.assertIsNone(a['review_status'])
        self.assertTrue(any(v.kind=='LLMValidationFailed' for v in h.executions.records()))

    def test_failed_source_recheck_preserves_first_review_and_failure_record(self):
        case,h,s,r,t,ctx,c=self.world();raw=review_for(case['candidate'])
        claim=raw['claims'][0]
        claim.update(kind='direct_quote',reported_quote='42÷6=?',status='FAIL',support='text_absent',sources=[])
        next(row for row in raw['criteria'] if row['id']=='grounding')['status']='FAIL'
        llm=self.adapter(case,raw=raw)
        llm.transport.side_effect=list(llm.transport.side_effect)+[TimeoutError()]
        review=r.validate_with_llm(t,c,llm);a=r.validation_assessment(c)
        self.assertEqual(review.status,'UNRESOLVED');self.assertEqual(a['execution_status'],'FAILED')
        self.assertEqual(len(a['recheck_failure_refs']),1)
        self.assertEqual(next(row for row in a['checks'] if row['id']=='grounding')['execution_status'],'COMPLETED')
        self.assertEqual(r.commit(t,c,review.identity).status,'ValidationFailed')

    def test_cached_result_does_not_start_a_new_assessment_or_model_call(self):
        case,h,s,r,t,ctx,c=self.world();llm=self.adapter(case)
        first=r.validate_with_llm(t,c,llm)
        self.assertEqual(r.validate_with_llm(t,c,llm),first);self.assertEqual(llm.calls,3)
        self.assertEqual(len([v for v in h.executions.records() if v.kind=='ValidationAssessment']),1)

    def test_in_progress_projection_preserves_completed_prefix(self):
        case,h,s,r,t,ctx,c=self.world();llm=self.adapter(case)
        outputs=list(llm.transport.side_effect);seen=[]
        def transport(*args):
            if len(seen)==1:
                a=r.validation_assessment(c)
                self.assertEqual(a['execution_status'],'INCOMPLETE')
                self.assertEqual(a['dimensions']['content_validity']['execution_status'],'INCOMPLETE')
                self.assertEqual(a['dimensions']['required_meaning']['execution_status'],'NOT_RUN')
            seen.append(True)
            return outputs[len(seen)-1]
        llm.transport=transport
        r.validate_with_llm(t,c,llm)
        self.assertEqual(llm.calls,3)

    def test_audit_summary_cannot_override_failed_required_review(self):
        case,h,s,r,t,ctx,c=self.world();raw=review_for(case['candidate'])
        next(row for row in raw['criteria'] if row['id']=='method').update(status='FAIL',quotes=[])
        review=r.validate_with_llm(t,c,self.adapter(case,raw=raw))
        r.execution('ValidationAssessment',ctx.subject,{'all_required_checks_passed':True,'review_status':'PASS'})
        self.assertFalse(r.validation_assessment(c)['all_required_checks_passed'])
        self.assertEqual(r.commit(t,c,review.identity).status,'ValidationFailed')

    def test_failed_attempt_can_close_its_bound_turn_without_policy(self):
        case,h,s,r,t,ctx,c=self.world();session=SerialSession(r)
        ref=seed(h,Ref(Space.FACT,'dimension-input','1'),kind='CurrentInteractionInput',payload={'text':'work'})
        session.enqueue('C',ref);turn=session.start('C');session.bind_reasoning_context(turn,ctx)
        with self.assertRaises(ModelFailure):r.validate_with_llm(t,c,self.adapter(case,failure=1))
        failure=next(v for v in h.executions.records() if v.kind=='ValidationAttemptFailed')
        session.begin_close(turn,failure.ref);session.finish_close(turn)
        self.assertEqual(session.turns[turn]['phase'],'SETTLED')
        self.assertFalse(any(v.kind=='PolicyOutcome' for v in h.states.records()))

    def test_dimension_profile_cannot_remove_or_reclassify_required_checks(self):
        self.assertEqual(check_observation_contract(PROTOCOL)['status'],'PASS')
        for key in ('format','groups','classifier'):
            bad=deepcopy(PROTOCOL)
            if key=='format':bad['validation_dimensions']['format']='invented'
            elif key=='groups':bad['validation_dimensions']['criteria_groups']['required_meaning'].remove('final_result')
            else:bad.pop('responsibility_profile')
            with self.assertRaises(ValueError):check_observation_contract(bad)
            with self.assertRaises(ContractError):setup_boundary(prepare_candidate=False,protocol_payload=bad)


if __name__=='__main__':unittest.main()
