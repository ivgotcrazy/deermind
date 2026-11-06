import { reactive, ref, watch } from 'vue';
import { clone, id, domainData, type Task, type Method, type Step } from './domain';
import { imports } from './imports';
import { chapters } from './material-flow';

export interface Aspect { id:string; name:string; enabled:boolean; reason:string; custom?:boolean }
export interface Criterion {
  id:string; name:string; input:string; basis:string; met:string; counter:string; insufficient:string; examples:string;
}
export interface MethodExecution { methodId:string; criteria:string[] }
export interface AspectRule { methodId:string; aspectId:string; judgment:string; condition:string }
interface PreviousRule { methodId:string; aspectId:string; criteria:string[]; condition:string }
interface PreviousDefinitions { criteria:Criterion[]; rules:PreviousRule[] }
export interface Claim {
  id:string; domainId:string; taskId:string; taskVersion:number; name:string;
  aspects:Aspect[]; criteria:Criterion[]; executions:MethodExecution[]; rules:AspectRule[]; previous?:PreviousDefinitions;
  version:number; updatedAt:string; history:{version:number;at:string;change:string}[];
}
export interface Requirement {
  id:string; claimId:string; claimVersion:number; name:string; chapters:string[]; scope:string;
  methods:string[]; methodMode:'any'|'all'; standards:{aspectId:string;text:string}[];
  omissionReason:string; checked:boolean; criteriaBasis?:string;
}
export interface LearningTarget {
  id:string; name:string; bookId:string; chapters:string[]; requirements:Requirement[];
  version:number; updatedAt:string; history:{version:number;at:string;change:string}[];
}
export const evaluationStorageKey='deermind-m1-evaluation-v3';
const previousKey='deermind-m1-evaluation-v2';
const oldKey='deermind-m1-evaluation-v1';
const defaultConditions:Record<string,string>={
  independent:'记录本次作答、实际获得的提示，以及关键步骤由谁完成。',
  explanation:'取得能够说明关系的表达、图示或过程记录。',
  transfer:'核对先前学习经历、此次变化和实际方法，确认变化符合目标要求。',
  retention:'核对先前合格表现、后测间隔、任务可比性及期间练习与帮助。',
};
export const defaultCondition=(aspectId:string)=>defaultConditions[aspectId]||'';
type OldAspect = Aspect & {criterion:string; counter:string; insufficient:string};
type PreviousClaim = Omit<Claim,'executions'|'rules'|'previous'> & {rules:PreviousRule[]};
type OldClaim = Omit<PreviousClaim,'criteria'|'rules'|'aspects'> & {
  aspects:OldAspect[]; scope:string; methods:string[]; methodMode:'any'|'all';
};
function upgradeClaim(old:OldClaim):PreviousClaim {
  const {aspects,methods,methodMode,scope,...base}=old;
  const claim:PreviousClaim={...base,aspects:[],criteria:[],rules:[],version:old.version+1};
  for(const {criterion,counter,insufficient,...aspect} of aspects){
    claim.aspects.push(aspect);
    if(!criterion&&!counter&&!insufficient)continue;
    const key='C-'+aspect.id;
    claim.criteria.push({id:key,name:aspect.name+'判据',input:'',basis:'',met:criterion,counter,insufficient,examples:''});
    for(const methodId of methods)claim.rules.push({methodId,aspectId:aspect.id,criteria:[key],condition:defaultCondition(aspect.id)});
  }
  claim.updatedAt=new Date().toLocaleString('sv-SE');
  claim.history.unshift({version:claim.version,at:claim.updatedAt,change:'旧版方面说明转为本层判据，请核对必要输入与依据。旧范围记录：'+(scope||'未填写')+'。原方法约定：'+(methodMode==='all'?'分别覆盖':'任选')+'。'});
  return claim;
}
const commonJudgments:Record<string,string>={
  independent:'学生自行选择方法并完成关键步骤，结果符合本方法的执行判据。',
  explanation:'',
  transfer:'在目标规定且此前未练过的变化下，学生仍能用这个方法完成指定任务。',
  retention:'在目标约定的间隔之后，学生仍能用这个方法完成先前已表现出的求解或解释责任。',
};
export function defaultAspectRule(methodId:string,aspectId:string):AspectRule {
  return {methodId,aspectId,judgment:commonJudgments[aspectId]||'',condition:defaultCondition(aspectId)};
}
function separateDefinitions(old:PreviousClaim):Claim {
  const {criteria,rules,...base}=old;
  const claim:Claim={...base,criteria:[],executions:[],rules:[],version:old.version+1};
  // Only untouched built-in examples have known meanings for the old mixed references.
  const sample=old.version===1 && ['载入子任务的乘法判据','载入比例增加任务的方法与判据'].includes(old.history[0]?.change);
  if(sample){
    const executionIds=new Set(rules.filter(r=>r.aspectId==='independent').flatMap(r=>r.criteria));
    claim.criteria=criteria.filter(c=>executionIds.has(c.id));
    claim.executions=rules.filter(r=>r.aspectId==='independent').map(r=>({methodId:r.methodId,criteria:r.criteria}));
  }else if(criteria.length||rules.length){
    claim.previous={criteria,rules};
  }
  claim.rules=rules.map(r=>{
    const rule=defaultAspectRule(r.methodId,r.aspectId);
    rule.condition=r.condition;
    if(sample&&r.aspectId==='explanation'){
      rule.judgment=criteria.filter(c=>r.criteria.includes(c.id)).map(c=>c.met).join(' ');
    }
    return rule;
  });
  claim.updatedAt=new Date().toLocaleString('sv-SE');
  claim.history=[{version:claim.version,at:claim.updatedAt,change:'分开维护方法执行判据和评价方面规则'},...old.history];
  return claim;
}
export const evaluationStorageError=ref('');
let readable=true, saved:{claims:Claim[];targets:LearningTarget[]}={claims:[],targets:[]};
try {
  const current=localStorage.getItem(evaluationStorageKey);
  const previous=localStorage.getItem(previousKey);
  const raw=current??previous??localStorage.getItem(oldKey);
  if(raw){
    const value=JSON.parse(raw);
    if(!Array.isArray(value.claims)||!Array.isArray(value.targets))throw Error();
    saved=current!==null?value:{
      claims:previous!==null?value.claims.map(separateDefinitions):value.claims.map((c:OldClaim)=>separateDefinitions(upgradeClaim(c))),
      targets:value.targets,
    };
    let changed=current===null;
    for(const claim of saved.claims){
      if('support' in claim){delete claim.support;changed=true;}
      for(const rule of claim.rules){
        if(rule.aspectId!=='independent')continue;
        if(rule.condition==='记录允许的工具、实际采用的方法及当题帮助，核对关键步骤由学生承担。'){
          rule.condition=defaultCondition('independent');changed=true;
        }
        if(rule.judgment==='在允许的工具与帮助边界内，学生自行选择方法、完成关键步骤，并达到方法的执行要求。'){
          rule.judgment=commonJudgments.independent;changed=true;
        }
      }
    }
    if(changed)localStorage.setItem(evaluationStorageKey,JSON.stringify(saved));
  }
}catch{readable=false;evaluationStorageError.value='评价与目标草稿无法读取，未覆盖原记录。请保留浏览器数据后检查。';}
export const evaluationData=reactive(saved);
watch(evaluationData,value=>{
  if(!readable)return;
  try{localStorage.setItem(evaluationStorageKey,JSON.stringify(value));evaluationStorageError.value='';}
  catch{evaluationStorageError.value='评价与目标草稿保存失败，请勿关闭页面。';}
},{deep:true});
export const aspectNames=['独立完成','理解与解释','迁移','延迟保持'];
export function blankClaim(domainId='',taskId=''):Claim {
  const task=domainData.tasks.find(t=>t.id===taskId);
  return {id:id('CLAIM'),domainId,taskId,taskVersion:task?.version||0,name:'',criteria:[],executions:[],rules:[],
    aspects:aspectNames.map((name,i)=>({id:['independent','explanation','transfer','retention'][i],name,enabled:true,reason:''})),version:0,updatedAt:'',history:[]};
}
export const blankTarget=():LearningTarget=>({id:id('TARGET'),name:'',bookId:'',chapters:[],requirements:[],version:0,updatedAt:'',history:[]});
export const blankRequirement=():Requirement=>({id:id('REQ'),claimId:'',claimVersion:0,name:'',chapters:[],scope:'',methods:[],methodMode:'any',standards:[],omissionReason:'',checked:false});
export const claimTask=(c:Claim)=>domainData.tasks.find(t=>t.id===c.taskId&&t.domainId===c.domainId);
export const bookImport=(bookId:string)=>imports.find(d=>d.book.id===bookId);
export const bookChapters=(bookId:string)=>{const d=bookImport(bookId);return d?d.flow?chapters(d.flow):d.book.units.flatMap(u=>u.chapters.map(c=>c.name)):[];};
export const chapterLinks=(bookId:string,ch:string)=>bookImport(bookId)?.flow?.links[ch]||[];
export const methodName=(key:string)=>domainData.methods.find(m=>m.id===key)?.name||'方法已不存在';
export const taskUrl=(t:Task)=>'#/domain?'+new URLSearchParams({domain:t.domainId,kind:'task',id:t.id});
export function saveDefinition<T extends Claim|LearningTarget>(rows:T[],value:T,change:string){
  if(evaluationStorageError.value)return;
  const index=rows.findIndex(x=>x.id===value.id),next=clone(value);
  next.version=index<0?1:rows[index].version+1;next.updatedAt=new Date().toLocaleString('sv-SE');
  next.history.unshift({version:next.version,at:next.updatedAt,change});
  if(index<0)rows.unshift(next);else rows[index]=next;
  return next;
}
export function directMethods(c:Claim){
  return claimTask(c)?.methods.filter(key=>domainData.methods.some(m=>m.id===key&&m.domainId===c.domainId))||[];
}
export function aspectRule(c:Claim,methodId:string,aspectId:string):AspectRule {
  return c.rules.find(r=>r.methodId===methodId&&r.aspectId===aspectId)??defaultAspectRule(methodId,aspectId);
}
export function executionCriteria(c:Claim,methodId:string){
  const keys=c.executions.find(e=>e.methodId===methodId)?.criteria||[];
  return c.criteria.filter(item=>keys.includes(item.id));
}
export function newCriterion():Criterion {
  return {id:id('C'),name:'',basis:'',input:'',met:'',insufficient:'',counter:'',examples:''};
}
export function completeCriterion(item:Criterion){
  return [item.name,item.input,item.basis,item.met,item.counter,item.insufficient].every(text=>text.trim());
}
export function claimReferenceIssues(c:Claim){
  const task=claimTask(c);
  if(!task)return ['关联任务不存在或不属本领域'];
  const issues:string[]=[];
  if(task.version!==c.taskVersion)issues.push('关联任务版本已变更，请核对并采用当前版本');
  if(!task.methods.length)issues.push('Task 尚未在领域中关联方法');
  if(directMethods(c).length!==task.methods.length)issues.push('Task 引用了缺失或跨领域的方法');
  if(!c.aspects.some(a=>a.enabled))issues.push('至少保留一个评价方面');
  for(const a of c.aspects){
    if((!a.enabled||a.custom)&&!a.reason.trim())issues.push(a.name+'：裁剪或扩展依据待填写');
  }
  return issues;
}

export interface MethodNode {
  taskId:string; methodId:string; method?:Method; owner?:Claim; step?:Step; entryConditions:string[];
  issue:string; sources:Claim[]; children:MethodNode[];
}
// Expand occurrences, not a set of method IDs: a shared submethod can be called twice with different inputs.
export function methodTree(root:Claim,methodId:string):MethodNode {
  function visit(taskId:string,key:string,path:string[],step?:Step,parent?:Method):MethodNode {
    const task=domainData.tasks.find(t=>t.id===taskId&&t.domainId===root.domainId);
    const method=domainData.methods.find(m=>m.id===key&&m.domainId===root.domainId);
    const entryConditions=step?.key?parent?.steps.flatMap(s=>(s.routes||[]).filter(r=>r.next===step.key).map(r=>r.condition))||[]:[];
    const node:MethodNode={taskId,methodId:key,method,step,entryConditions,issue:'',sources:[],children:[]};
    if(!task||!method||!task.methods.includes(key)){
      node.issue='Domain 中的子任务或所选方法缺失，请核对该分解步骤';
      return node;
    }
    const pair=taskId+'/'+key;
    if(path.includes(pair)){
      node.issue='分解路径重复，已在此处停止展开';
      return node;
    }
    if(!step)node.owner=root;
    else {
      node.sources=evaluationData.claims.filter(c=>c.domainId===root.domainId&&c.taskId===taskId);
      const matching=node.sources.filter(c=>c.taskVersion===task.version);
      if(matching.length===1)node.owner=matching[0];
      else if(matching.length>1)node.issue='有多个当前版本的子任务 Claim，请核对判据来源';
      else node.issue=node.sources.length?'子任务 Claim 引用旧版 Task，请核对版本':'子任务尚无 Claim，请先建立本层判据';
    }
    node.children=method.steps.filter(s=>s.divided).map(s=>visit(s.taskId,s.solutionId,[...path,pair],s,method));
    return node;
  }
  return visit(root.taskId,methodId,[]);
}

function executionIssues(c:Claim,key:string){
  const binding=c.executions.find(e=>e.methodId===key);
  const prefix=methodName(key)+'：';
  if(!binding?.criteria.length)return [prefix+'尚未关联本层执行判据'];
  if(binding.criteria.some(id=>!c.criteria.some(item=>item.id===id&&completeCriterion(item))))return [prefix+'执行判据缺失或待补充'];
  return [];
}
function treeIssues(node:MethodNode,aspects:string[],checkExecution=aspects.some(id=>id!=='explanation')):string[]{
  const issues=node.issue?[methodName(node.methodId)+'：'+node.issue]:[];
  if(node.owner){
    if(checkExecution)issues.push(...executionIssues(node.owner,node.methodId));
    if(!node.step){
      for(const id of aspects){
        const rule=aspectRule(node.owner,node.methodId,id);
        if(!rule.judgment.trim()||!rule.condition.trim())issues.push(methodName(node.methodId)+'：评价规则或证据条件待填写');
      }
    }
  }
  if(checkExecution)node.children.forEach(child=>issues.push(...treeIssues(child,[],true)));
  return issues;
}
export function claimIssues(c:Claim){
  const issues=claimReferenceIssues(c);
  for(const key of directMethods(c))issues.push(...treeIssues(methodTree(c,key),c.aspects.filter(a=>a.enabled).map(a=>a.id),true));
  return [...new Set(issues)];
}
export function requirementBasis(c:Claim,r:Requirement){
  function source(node:MethodNode):unknown {
    return [node.taskId,node.methodId,node.method?.version,node.owner?.id,node.owner?.version,node.issue,node.children.map(source)];
  }
  return JSON.stringify(r.methods.map(key=>source(methodTree(c,key))));
}
export function mappedChapters(t:LearningTarget,c:Claim){return t.chapters.filter(ch=>chapterLinks(t.bookId,ch).some(l=>l.taskId===c.taskId));}
export function allowedMethods(t:LearningTarget,c:Claim,selected:string[]){
  return directMethods(c).filter(key=>selected.length>0&&selected.every(ch=>chapterLinks(t.bookId,ch).some(l=>l.taskId===c.taskId&&l.methodIds.includes(key))));
}
export function candidateIssues(t:LearningTarget,c:Claim){
  const d=bookImport(t.bookId),issues:string[]=[];
  if(!d||c.domainId!==d.book.domainId)return ['不属于教材领域'];
  const mapped=mappedChapters(t,c);
  if(!mapped.length)return ['所选章节未关联该任务'];
  issues.push(...claimReferenceIssues(c));
  const eligible=new Set(mapped.flatMap(ch=>allowedMethods(t,c,[ch])));
  if(!eligible.size)issues.push('章节尚无可用的任务方法');
  else {
    const aspects=c.aspects.filter(a=>a.enabled);
    const hasUsableCell=[...eligible].some(key=>{
      const tree=methodTree(c,key);
      return aspects.some(a=>!treeIssues(tree,[a.id]).length);
    });
    if(!hasUsableCell)issues.push('章节所用方法的判据待准备');
  }
  return issues;
}
export function requirementIssues(t:LearningTarget,r:Requirement){
  const c=evaluationData.claims.find(x=>x.id===r.claimId);
  if(!c)return ['引用的 Claim 不存在'];
  const issues=candidateIssues(t,c);
  if(r.claimVersion!==c.version)issues.push('Claim 已更新，请重新核对并保存该要求');
  if(!r.chapters.length||r.chapters.some(ch=>!t.chapters.includes(ch)||!bookChapters(t.bookId).includes(ch)||!mappedChapters(t,c).includes(ch)))issues.push('要求章节不在目标范围内或未关联该任务');
  const allowed=allowedMethods(t,c,r.chapters);
  if(!r.methods.length||r.methods.some(m=>!allowed.includes(m)))issues.push('所选方法与教材章节不兼容，请核对章节关联');
  for(const key of r.methods)issues.push(...treeIssues(methodTree(c,key),r.standards.map(s=>s.aspectId)));
  if(r.criteriaBasis&&r.criteriaBasis!==requirementBasis(c,r))issues.push('引用的判据来源或方法版本已变更，请重新核对学习要求');
  if(!r.name.trim()||!r.scope.trim())issues.push('请填写学习要求名称和具体任务范围');
  if(!r.standards.length||r.standards.some(s=>!s.text.trim()||!c.aspects.some(a=>a.id===s.aspectId&&a.enabled)))issues.push('请选择适用评价方面，并填写达标标准');
  if(c.aspects.some(a=>a.enabled&&!r.standards.some(s=>s.aspectId===a.id))&&!r.omissionReason.trim())issues.push('未纳入全部适用方面，请说明裁剪理由');
  if(!r.checked)issues.push('请核对范围、方法与达标标准');
  return [...new Set(issues)];
}
export function targetIssues(t:LearningTarget){
  const issues:string[]=[];
  if(!bookImport(t.bookId))issues.push('教材已不存在');
  if(!t.chapters.length||t.chapters.some(ch=>!bookChapters(t.bookId).includes(ch)))issues.push('教材章节范围待核对');
  if(!t.requirements.length)issues.push('尚未添加学习要求');
  t.requirements.forEach(r=>requirementIssues(t,r).forEach(s=>issues.push((r.name||'未命名要求')+'：'+s)));
  return issues;
}
