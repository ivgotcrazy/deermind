"""Freeze four existing cases, source crops, and stage-specific contracts. No model calls."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
def save(name,data):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def obj(fields):return dict(type='object',properties=fields,required=list(fields),additionalProperties=False)
def arr(item,minimum=0):return dict(type='array',items=item,minItems=minimum)
def enum(*values):return dict(enum=list(values))
def ref(name):return {'$ref':'#/$defs/'+name}
S={'type':'string'}
old=json.loads((BASE/'schema.json').read_text(encoding='utf-8'))
types={b['properties']['type']['enum'][0]:copy.deepcopy(b) for b in old['$defs']['block']['oneOf']}
types['formula']['properties'].pop('latex');types['formula']['required'].remove('latex')
types['shape_row']=obj({'type':enum('shape_row'),'items':arr(obj({'shape':enum('circle','ellipse','triangle','square','pentagon','hexagon'),'classificationBasis':enum('visual_recognition','explicit_text'),'dot':enum('none','center_like','other'),'label':S}),1),'dimensionsRole':enum('layout_only')})
cases=[
 dict(id='C02',title='跨页题目与两种原有解法',scope='第49页原题条件及首问；第50页两列解法、答句空白及旁边提示。不要自行补全答句。约分笔迹无法表达时列出遗漏。',types=['text','formula','worked_example','table'],regions=[(49,[.07,.22,.89,.315]),(50,[.065,.10,.82,.255])]),
 dict(id='C03',title='保留原题中的错误演算',scope='提取提问和所给一列演算；这是要学生检查的原始内容，不要改正或重新求解。',types=['text','worked_example'],regions=[(50,[.075,.65,.67,.025]),(50,[.215,.70,.17,.102])]),
 dict(id='C05',title='三种统计图与教学提示',scope='提取三种统计图、原题提问和下方提示；提示必须单独保存。',types=['text','chart'],regions=[(93,[.075,.16,.86,.79])]),
 dict(id='C06',title='六种平面图形和原图标记',scope='提取剪图比较要求、图形序列和图内可见标记，不包含该区域之外的滚动、对折说明。',types=['text','shape_row'],regions=[(11,[.105,.603,.765,.109])])
]
source=json.loads((BASE/'reference.json').read_text(encoding='utf-8'))
(ROOT/'inputs').mkdir(exist_ok=True)
for case in cases:
    regions=[]
    for i,(page,rect) in enumerate(case['regions']):
        original=next(s for s in source['sources'] if s['printedPage']==page)
        with Image.open(BASE/original['file']) as image:
            w,h=image.size;x,y,rw,rh=rect;box=[round(x*w),round(y*h),round((x+rw)*w),round((y+rh)*h)]
            name=f"inputs/{case['id']}-{i}.png";image.crop(box).save(ROOT/name)
        regions.append(dict(index=i,page=page,original='../'+original['file'],originalSha256=original['sha256'],pixelBox=box,originalSize=[w,h],file=name,sha256=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()))
    case['regions']=regions
    defs={'expression':old['$defs']['expression'],'block':{'oneOf':[types[k] for k in case['types']]}}
    defs['part']=obj({'regionIndex':{'type':'integer','minimum':0,'maximum':len(regions)-1},'blocks':arr(ref('block'),1)})
    task=obj({'question':arr(ref('part'),1),'solutions':arr(obj({'content':arr(ref('part'),1)})),'knowledge':arr(ref('part')),'teachingAids':arr(ref('part'))})
    schema={'$schema':old['$schema'],'$defs':defs,**obj({'tasks':arr(task,1),'uncertainties':arr(S)})}
    save(case['id']+'-schema.json',schema)
save('cases.json',cases)
match=obj({'catalogId':{'type':['string','null']},'reason':S,'unmatchedProposal':{'type':['string','null']}})
mapping=obj({'tasks':arr(obj({'taskIndex':{'type':'integer','minimum':0},'taskMatch':match,'solutions':arr(obj({'solutionIndex':{'type':'integer','minimum':0},'match':match})),'knowledge':arr(obj({'knowledgeIndex':{'type':'integer','minimum':0},'match':match}))}),1)})
save('mapping-schema.json',{'$schema':old['$schema'],**mapping})
save('catalog.json',source['definitions'])
save('plan.json',dict(version='0.2',cases=[c['id'] for c in cases],stages=['extract','author_review','map','program_link','author_review'],provider='existing official DeepSeek configuration',modelPolicy='keep configured model, temperature 0, thinking disabled',maxNormalCalls=8,maxTransportRetriesPerCall=1,maxTotalCalls=16,maxOutputTokens=5000,timeoutSeconds=90,maxParallel=2,semanticRetries=0,stop='Four cases only. Do not tune prompts after seeing outputs. All edits explicit and separate.',comparisonLimits=['Region cropping, schema simplification, stage separation and deterministic geometry change together; not a controlled causal test','Existing small catalog only; no claims about full-book extraction or open-world model creation','Author review is required and timed; not independent user correction-time measurement']))
print('Prepared four cases and '+str(sum(len(c['regions']) for c in cases))+' source crops.')
