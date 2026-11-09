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
            for section in ['4.10','4.18','4.19','4.20']:
                pattern=rf'(?ms)^### {re.escape(section)} .*?(?=^### |^## |\Z)'
                assert re.search(pattern,text).group()==re.search(pattern,before).group().replace('／适用分项',''),section
        if rel.endswith('DECISIONS.md'):
            prior=before[before.index('## 2.'):].strip()
            current=text[text.index('## 2.'):text.index('## 27.')].strip()
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
result=dict(
 reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
 scope='M1 generation, method-aspect Belief, natural queries and deferred personal-evaluation correction; documentation only',
 documents=documents,localLinksChecked=links,linkErrors=errors,
 unchangedMermaidDiagrams=diagrams,unchangedImageReferences=screenshots,
 unchangedFrozenFiles=len(baseline['frozen']),unchangedPrototypeFiles=len(inventory),
 preserved=['Earlier decision entries 2-26','Evaluation v1.7','Content formulas, parameters, thresholds and existing numerical example','Prototype sources and existing screenshots','Original content extraction trial report'],
 numericalReference=dict(initial=p0,afterQuarter=p1,afterFifth=p2,quarterEvidenceCount=1,requiredQuarterEvidenceCount=2,teachingBetween=False),
 authorReview=['Runtime generation is required; no per-question approval','Method-aspect estimates share eligible parameters; targets retain actual coverage checks','Book browsing does not constrain dialogue; adopted course methods remain enforced','Personal evaluation correction is deferred; ordinary new evidence, processing retries and content maintenance remain','Implementation order covers the whole book; no new UI work required in this batch'],
 modelCalls=0,newScreenshots=0,
 notExecuted=['Browser regression','Production evaluation and event processing','Real Agent extraction or generation','Parameter calibration','Whole-book acceptance','Student effectiveness study'],
 result='PASS: document versions, links, preserved assets, numerical illustration and author scope review'
)
review.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in {'documents','authorReview'}},ensure_ascii=False,indent=2))
