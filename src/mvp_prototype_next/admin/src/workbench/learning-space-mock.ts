import { reactive } from 'vue';
import { readFlow, subscribeFlow, lessonFeedback, type FlowState } from '../../../shared/learning-flow';
import { domainMock } from './domain-mock';
import { evaluationMock } from './evaluation-mock';
import { textbookMock } from './textbook-mock';
import { targetMock } from './target-mock';

const copy=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
// Fixed adoption snapshots and authored personal examples; no evaluation or migration engine.
const baseline=copy({book:textbookMock.books[0]!,target:targetMock.targets[0]!,claims:evaluationMock.claims,domain:domainMock});
export interface SpaceActivity {
  id:string; name:string; chapterId:string; at:string; kind:string; help:string;
  messages:{actor:string;text:string}[];
  evidence:{id:string;claimId:string;aspectId:string;meaning:string}[];
}
export interface SpaceJudgment {
  claimId:string; aspectId:string; judgment:string; uncertainty:string; evidenceIds:string[];
}
export interface SpaceAssessment { requirementId:string; status:'已达标'|'需加强'|'待确认'; reason:string }
export interface MockLearningSpace {
  id:string; name:string; studentId:string; studentName:string; createdAt:string; chapterIds:string[];
  classroom:{chapterIds:string[];confirmedAt:string}|null;
  adopted:typeof baseline; activities:SpaceActivity[]; judgments:SpaceJudgment[]; assessments:SpaceAssessment[];
  history:{at:string;actor:string;description:string}[];
}
const create=(id:string,name:string,studentId:string,studentName:string,chapterIds:string[]):MockLearningSpace=>({
  id,name,studentId,studentName,createdAt:'2026-10-22 16:00',chapterIds,classroom:null,adopted:copy(baseline),activities:[],judgments:[],assessments:[],
  history:[{at:'2026-10-22 16:00',actor:'学生本人（示例）',description:'创建空间，选用教材 v1 与目标 v1，并记录所选章节及相关定义快照。此后尚未更换采用内容。'}],
});
export const learningSpaces=reactive<MockLearningSpace[]>([
  create('SPACE-001','校内数学','LEARNER-A','学生 A',['CH-PART','CH-INCREASE','CH-TRIANGLE','CH-GARDEN','CH-PENDING']),
  create('SPACE-002','校外数学','LEARNER-A','学生 A',['CH-TRIANGLE']),
  create('SPACE-003','校内数学','LEARNER-B','学生 B',['CH-INCREASE','CH-TRIANGLE']),
]);
const school=learningSpaces[0]!;
school.classroom={chapterIds:['CH-TRIANGLE'],confirmedAt:'2026-10-24 08:30'};
school.activities=[
  {id:'SPACE-ACT-003',name:'解释底高关系与面积公式',chapterId:'CH-TRIANGLE',at:'2026-10-24 17:00',kind:'解释与反馈',help:'先独立解释，随后获得讲解；两段表现分开记录。',messages:[
    {actor:'DeerMind',text:'三角形的底是 10 厘米，对应高为 6 厘米，另一条斜边是 8 厘米。求面积，并说明为什么除以 2。'},
    {actor:'学生',text:'10 × 6 ÷ 2 = 30 平方厘米。我用的是对应高 6，不是斜边 8。为什么要除以 2，我只能记住公式。'},
    {actor:'DeerMind',text:'你选用了正确的底和高。我们用两个相同三角形拼成平行四边形，看看为什么一个三角形的面积要除以 2。'},
  ],evidence:[{id:'SPACE-EV-003',claimId:'CLAIM-GEOMETRY',aspectId:'independent',meaning:'在解释前独立选用给定底高并计算正确；不据此证明理解面积公式的理由。'},{id:'SPACE-EV-004',claimId:'CLAIM-GEOMETRY',aspectId:'understanding',meaning:'能选用对应高，但独立解释中只能复述公式，未说明除以 2 的理由；未满足解释要求。'}]},
  {id:'SPACE-ACT-002',name:'独立计算三角形面积',chapterId:'CH-TRIANGLE',at:'2026-10-23 17:10',kind:'作答',help:'未给公式、方法或底高提示。',messages:[
    {actor:'DeerMind',text:'一个三角形的底为 12 厘米，对应高为 7 厘米，求面积。'},
    {actor:'学生',text:'12 × 7 ÷ 2 = 42 平方厘米。'},
  ],evidence:[{id:'SPACE-EV-002',claimId:'CLAIM-GEOMETRY',aspectId:'independent',meaning:'独立列式与计算正确，只支持本次明确底高条件下的表现。'}]},
  {id:'SPACE-ACT-001',name:'提示后求增加后的水量',chapterId:'CH-INCREASE',at:'2026-10-22 17:00',kind:'问题讲解',help:'已提示关键关系和计算步骤。',messages:[
    {actor:'学生',text:'原来有 80 升水，增加原来的四分之一，现在多少升？我不知道怎么算。'},
    {actor:'DeerMind',text:'先求增加的水：80 × 1/4，再把它加回原量 80。'},
    {actor:'学生',text:'80 × 1/4 = 20，80 + 20 = 100 升。'},
  ],evidence:[{id:'SPACE-EV-001',claimId:'CLAIM-FRACTION',aspectId:'independent',meaning:'提示后完成，不支持独立完成，也不因求助直接判为未掌握。'}]},
];
school.judgments=[
  {claimId:'CLAIM-GEOMETRY',aspectId:'independent',judgment:'对明确给定底高的计算有支持',uncertainty:'目前只覆盖已给定底高的常规题，不能外推到旋转图形或延迟保持。',evidenceIds:['SPACE-EV-002','SPACE-EV-003']},
  {claimId:'CLAIM-GEOMETRY',aspectId:'understanding',judgment:'面积公式的理由需加强',uncertainty:'尚不能解释公式理由；后续讲解后的独立解释尚未取得。',evidenceIds:['SPACE-EV-004']},
  {claimId:'CLAIM-FRACTION',aspectId:'independent',judgment:'只有受助完成记录，独立表现待确认',uncertainty:'本章方法配置也待核对；当前不能据此形成达标结论。',evidenceIds:['SPACE-EV-001']},
];
school.assessments=[
  {requirementId:'REQ-G1',status:'已达标',reason:'预写判断示例：当前记录支持本目标限定的、明确给定底高的独立计算要求；不代表其他方面达标。'},
  {requirementId:'REQ-G2',status:'需加强',reason:'能够选用底高计算，但尚未说明除以二的理由；讲解后的独立再验证仍缺失。'},
];

export const spaceChapters=(s:MockLearningSpace)=>s.adopted.book.units.flatMap(u=>u.chapters).filter(ch=>s.chapterIds.includes(ch.id));
export const spaceRequirements=(s:MockLearningSpace)=>s.adopted.target.claims.flatMap(selection=>selection.requirements.filter(r=>r.chapterIds.some(id=>s.chapterIds.includes(id))).map(requirement=>({selection,requirement,claim:s.adopted.claims.find(c=>c.id===selection.claimId)})));
export const spaceClaims=(s:MockLearningSpace)=>s.adopted.claims.filter(c=>spaceRequirements(s).some(r=>r.selection.claimId===c.id));
export const spaceEvidence=(s:MockLearningSpace)=>s.activities.flatMap(a=>a.evidence.map(e=>({...e,activity:a})));
export const lastActivity=(s:MockLearningSpace)=>s.activities.map(a=>a.at).sort().reverse()[0]||'';
export function requirementIssues(s:MockLearningSpace,requirementId:string){
  const row=spaceRequirements(s).find(r=>r.requirement.id===requirementId);if(!row)return ['当前空间没有这项学习要求。'];
  const {requirement:r,claim:c}=row;if(!c)return ['尚无对应的 Claim 定义。'];
  const issues:string[]=[];
  if(r.chapterIds.some(id=>!s.chapterIds.includes(id)))issues.push('此要求跨多个章节，当前空间未选全适用章节，不能按局部范围宣称整项达标。');
  if(r.aspectIds.some(id=>!c.aspects.some(a=>a.id===id&&a.applicable)))issues.push('所需评价方面尚未定义完整。');
  for(const id of r.chapterIds.filter(id=>s.chapterIds.includes(id))){
    const ch=spaceChapters(s).find(ch=>ch.id===id),mapping=ch?.mappings.filter(m=>m.taskId===c.taskId)||[];
    if(!mapping.length)issues.push((ch?.name||id)+'：尚无对应 Task 的教材映射。');
    else if(c.methodMode==='all'?c.methods.some(id=>!mapping.some(m=>m.methods.includes(id))):!c.methods.some(id=>mapping.some(m=>m.methods.includes(id))))issues.push((ch?.name||id)+'：教材采用的方法未完整覆盖 Claim 方法条件，需核对定义；本空间不会静默裁剪。');
  }
  return issues;
}
export const assessmentFor=(s:MockLearningSpace,id:string):SpaceAssessment=>requirementIssues(s,id).length?{requirementId:id,status:'待确认',reason:'评价配置待核对，不能把内容缺口记为学生未掌握。'}:s.assessments.find(a=>a.requirementId===id)||{requirementId:id,status:'待确认',reason:'尚无足以支持本要求的个人表现；未检测不等于未掌握。'};
export function courseKnowledge(s:MockLearningSpace,roots:string[]){
  const methods=new Set<string>(),rows=new Map<string,{id:string;name:string;roots:Set<string>}>(),issues=new Set<string>();
  function visit(id:string,root:string,path:string[]){
    if(path.includes(id)){issues.add('方法存在循环引用。');return;}
    const method=s.adopted.domain.methods.find(m=>m.id===id);if(!method){issues.add('缺少方法 '+id);return;}
    methods.add(id);
    for(const id of method.kc){const kc=s.adopted.domain.knowledge.find(k=>k.id===id);if(!kc){issues.add('缺少知识 '+id);continue;}if(!rows.has(id))rows.set(id,{id,name:kc.name,roots:new Set()});rows.get(id)!.roots.add(root);}
    for(const step of method.steps){if(step.solutionId)visit(step.solutionId,root,[...path,id]);else if(step.decomposed)issues.add('子方法尚未指定。');}
  }
  for(const id of roots)visit(id,id,[]);
  return {rows:[...rows.values()],methods:[...methods],issues:[...issues]};
}
export function adoptedDefinitions(s:MockLearningSpace){
  const chapterTasks=[...new Set(spaceChapters(s).flatMap(ch=>ch.mappings.map(m=>m.taskId)))];
  const roots=[...new Set(spaceChapters(s).flatMap(ch=>ch.mappings.flatMap(m=>m.methods)))];
  const knowledge=courseKnowledge(s,roots),b=s.adopted;
  const entry=(kind:string,value:{id:string;name:string},current:unknown,version:string,currentVersion:string)=>({kind,id:value.id,name:value.name,value,current,version,currentVersion,changed:JSON.stringify(value)!==JSON.stringify(current)});
  return [
    entry('教材',b.book,textbookMock.books.find(x=>x.id===b.book.id),'v'+b.book.revision,'v'+(textbookMock.books.find(x=>x.id===b.book.id)?.revision||'?')),
    entry('学习目标',b.target,targetMock.targets.find(x=>x.id===b.target.id),'v'+b.target.revision,'v'+(targetMock.targets.find(x=>x.id===b.target.id)?.revision||'?')),
    ...spaceClaims(s).map(c=>entry('Task Claim',c,evaluationMock.claims.find(x=>x.id===c.id),'v'+c.version,'v'+(evaluationMock.claims.find(x=>x.id===c.id)?.version||'?'))),
    ...b.domain.tasks.filter(t=>chapterTasks.includes(t.id)).map(t=>entry('Task',t,domainMock.tasks.find(x=>x.id===t.id),'初始快照','当前内容')),
    ...b.domain.methods.filter(m=>knowledge.methods.includes(m.id)).map(m=>entry('Solution',m,domainMock.methods.find(x=>x.id===m.id),'初始快照','当前内容')),
    ...b.domain.knowledge.filter(k=>knowledge.rows.some(r=>r.id===k.id)).map(k=>entry('KC',k,domainMock.knowledge.find(x=>x.id===k.id),'初始快照','当前内容')),
  ];
}

// New browser-local course journeys are exposed through the existing space and learner views.
function syncCourseJourneys(state:FlowState){
  for(const space of learningSpaces.filter(s=>!s.id.startsWith('FLOW-SPACE-'))){
    const course=state.courses.find(c=>c.snapshot.book.id===space.adopted.book.id&&c.snapshot.target.id===space.adopted.target.id);
    if(course&&!space.history.some(h=>h.at===course.appliedAt&&h.actor==='管理员应用')){
      space.adopted=copy(course.snapshot);space.chapterIds=course.snapshot.book.units.flatMap(u=>u.chapters.map(ch=>ch.id));
      space.history.unshift({at:course.appliedAt,actor:'管理员应用',description:'教材与目标同步更新，历史作答保留，不要求学生维护章节或版本。'});
    }
  }
  for(const source of state.spaces){
    const course=state.courses.find(c=>c.id===source.courseId);if(!course)continue;
    const lessons=state.lessons.filter(a=>a.spaceId===source.id);
    const activities:SpaceActivity[]=lessons.map(a=>({id:a.id,name:'增加四分之一 · '+(a.stage==='finished'?'学习反馈':'学习中'),chapterId:a.chapterId,at:a.at,kind:'Mock 学习流程',help:'保留刚才讲解及逐题帮助；不直接认定独立完成。',messages:a.messages.map(m=>({actor:m.actor,text:m.text})),evidence:state.uses.filter(u=>u.activityId===a.id&&u.answer).map(u=>({id:'FLOW-EV-'+u.id,claimId:a.snapshot.claims.find(c=>c.taskId===u.question.taskId)?.id||'',aspectId:'independent',meaning:`Mock 表现记录：${u.result}。${u.help}；仅提供本次作答依据，不判为稳定掌握。`}))}));
    const latest=lessons.slice(-1)[0],lastClaim=latest?.snapshot.claims.find(c=>c.taskId==='fraction');
    const row:MockLearningSpace={id:source.id,name:source.name,studentId:'LEARNER-A',studentName:'学生 A',createdAt:source.createdAt,chapterIds:course.snapshot.book.units.flatMap(u=>u.chapters.map(ch=>ch.id)),classroom:null,adopted:copy(course.snapshot),activities,assessments:[],history:source.history.map(h=>({...h,actor:'本轮 mock 操作'})),judgments:latest&&lastClaim?lessonFeedback(state,latest).aspects.map((a,i)=>({claimId:lastClaim.id,aspectId:['independent','understanding','transfer','retention'][i]!,judgment:a[1]!,uncertainty:'交互走查结果，未运行真实 Evaluation。',evidenceIds:i===0?activities.flatMap(a=>a.evidence.map(e=>e.id)):[]})):[]};
    const index=learningSpaces.findIndex(s=>s.id===row.id);if(index<0)learningSpaces.push(row);else learningSpaces[index]=row;
  }
}
syncCourseJourneys(readFlow());subscribeFlow(syncCourseJourneys);
