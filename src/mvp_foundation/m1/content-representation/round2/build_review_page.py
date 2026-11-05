"""Package actual trial evidence for local browsing; no model calls or data repair."""
from pathlib import Path
from pipeline import ROOT,read,save
from jsonschema import Draft202012Validator

run=(ROOT/'latest-run.txt').read_text(encoding='utf-8').strip();folder=ROOT/'runs'/run
cases=[]
for case in read(ROOT/'cases.json'):
    p=folder/case['id'];item=dict(case)
    for key,name in [('raw','extract-output.json'),('extractResult','extract-result.json'),('reviewed','reviewed-content.json'),('contentReview','content-review.json'),('mapping','map-output.json'),('mapResult','map-result.json'),('graph','graph.json'),('mappingReview','mapping-review.json')]:
        item[key]=read(p/name) if (p/name).exists() else None
    item['evidencePath']=f'runs/{run}/{case["id"]}/'
    item['mappingPrefix']='map'
    if (p/'map-recovery-result.json').exists():
        item['mappingPrefix']='map-recovery';item['mapResult']=read(p/'map-recovery-result.json')
        item['mapping']=read(p/'map-recovery-output.json') if (p/'map-recovery-output.json').exists() else None
    if (p/'map-direct-result.json').exists():
        item['mappingPrefix']='map-direct';item['mapResult']=read(p/'map-direct-result.json')
        item['mapping']=read(p/'map-direct-output.json') if (p/'map-direct-output.json').exists() else None
    schema=read(ROOT/(case['id']+'-schema.json'));validator=Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/block'})
    for mode in ['raw','reviewed']:
        item[mode+'InvalidBlocks']=[]
        for task in (item[mode] or {}).get('tasks',[]):
            parts=task['question']+task['knowledge']+task['teachingAids']+[part for s in task['solutions'] for part in s['content']]
            for part in parts:
                for block in part['blocks']:
                    if not validator.is_valid(block):item[mode+'InvalidBlocks'].append(block)
    cases.append(item)
save(ROOT/'review-data.json',dict(run=run,cases=cases))
# Reuse only pure render functions from the first trial; no page initialization or requests.
source=(ROOT.parent/'viewer.js').read_text(encoding='utf-8')
renderer=source.splitlines()[0]+'\n'+source[source.index('function expr'):source.index('function renderElement')]
renderer+='''
export function renderBlock(b){
 if(b.type!=='shape_row')return block(b);
 const size=100,width=size*b.items.length;
 return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} 115" role="img" data-shape-row>`+b.items.map((o,i)=>{
  const x=50+i*size,y=50,r=34,a='fill="none" stroke="#1883ad" stroke-width="2"';let shape='';
  if(o.shape==='circle')shape=`<circle cx="${x}" cy="${y}" r="${r}" ${a}/>`;
  else if(o.shape==='ellipse')shape=`<ellipse cx="${x}" cy="${y}" rx="38" ry="27" ${a}/>`;
  else if(o.shape==='square')shape=`<rect data-square x="${x-r}" y="${y-r}" width="${r*2}" height="${r*2}" ${a}/>`;
  else {const count={triangle:3,pentagon:5,hexagon:6}[o.shape];const points=Array.from({length:count},(_,j)=>{const angle=-Math.PI/2+j*2*Math.PI/count;return `${x+Math.cos(angle)*r},${y+Math.sin(angle)*r}`;}).join(' ');shape=`<polygon points="${points}" ${a}/>`;}
  const dot=o.dot==='center_like'?`<circle data-dot cx="${x}" cy="${y}" r="2.5" fill="#c93689"/>`:'';
  return `<g data-shape="${esc(o.shape)}">${shape}${dot}${text(x,104,o.label,'text-anchor="middle"')}${o.dot==='other'?text(x,112,'标记位置需核对','text-anchor="middle"'):''}</g>`;
 }).join('')+'</svg>';
}
'''
(ROOT/'render-block.js').write_text(renderer,encoding='utf-8')
print('Prepared review page data for '+run)
