"""Check the student documentation batch; this is not a learning-quality evaluation."""
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import subprocess
import unicodedata

base=Path(__file__).resolve().parent
root=base.parents[4]
assets=root/'doc/mvp/m1/design/assets/student-forest-v0.1'
versions={
 'doc/mvp/m1/PRD.md':('v0.16','v0.17'),
 'doc/mvp/m1/design/Interaction_Design.md':('v0.14','v0.15'),
 'doc/mvp/m1/design/Content_and_Model_Reference.md':('v0.15','v0.16'),
 'doc/mvp/m1/design/README.md':('v0.16','v0.17'),
 'doc/mvp/m1/README.md':('v0.16','v0.17'),
 'doc/mvp/README.md':('v0.26','v0.27'),
 'doc/mvp/DECISIONS.md':('v0.17','v0.18'),
 'doc/mvp/m1/prototype/README.md':('v0.5','v0.6'),
}
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def anchors(p):
 body=re.sub(r'```.*?```','',p.read_text(encoding='utf-8'),flags=re.S)
 used={};result=set(re.findall(r'<a\s+id="([^"]+)"',body))
 for title in re.findall(r'^#{1,6}\s+(.+?)\s*$',body,re.M):
  title=re.sub(r'<[^>]*>','',title).strip().lower()
  key=''.join(c for c in title if c in '_- ' or unicodedata.category(c)[0] in 'LN' or unicodedata.category(c)=='Mn').replace(' ','-')
  n=used.get(key,0);used[key]=n+1;result.add(key if not n else key+'-'+str(n))
 return result

baseline=json.loads((base/'baseline.json').read_text(encoding='utf-8'))
for r in baseline['files']: assert digest(base/'before'/r['path'])==r['sha256'],r['path']
for r in baseline['prototypeSources']: assert digest(root/r['path'])==r['sha256'],'UI changed: '+r['path']
assert {p.relative_to(root).as_posix() for p in (root/'doc/mvp/m1/prototype/src').rglob('*') if p.is_file()}=={r['path'] for r in baseline['prototypeSources']}
errors=[];documents=[];links=0;diagrams=0
review_path=assets/'review.json'
for file,(old,new) in versions.items():
 p=root/file;body=p.read_text(encoding='utf-8');before=(base/'before'/file).read_text(encoding='utf-8')
 assert f'> **版本**：{new}<br>' in body,file
 assert f'{old} → {new}' in body,file
 assert '> **更新日期**：2026-11-09<br>' in body,file
 for name in ['文档性质','状态','上游依据与基线','维护责任','评审记录','写作规范','修订说明']:
  assert f'> **{name}**：' in body,(file,name)
 assert body.count('```')%2==0,file
 old_graphs=re.findall(r'```mermaid\s*\n(.*?)```',before,re.S)
 graphs=re.findall(r'```mermaid\s*\n(.*?)```',body,re.S)
 assert old_graphs==graphs,'Changed diagram requires a new render: '+file
 diagrams+=len(graphs)
 for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',body):
  if re.match(r'(https?://|mailto:)',href):continue
  part,_,anchor=unquote(href.strip('<>')).partition('#')
  target=(p.parent/part).resolve() if part else p
  links+=1
  if not target.exists() and target!=review_path:errors.append([file,href,'missing file'])
  elif anchor and target.suffix.lower()=='.md' and anchor not in anchors(target):errors.append([file,href,'missing anchor'])
 # Parallel table rows must have a stable column count.
 count=None;in_code=False
 for line in body.splitlines():
  if line.startswith('```'):in_code=not in_code
  if in_code:continue
  if line.startswith('|'):
   columns=len(re.split(r'(?<!\\)\|',line))
   if count is not None and columns!=count:errors.append([file,line[:75],'table column count'])
   count=columns
  else:count=None
 documents.append(dict(path=file,old=old,version=new,sha256=digest(p)))
manifest=json.loads((assets/'capture-manifest.json').read_text(encoding='utf-8'))
assert len(manifest['captures'])==13
assert not manifest['errors'] and not manifest['apiCalls']
for r in manifest['sources']:assert digest(root/r['path'])==r['sha256'],r['path']
body=(root/'doc/mvp/m1/design/Interaction_Design.md').read_text(encoding='utf-8')
for r in manifest['captures']:
 p=assets/r['file'];assert digest(p)==r['sha256'],r['file']
 assert p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
 assert f'(assets/student-forest-v0.1/{r["file"]})' in body,r['file']
 assert r['step'] in body,r['step']
assert not errors,json.dumps(errors,ensure_ascii=False,indent=2)
subprocess.run(['git','diff','--check','--',*versions],cwd=root,check=True)
result=dict(version='0.1',reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
 scope='Confirmed student single-page interaction, activity forest, history navigation and book-context documentation; no UI change',
 baseline='src/mvp_foundation/m1/design-reviews/20261109-student-forest/baseline.json',
 captureScript=manifest['sourceScript'],checkScript=Path(__file__).relative_to(root).as_posix(),
 documents=documents,localLinksChecked=links,linkErrors=errors,unchangedMermaidDiagrams=diagrams,
 screenshotsVerified=13,unchangedPrototypeSourceFiles=len(baseline['prototypeSources']),
 visualReview=dict(images=[r['id'] for r in manifest['captures']],checks=['Student current path stays separate from history selection','Book browsing and explicit references differ','Normal empty entry and isolated seeded demo are distinct','Pause, return, end and round-help boundaries remain visible']),
 checksExecutedThisBatch=[
  dict(command='node --test --test-concurrency=1 tests/student-activity-fixture.test.mjs tests/student-activity-directory.test.mjs tests/student-book-context.test.mjs tests/student-activity-heading.test.mjs tests/student-entry.test.mjs tests/activity-flow.test.mjs',cwd='doc/mvp/m1/prototype',passed=29,failed=0),
  dict(command='node '+manifest['sourceScript'],result='13 screenshots; no API calls or browser errors'),
  dict(command='python '+Path(__file__).relative_to(root).as_posix(),result='Document versions, local links, image hashes, tables and unchanged source checked'),
 ],
 mainFlowReview=dict(location='doc/mvp/m1/README.md#6',
  alreadyDecidedAlignment=['LC-01: implement the existing KC Task/composite Task contract'],
  necessaryProductHandoffs=['LC-02: applied course output and student selectable availability','LC-03: evaluation output to student feedback','LC-04: system task to activity and subsequent result'],
  excluded=['Differences between mock datasets','Absence of a shared DB or LLM','New peripheral UI or reopening the agreed algorithm']),
 limitations=['Uses existing prototype build; no new build or UI implementation in this batch','No real model, teaching, Evidence or probability quality validation','No full-book modeling or M1 Gate approval'])
review_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(documents=len(documents),links=links,screenshots=13,unchangedUIFiles=len(baseline['prototypeSources']),unchangedDiagrams=diagrams,errors=errors),ensure_ascii=False))
