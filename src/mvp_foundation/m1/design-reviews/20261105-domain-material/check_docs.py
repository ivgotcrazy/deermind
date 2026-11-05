from pathlib import Path
from urllib.parse import unquote
from hashlib import sha256
import json, re, unicodedata, datetime

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
ASSETS = ROOT / 'doc/mvp/m1/design/assets/domain-material-v0.1'
baseline = json.loads((BASE/'baseline.json').read_text(encoding='utf-8-sig'))
errors, versions, local_links = [], [], 0

def anchors(text):
    values = set()
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M):
        title = re.sub(r'<[^>]+>', '', title).lower()
        title = ''.join(c for c in title if c in '-_' or not unicodedata.category(c).startswith(('P','S')))
        values.add(title.replace(' ', '-'))
    return values

for entry in baseline['files']:
    path = ROOT / entry['path']
    before = (BASE/'before'/entry['path']).read_text(encoding='utf-8-sig')
    text = path.read_text(encoding='utf-8-sig')
    old = re.search(r'\*\*版本\*\*：v([\d.]+)', before).group(1)
    new = re.search(r'\*\*版本\*\*：v([\d.]+)', text).group(1)
    if new == old: errors.append({'path':entry['path'],'error':'version not incremented'})
    for field in ['文档性质','状态','上游依据与基线','维护责任','评审记录','写作规范','更新日期','修订说明']:
        if f'**{field}**：' not in text: errors.append({'path':entry['path'],'error':'missing header '+field})
    versions.append({'path':entry['path'],'before':old,'after':new,'sha256':sha256(path.read_bytes()).hexdigest()})
    if sha256((BASE/'before'/entry['path']).read_bytes()).hexdigest().lower()!=entry['sha256'].lower():
        errors.append({'path':entry['path'],'error':'baseline snapshot changed'})
    for target in re.findall(r'!?\[[^\]\n]*\]\(([^\n)]+)\)', text):
        target=target.strip('<>')
        if re.match(r'^(https?://|mailto:)',target): continue
        ref,_,fragment=unquote(target).partition('#')
        dest=(path.parent/ref).resolve() if ref else path
        local_links+=1
        if not dest.exists():
            errors.append({'path':entry['path'],'target':target,'error':'missing local file'});continue
        if fragment and dest.suffix=='.md' and fragment not in anchors(dest.read_text(encoding='utf-8-sig')):
            errors.append({'path':entry['path'],'target':target,'error':'missing anchor'})
manifest=json.loads((ASSETS/'capture-manifest.json').read_text(encoding='utf-8'))
for item in manifest['screens']:
    path=ASSETS/item['file']
    if not path.exists() or sha256(path.read_bytes()).hexdigest()!=item['sha256']:
        errors.append({'error':'screenshot mismatch','file':item['file']})
report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'documents':versions,'localLinksChecked':local_links,'screenshotsChecked':len(manifest['screens']),'errors':errors}
(ASSETS/'document-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'documents':len(versions),'localLinks':local_links,'screenshots':len(manifest['screens']),'errors':errors},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
