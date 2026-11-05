import { reactive, ref, watch } from 'vue';
import { clone, id, domainData, type Task } from './domain';
import { imports } from './imports';
import { chapters } from './material-flow';

export interface Aspect { id:string; name:string; enabled:boolean; criterion:string; insufficient:string; counter:string; reason:string; custom?:boolean }
export interface Claim {
  id:string; domainId:string; taskId:string; taskVersion:number; name:string; scope:string;
  methods:string[]; methodMode:'any'|'all'; support:string; aspects:Aspect[];
  version:number; updatedAt:string; history:{version:number;at:string;change:string}[];
}
export interface Requirement {
  id:string; claimId:string; claimVersion:number; name:string; chapters:string[]; scope:string;
  methods:string[]; methodMode:'any'|'all'; standards:{aspectId:string;text:string}[];
  omissionReason:string; checked:boolean;
}
export interface LearningTarget {
  id:string; name:string; bookId:string; chapters:string[]; requirements:Requirement[];
  version:number; updatedAt:string; history:{version:number;at:string;change:string}[];
}
export const evaluationStorageKey='deermind-m1-evaluation-v1';
export const evaluationStorageError=ref('');
let readable=true, saved:{claims:Claim[];targets:LearningTarget[]}={claims:[],targets:[]};
try {
  const raw=localStorage.getItem(evaluationStorageKey);
  if(raw){const value=JSON.parse(raw);if(!Array.isArray(value.claims)||!Array.isArray(value.targets))throw Error();saved=value;}
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
  return {id:id('CLAIM'),domainId,taskId,taskVersion:task?.version||0,name:'',scope:'',methods:[],methodMode:'any',support:'',
    aspects:aspectNames.map((name,i)=>({id:['independent','explanation','transfer','retention'][i],name,enabled:true,criterion:'',insufficient:'',counter:'',reason:''})),version:0,updatedAt:'',history:[]};
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
export function claimReferenceIssues(c:Claim){
  const t=claimTask(c),issues:string[]=[];
  if(!t)return ['关联任务不存在或不属于该领域'];
  if(c.taskVersion!==t.version)issues.push('关联任务已有新版本，请重新核对范围与方法');
  if(!c.methods.length)issues.push('尚未选择允许的方法');
  if(c.methods.some(key=>!t.methods.includes(key)||!domainData.methods.some(m=>m.id===key&&m.domainId===c.domainId)))issues.push('部分方法已不属于该任务');
  return issues;
}
export function claimIssues(c:Claim){
  const issues=claimReferenceIssues(c);
  if(!c.scope.trim())issues.push('评价范围待填写');
  if(!c.support.trim())issues.push('帮助与工具条件待填写');
  if(!c.aspects.some(a=>a.enabled))issues.push('至少保留一个评价方面');
  for(const a of c.aspects){
    if(a.enabled&&(!a.criterion.trim()||!a.insufficient.trim()||!a.counter.trim()))issues.push(a.name+'：表现、证据不足或反证说明待补齐');
    if((!a.enabled||a.custom)&&!a.reason.trim())issues.push(a.name+'：裁剪或扩展依据待补齐');
  }
  return issues;
}
export function mappedChapters(t:LearningTarget,c:Claim){return t.chapters.filter(ch=>chapterLinks(t.bookId,ch).some(l=>l.taskId===c.taskId));}
export function allowedMethods(t:LearningTarget,c:Claim,selected:string[]){
  return c.methods.filter(key=>selected.length>0&&selected.every(ch=>chapterLinks(t.bookId,ch).some(l=>l.taskId===c.taskId&&l.methodIds.includes(key))));
}
export function candidateIssues(t:LearningTarget,c:Claim){
  const d=bookImport(t.bookId),issues:string[]=[];
  if(!d||c.domainId!==d.book.domainId)return ['不属于教材领域'];
  const mapped=mappedChapters(t,c);
  if(!mapped.length)return ['所选章节未关联该任务'];
  issues.push(...claimIssues(c));
  const compatible=mapped.some(ch=>{const m=allowedMethods(t,c,[ch]);return c.methodMode==='all'?c.methods.every(key=>m.includes(key)):m.length>0;});
  if(!compatible)issues.push('章节采用的方法与 Claim 条件不兼容');
  return issues;
}
export function requirementIssues(t:LearningTarget,r:Requirement){
  const c=evaluationData.claims.find(x=>x.id===r.claimId);
  if(!c)return ['引用的 Claim 不存在'];
  const issues=candidateIssues(t,c);
  if(r.claimVersion!==c.version)issues.push('Claim 已更新，请重新核对并保存该要求');
  if(!r.chapters.length||r.chapters.some(ch=>!t.chapters.includes(ch)||!bookChapters(t.bookId).includes(ch)||!mappedChapters(t,c).includes(ch)))issues.push('要求章节不在目标范围内或未关联该任务');
  const allowed=allowedMethods(t,c,r.chapters);
  if(!r.methods.length||r.methods.some(m=>!allowed.includes(m)))issues.push('采用的方法必须同时属于 Claim 和每个所选章节');
  if(c.methodMode==='all'&&(r.methodMode!=='all'||c.methods.some(m=>!r.methods.includes(m))))issues.push('Claim 要求分别覆盖全部方法，目标不能放宽为任选或减少方法');
  if(!r.name.trim()||!r.scope.trim())issues.push('请填写学习要求名称和具体任务范围');
  if(!r.standards.length||r.standards.some(s=>!s.text.trim()||!c.aspects.some(a=>a.id===s.aspectId&&a.enabled)))issues.push('请选择适用评价方面，并填写达标标准');
  if(c.aspects.some(a=>a.enabled&&!r.standards.some(s=>s.aspectId===a.id))&&!r.omissionReason.trim())issues.push('未纳入全部适用方面，请说明裁剪理由');
  if(!r.checked)issues.push('请核对范围、方法与标准未改变 Claim 的含义');
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
