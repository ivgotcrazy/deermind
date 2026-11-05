"""Generate the bounded, model-independent JSON Schema used by this trial."""
import json
from pathlib import Path

def obj(properties, required=None):
    return dict(type='object',properties=properties,required=list(properties) if required is None else required,additionalProperties=False)
def arr(items,minItems=0): return dict(type='array',items=items,minItems=minItems)
def enum(*values): return dict(enum=list(values))
def ref(name): return {'$ref':f'#/$defs/{name}'}
s={'type':'string'}; number={'type':'number'}; strings=arr(s)
expr={'oneOf':[obj({'op':enum('number'),'value':{'type':'string','pattern':r'^-?\d+(\.\d+)?$'}}),
               obj({'op':enum('group'),'args':dict(arr(ref('expression'),1),maxItems=1)}),
               obj({'op':enum('fraction','multiply','divide','add','subtract','equal'),'args':dict(arr(ref('expression'),2),maxItems=2)})]}
point=dict(arr(number,2),maxItems=2)
shapes=[]
for kind,props in {
 'point':{'x':number,'y':number,'label':s},
 'circle':{'cx':number,'cy':number,'r':number},
 'ellipse':{'cx':number,'cy':number,'rx':number,'ry':number},
 'polygon':{'points':arr(point,3)}
}.items(): shapes.append(obj({'kind':enum(kind),'id':s,**props}))
types=[
 obj({'type':enum('text'),'text':s}),
 obj({'type':enum('formula'),'expression':ref('expression'),'latex':s}),
 obj({'type':enum('worked_example'),'expressions':arr(ref('expression'),2),'assertedCorrect':{'type':'boolean'}}),
 obj({'type':enum('table'),'headers':strings,'rows':arr(arr(obj({'state':enum('provided','response_blank','unreadable','source_missing'),'value':{'type':['string','number','null']}}))),'unit':s}),
 obj({'type':enum('scene'),'coordinates':enum('layout_only'),'viewBox':dict(arr(number,4),maxItems=4),'objects':arr({'oneOf':shapes},1),'meaning':s,'relations':arr(obj({'subject':s,'predicate':s,'object':s,'basis':enum('explicit_text','explicit_mark','author_inference')}))}),
 obj({'type':enum('bearing'),'reference':s,'target':s,'referenceAxis':enum('north'),'turn':enum('east','west'),'angleDegrees':dict(number,minimum=0,maximum=180),'distance':dict(number,exclusiveMinimum=0),'unit':s,'screenDistance':dict(number,exclusiveMinimum=0)}),
 obj({'type':enum('solids'),'items':arr(obj({'id':s,'shape':enum('cylinder','cone'),'orientation':enum('upright')}),1),'dimensionsRole':enum('layout_only')}),
 obj({'type':enum('views'),'items':arr(obj({'solid':enum('cylinder','cone'),'direction':enum('top','front','side'),'outline':enum('circle','rectangle','triangle'),'centerDot':{'type':'boolean'}}),1)})]
chart_props={'type':enum('chart'),'title':s,'chartType':enum('bar','line','pie'),'categories':strings,'unit':s,'precision':{'type':'integer','minimum':0,'maximum':6},'labels':{'type':'boolean'},'series':arr(obj({'name':s,'values':arr(number),'color':s}),1),'colors':strings,'axis':obj({'min':number,'max':number,'step':dict(number,exclusiveMinimum=0)}),'cohortRelation':enum('second_subset_of_first','disjoint_parts'),'stacked':{'type':'boolean'},'derivedFrom':s,'conversion':s}
types.append(obj(chart_props,[k for k in chart_props if k not in ['axis','colors','derivedFrom','conversion']]))
definitions={'oneOf':[]}
common={'id':s,'kind':s,'title':s,'definition':s,'origin':enum('author_abstraction','model_candidate'),'domainId':s}
for kind,extra in [('KnowledgeComponent',{}),('TaskTemplate',{'solutionIds':strings}),('SolutionTemplate',{'kcIds':strings,'subsolutionIds':strings})]:
    definitions['oneOf'].append(obj({**common,'kind':enum(kind),**extra}))
instance_common={'id':s,'kind':s,'templateId':s,'contentRefs':strings}
instances={'oneOf':[obj({**instance_common,'kind':enum('TaskInstance')}),obj({**instance_common,'kind':enum('SolutionInstance'),'taskInstanceId':s,'origin':enum('textbook','system_generated','author_generated')})]}
root=obj({'schemaVersion':enum('0.1'),'id':s,'status':enum('author_reference_not_llm_output','llm_candidate'),'sourceUrl':s,
 'sources':arr(obj({'id':s,'printedPage':{'type':'integer'},'readerIndex':{'type':'integer'},'file':s,'sha256':s}),1),
 'definitions':arr(ref('definition')),'instances':arr(ref('instance')),
 'elements':arr(obj({'id':s,'owner':s,'role':enum('question','solution','knowledge','teaching_aid'),'origin':enum('textbook','system_generated','author_generated'),'content':arr(ref('block'),1),'sourceRefs':arr(obj({'page':s,'rect':dict(arr(dict(number,minimum=0,maximum=1),4),maxItems=4)}),1)})),
 'cases':arr(obj({'id':s,'title':s,'pages':arr({'type':'integer'},1),'scope':s,'checks':strings,'taskId':s,'solutionIds':strings,'notes':strings}),1)})
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:deermind:m1:content-representation:0.1','title':'M1 bounded content representation trial',**root,'$defs':{'expression':expr,'block':{'oneOf':types},'definition':definitions,'instance':instances}}
Path(__file__).with_name('schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
extraction={'$schema':schema['$schema'],'$defs':schema['$defs'],**obj({'schemaVersion':enum('0.1'),'caseId':s,'taskId':s,'solutionIds':strings,'newDefinitions':arr(ref('definition')),'instances':root['properties']['instances'],'elements':root['properties']['elements'],'uncertainties':strings})}
Path(__file__).with_name('extraction-schema.json').write_text(json.dumps(extraction,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
