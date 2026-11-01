from pathlib import Path
from urllib.parse import unquote
import hashlib, json, re, subprocess, unicodedata

# Verify the screenshot-backed product specification using only the Python standard library.
root = Path(__file__).resolve().parents[3]
doc = root/'doc/mvp/phase-4-product-and-domain-foundation/MVP_Product_and_Interaction_Design.md'
assets = doc.parent/'assets/product-interaction'
text = doc.read_text(encoding='utf-8')
manifests = [(folder, json.loads((assets/folder/'capture-manifest.json').read_text(encoding='utf-8')), count)
             for folder, count in [('', 52), ('teaching-model', 24), ('student-teaching', 25), ('fraction-flow', 18), ('student-pages', 18), ('conversation',18)]]

def anchors(text):
    result = set(re.findall(r'<a id="([^"]+)"', text))
    for title in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        result.add(''.join(c for c in title.lower() if c.isspace() or c in '-_' or unicodedata.category(c)[0] in 'LN').replace(' ', '-'))
    return result

errors=[]
for href in re.findall(r'\]\(([^)]+)\)', text):
    if href.startswith(('https://','http://')): continue
    rel, _, anchor = unquote(href).partition('#')
    target = doc.parent/rel if rel else doc
    if not target.exists(): errors.append(['missing_file', href]); continue
    if anchor and target.suffix == '.md' and anchor not in anchors(target.read_text(encoding='utf-8')):
        errors.append(['missing_anchor', href])

images=re.findall(r'!\[[^\]]*\]\(assets/product-interaction/([^)]*)\)',text)
assert len(images)==155 and len(set(images))==155
captured=set()
for folder, manifest, count in manifests:
    assert len(manifest['captures'])==count
    assert manifest['errors']==[] and manifest['modelCalls']==0
    if folder: assert manifest['completed']
    for c in manifest['captures']:
        file=Path(folder)/c['file']
        captured.add(file.as_posix())
        assert hashlib.sha256((assets/file).read_bytes()).hexdigest()==c['sha256'],c['id']
    for file, digest in manifest['sourceHashes'].items():
        assert hashlib.sha256((root/'src/mvp_prototype'/file).read_bytes()).hexdigest()==digest,file
assert set(images)==captured

old=subprocess.check_output(['git','show','HEAD:'+doc.relative_to(root).as_posix()],cwd=root).decode('utf-8').replace('\r\n','\n')
old_mermaid=re.findall(r'```mermaid\n(.*?)\n```',old,re.S)
new_mermaid=re.findall(r'```mermaid\n(.*?)\n```',text,re.S)
diagram_review=json.loads((assets/'student-pages/diagram-review.json').read_text(encoding='utf-8'))
for m in new_mermaid:
    if m not in old_mermaid:
        digest=hashlib.sha256(m.encode('utf-8')).hexdigest()
        rendered=next((d for d in diagram_review if d['sourceSha256']==digest),None)
        assert rendered, 'A changed Mermaid diagram needs a matching rendered source'
        assert hashlib.sha256((assets/'student-pages'/rendered['file']).read_bytes()).hexdigest()==rendered['sha256']

inbound=0
for other in (root/'doc').rglob('*.md'):
    if 'archive' in other.parts or other==doc: continue
    for href in re.findall(r'\]\(([^)]+)\)',other.read_text(encoding='utf-8')):
        if 'MVP_Product_and_Interaction_Design.md' not in href or href.startswith(('http://','https://')): continue
        rel,_,anchor=unquote(href).partition('#')
        if (other.parent/rel).resolve()!=doc.resolve(): continue
        inbound+=1
        if anchor and anchor not in anchors(text): errors.append(['inbound_anchor',str(other.relative_to(root)),href])

version=re.search(r'> \*\*版本\*\*：(v[\d.]+)',text).group(1)
result={'documentVersion':version,'screenshotsReferenced':len(images),'screenshotHashesVerified':len(images),'captureBatches':len(manifests),'capturePageErrors':[],'modelCalls':0,'mermaidBlocksChecked':len(new_mermaid),'newDiagramsRendered':len(diagram_review),'inboundLinksChecked':inbound,'linkErrors':errors}
print(json.dumps(result,ensure_ascii=True,indent=2))
assert not errors
(assets/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
