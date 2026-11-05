"""Schema and explicit invariants; does NOT grade visual extraction accuracy."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parent
SCHEMA=json.loads(ROOT.joinpath('schema.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR=Draft202012Validator(SCHEMA)

def evaluate(e):
    if e['op']=='number': return Fraction(e['value'])
    args=[evaluate(v) for v in e['args']]
    if e['op']=='group': return args[0]
    a,b=args
    if e['op'] in ['divide','fraction']: return a/b
    if e['op']=='multiply': return a*b
    if e['op']=='add': return a+b
    if e['op']=='subtract': return a-b
    if e['op']=='equal': return a==b
    raise ValueError(e['op'])

def inspect(data, check_sources=True):
    errors=[f'{list(e.absolute_path)}: {e.message}' for e in VALIDATOR.iter_errors(data)]
    if errors:return errors
    definitions={d['id']:d for d in data['definitions']};instances={i['id']:i for i in data['instances']};elements={e['id']:e for e in data['elements']};pages={s['id']:s for s in data['sources']}
    for group in ['definitions','instances','elements','sources','cases']:
        if len({v['id'] for v in data[group]})!=len(data[group]):errors.append(group+': duplicate IDs')
    def require(ok,message):
        if not ok:errors.append(message)
    for d in definitions.values():
        for k in d.get('kcIds',[]):require(definitions.get(k,{}).get('kind')=='KnowledgeComponent',d['id']+': invalid KC')
        for m in d.get('solutionIds',[])+d.get('subsolutionIds',[]):require(definitions.get(m,{}).get('kind')=='SolutionTemplate',d['id']+': invalid method')
    def visit(mid,seen):
        if mid in seen:errors.append(mid+': method cycle');return
        for nxt in definitions.get(mid,{}).get('subsolutionIds',[]):visit(nxt,seen|{mid})
    for d in definitions.values():visit(d['id'],set())
    for i in instances.values():
        expected='TaskTemplate' if i['kind']=='TaskInstance' else 'SolutionTemplate'
        require(definitions.get(i['templateId'],{}).get('kind')==expected,i['id']+': wrong template type')
        if i['kind']=='SolutionInstance':
            task=instances.get(i['taskInstanceId'],{});require(task.get('kind')=='TaskInstance',i['id']+': missing task')
            require(i['templateId'] in definitions.get(task.get('templateId'),{}).get('solutionIds',[]),i['id']+': method not allowed for task')
        for eid in i['contentRefs']:
            e=elements.get(eid,{})
            require(e.get('owner')==i['id'],i['id']+': wrong content owner')
            require(e.get('role')==('question' if i['kind']=='TaskInstance' else 'solution'),i['id']+': answer/help exposed in question')
    for e in elements.values():
        require(e['owner'] in instances or definitions.get(e['owner'],{}).get('kind')=='KnowledgeComponent',e['id']+': missing owner')
        for r in e['sourceRefs']:
            require(r['page'] in pages,e['id']+': missing source')
            x,y,w,h=r['rect'];require(w>0 and h>0 and x+w<=1 and y+h<=1,e['id']+': source rectangle out of bounds')
        for b in e['content']:
            if b['type']=='table':
                for row in b['rows']:
                    require(len(row)==len(b['headers']),e['id']+': table width')
                    for c in row:require((c['value'] is not None)==(c['state']=='provided'),e['id']+': blank/missing cells must not contain values')
            elif b['type']=='chart':
                require(all(len(s['values'])==len(b['categories']) for s in b['series']),e['id']+': chart categories')
                require(not(b['cohortRelation']=='second_subset_of_first' and b['stacked']),e['id']+': overlapping groups cannot stack')
                if b['chartType']=='pie':require(sum(Decimal(str(v)) for v in b['series'][0]['values'])==100,e['id']+': percent sum')
                else:require('axis' in b and b['axis']['min']<b['axis']['max'],e['id']+': chart axis')
                if b.get('derivedFrom'):
                    require(b['derivedFrom'] in elements,e['id']+': unknown source table')
            elif b['type']=='formula':
                try:
                    value=evaluate(b['expression'])
                    if isinstance(value,bool):require(value,e['id']+': incorrect equality outside deliberate worked example')
                except (ValueError,ZeroDivisionError):errors.append(e['id']+': invalid expression')
    for c in data['cases']:
        require(c['taskId'] in instances,c['id']+': unknown task')
        for sid in c['solutionIds']:require(instances.get(sid,{}).get('taskInstanceId')==c['taskId'],c['id']+': solution belongs to another task')
    if check_sources:
        for s in pages.values():require(hashlib.sha256(ROOT.joinpath(s['file']).read_bytes()).hexdigest()==s['sha256'],s['id']+': source changed')
    return errors

def run():
    data=json.loads(ROOT.joinpath('reference.json').read_text(encoding='utf-8'));errors=inspect(data)
    assert not errors, '\n'.join(errors)
    elements={e['id']:e for e in data['elements']}
    math=[b for b in elements['E-EXPR']['content'] if b['type']=='formula']
    assert [evaluate(b['expression']) for b in math]==[Fraction(40),Fraction(75,28),Fraction(1)]
    wrong=elements['E-WRONG']['content'][1]['expressions']
    assert [evaluate(e) for e in wrong]==[Fraction(63,32),Fraction(7,32),Fraction(7,32)]
    counts=elements['E-COUNTS']['content'][1]['rows']
    for chart in elements['E-CHARTS']['content'][1:3]:
        for j,series in enumerate(chart['series']):
            assert [Decimal(c[j+1]['value']/100000000).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) for c in counts]==[Decimal(str(v)).quantize(Decimal('.01')) for v in series['values']]
    mutations=[]
    def reject(name,change):
        bad=copy.deepcopy(data);change(bad);found=inspect(bad,False);assert found,name;mutations.append(dict(name=name,rejected=True))
    reject('题面引用解法内容',lambda d:d['instances'][0]['contentRefs'].append('E-SOL-A'))
    reject('TaskTemplate直接关联KC',lambda d:next(v for v in d['definitions'] if v['kind']=='TaskTemplate').update(kcIds=['KC-ORDER']))
    reject('互相包含的人群画成堆叠柱',lambda d:next(e for e in d['elements'] if e['id']=='E-CHARTS')['content'][1].update(stacked=True))
    reject('待填空格被补入答案',lambda d:next(e for e in d['elements'] if e['id']=='E-PLAN')['content'][1]['rows'][0][0].update(value='已填答案'))
    reject('表格行列错位',lambda d:next(e for e in d['elements'] if e['id']=='E-COUNTS')['content'][1]['rows'][0].pop())
    reject('图例系列长度错误',lambda d:next(e for e in d['elements'] if e['id']=='E-CHARTS')['content'][1]['series'][0]['values'].pop())
    reject('错误模板归属',lambda d:next(i for i in d['instances'] if i['id']=='SI-CHAIN-A').update(templateId='ST-ERROR'))
    reject('来源区域越界',lambda d:d['elements'][0]['sourceRefs'][0].update(rect=[.9,.9,.5,.5]))
    report=dict(checkedAt=datetime.now(timezone.utc).isoformat(),status='structure_checks_passed',referenceSha256=hashlib.sha256(ROOT.joinpath('reference.json').read_bytes()).hexdigest(),schemaSha256=hashlib.sha256(ROOT.joinpath('schema.json').read_bytes()).hexdigest(),caseCount=len(data['cases']),elementCount=len(data['elements']),mutations=mutations,numericChecks=['C01: 40, 75/28, 1','C03: original error preserved; correct value 63/32 is not inserted into task','C05: persons to rounded hundred-million counts; pie sums to 100'],limitations=['No LLM calls made by this verifier','No claim of extraction accuracy or full-book coverage','Schema validity does not establish semantic correctness'])
    ROOT.joinpath('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(cases=len(data['cases']),elements=len(data['elements']),negativeTests=len(mutations),status=report['status'])))

if __name__=='__main__':run()
