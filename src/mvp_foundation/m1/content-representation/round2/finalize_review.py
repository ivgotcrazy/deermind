"""Record author mapping review and measured aggregate evidence, not a quality estimator."""
from datetime import datetime,timezone
from pipeline import ROOT,read,save,digest

run=ROOT/'runs'/(ROOT/'latest-run.txt').read_text(encoding='utf-8').strip()
expectations={'C02':('TT-CHAIN',['ST-TWO','ST-COMBINE']),'C03':('TT-ERROR',[]),'C05':('TT-CHART',[]),'C06':('TT-SHAPE',[])}
rows=[]
for cid,(template,methods) in expectations.items():
    folder=run/cid;graph=read(folder/'graph.json');review=read(folder/'content-review.json');content=read(folder/'reviewed-content.json')
    assert graph['contentHash']==digest(content)
    tasks=[i for i in graph['instances'] if i['kind']=='TaskInstance'];solutions=[i for i in graph['instances'] if i['kind']=='SolutionInstance']
    assert [t['templateId'] for t in tasks]==[template]
    assert [s['templateId'] for s in solutions]==methods
    byid={e['id']:e for e in graph['elements']};assert len(byid)==len(graph['elements'])
    owners={i['id'] for i in graph['instances']}|{k['sourceId'] for k in graph['knowledgeBindings']}
    assert all(e['owner'] in owners for e in graph['elements'])
    for i in graph['instances']:
        for eid in i['contentRefs']:
            assert byid[eid]['owner']==i['id']
            assert byid[eid]['role']==('question' if i['kind']=='TaskInstance' else 'solution')
    before=read(folder/'map-request.json')
    for prefix in ['map-recovery','map-direct']:
        path=folder/(prefix+'-request.json')
        if path.exists():assert read(path)['logicalPayloadHash']==before['logicalPayloadHash']
    record=dict(reviewer='Codex author semantic review against source and existing catalog',reviewedAt=datetime.now(timezone.utc).isoformat(),status='accepted_for_this_trial',conclusion='本例核对后内容匹配正确；程序编号、题目/解法归属及来源检查通过。',taskTemplate=template,solutionTemplates=methods,contentHash=graph['contentHash'],limitation='Small known catalog. Author-corrected input for C02/C03/C05; not raw extraction success, full-book acceptance or learner assessment.')
    save(folder/'mapping-review.json',record)
    rows.append(dict(caseId=cid,rawJudgment=review['rawJudgment'],rawFormat=read(folder/'extract-result.json')['status'],correctionPaths=len(review['changes']),graphInstances=len(graph['instances']),mapping='author_accepted',taskTemplate=template,solutionTemplates=methods))
records=[read(p) for p in run.glob('*/*-result.json')]
usage=dict(inputTokens=sum(r.get('usage',{}).get('prompt_tokens',0) for r in records),outputTokens=sum(r.get('usage',{}).get('completion_tokens',0) for r in records))
reviews=[read(p) for p in run.glob('*/content-review.json')]
start=min(r['reviewWindowStart'] for r in reviews);end=max(r['reviewWindowEnd'] for r in reviews)
summary=dict(status='four_case_review_completed',cases=rows,modelHttpAttempts=sum(len(r['attempts']) for r in records),http200=sum(r.get('httpStatus')==200 for r in records),transportFailures=sum(a['status']=='transport_error' for r in records for a in r['attempts']),usage=usage,contentReviewWindow=dict(start=start,end=end,seconds=round((datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds(),1),includes='Author inspection, reasoning and correction-script writing for all four cases. Excludes later mapping/browser review. Not end-user correction time.'),boundaries=['No additional semantic calls or sample expansion','Original extraction remains unmodified','Source annotations such as cancellation strokes still not fully represented','No extracted standalone KC statements in these cropped cases; KC creation/mapping is not validated by empty lists'])
save(run/'final-summary.json',summary);save(ROOT/'summary.json',summary);print(__import__('json').dumps(summary,ensure_ascii=False))
