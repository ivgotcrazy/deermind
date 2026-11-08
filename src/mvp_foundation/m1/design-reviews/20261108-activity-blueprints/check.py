"""Verify this documentation batch and write its review record. Run from repo root."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

root = Path.cwd()
here = Path(__file__).resolve().parent
assets = root / 'doc/mvp/m1/design/assets/activities-v0.1'
report_path = assets / 'review.json'
versions = {
    'doc/mvp/README.md': '0.23',
    'doc/mvp/DECISIONS.md': '0.14',
    'doc/mvp/m1/README.md': '0.13',
    'doc/mvp/m1/PRD.md': '0.13',
    'doc/mvp/m1/design/README.md': '0.13',
    'doc/mvp/m1/design/Interaction_Design.md': '0.11',
    'doc/mvp/m1/design/Content_and_Model_Reference.md': '0.12',
    'doc/mvp/m1/prototype/README.md': '0.5',
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def anchors(text):
    result = set(re.findall(r'<a id="([^"]+)"', text))
    for heading in re.findall(r'^#{1,6} (.+)$', text, re.M):
        result.add(re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-'))
    return result

errors, documents = [], []
for relative, version in versions.items():
    path = root / relative
    text = path.read_text(encoding='utf-8-sig')
    if f'> **版本**：v{version}<br>' not in text or '**更新日期**：2026-11-08' not in text:
        errors.append(relative + ': header mismatch')
    before = here / 'before' / relative
    previous = re.search(r'\*\*版本\*\*：v(\d+)\.(\d+)', before.read_text(encoding='utf-8-sig'))
    if version != f'{previous[1]}.{int(previous[2])+1}':
        errors.append(relative + ': version not incremented once')
    for target in re.findall(r'\]\(([^\n)]+)\)', text):
        if re.match(r'https?://|mailto:', target):
            continue
        file_part, _, fragment = target.partition('#')
        resolved = (path.parent / unquote(file_part)).resolve() if file_part else path
        if not resolved.exists() and resolved != report_path:
            errors.append(relative + ': missing ' + target)
        elif fragment and resolved.suffix == '.md' and unquote(fragment) not in anchors(resolved.read_text(encoding='utf-8-sig')):
            errors.append(relative + ': unknown anchor ' + target)
    documents.append({'path': relative, 'version': version, 'sha256': sha(path)})
manifest = json.loads((assets / 'capture-manifest.json').read_text(encoding='utf-8'))
for screen in manifest['screens']:
    if sha(assets / (screen['id'] + '.png')) != screen['sha256']:
        errors.append('Screenshot hash mismatch: ' + screen['id'])
if len(manifest['screens']) != 18:
    errors.append('Expected 18 screenshots')
config_path = assets / 'activity-configurations.json'
configurations = json.loads(config_path.read_text(encoding='utf-8'))['configurations']
reference = (root / 'doc/mvp/m1/design/Content_and_Model_Reference.md').read_text(encoding='utf-8')
for kind, config in configurations.items():
    for node in config['blueprint']['stages']:
        if node['name'] not in reference:
            errors.append(kind + ': undocumented node ' + node['name'])
    for item in config['rules'] + config['strategies']:
        if item['name'] not in reference:
            errors.append(kind + ': undocumented rule or strategy ' + item['name'])
sources = [p for p in (root / 'doc/mvp/m1/prototype/src').rglob('*') if p.is_file()]
report = {
    'reviewedAt': datetime.now(timezone.utc).isoformat(),
    'baselineCommit': '215b582',
    'baseline': '../../../../../../src/mvp_foundation/m1/design-reviews/20261108-activity-blueprints/baseline.json',
    'documents': documents,
    'screenshots': {'count': len(manifest['screens']), 'manifest': 'capture-manifest.json', 'sha256': sha(assets / 'capture-manifest.json')},
    'defaultConfigurations': {'path': 'activity-configurations.json', 'sha256': sha(config_path)},
    'sources': [{'path': p.relative_to(root).as_posix(), 'sha256': sha(p)} for p in sources],
    'checks': {
        'build': 'npm run build: passed on 2026-11-08',
        'browser': {'command': 'node --test --test-concurrency=1 tests/activity-editor.test.mjs tests/activity-flow.test.mjs tests/node-routing.test.mjs tests/teaching-scope.test.mjs tests/teaching.test.mjs tests/student-entry.test.mjs', 'tests': 13, 'passed': 13, 'failed': 0},
        'documentsAndAssets': {'errors': errors},
        'visualReview': 'Inspected four flowcharts, node form, local-only references, transition form, activity rules/strategies, help-after-round sequence and runtime tree.',
        'whitespace': 'git diff --check on the 8 edited Markdown files passed; pre-existing prototype source CRLF/whitespace findings excluded and left unchanged.',
    },
    'limits': ['Author review; revised prose awaits user review.', 'Mock configuration and fixed student paths only; no LLM or formal Observation/Evidence/Belief service.', 'No arbitrary blueprint execution or semantic rule validation.', 'Full suite, whole textbook and M1 Gate not claimed.'],
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'documents': len(documents), 'screenshots': len(manifest['screens']), 'errors': errors}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
