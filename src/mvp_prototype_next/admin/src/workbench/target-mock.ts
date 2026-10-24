import { reactive } from 'vue';
import { textbookMock, mockId } from './textbook-mock';
import { evaluationMock } from './evaluation-mock';
import { domainMock } from './domain-mock';

export interface LearningRequirement { id:string; name:string; chapterIds:string[]; aspectIds:string[]; standard:string }
export interface TargetClaimSelection { claimId:string; requirements:LearningRequirement[]; omissionReason:string }
export interface MockTarget { id:string; name:string; description:string; bookId:string; chapterIds:string[]; claims:TargetClaimSelection[]; revision:number; history:{at:string;change:string}[] }
export const targetBook=(t:MockTarget)=>textbookMock.books.find(b=>b.id===t.bookId);
export const targetClaim=(id:string)=>evaluationMock.claims.find(c=>c.id===id);
export const allChapters=(bookId:string)=>textbookMock.books.find(b=>b.id===bookId)?.units.flatMap(u=>u.chapters)||[];
export const mappedChapters=(t:MockTarget,claimId:string)=>allChapters(t.bookId).filter(ch=>t.chapterIds.includes(ch.id)&&ch.mappings.some(m=>m.taskId===targetClaim(claimId)?.taskId));
export const omittedAspects=(s:TargetClaimSelection)=>targetClaim(s.claimId)?.aspects.filter(a=>a.applicable&&!s.requirements.some(r=>r.aspectIds.includes(a.id)))||[];
export function conditionIssues(t:MockTarget,s:TargetClaimSelection):string[]{
  const c=targetClaim(s.claimId),b=targetBook(t);if(!c||!b)return ['教材或 Claim 已不存在。'];
  const task=domainMock.tasks.find(task=>task.id===c.taskId&&task.domainId===b.domainId);
  if(c.domainId!==b.domainId||!task)return ['Claim 绑定的任务不在本教材领域中。'];
  const chapters=mappedChapters(t,c.id),used=[...new Set(s.requirements.flatMap(r=>r.chapterIds))];
  if(!chapters.length)return ['所选章节中没有该 Task 的映射。'];
  const issues:string[]=[];
  if(used.some(id=>!chapters.some(ch=>ch.id===id)))issues.push('有学习要求的章节已不在目标范围或不再映射这个 Task。');
  if(!c.methods.length||c.methods.some(id=>!task.methods.includes(id)||!domainMock.methods.some(m=>m.id===id&&m.domainId===b.domainId)))issues.push('Claim 的方法定义尚未补齐或已失效。');
  for(const ch of chapters.filter(ch=>!used.length||used.includes(ch.id))){
    const methods=ch.mappings.filter(m=>m.taskId===c.taskId).flatMap(m=>m.methods);
    const missing=c.methods.filter(id=>!methods.includes(id));
    if(c.methodMode==='all'?missing.length>0:!c.methods.some(id=>methods.includes(id)))issues.push(ch.name+'：未映射 Claim 条件中的“'+missing.map(id=>domainMock.methods.find(m=>m.id===id)?.name||id).join('、')+'”。');
  }
  return issues;
}
export function configurationIssues(t:MockTarget,s:TargetClaimSelection):string[]{
  const c=targetClaim(s.claimId),issues=conditionIssues(t,s);
  if(!s.requirements.length)issues.push('尚未填写具体学习要求。');
  if(omittedAspects(s).length&&!s.omissionReason.trim())issues.push('有未纳入目标的评价方面，尚未说明裁剪依据。');
  if(s.requirements.some(r=>!r.name.trim()||!r.standard.trim()||!r.chapterIds.length||!r.aspectIds.length||r.aspectIds.some(id=>!c?.aspects.some(a=>a.id===id&&a.applicable&&a.criterion.trim()&&a.evidence.trim()))))issues.push('有学习要求不完整，或引用的 Claim 方面已变化。');
  return issues;
}
export const blankTarget=():MockTarget=>({id:mockId('TARGET'),name:'',description:'',bookId:'',chapterIds:[],claims:[],revision:1,history:[]});
const requirement=(id:string,name:string,chapter:string,aspect:string,standard:string):LearningRequirement=>({id,name,chapterIds:[chapter],aspectIds:[aspect],standard});
export const targetMock=reactive({targets:[{
  id:'TARGET-MATH',name:'分数与面积·学习目标示例',description:'围绕数量变化与三角形面积，明确学生需要形成的理解和求解能力。以下要求用于交互讨论，不是已经验证的课程标准。',bookId:'BOOK-MATH',chapterIds:['CH-INCREASE','CH-TRIANGLE'],revision:1,history:[{at:'2026-10-24 09:00',change:'建立目标交互示例'}],claims:[
    {claimId:'CLAIM-FRACTION',omissionReason:'',requirements:[
      requirement('REQ-F1','能独立求出增加后的数量','CH-INCREASE','independent','独立识别原量和增加比例，正确建立关系、计算并保留单位；有效判断足以支持，未解释的关键冲突应保留待确认。'),
      requirement('REQ-F2','能说明为什么要把增加量加回原量','CH-INCREASE','understanding','用自己的话解释参照量与最终量的关系，不能仅复述刚展示的解答。'),
      requirement('REQ-F3','换成规定的图示仍能解决数量增加问题','CH-INCREASE','transfer','满足 Claim 中规定的变化范围，在未见过的长度示意图中独立建立关系；只换数字不算满足此要求。'),
      requirement('REQ-F4','间隔后仍能独立解决同类问题','CH-INCREASE','retention','满足 Claim 的延迟条件并再次独立完成；保留期间练习与帮助，尚无延迟表现时保持待确认。'),
    ]},
    {claimId:'CLAIM-GEOMETRY',omissionReason:'',requirements:[
      requirement('REQ-G1','能独立选择底和高并计算面积','CH-TRIANGLE','independent','底高对应、列式与计算正确，使用面积单位；不得由已提示公式后的正确答案确认独立完成。'),
      requirement('REQ-G2','能解释为什么底乘高后还要除以二','CH-TRIANGLE','understanding','给出自己的图示或解释，说明底高关系和除以二的理由。'),
      requirement('REQ-G3','图形旋转后仍能找到正确的底和高','CH-TRIANGLE','transfer','在 Claim 规定的旋转图形或外部高条件下，仍能正确识别底高并计算，记录先前接触情况。'),
      requirement('REQ-G4','间隔后仍能识别底高并求面积','CH-TRIANGLE','retention','按 Claim 的延迟条件再次完成底高判断与计算；经过时间本身不算已满足要求。'),
    ]},
  ],
}] as MockTarget[]});
export function recordTargetChange(t:MockTarget,change:string){t.revision++;t.history.unshift({at:new Date().toLocaleString('sv-SE',{hour12:false}),change});}
