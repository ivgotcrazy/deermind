"""Check this approved revision against its saved pre-edit workspace."""
import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from urllib.parse import unquote

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[5]
assets = root / 'doc/mvp/m1/design/assets/domain-model-v0.1'
versions = json.loads((assets / 'document-versions.json').read_text(encoding='utf-8'))
baseline = json.loads((args.baseline / 'manifest.json').read_text(encoding='utf-8'))
errors, local_links, anchor_count = [], 0, 0


@cache
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@cache
def anchors(path):
    text = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
    result, counts = set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text)), {}
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*$', text, re.M):
        title = re.sub(r'<[^>]*>', '', title).lower().strip()
        key = ''.join(c for c in title if c in '_- ' or unicodedata.category(c)[0] in 'LN' or unicodedata.category(c) == 'Mn').replace(' ', '-')
        count = counts.get(key, 0)
        counts[key] = count + 1
        result.add(key if not count else f'{key}-{count}')
    return result


for entry in versions:
    path = root / entry['path']
    text = path.read_text(encoding='utf-8')
    if f'> **版本**：{entry["after"]}' not in text:
        errors.append(f'Wrong version: {entry["path"]}')
    if entry['before'] == entry['after']:
        errors.append(f'No version increment: {entry["path"]}')
    # Frozen decision history and reassessment citations keep their original baselines.
    if path.name == 'DECISIONS.md':
        text = text.split('## 68.', 1)[1]
    if path.name == 'DeerMind_Learning_Model_Reassessment.md':
        text = text.split('\n## ', 1)[0]
    for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', text):
        if re.match(r'(https?://|mailto:)', href):
            continue
        name, _, fragment = unquote(href.strip('<>')).partition('#')
        target = (path.parent / name).resolve() if name else path
        local_links += 1
        if target == assets / 'review.json':
            continue  # Written by this check below.
        if not target.exists():
            errors.append(f'Missing link: {entry["path"]} -> {href}')
        elif fragment and target.suffix == '.md':
            anchor_count += 1
            if fragment not in anchors(target):
                errors.append(f'Missing anchor: {entry["path"]} -> {href}')

covered = {entry[key] for entry in versions for key in ('path', 'previousPath')}
for name, digest in baseline.items():
    path = root / name
    if name.startswith('doc/') and name.endswith('.md') and name not in covered:
        if not path.exists() or sha(path) != digest:
            errors.append(f'Unregistered document change: {name}')

capture = json.loads((assets / 'capture-manifest.json').read_text(encoding='utf-8'))
for screen in capture['screens']:
    if sha(assets / screen['file']) != screen['sha256']:
        errors.append(f'Screenshot hash mismatch: {screen["file"]}')

diagrams = json.loads((assets / 'diagram-render.json').read_text(encoding='utf-8'))['diagrams']
for diagram in diagrams:
    source = (root / diagram['document']).read_text(encoding='utf-8')
    graph = re.findall(r'```mermaid\s*\n(.*?)```', source, re.S)[diagram['index'] - 1].strip()
    if hashlib.sha256(graph.encode()).hexdigest() != diagram['sourceSha256']:
        errors.append(f'Diagram source changed after rendering: {diagram["id"]}')
    if not all((assets / (diagram['id'] + ext)).exists() for ext in ('.png', '.svg')):
        errors.append(f'Diagram output missing: {diagram["id"]}')

content_path = Path('doc/mvp/m1/design/Content_and_Model_Reference.md')
before = (args.baseline / 'before' / content_path).read_text(encoding='utf-8')
after = (root / content_path).read_text(encoding='utf-8')


def numeric_contract(text):
    section = text.split('### 4.18', 1)[1].split('### 4.21', 1)[0]
    return {
        'formulas': re.findall(r'\\\[.*?\\\]', section, re.S),
        'parameter_rows': re.findall(r'^\| (?:p0|S|G|L) \|.*$', section, re.M),
        'numbers': re.findall(r'\b0\.\d+\b', section),
    }


numeric_unchanged = numeric_contract(before) == numeric_contract(after)
if not numeric_unchanged:
    errors.append('Numeric contract changed')
catalog_path = Path('doc/mvp/m1/engineering/README.md')


def operation_ids(text):
    section = text.split('## 5.', 1)[1].split('## 6.', 1)[0]
    return re.findall(r'^\| `([a-z_]+\.[a-z_]+)`', section, re.M)


old_ops = operation_ids((args.baseline / 'before' / catalog_path).read_text(encoding='utf-8'))
new_ops = operation_ids((root / catalog_path).read_text(encoding='utf-8'))
if old_ops != new_ops or len(new_ops) != 9:
    errors.append('AI Operation catalog identities changed')

log = (assets / 'tests.log').read_text(encoding='utf-8-sig')
test_counts = {k: int(re.search(rf'^# {k} (\d+)$', log, re.M).group(1)) for k in ('tests', 'pass', 'fail', 'skipped')}
if test_counts != {'tests': 54, 'pass': 54, 'fail': 0, 'skipped': 0}:
    errors.append('Unexpected regression result')
changed = []
for name, digest in baseline.items():
    path = root / name
    if not path.exists() or sha(path) != digest:
        changed.append(name)
hashes = {entry['path']: sha(root / entry['path']) for entry in versions}
for path in (root / 'doc/mvp/m1/prototype/src').rglob('*'):
    if path.is_file():
        hashes[path.relative_to(root).as_posix()] = sha(path)
(assets / 'reviewed-files.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
result = {
    'checkedAt': datetime.now(timezone.utc).isoformat(),
    'status': 'passed' if not errors else 'failed',
    'scope': 'Approved Domain model revision; documents and browser mock only',
    'documents': len(versions), 'localLinks': local_links, 'anchors': anchor_count,
    'screenshots': len(capture['screens']), 'renderedDiagrams': len(diagrams),
    'numericContractUnchanged': numeric_unchanged, 'aiOperationIds': new_ops,
    'regression': test_counts,
    'tests': 'Default 11-file npm test suite; Edge browser; tests.log',
    'build': 'npm run build; see build.log',
    'baselineChangedPaths': changed,
    'preservation': 'Compared against pre-edit workspace including 14 existing dirty documents. Frozen experiments and historical prototypes unchanged.',
    'manualReview': 'RV01-RV11 checked within stated scope; screenshots and six diagrams visually inspected.',
    'limitations': ['No LLM calls or real teaching/evidence extraction', 'Related-Task evidence attribution reviewed in specification, not claimed as implemented', 'No production migration or historical recalculation', 'Frozen historical import tests and unchanged student-specific suite not rerun'],
    'userReview': 'pending', 'errors': errors,
}
(assets / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('status', 'documents', 'localLinks', 'anchors', 'screenshots', 'renderedDiagrams', 'errors')}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
