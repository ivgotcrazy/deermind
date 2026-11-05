"""Mechanism checks; these tests do not stand in for semantic extraction review."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from pipeline import ROOT,read,save,digest,compile_graph,content_errors,approved_content

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.case=read(ROOT/'cases.json')[0];self.catalog=read(ROOT/'catalog.json')
        part={'regionIndex':0,'blocks':[{'type':'text','text':'原题条件'}]}
        self.content={'tasks':[{'question':[part],'solutions':[{'content':[dict(part,regionIndex=1)]}],'knowledge':[],'teachingAids':[dict(part,regionIndex=1)]}],'uncertainties':[]}
        def m(id):return {'catalogId':id,'reason':'test','unmatchedProposal':None}
        self.mapping={'tasks':[{'taskIndex':0,'taskMatch':m('TT-CHAIN'),'solutions':[{'solutionIndex':0,'match':m('ST-TWO')}],'knowledge':[]}]}
    def test_program_ids_source_and_separate_help(self):
        before=copy.deepcopy(self.content);g=compile_graph(self.case,self.content,self.mapping,self.catalog)
        self.assertEqual(g,compile_graph(self.case,self.content,self.mapping,self.catalog));self.assertEqual(before,self.content)
        byid={e['id']:e for e in g['elements']};self.assertEqual(len(byid),len(g['elements']))
        for i in g['instances']:
            for eid in i['contentRefs']:
                self.assertEqual(byid[eid]['owner'],i['id']);self.assertEqual(byid[eid]['role'],'question' if i['kind']=='TaskInstance' else 'solution')
        self.assertEqual(g['elements'][0]['source']['sourceSha256'],self.case['regions'][0]['originalSha256'])
    def test_wrong_method_rejected(self):
        self.mapping['tasks'][0]['solutions'][0]['match']['catalogId']='ST-VIEW'
        with self.assertRaisesRegex(ValueError,'not permitted'):compile_graph(self.case,self.content,self.mapping,self.catalog)
    def test_unknown_template_rejected(self):
        self.mapping['tasks'][0]['taskMatch']['catalogId']='NOT-EXIST'
        with self.assertRaisesRegex(ValueError,'catalog'):compile_graph(self.case,self.content,self.mapping,self.catalog)
    def test_missing_task_mapping_rejected(self):
        self.content['tasks'].append(copy.deepcopy(self.content['tasks'][0]))
        with self.assertRaisesRegex(ValueError,'exactly'):compile_graph(self.case,self.content,self.mapping,self.catalog)
    def test_template_mutation_in_response_rejected(self):
        self.mapping['definitions']=[]
        with self.assertRaises(ValueError):compile_graph(self.case,self.content,self.mapping,self.catalog)
    def test_stale_review_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);save(p/'reviewed-content.json',self.content);save(p/'content-review.json',dict(decision='accept_for_mapping',reviewedContentHash=digest(self.content)))
            self.assertEqual(approved_content(p,self.case),self.content)
            self.content['uncertainties'].append('changed');save(p/'reviewed-content.json',self.content)
            with self.assertRaisesRegex(ValueError,'stale'):approved_content(p,self.case)
    def test_invalid_formula_or_source_rejected(self):
        self.assertEqual(content_errors(self.case,self.content),[])
        self.content['tasks'][0]['question'][0]['regionIndex']=99
        self.assertTrue(content_errors(self.case,self.content))
    def test_source_error_is_not_silently_corrected(self):
        case=read(ROOT/'cases.json')[1];error={'op':'fraction','args':[{'op':'number','value':'7'},{'op':'number','value':'32'}]}
        data={'tasks':[{'question':[{'regionIndex':1,'blocks':[{'type':'worked_example','expressions':[error,error],'assertedCorrect':False}]}],'solutions':[],'knowledge':[],'teachingAids':[]}],'uncertainties':[]}
        original=copy.deepcopy(data);self.assertEqual(content_errors(case,data),[]);self.assertEqual(data,original)

if __name__=='__main__':unittest.main()
