"""Validate the documentation batch; no application service is exercised."""
from pathlib import Path
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import subprocess
import unicodedata

batch = Path(__file__).parent
root = batch.resolve().parents[4]
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

errors = []
documents = []
links = diagrams = 0
for record in baseline['files']:
    rel = record['path']
    path = root / rel
    saved = batch / 'before' / rel
    assert digest(saved) == record['sha256'], rel
    before = saved.read_text(encoding='utf-8')
    body = path.read_text(encoding='utf-8')
    assert f'> **版本**：{record["new"]}<br>' in body, rel
    assert f'{record["old"]} → {record["new"]}' in body, rel
    for name in ['文档性质', '状态', '上游依据与基线', '维护责任', '评审记录', '写作规范', '更新日期', '修订说明']:
        assert f'> **{name}**：' in body, (rel, name)
    assert body.count('```') % 2 == 0, rel
    graphs = re.findall(r'```mermaid\s*\n(.*?)```', body, re.S)
    assert graphs == re.findall(r'```mermaid\s*\n(.*?)```', before, re.S), rel
    diagrams += len(graphs)
    assert re.findall(r'!\[[^\]]*\]\([^)]+\)', body) == re.findall(r'!\[[^\]]*\]\([^)]+\)', before), rel
    for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', body):
        if re.match(r'(https?://|mailto:)', href):
            continue
        part, _, anchor = unquote(href.strip('<>')).partition('#')
        target = (path.parent / part).resolve() if part else path
        links += 1
        if not target.exists() and target != review.resolve():
            errors.append((rel, href, 'missing file'))
        elif anchor and target.suffix.lower() == '.md' and anchor not in anchors(target):
            errors.append((rel, href, 'missing anchor'))
    columns = None
    in_code = False
    for line in body.splitlines():
        if line.startswith('```'):
            in_code = not in_code
        if in_code:
            continue
        if line.startswith('|'):
            size = len(re.split(r'(?<!\\)\|', line))
            if columns is not None and columns != size:
                errors.append((rel, line[:75], 'table columns'))
            columns = size
        else:
            columns = None
    documents.append(dict(path=rel, old=record['old'], version=record['new'], sha256=digest(path)))
assert not errors, json.dumps(errors, ensure_ascii=False, indent=2)
for record in baseline['prototypeSources']:
    assert digest(root / record['path']) == record['sha256'], record['path']
assert {p.relative_to(root).as_posix() for p in (root / 'doc/mvp/m1/prototype/src').rglob('*') if p.is_file()} == {r['path'] for r in baseline['prototypeSources']}
assets = root / 'doc/mvp/m1/design/assets/student-forest-v0.1'
captures = json.loads((assets / 'capture-manifest.json').read_text(encoding='utf-8'))['captures']
for capture in captures:
    assert digest(assets / capture['file']) == capture['sha256'], capture['file']
subprocess.run(['git', 'diff', '--check', '--', *[r['path'] for r in baseline['files']]], cwd=root, check=True)
result = dict(
    reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    scope='LC-02 course application and student adoption specification; documentation only',
    baseline='src/mvp_foundation/m1/design-reviews/20261109-course-application/baseline.json',
    documents=documents, localLinksChecked=links, linkErrors=errors,
    unchangedMermaidDiagrams=diagrams,
    unchangedPrototypeSources=len(baseline['prototypeSources']),
    previousStudentScreenshotsHashVerified=len(captures), newScreenshots=0,
    authorSemanticReview=[
        {'case': 'Saved without application', 'expected': 'No new selectable combination; previous applied result stays effective', 'result': 'consistent'},
        {'case': 'First application', 'expected': 'Applied book and target available to all trial students; space creation does not imply mastery', 'result': 'consistent'},
        {'case': 'Ordinary update of same combination', 'expected': 'Current references updated; past activities retain actual versions; no Evidence or Belief change', 'result': 'consistent'},
        {'case': 'Missing transfer criterion', 'expected': 'Course preparation gap blocks that formal evaluation, not all questions or reliable help', 'result': 'consistent'},
        {'case': 'No reserve question', 'expected': 'Generate, check, save then use; lack of stored question alone is not a block', 'result': 'consistent'},
        {'case': 'Retention interval not elapsed', 'expected': 'Personal condition distinct from missing course definition; no early retention claim', 'result': 'consistent'},
        {'case': 'Application or runtime failure', 'expected': 'Keep prior effective adoption; do not write student failure Evidence', 'result': 'consistent'},
    ],
    remaining=['LC-03 student feedback contract', 'LC-04 system task and activity result contract', 'Existing LC-01 Domain constraints require implementation alignment', 'Application UI operations not implemented in this batch'],
    limitations=['Semantic review is an author walkthrough, not executable integration tests', 'No UI, screenshot or algorithm changes', 'No LLM or application service execution', 'No full-book modeling or engineering Gate approval'])
review.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ['localLinksChecked', 'linkErrors', 'unchangedMermaidDiagrams', 'unchangedPrototypeSources', 'previousStudentScreenshotsHashVerified']}, ensure_ascii=False))
