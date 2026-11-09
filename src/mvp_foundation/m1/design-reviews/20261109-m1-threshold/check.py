"""Check this documentation-only batch; no runtime or model tests are claimed."""
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta
import hashlib, json, re, subprocess, unicodedata

batch = Path(__file__).resolve().parent
root = batch.parents[4]
baseline = json.loads((batch / 'baseline.json').read_text(encoding='utf-8'))
review = batch / 'review.json'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def anchors(path):
    body = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
    result = set(re.findall(r'<a\s+id="([^"]+)"', body))
    used = {}
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*$', body, re.M):
        title = re.sub(r'<[^>]*>', '', title).strip().lower()
        key = ''.join(c for c in title if c in '_- ' or unicodedata.category(c)[0] in 'LN' or unicodedata.category(c) == 'Mn').replace(' ', '-')
        n = used.get(key, 0)
        used[key] = n + 1
        result.add(key if not n else key + '-' + str(n))
    return result


errors=[]
documents=[]
links=diagrams=screenshots=0
records=baseline['files']+baseline['newFiles']
for record in records:
    rel=record['path']; path=root/rel
    text=path.read_text(encoding='utf-8')
    assert f'> **版本**：{record["new"]}<br>' in text, rel
    for name in ['文档性质','状态','维护责任','评审记录','写作规范','更新日期','修订说明']:
        assert f'> **{name}**：' in text,(rel,name)
    assert '> **更新日期**：2026-11-09' in text,rel
    assert f'{record["old"]} → {record["new"]}' in text,rel
    assert text.count('```') % 2 == 0,rel
    if 'sha256' in record:
        saved=batch/'before'/rel
        assert digest(saved)==record['sha256'],rel
        before=saved.read_text(encoding='utf-8')
        graphs=re.findall(r'```mermaid\s*\n(.*?)```',text,re.S)
        assert graphs==re.findall(r'```mermaid\s*\n(.*?)```',before,re.S),rel
        diagrams+=len(graphs)
        images=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text)
        assert images==re.findall(r'!\[[^\]]*\]\(([^)]+)\)',before),rel
        screenshots+=len(images)
        if rel.endswith('Content_and_Model_Reference.md'):
            formulas=r'\\\[(.*?)\\\]'
            assert re.findall(formulas,text,re.S)==re.findall(formulas,before,re.S),'numerical formulas'
            for section in ['4.19']:
                pattern=rf'(?ms)^### {re.escape(section)} .*?(?=^### |^## |\Z)'
                assert re.search(pattern,text).group()==re.search(pattern,before).group().replace('／适用分项',''),section
        if rel.endswith('DECISIONS.md'):
            prior=before[before.index('## 2.'):].strip()
            current=text[text.index('## 2.'):text.index('## 28.')].strip()
            assert prior==current,'prior decisions changed'
    for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',text):
        if re.match(r'(https?://|mailto:)',href): continue
        part,_,anchor=unquote(href.strip('<>')).partition('#')
        target=(path.parent/part).resolve() if part else path
        links+=1
        if not target.exists() and target!=review:
            errors.append((rel,href,'missing file'))
        elif anchor and target.suffix.lower()=='.md' and anchor not in anchors(target):
            errors.append((rel,href,'missing anchor'))
    columns=None; code=False
    for line in text.splitlines():
        if line.startswith('```'): code=not code
        if code: continue
        if line.startswith('|'):
            size=len(re.split(r'(?<!\\)\|',line))
            if columns is not None and columns!=size:
                errors.append((rel,line[:75],'table columns'))
            columns=size
        else: columns=None
    documents.append(dict(path=rel,old=record['old'],version=record['new'],sha256=digest(path)))
assert not errors,json.dumps(errors,ensure_ascii=False,indent=2)
for record in baseline['frozen']:
    assert digest(root/record['path'])==record['sha256'],record['path']
prototype=root/'doc/mvp/m1/prototype'
excluded={'node_modules','dist','.tmp','.vite','test-results'}
inventory={p.relative_to(root).as_posix() for p in prototype.rglob('*') if p.is_file() and not(set(p.relative_to(prototype).parts)&excluded)}
assert inventory=={r['path'] for r in baseline['frozen'] if r['path'].startswith('doc/mvp/m1/prototype/')},'prototype inventory'
subprocess.run(['git','-c','core.whitespace=cr-at-eol','diff','--check'],cwd=root,check=True)
p0=.5; slip=.15; guess=.25
positive=lambda p:p*(1-slip)/(p*(1-slip)+(1-p)*guess)
p1=positive(p0);p2=positive(p1)
assert abs(p1-.772727)<.000001 and abs(p2-.920382)<.000001
# Illustration of coverage only; this is not a production evaluator.
evidence=[dict(ratio='1/4',method='A',aspect='independent'),dict(ratio='1/5',method='A',aspect='independent')]
assert len({(e['method'],e['aspect']) for e in evidence})==1
assert sum(e['ratio']=='1/4' for e in evidence)==1
# Reference checks only, not the production algorithm or a calibrated learner model.
def status(p_obs, eligible=True):
    if not eligible or p_obs is None: return 'pending'
    return 'met' if p_obs >= .9 else 'needs_support'
assert status(.9) == 'met' and status(.899999) == 'needs_support'
assert status(.5, False) == 'pending'
assert status(p1) == 'needs_support' and status(p2) == 'met'
negative=lambda p:p*slip/(p*slip+(1-p)*(1-guess))
p3=negative(p2);p4=positive(p3);p5=positive(p4)
assert [status(p) for p in [p2,p3,p4,p5]] == ['met','needs_support','needs_support','met']
assert [round(p,6) for p in [p3,p4,p5]] == [.698068,.887143,.963934]
# E2: independent, understanding, transfer, retention. E4 adds one retention observation.
assert [status(p) for p in [p2,p2,p1,None]] == ['met','met','needs_support','pending']
assert [status(p) for p in [positive(p2),positive(p2),p1,p1]] == ['met','met','needs_support','needs_support']
# L crossing is a prediction; the observed probability remains the target input.
assert .89 + (1-.89)*.2 > .9 and status(.89) == 'needs_support'
content=(root/'doc/mvp/m1/design/Content_and_Model_Reference.md').read_text(encoding='utf-8')
assert 'θ=0.90' in content and 'p_obs≥0.90' in content
assert '本例前三项达到' not in content and '本例目标四项满足' not in content
validation=(root/'doc/mvp/m1/validation/Validation_Plan.md').read_text(encoding='utf-8')
assert '0.887143→0.963934' in validation
engineering=(root/'doc/mvp/m1/engineering/README.md').read_text(encoding='utf-8')
assert '工程设计属于工程阶段' in engineering

result=dict(
 reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
 scope='M1 global 0.90 threshold, Evolution deferral and engineering stage boundary; documentation only',
 documents=documents,localLinksChecked=links,linkErrors=errors,
 unchangedMermaidDiagrams=diagrams,unchangedImageReferences=screenshots,
 unchangedFrozenFiles=len(baseline['frozen']),unchangedPrototypeFiles=len(inventory),
 preserved=['Earlier decision entries 2-27','Evaluation v1.7 and v1.8','Belief update formulas, shared parameters and existing numerical example','Prototype sources and existing screenshots','Original content extraction trial report'],
 numericalReference=dict(initial=p0,afterQuarter=p1,afterFifth=p2,quarterEvidenceCount=1,globalThreshold=.9,recovery=[p2,p3,p4,p5],teachingBetween=False),
 authorReview=['One global threshold, evaluated separately per method and aspect; no averaging','Eligible evidence required; prior and L-only prediction cannot imply measured mastery','Fixed-count acceptance and extra recovery rules replaced; ordinary negative and positive evidence update the same estimate','E2 transfer and E4 retention remain below threshold; feedback and task outcomes updated','Evolution compatibility and migration deferred to M2/M3; append-only facts retained','Engineering design is engineering; no engineering design document or production code created in this batch'],
 modelCalls=0,newScreenshots=0,
 notExecuted=['Browser regression','Production evaluation and event processing','Real Agent extraction or generation','Parameter calibration','Whole-book acceptance','Student effectiveness study'],
 result='PASS: document versions, links, preserved assets, numerical illustration and author scope review'
)
review.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'documents','authorReview'}},ensure_ascii=False,indent=2))
