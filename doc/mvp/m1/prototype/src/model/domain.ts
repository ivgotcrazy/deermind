import { reactive, ref, watch } from 'vue';
import { visualIssues, type ContentVisual } from './content-visuals';
import type { ReviewPart } from './review-content';

export interface Domain { id:string; name:string; scope:string; description:string; version:number; exampleKey?:string; exampleRevision?:number }
export interface Entity { id:string; domainId:string; name:string; version:number }
export type Kind = 'task'|'solution'|'kc';
export const parameterRoles=['题目已给定','需要研究或求解','需要通过调查获取'] as const;
export const parameterKinds=['数值','点／图形','函数／表达式','区间／集合','配置／资源','状态／观测','文本'] as const;
export interface Parameter { symbol:string; name:string; kind:string; role:typeof parameterRoles[number]; condition:string }
export interface Completion { deliverable:string; criterion:string }
export interface Variation { target:string; range:string; constraint:string }
export interface TaskPrerequisite { taskId:string; reason:string; methodIds:string[] }
export interface Task extends Entity {
  summary:string; goal:string; responsibility:string; requirements:Completion[];
  parameters:Parameter[]; relations:string; variations:Variation[]; exclusions:string; methods:string[];
  prerequisites?:TaskPrerequisite[];
}
export const stepKinds={process:'顺序处理',choice:'条件选择',cases:'分类讨论',check:'检查与复查'} as const;
export interface Route { condition:string; action:string; result:string; next:string }
export interface Step {
  title:string; detail:string; divided:boolean; taskId:string; solutionId:string;
  key?:string; kind?:keyof typeof stepKinds; inputs?:string; output?:string; next?:string;
  routes?:Route[]; coverage?:string;
}
export interface Method extends Entity {
  description:string; conditions:string; inputs:string; output:string; steps:Step[]; kc:string[];
  procedure?:string;
  ending?:{success:string;stop:string};
}
export interface Knowledge extends Entity { description:string; conditions:string; example:string; prerequisites:string[]; visuals?:ContentVisual[] }
export interface ReferenceSolution {
  methodId:string; working:string; id?:string; taskInstanceId?:string;
  origin?:'教材原有'|'系统生成'|'来源待确认'; sourceNote?:string; result?:string;
  visuals?:ContentVisual[];
}
// Existing saved records keep their content IDs and their enclosing question.
export type InstanceSolution = ReferenceSolution;
export interface Instance {
  reviewContent?:ReviewPart[];
  reviewSource?:{importId:string;itemId:string};
  id:string; domainId:string; taskId:string; version:number; question:string; bindings:Record<string,string>;
  table:{headers:string[];rows:string[][]}|null; answer:string; solutions:ReferenceSolution[];
  source:'人工编写'|'教材导入'; sourceNote:string; checkedSignature:string; checkedAt:string;
  visuals?:ContentVisual[];
}
export interface DomainData { domains:Domain[]; tasks:Task[]; methods:Method[]; knowledge:Knowledge[]; instances:Instance[] }
export const kinds:Record<Kind,{name:string;english:string}> = {
  task:{name:'任务',english:'Task'}, solution:{name:'方法',english:'Solution'}, kc:{name:'知识成分',english:'KnowledgeComponent'},
};
export const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
export const id=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8).toUpperCase();
export const domainStorageKey='deermind-m1-domain-v1';
export const domainStorageError=ref('');
let readable=true;
let saved:DomainData={domains:[],tasks:[],methods:[],knowledge:[],instances:[]};
type StoredTask=Omit<Task,'parameters'|'variations'|'requirements'>&{
  output?:string; requirements?:Completion[]; variations:string|Variation[];
  parameters:(Omit<Parameter,'role'|'kind'>&{role:string;kind?:string})[];
};
function readTask(value:StoredTask):Task {
  const {output,...task}=value;
  return {...task,requirements:task.requirements??(output?[{deliverable:output,criterion:''}]:[]),
    parameters:(task.parameters||[]).map(p=>({...p,kind:p.kind||'',role:p.role==='已知量'?'题目已给定':p.role==='最终输出'?'需要研究或求解':p.role as Parameter['role']})),
    variations:typeof task.variations==='string'?(task.variations?[{target:'旧版变化说明',range:task.variations,constraint:''}]:[]):task.variations};
}
try {
  const raw=localStorage.getItem(domainStorageKey);
  if(raw){const parsed=JSON.parse(raw);if(!Object.keys(saved).every(k=>Array.isArray(parsed[k])))throw Error();saved={...parsed,tasks:parsed.tasks.map(readTask)};}
} catch { readable=false;domainStorageError.value='领域草稿无法读取，未覆盖原记录。请保留浏览器数据后检查。'; }
export const domainData=reactive(saved);
watch(domainData,value=>{
  if(!readable)return;
  try{localStorage.setItem(domainStorageKey,JSON.stringify(value));domainStorageError.value='';}
  catch{domainStorageError.value='领域草稿保存失败，请勿关闭页面。';}
},{deep:true});

export function blankTask(domainId:string):Task {
  return {id:id('TT'),domainId,name:'',version:0,summary:'',goal:'',responsibility:'',requirements:[],parameters:[],relations:'',variations:[],exclusions:'',methods:[],prerequisites:[]};
}
export function blankMethod(domainId:string):Method {
  return {id:id('ST'),domainId,name:'',version:0,description:'',conditions:'',inputs:'',output:'',procedure:'',steps:[],kc:[],ending:{success:'',stop:''}};
}
export function blankStep():Step {
  return {title:'',detail:'',divided:false,taskId:'',solutionId:'',key:id('STEP'),kind:'process',inputs:'',output:'',next:'$next',routes:[],coverage:''};
}
export function readMethod(m:Method):Method {
  return {...clone(m),procedure:methodProcedure(m),ending:m.ending?clone(m.ending):{success:'',stop:''},steps:m.steps.map((s,i)=>({
    ...s,key:s.key||'step-'+(i+1),kind:s.kind||'process',inputs:s.inputs||'',output:s.output||'',next:s.next||'$next',routes:clone(s.routes||[]),coverage:s.coverage||'',
  }))};
}
export function methodProcedure(m:Method):string {
  if(m.procedure!==undefined)return m.procedure;
  // Preserve the reasoning in old mock records, without interpreting calls as dependencies.
  return m.steps.map((s,i)=>[`${i+1}. ${s.title}`,s.detail,
    ...(s.routes||[]).map(r=>`${r.condition}：${r.action}；${r.result}`),s.coverage].filter(Boolean).join('\n')).join('\n\n');
}
export function nextLabel(m:Method,key:string){
  return key==='$next'?'下一步（末步后核对完成条件）':key==='$success'?'核对成功条件并结束':key==='$stop'?'未解决，停止当前方法':
    (m.steps.findIndex(s=>s.key===key)>=0?'步骤 '+(m.steps.findIndex(s=>s.key===key)+1)+' · '+m.steps.find(s=>s.key===key)!.title:'去向缺失');
}
export function methodFlowIssues(m:Method):string[]{
  const issues:string[]=[],keys=m.steps.map((s,i)=>s.key||'step-'+(i+1));
  if(!m.ending?.success.trim())issues.push('缺少成功完成条件');
  if(!m.ending?.stop.trim())issues.push('缺少无法继续时的停止条件');
  if(new Set(keys).size!==keys.length)issues.push('步骤标识重复');
  const valid=(key:string)=>['$next','$success','$stop'].includes(key)||keys.includes(key);
  m.steps.forEach((s,i)=>{
    const prefix='步骤'+(i+1)+'：';
    if(!s.inputs?.trim()||!s.output?.trim())issues.push(prefix+'需要补齐使用的输入与产出结果');
    if(!s.kind||s.kind==='process'){
      if(!valid(s.next||'$next'))issues.push(prefix+'完成后的去向已不存在');
      if((s.next||'$next')===keys[i])issues.push(prefix+'不能无条件返回自身，请用检查条件说明继续与停止');
    }else{
      if(!s.routes?.length)issues.push(prefix+'尚未定义条件及处理');
      if(s.routes?.some(r=>!r.condition.trim()||!r.action.trim()||!r.result.trim()))issues.push(prefix+'条件、处理和结果需要补齐');
      if(s.kind==='cases'){
        if(!s.coverage?.trim())issues.push(prefix+'需要说明分类覆盖及汇总方式');
        if(!valid(s.next||'$next'))issues.push(prefix+'汇总后的去向已不存在');
      }else if(s.routes?.some(r=>!valid(r.next)))issues.push(prefix+'分支去向已不存在');
      if((s.kind==='choice'||s.kind==='check')&&!s.coverage?.trim())issues.push(prefix+'需要说明条件无法判断时如何处理');
    }
  });
  return issues;
}
export function blankKnowledge(domainId:string):Knowledge {
  return {id:id('KC'),domainId,name:'',version:0,description:'',conditions:'',example:'',prerequisites:[]};
}
export function blankInstance(task:Task):Instance {
  return {id:id('TI'),domainId:task.domainId,taskId:task.id,version:0,question:'',bindings:Object.fromEntries(task.parameters.filter(p=>p.role==='题目已给定').map(p=>[p.symbol,''])),table:null,answer:'',solutions:[],source:'人工编写',sourceNote:'',checkedSignature:'',checkedAt:''};
}
export function saveEntity<T extends {id:string;version:number}>(rows:T[],value:T){
  const index=rows.findIndex(r=>r.id===value.id), next=clone(value);
  next.version=index<0?1:rows[index].version+1;
  if(index<0)rows.push(next);else rows[index]=next;
  return next;
}
export function collection(kind:Kind){return kind==='task'?domainData.tasks:kind==='solution'?domainData.methods:domainData.knowledge;}

export function knowledgeIssues(k:Knowledge):string[]{
  const issues=visualIssues(k.visuals);
  if(!k.description.trim())issues.push(k.name+'：缺少知识定义');
  if(!k.conditions.trim())issues.push(k.name+'：缺少适用条件');
  return issues;
}
export function collectKnowledge(methodIds:string[],domainId:string){
  const rows=new Map<string,{knowledge:Knowledge;paths:string[][]}>(), issues=new Set<string>();
  for(const key of new Set(methodIds)){
    const m=domainData.methods.find(x=>x.id===key&&x.domainId===domainId);
    if(!m){issues.add('引用的方法不存在或不属本领域：'+key);continue;}
    for(const [field,label] of [[m.description,'方法思路'],[m.conditions,'适用条件'],[methodProcedure(m),'关键过程']])if(!field.trim())issues.add(m.name+'：缺少'+label);
    if(!m.kc.length)issues.add(m.name+'：尚未关联知识依据');
    if(m.procedure===undefined&&m.steps.some(s=>s.divided))issues.add(m.name+'：旧版子调用尚未核对，请确认本方法所用知识与过程；不再递归汇总');
    for(const key of new Set(m.kc)){
      const k=domainData.knowledge.find(x=>x.id===key&&x.domainId===domainId);
      if(!k){issues.add(m.name+'：知识不存在或不属本领域');continue;}
      knowledgeIssues(k).forEach(x=>issues.add(x));
      if(!rows.has(key))rows.set(key,{knowledge:k,paths:[]});
      rows.get(key)!.paths.push([m.id]);
    }
  }
  return {rows:[...rows.values()],issues:[...issues]};
}
export function prerequisiteIssues(task:Task):string[]{
  const issues=new Set<string>();
  const visit=(t:Task,path:string[])=>{
    if(path.includes(t.id)){issues.add('先导任务存在循环');return;}
    const seen=new Set<string>();
    for(const dep of t.prerequisites||[]){
      if(seen.has(dep.taskId))issues.add('先导任务重复');
      seen.add(dep.taskId);
      if(dep.taskId===t.id){issues.add('不能将自身设为先导任务');continue;}
      if(!dep.reason.trim())issues.add('请说明先导理由');
      if(dep.methodIds.some(key=>!t.methods.includes(key)))issues.add('先导关系的适用方法不在当前任务中');
      const next=dep.taskId===task.id?task:domainData.tasks.find(x=>x.id===dep.taskId&&x.domainId===task.domainId);
      if(!next)issues.add('先导任务不存在或不属本领域');else visit(next,[...path,t.id]);
    }
  };
  visit(task,[]);
  return [...issues];
}
export function taskDefinitionIssues(t:Task):string[]{
  const issues:string[]=[];
  for(const [value,label] of [[t.goal,'任务目标'],[t.responsibility,'学习者承担的工作'],[t.relations,'条件与关系'],[t.exclusions,'适用边界']])if(!value.trim())issues.push('缺少'+label);
  if(!t.requirements.length)issues.push('尚未定义完成要求');
  if(t.requirements.some(r=>!r.deliverable.trim()||!r.criterion.trim()))issues.push('完成要求的交付内容和完成条件需要补齐');
  if(t.parameters.some(p=>!p.symbol.trim()||!p.name.trim()||!p.kind.trim()||!parameterRoles.includes(p.role)||!p.condition.trim()))issues.push('对象与变量的标识、名称、类型、用途和约束需要补齐');
  if(new Set(t.parameters.map(p=>p.symbol.trim())).size!==t.parameters.length)issues.push('对象或变量标识重复');
  if(t.variations.some(v=>!v.target.trim()||!v.range.trim()||!v.constraint.trim()))issues.push('允许的变化需要补齐变化对象、范围和条件');
  return issues;
}
export function taskIssues(t:Task){return [...taskDefinitionIssues(t),...prerequisiteIssues(t),...(!t.methods.length?['尚未关联方法']:collectKnowledge(t.methods,t.domainId).issues)];}
export function instanceIssues(q:Instance):string[]{
  const t=domainData.tasks.find(x=>x.id===q.taskId&&x.domainId===q.domainId);
  if(!t)return ['所属任务不存在'];
  const issues=taskDefinitionIssues(t);
  issues.push(...visualIssues(q.visuals),...q.solutions.flatMap(s=>visualIssues(s.visuals)));
  if(q.visuals?.some(v=>v.kind==='description'))issues.push('题面必要图形尚待补绘，不能视为完整题面');
  if(!q.question.trim())issues.push('请填写题面');
  if(!q.answer.trim())issues.push('请填写参考答案或评分要点');
  if(!q.sourceNote.trim())issues.push('请填写来源说明');
  for(const s of q.solutions){
    if(!t.methods.includes(s.methodId))issues.push('参考方法不在当前任务的方法中');
    if(!s.working.trim())issues.push('请补齐所选方法的具体解答');
  }
  if(q.table&&(!q.table.headers.length||q.table.headers.some(h=>!h.trim())||!q.table.rows.length||q.table.rows.some(r=>r.length!==q.table!.headers.length)))issues.push('请补齐题面表格的表头和行列结构');
  return [...new Set([...issues,...collectKnowledge(q.solutions.map(s=>s.methodId),q.domainId).issues])];
}
// Invalidates a mock check when the instance or any relevant definition changes.
export function instanceSignature(q:Instance):string {
  const t=domainData.tasks.find(x=>x.id===q.taskId);
  const methods=new Set(q.solutions.map(s=>s.methodId)),knowledge=new Set(domainData.methods.filter(m=>methods.has(m.id)).flatMap(m=>m.kc));
  const {id:_,version:__,checkedSignature:___,checkedAt:____,...content}=q;
  return JSON.stringify({content,task:t,methods:domainData.methods.filter(m=>methods.has(m.id)),knowledge:domainData.knowledge.filter(k=>knowledge.has(k.id))});
}
export function instanceStatus(q:Instance){
  if(!q.checkedSignature)return '待检查';
  return q.checkedSignature===instanceSignature(q)&&!instanceIssues(q).length?'可用（mock）':'需重新检查';
}
