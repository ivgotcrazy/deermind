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
    if rel.endswith('Content_and_Model_Reference.md'):
        for section in ['4.10', '4.18', '4.19', '4.20']:
            pattern = rf'(?ms)^### {re.escape(section)} .*?(?=^### |^## |\Z)'
            assert re.search(pattern, body).group() == re.search(pattern, before).group(), section
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
# Recompute the already adopted observation-only example, not new parameters.
p0, slip, guess = 0.50, 0.15, 0.25
def update(p, passed):
    a, b = ((1-slip), guess) if passed else (slip, (1-guess))
    return p*a/(p*a+(1-p)*b)
p1 = update(p0, True)
p2 = update(p1, True)
p3 = update(p2, True)
p_negative = update(p2, False)
for actual, expected in [(p1, .772727), (p2, .920382), (p3, .975189), (p_negative, .698068)]:
    assert abs(actual - expected) < 0.0000006, (actual, expected)
# This is a prose/specification review; no student events are simulated as real records.
result = dict(
    reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    scope='LC-03 and LC-04 student feedback and system task handoff; documentation only',
    baseline='src/mvp_foundation/m1/design-reviews/20261109-feedback-tasks/baseline.json',
    documents=documents, localLinksChecked=links, linkErrors=errors,
    unchangedMermaidDiagrams=diagrams,
    unchangedPrototypeSources=len(baseline['prototypeSources']),
    previousStudentScreenshotsHashVerified=len(captures), newScreenshots=0,
    numericalCheck=dict(parameters=dict(p0=p0, S=slip, G=guess), positive1=p1, positive2=p2, positive3=p3, afterNegative=p_negative, learningTransitionApplied=False),
    authorSemanticReview=[
        {'case':'E1 and E2', 'result':'Two distinct submissions; A has independent and explanation support plus one qualifying transfer; retention not yet observed; no copied success for B'},
        {'case':'Only answer versus steps without explanation', 'result':'Answer-only cannot identify method; valid steps can support independent execution without inferring understanding'},
        {'case':'Transfer background unknown', 'result':'Describe current table performance, not verified novel transfer'},
        {'case':'Partial evaluation failure', 'result':'Keep successful facts and valid revisions; mark incomplete results; do not fabricate mastery or student failure'},
        {'case':'Delayed task', 'result':'Use actual E2 performance time plus at least 7x24 hours; recheck necessity before invitation and execution'},
        {'case':'Defer or refuse', 'result':'Preserve existing next-day and new-basis-only rules; no new task identifiers to bypass refusal'},
        {'case':'Task acceptance and activity', 'result':'Acceptance is not execution; explicit start, no competing active leaf, retain task/activity/round relationship'},
        {'case':'E4 return', 'result':'Actual new submission updates applicable A components; evaluation checks goal, then task purpose; completion event is not student Evidence'},
        {'case':'Help or failure', 'result':'End round before help, retain untested status, new plan for confirmation; no automatic redoing due to processing failure'},
    ],
    remaining=['Engineering intake must record exact versions, existing prototype gaps and the first real implementation path', 'LC-01 Domain role and dependency constraints need implementation alignment', 'Application, complete student evaluation feedback and system task responses are not implemented by this batch'],
    limitations=['Author semantic review is not an executable integration test', 'Numbers only reproduce existing trial formulas, not parameter or learning-effect validation', 'No UI or screenshot changes', 'No LLM, evaluation or task service executed', 'No full-book modeling or Gate approval'])
review.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ['localLinksChecked', 'linkErrors', 'unchangedMermaidDiagrams', 'unchangedPrototypeSources', 'previousStudentScreenshotsHashVerified', 'numericalCheck']}, ensure_ascii=False))
