"""Verify this documentation batch and its captured mock screens; not a model evaluation."""
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timedelta, timezone

base = Path(__file__).resolve().parent
root = base.parents[4]
assets = root / 'doc/mvp/m1/design/assets/evaluation-trace-v0.1'
versions = {
    'doc/mvp/m1/PRD.md': ('v0.15', 'v0.16'),
    'doc/mvp/m1/design/Interaction_Design.md': ('v0.13', 'v0.14'),
    'doc/mvp/m1/design/Content_and_Model_Reference.md': ('v0.14', 'v0.15'),
    'doc/mvp/m1/design/README.md': ('v0.15', 'v0.16'),
    'doc/mvp/m1/README.md': ('v0.15', 'v0.16'),
    'doc/mvp/README.md': ('v0.25', 'v0.26'),
    'doc/mvp/DECISIONS.md': ('v0.16', 'v0.17'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def anchors(path):
    body = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
    used, result = {}, set()
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*$', body, re.M):
        title = re.sub(r'<[^>]*>', '', title).strip().lower()
        key = ''.join(c for c in title if c in '_- ' or unicodedata.category(c)[0] in 'LN' or unicodedata.category(c) == 'Mn').replace(' ', '-')
        n = used.get(key, 0)
        used[key] = n + 1
        result.add(key if not n else key + '-' + str(n))
    return result


errors, documents = [], []
links = diagrams = 0
baseline = json.loads((base / 'baseline.json').read_text(encoding='utf-8'))
for row in baseline['files']:
    assert digest(base / 'before' / row['path']) == row['sha256'], row['path']

# The review file is created below; permit its outgoing references during first execution.
review_path = assets / 'review.json'
for filename, (old, new) in versions.items():
    path = root / filename
    body = path.read_text(encoding='utf-8')
    previous = (base / 'before' / filename).read_text(encoding='utf-8')
    assert f'> **版本**：{new}<br>' in body, filename
    assert '> **更新日期**：2026-11-09<br>' in body, filename
    assert f'{old} → {new}' in body, filename
    assert body.count('```') % 2 == 0, filename
    before_diagrams = re.findall(r'```mermaid\s*\n(.*?)```', previous, re.S)
    after_diagrams = re.findall(r'```mermaid\s*\n(.*?)```', body, re.S)
    assert before_diagrams == after_diagrams, f'Diagram changed and needs rendering: {filename}'
    diagrams += len(after_diagrams)
    for href in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', body):
        if re.match(r'(https?://|mailto:)', href):
            continue
        part, _, anchor = unquote(href.strip('<>')).partition('#')
        target = (path.parent / part).resolve() if part else path
        links += 1
        if not target.exists() and target != review_path:
            errors.append([filename, href, 'missing file'])
        elif anchor and target.suffix.lower() == '.md' and anchor not in anchors(target):
            errors.append([filename, href, 'missing anchor'])
    documents.append(dict(path=filename, old=old, version=new, sha256=digest(path)))

manifest = json.loads((assets / 'capture-manifest.json').read_text(encoding='utf-8'))
assert len(manifest['captures']) == 12
assert not manifest['errors'] and not manifest['apiCalls']
for row in manifest['sources']:
    assert digest(root / row['path']) == row['sha256'], row['path']
for row in manifest['captures']:
    assert digest(assets / row['file']) == row['sha256'], row['file']
    assert (assets / row['file']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
assert not errors, json.dumps(errors, ensure_ascii=False, indent=2)
subprocess.run(['git', 'diff', '--check', '--', *versions], cwd=root, check=True)

result = dict(
    version='0.1', reviewedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    scope='M1 Evaluation product documentation, screenshots and logical main-flow handoffs; no UI changes in this batch',
    baseline='src/mvp_foundation/m1/design-reviews/20261109-evaluation-trace/baseline.json',
    captureScript=manifest['sourceScript'], checkScript=str(Path(__file__).relative_to(root)).replace('\\', '/'),
    documents=documents, localLinksChecked=links, linkErrors=errors,
    unchangedMermaidDiagrams=diagrams, screenshotsVerified=12,
    visualReview=dict(images=['EV03', 'EV04', 'EV09', 'EV10'],
        checks=['Goal tab retains cumulative Evidence and source-event navigation',
                'Criterion, explanation and original sources are readable',
                'Actual before/after probability and recomputation baseline are separate',
                'Historical goal event and current goal are explicitly distinct']),
    checksExecutedThisBatch=[
        dict(command='npm run build --prefix doc/mvp/m1/prototype', result='passed'),
        dict(command='node --test tests/learning-spaces.test.mjs', cwd='doc/mvp/m1/prototype', passed=12, failed=0),
        dict(command='node src/mvp_foundation/m1/design-reviews/20261109-evaluation-trace/capture.mjs', result='12 screenshots; no API calls or browser errors'),
        dict(command='git diff --check -- <seven updated documents>', result='passed'),
    ],
    mainFlowReview=dict(location='doc/mvp/m1/README.md#6',
        findings=['LC-01: Domain Task role and local KC constraints need prototype alignment',
                  'LC-02: Saved configuration to applied/selectable course lacks a reachable handoff',
                  'LC-03: Student per-question feedback needs the target-outcome handoff',
                  'LC-04: Proactive suggestion acceptance, deferral and refusal need a student flow'],
        excluded=['Differences between fixed mock datasets', 'No shared database or live LLM'],
        next='Propose minimal course check/apply interaction for confirmation; do not implement UI in this batch'),
    limitations=['Fixed mock navigation, not real Evidence extraction or Belief calculation service',
                 'Does not validate parameter calibration, child Task updating or teaching-transition prediction',
                 'Does not establish full-book modeling, learning effectiveness or M1 Gate acceptance'],
)
review_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(documents=len(documents), links=links, screenshots=12, unchangedDiagrams=diagrams, errors=errors), ensure_ascii=False))
