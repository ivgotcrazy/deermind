"""Read-only assessment of the single closed E1 v2 review campaign."""
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'review-packages/policy-e1-v2-reviewed'
RUN=ROOT/'runs/policy-v2-review-real-v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return sha256(p.read_bytes()).hexdigest()
def main():
    summary=read(RUN/'summary.json');manifest=read(RUN/'manifest.json');package=read(PACKAGE/'manifest.json')
    assert manifest['package_manifest_sha256']==digest(PACKAGE/'manifest.json')
    for p,h in summary['artifact_sha256'].items():assert digest(RUN/p)==h,p
    for p,h in package['artifact_sha256'].items():assert digest(PACKAGE/p)==h,p
    requests=read(PACKAGE/'requests.json');records=read(RUN/'execution/adapter-records.json');rows=read(RUN/'execution/results.json')
    assert len(rows)==36 and len(records)<=36
    for rec,req in zip(records,requests):
        assert rec['messages']==req['messages'] and rec['output_contract']==req['output_contract']
    cases=read(PACKAGE/'cases.json');labels={x['id']:x for x in read(PACKAGE/'author-expectations.json')}
    comparisons=[];mismatches=[];counts=Counter();dimensions=Counter()
    for case in cases:
        identity=case['id'];label=labels[identity];pair={x['stage']:x for x in rows if x['case_id']==identity}
        semantic=pair['semantic'];utility=pair['utility'];expected=label['semantic_expected']
        actual=semantic.get('semantic_or_utility_status');scored={x['id']:x for x in utility.get('output',{}).get('scores',[])}
        comparison={'case_id':identity,'stratum':case['review_stratum'],'semantic_expected':expected,'semantic_actual':actual,
            'semantic_execution':semantic['status'],'utility_actual':utility.get('semantic_or_utility_status'),
            'utility_execution':utility['status'],'labelled_utility_dimensions':[]}
        if expected is not None:
            counts['labelled']+=1;counts['semantic_matches']+=actual==expected
            if actual!=expected:mismatches.append({'case_id':identity,'stage':'semantic','expected':expected,'actual':actual,'output':semantic.get('output')})
        for name,score in label['utility_expected_only_for_dimensions'].items():
            actual_score=scored.get(name,{}).get('status');dimensions['labelled']+=1;dimensions['matches']+=actual_score==score
            comparison['labelled_utility_dimensions'].append({'dimension':name,'expected':score,'actual':actual_score})
            if actual_score!=score:mismatches.append({'case_id':identity,'stage':'utility','dimension':name,'expected':score,'actual':actual_score,'output':scored.get(name)})
        comparisons.append(comparison)
    usage=Counter();missing=0
    for rec in records:
        if not isinstance(rec.get('usage'),dict):missing+=1;continue
        for key in ('prompt_tokens','completion_tokens','total_tokens'):usage[key]+=rec['usage'].get(key,0)
    assessment={'schema':'policy-v2-fixed-review-assessment-v1','result':'INCONCLUSIVE','scope':'Author-labelled fixed review exploration, not full E1 or independent accuracy',
        'execution':summary,'comparison_counts':dict(counts),'utility_label_counts':dict(dimensions),
        'comparisons':comparisons,'mismatches':mismatches,'returned_models':sorted({str(r.get('model')) for r in records}),
        'returned_fingerprints':sorted({str(r.get('system_fingerprint')) for r in records}),
        'finish_reasons':dict(Counter(str(r.get('finish_reason')) for r in records)),
        'usage_totals':dict(usage),'usage_missing_records':missing,
        'maximum_prompt_tokens':max((r.get('usage') or {}).get('prompt_tokens',0) for r in records),
        'maximum_completion_tokens':max((r.get('usage') or {}).get('completion_tokens',0) for r in records),
        'no_new_generation_commit_or_effect':True,'independent_review':'NOT_REVIEWED_NOT_CLAIMED',
        'original_A2':'DENIED','original_E1':'INCONCLUSIVE','full_cases_completed':9,'gate_E':'OPEN','gate_F':'OPEN',
        'automatic_additional_batches':False,'source_sha256':{str(p.relative_to(ROOT.parents[1])).replace('\\','/'):digest(p)
            for p in (RUN/'summary.json',PACKAGE/'manifest.json',PACKAGE/'author-expectations.json',RUN/'execution/results.json',Path(__file__))}}
    destination=ROOT/'reports/policy-v2-real-assessment-20261006.json'
    destination.write_text(json.dumps(assessment,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in assessment.items() if k not in ('execution','source_sha256','mismatches')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
