// M1 interaction fixture. Re-parsing and semantic matching are fixed mock results, never keyword inference.
import { clone, id, domainData } from './domain';
import { initializeReview, blankBlock, blockIssues, type ReviewBlock } from './review-content';
import { correctionCandidates, reviewCatalog } from './review-fixtures';
import type { ImportDraft } from './imports';
import type { MaterialAssistantState } from './material-assistant';

export type ElementKind='question'|'solution'|'knowledge';
export interface ParsedElement {
  id:string; itemId:string; chapter:string; kind:ElementKind; title:string; blocks:ReviewBlock[];
  taskElementId:string; recipe:string; sourceNote:string; pending:string;
}
export interface IntakeGroup {
  id:string; chapter:string; rootId:string; elements:ParsedElement[]; status:'pending'|'done'|'outdated';
  result:Record<string,{objectId:string;templateId:string}>; at:string;
  removed?:string[]; templates?:Record<string,string>;
}
export interface ChapterLink { taskId:string; methodIds:string[] }
export interface MaterialFlow {
  assistant?:MaterialAssistantState;
  elements:ParsedElement[]; selectedChapter:string; tab:'content'|'links'; requests:IntakeGroup[];
  links:Record<string,ChapterLink[]>; changes:{at:string;prompt:string;before:ParsedElement[];after:ParsedElement[]}[];
}
export const elementNames:Record<ElementKind,string>={question:'题目',solution:'教材解法',knowledge:'知识'};
const cases:Record<string,string>={'MAT-GROUPS':'C02','MAT-ERROR':'C03','MAT-CHARTS':'C05','MAT-CIRCLES':'C06'};
const taskRecipes:Record<string,string>={C02:'TT-CHAIN',C03:'TT-ERROR',C05:'TT-CHART',C06:'TT-SHAPE','MAT-MIXED':'TT-DIVIDE','MAT-MIXED-2':'TT-DIVIDE','MAT-MIXED-3':'TT-DIVIDE'};
const extraCatalog=[
  {id:'ST-DIVIDE',kind:'Solution',title:'按运算顺序将除法转为乘倒数',definition:'按原式的运算顺序逐步转化，除数取倒数，保留其他因数并检查约分。',solutionIds:[],kcIds:['KC-RECIP']},
  {id:'TT-DIVIDE',kind:'Task',title:'分数除乘混合运算',definition:'按给定的运算顺序完成分数除乘混合计算，并说明运算变换。',solutionIds:['ST-DIVIDE'],kcIds:[]},
];
export const catalog=[...reviewCatalog,...extraCatalog];
const canonicalCase=(itemId:string)=>cases[itemId]||itemId;
export function elementText(e:ParsedElement){return e.blocks.map(b=>b.type==='formula'?b.lines.join('\n'):b.type==='chart'?b.chart.title:b.type==='table'?b.headers.join(' / '):b.text).filter(Boolean).join('\n');}
export function elementProblems(e:ParsedElement){return [...new Set([...(e.pending?[e.pending]:[]),...(!e.blocks.length?['未解析出内容']:[]),...e.blocks.flatMap(blockIssues)])];}
export function chapters(flow:MaterialFlow){return [...new Set(flow.elements.map(e=>e.chapter))];}
export function initializeFlow(draft:ImportDraft):MaterialFlow {
  if(draft.flow)return draft.flow;
  const state=initializeReview(draft),elements:ParsedElement[]=[];
  for(const item of state.items){
    const key=canonicalCase(item.id),qId=item.id+'-question';
    for(const part of item.parts.filter(p=>['question','solution','knowledge'].includes(p.role))){
      const kind=part.role as ElementKind;
      elements.push({id:kind==='question'?qId:part.id,itemId:item.id,chapter:item.chapter,kind,title:kind==='question'?item.title:part.name,
        blocks:clone(part.blocks),taskElementId:kind==='solution'?qId:'',recipe:kind==='question'?(taskRecipes[key]||''):kind==='solution'&&key==='C02'?(item.parts.filter(p=>p.role==='solution').indexOf(part)===1?'ST-COMBINE':'ST-TWO'):kind==='knowledge'&&item.id==='MAT-KNOWLEDGE-DIVISION'?'KC-RECIP':'',sourceNote:item.sourceNote,
        pending:key==='C05'&&kind==='question'&&!part.blocks.some(b=>b.type==='chart')?'统计图尚未完整解析，请与教材助手核对。':''});
    }
  }
  // Knowledge statements embedded in the old import also remain available as separate candidates.
  for(const entry of draft.integration?.entries||[]){
    if(entry.knowledgeOnly)continue;
    for(const k of entry.knowledgeItems||[]){const b=blankBlock('text',entry.pages[0]||50);b.text=k.meaning;elements.push({id:k.id,itemId:entry.id,chapter:state.items.find(i=>i.id===entry.id)?.chapter||'未分章',kind:'knowledge',title:k.name,blocks:[b],taskElementId:'',recipe:({base:'KC-FRACTION',multiply:'KC-FRACTION',associate:'KC-ASSOC'} as Record<string,string>)[k.key]||'',sourceNote:k.sourceNote,pending:''});}
  }
  if(draft.reviewExamples){const b=blankBlock('text',50);b.text='除以一个不为零的数，等于乘这个数的倒数。';elements.push({id:'K-RECIP',itemId:'K-RECIP',chapter:'分数的应用',kind:'knowledge',title:'除以非零数等于乘其倒数',blocks:[b],taskElementId:'',recipe:'KC-RECIP',sourceNote:'教材第50页“注意哟”；固定mock提取。',pending:''});}
  draft.flow={elements,selectedChapter:elements[0]?.chapter||'',tab:'content',requests:[],links:{},changes:[]};
  return draft.flow;
}

export function reparseCandidate(flow:MaterialFlow,element:ParsedElement):ParsedElement[]{
  const key=canonicalCase(element.itemId),copy=clone(element),blocks=clone(correctionCandidates[key]||[]);
  const fresh=(b:ReviewBlock)=>({...b,id:id('CONTENT')});
  if(element.kind==='question'&&key==='C02'){
    const b=blankBlock('text',49);b.text='气象小组有12人。摄影小组人数是气象小组的1/3，航模小组人数是摄影小组的3/4。航模小组有多少人？说一说你是如何思考的。';
    copy.blocks=[b];copy.title='三个兴趣小组的人数';copy.pending='';
  }else if(element.kind==='solution'&&key==='C02'){
    const a=blankBlock('text',50);a.text='先求摄影小组人数，再求航模小组人数。';
    const b=blankBlock('text',50);b.text='先求航模小组人数是气象小组人数的几分之几。';
    const fa=blocks[2]||blankBlock('formula',50);fa.lines=['12 × 1/3 × 3/4','= 3'];fa.unit='人';fa.gap='';
    const fb=blocks[3]||blankBlock('formula',50);fb.lines=['12 × (1/3 × 3/4)','= 12 × 1/4','= 3'];fb.unit='人';fb.gap='';
    const first={...copy,title:'逐层求出人数',blocks:[a,fresh(fa)],recipe:'ST-TWO',pending:''};
    const second={...copy,id:element.id+'-second',title:'先合并两层比例',blocks:[b,fresh(fb)],recipe:'ST-COMBINE',pending:''};
    // A previously separated source solution is re-parsed on its own; a merged source result yields two.
    if(element.recipe==='ST-COMBINE')return [{...second,id:element.id}];
    if(flow.elements.some(e=>e.taskElementId===element.taskElementId&&e.recipe==='ST-COMBINE'))return [first];
    return [first,second];
  }else if(element.kind==='question'&&key==='C03'){
    copy.blocks=copy.blocks.filter(b=>b.type!=='formula');copy.blocks.push(...blocks.map(fresh));copy.pending='';
  }else if(element.kind==='question'&&key==='C05'){
    copy.blocks=copy.blocks.filter(b=>b.type!=='chart'&&b.type!=='unsupported');copy.blocks.push(...blocks.map(fresh));copy.pending='';
  }else if(element.kind==='question'&&key==='C06'){
    copy.blocks=copy.blocks.filter(b=>b.type!=='shapes');copy.blocks.push(...blocks.map(fresh));copy.pending='';
  }
  return [copy];
}
export function adoptReparse(flow:MaterialFlow,before:ParsedElement[],after:ParsedElement[],prompt:string){
  const changedIds=new Set(before.map(e=>e.id));
  const remaining=flow.elements.filter(e=>!changedIds.has(e.id));
  const first=Math.max(0,flow.elements.findIndex(e=>changedIds.has(e.id)));
  remaining.splice(first,0,...clone(after));flow.elements=remaining;
  for(const request of flow.requests)if(request.elements.some(e=>changedIds.has(e.id))&&request.status==='pending')request.status='outdated';
  flow.changes.unshift({at:new Date().toLocaleString('zh-CN'),prompt,before:clone(before),after:clone(after)});
}
export function elementResult(flow:MaterialFlow,key:string){return [...flow.requests].reverse().find(r=>r.result[key])?.result[key];}
export function isImported(flow:MaterialFlow,e:ParsedElement){
  return [...flow.requests].reverse().some(r=>r.result[e.id]&&JSON.stringify(r.elements.find(x=>x.id===e.id))===JSON.stringify(e));
}
export function submitElements(flow:MaterialFlow,keys:string[]):string[]{
  const chosen=flow.elements.filter(e=>keys.includes(e.id)&&!isImported(flow,e));
  if(!chosen.length)return ['请选择尚未入库的内容。'];
  const roots=[...new Set(chosen.map(e=>e.taskElementId||e.id))];
  const groups:ParsedElement[][]=[];
  for(const root of roots){
    const parent=flow.elements.find(e=>e.id===root);if(!parent)return ['解法缺少所属题目，请与教材助手核对。'];
    const group=[clone(parent),...chosen.filter(e=>e.taskElementId===root).map(clone)];
    if(group.some(e=>elementProblems(e).length))return ['所选内容仍有解析问题，请先与教材助手核对。'];
    groups.push(group);
  }
  for(const group of groups){
    const old=flow.requests.find(r=>r.status==='pending'&&r.rootId===group[0].id);
    const result=Object.fromEntries(group.filter(e=>isImported(flow,e)).map(e=>[e.id,elementResult(flow,e.id)!]));
    if(old){old.elements=[...group,...old.elements.filter(e=>e.kind==='solution'&&!group.some(x=>x.id===e.id))];old.removed=old.removed?.filter(k=>!group.some(e=>e.id===k));Object.assign(old.result,result);old.at=new Date().toLocaleString('zh-CN');}
    else flow.requests.push({id:id('INTAKE'),chapter:group[0].chapter,rootId:group[0].id,elements:group,status:'pending',result,at:new Date().toLocaleString('zh-CN')});
  }
  return [];
}

export function chapterSuggestions(draft:ImportDraft,chapter:string):ChapterLink[]{
  const flow=initializeFlow(draft),rows=new Map<string,Set<string>>();
  for(const r of flow.requests.filter(r=>r.chapter===chapter&&r.status==='done')){
    const q=r.elements.find(e=>e.kind==='question');if(!q)continue;
    const task=domainData.tasks.find(t=>t.id===r.result[q.id]?.templateId&&t.domainId===draft.book.domainId);if(!task)continue;
    if(!rows.has(task.id))rows.set(task.id,new Set());
    const sourceMethods=r.elements.filter(e=>e.kind==='solution').map(e=>r.result[e.id]?.templateId).filter(k=>task.methods.includes(k));
    (sourceMethods.length?sourceMethods:task.methods).forEach(k=>rows.get(task.id)!.add(k));
  }
  return [...rows].map(([taskId,methods])=>({taskId,methodIds:[...methods]}));
}
export function saveChapterLinks(draft:ImportDraft,chapter:string,links:ChapterLink[]):string[]{
  if(!links.length){delete initializeFlow(draft).links[chapter];return [];}
  for(const link of links){const task=domainData.tasks.find(t=>t.id===link.taskId&&t.domainId===draft.book.domainId);if(!task||!link.methodIds.length||link.methodIds.some(k=>!task.methods.includes(k)||!domainData.methods.some(m=>m.id===k&&m.domainId===draft.book.domainId)))return ['每个任务至少选择一个属于该任务的有效方法。'];}
  initializeFlow(draft).links[chapter]=clone(links);return [];
}
export function materialUrl(draft:ImportDraft,chapter:string,tab:'content'|'links'='content'){
  return '#/textbooks?'+new URLSearchParams({tab:'import',source:draft.id,chapter,view:tab});
}
export function intakeUrl(draft:ImportDraft,chapter:string){return '#/domain?'+new URLSearchParams({domain:draft.book.domainId,tab:'intake',source:draft.id,chapter});}
