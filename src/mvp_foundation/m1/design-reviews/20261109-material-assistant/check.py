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
assets = root / 'doc/mvp/m1/design/assets/material-assistant-v0.1'
review = assets / 'review.json'
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
links = diagrams = screenshots = 0
records = baseline['files']
for record in records:
    rel = record['path']
    path = root / rel
    body = path.read_text(encoding='utf-8')
    assert f'> **版本**：{record["new"]}<br>' in body, rel
    for name in ['文档性质', '状态', '维护责任', '评审记录', '写作规范', '更新日期', '修订说明']:
        assert f'> **{name}**：' in body, (rel, name)
    assert '> **更新日期**：2026-11-09' in body, rel
    assert body.count('```') % 2 == 0, rel
    if record['old']:
        saved = batch / 'before' / rel
        assert digest(saved) == record['sha256'], rel
        before = saved.read_text(encoding='utf-8')
        assert f'{record["old"]} → {record["new"]}' in body, rel
        graphs = re.findall(r'```mermaid\s*\n(.*?)```', body, re.S)
        assert graphs == re.findall(r'```mermaid\s*\n(.*?)```', before, re.S), rel
        diagrams += len(graphs)
        image_pattern = r'!\[[^\]]*\]\(([^)]+)\)'
        screenshots += len(re.findall(image_pattern, body))
        if rel.endswith('Content_and_Model_Reference.md'):
            for section in ['4.10', '4.18', '4.19', '4.20']:
                pattern = rf'(?ms)^### {re.escape(section)} .*?(?=^### |^## |\Z)'
                assert re.search(pattern, body).group() == re.search(pattern, before).group(), section
            formulas = r'\\\[(.*?)\\\]'
            assert re.findall(formulas, body, re.S) == re.findall(formulas, before, re.S), 'formulas changed'
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
for collection in ['prototypeSources', 'frozenAssets']:
    for record in baseline[collection]:
        assert digest(root / record['path']) == record['sha256'], record['path']
# Prototype inventory includes configuration, tests and source, not generated/dependency folders.
prototype = root / 'doc/mvp/m1/prototype'
excluded = {'node_modules', 'dist', 'test-results', '.vite'}
inventory = {p.relative_to(root).as_posix() for p in prototype.rglob('*') if p.is_file() and p != prototype / 'README.md' and not (set(p.relative_to(prototype).parts) & excluded)}
assert inventory == {r['path'] for r in baseline['prototypeSources']}, 'prototype inventory changed'
package = json.loads((prototype / 'package.json').read_text(encoding='utf-8'))
all_tests = {p.relative_to(prototype).as_posix() for p in (prototype / 'tests').glob('*.test.mjs')}
current_tests = set(re.findall(r'tests/[\w-]+\.test\.mjs', package['scripts']['test']))
history_tests = set(re.findall(r'tests/[\w-]+\.test\.mjs', package['scripts']['test:previous-import-ui']))
unlisted_tests = all_tests-current_tests-history_tests
assert (len(all_tests), len(current_tests), len(history_tests), len(unlisted_tests)) == (24, 10, 5, 9)
engineering = (root/'doc/mvp/m1/engineering/README.md').read_text(encoding='utf-8')
assert set(re.findall(r'tests/[\w-]+\.test\.mjs', engineering)) == unlisted_tests
subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'diff', '--check', '--', *[r['path'] for r in records]], cwd=root, check=True)

manifest = json.loads((assets / 'capture-manifest.json').read_text(encoding='utf-8'))
assert len(manifest['captures']) == 15
assert manifest['errors'] == [] and manifest['modelCalls'] == 0
assert manifest['sources'] == baseline['prototypeSources']
for shot in manifest['captures']:
    assert digest(assets / shot['file']) == shot['sha256'], shot['id']
tap = (batch / 'browser-tests.tap').read_text(encoding='utf-8')
assert '# tests 17' in tap and '# pass 17' in tap and '# fail 0' in tap
result = dict(
    reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    scope='Textbook assistant conversation, references, candidate verification and adoption; documentation and screenshots only',
    baseline=str((batch / 'baseline.json').relative_to(root)),
    documents=documents, localLinksChecked=links, linkErrors=errors,
    unchangedMermaidDiagrams=diagrams, imageReferencesChecked=screenshots,
    unchangedPrototypeFiles=len(baseline['prototypeSources']), unchangedFrozenAssets=len(baseline['frozenAssets']),
    newScreenshots=len(manifest['captures']), modelCalls=0,
    browserTests=dict(tests=17, passed=17, failed=0, log=str((batch/'browser-tests.tap').relative_to(root))),
    visualReview=['TA04: two solutions, scoped quote and candidate actions', 'TA06: continued correction and reload', 'TA09: chapter methods retained as separate operation; no KC inferred from absent links', 'TA10: three rendered charts, full-height candidate capture', 'TA13: missing attachment requested rather than invented'],
    testInventory=dict(total=len(all_tests), current=len(current_tests), historical=len(history_tests), unlisted=sorted(unlisted_tests)),
    authorSemanticReview=[
        'Persistent import dialogue and explicit references; browsing does not silently retarget corrections',
        'Pending, superseded, adopted and discarded candidates; source version checked before adoption',
        'Adoption only changes parsed content; Domain intake and chapter association remain explicit and separate',
        'No manual content editor; metadata and chapter method forms retain their separate roles',
        'Mock supplement records filenames only, not uploads or recognition; production Agent behavior remains unverified',
        'Evaluation formulas, protected specification sections and historic experiment assets unchanged'
    ],
    notExecuted=['Real Agent correction', 'Probability calibration', 'Whole-book modeling acceptance', 'Student effectiveness study'],
    result='PASS: documentation checks, fixed-mock browser regression and screenshot review'
)
review.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'documents','authorSemanticReview','testInventory','visualReview'}}, ensure_ascii=False, indent=2))
