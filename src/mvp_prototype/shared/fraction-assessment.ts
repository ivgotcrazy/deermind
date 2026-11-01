import type { FlowState, Lesson, QuestionUse } from './learning-flow';

// Authored cases for product review, not a semantic evaluator or mastery formula.
export const fractionCases={mixed:'文字能解释，图示把增加量当总量',supported:'两种方法都能说明理由',bare:'只有数值答案',unclear:'输入不足，暂不判定'};
export type FractionCase=keyof typeof fractionCases;
export const isFractionLesson=(a:Lesson)=>a.snapshot.book.units.flatMap(u=>u.chapters).find(c=>c.id===a.chapterId)?.mappings.some(m=>m.taskId==='fraction')||false;
export const fractionFollowups=[
  {label:'为什么不是 20 米？',reply:'20 米是新增的部分，原来的 80 米并没有消失。题目问现在的总长度，所以还要加上原长：80 + 20 = 100 米。'},
  {label:'可以直接乘四分之五吗？',reply:'可以。原长是一整份，增加的是这同一整份的 1/4，所以现在是原长的 1 + 1/4 = 5/4。80 × 5/4 = 100 米。它和先求增加量再相加，是同一数量关系的两种方法。'},
];
export function fractionSample(q:QuestionUse['question'],kind:FractionCase,purpose:QuestionUse['purpose']='检测'):{answer:string;result:QuestionUse['result']} {
  const n=q.quantity||0,total=n*1.25,extra=n/4,unit=q.figure==='length'?'米':'本';
  if(kind==='unclear')return {answer:'我还没分清题目要求哪个量。',result:'待确认'};
  if(kind==='bare')return {answer:String(total),result:'正确'};
  if(kind==='mixed'&&purpose==='练习')return {answer:`${n} × 1/4 = ${extra}，我把增加量当成了现在的总量。`,result:'错误'};
  if(kind==='mixed'&&q.figure==='length')return {answer:`${n} × 1/4 = ${extra} 米，我把新增的这段当成现在的总长。`,result:'错误'};
  return {answer:kind==='supported'?`${n} × (1 + 1/4) = ${total} ${unit}。1 是原来的一整份，1/4 也是以原量为基准，合起来才是现在的总量。`:`${n} × 1/4 = ${extra}，${n} + ${extra} = ${total} ${unit}。四分之一以原量为基准，增加量还要加回原量。`,result:'正确'};
}
export function correctionFor(s:FlowState,u:QuestionUse){return s.corrections?.find(c=>c.questionId===u.question.id&&c.version===u.question.version);}
export interface FractionAspect {id:string;name:string;belief:string;status:'待确认'|'需加强';reason:string;uses:QuestionUse[]}
export function fractionAssessment(s:FlowState,a:Lesson):FractionAspect[] {
  const uses=s.uses.filter(u=>u.activityId===a.id&&u.purpose==='检测'&&u.answer&&!correctionFor(s,u));
  const valid=uses.filter(u=>{const expected=fractionSample(u.question,a.fractionCase||'mixed');return u.answer===expected.answer&&u.result===expected.result;});
  const text=valid.find(u=>!u.question.figure),graph=valid.find(u=>u.question.figure==='length');
  const explains=a.fractionCase!=='bare'&&text?.result==='正确';
  const claim=a.snapshot.claims.find(c=>c.taskId==='fraction');
  const taught=s.uses.some(u=>u.activityId===a.id&&u.purpose==='讲解');
  const rows:FractionAspect[]=[
    {id:'independent',name:'独立完成',belief:'尚不能确认稳定独立完成。',status:'待确认',reason:taught?'刚接受同类讲解，上文与右侧教材仍可见；保留当堂表现，不把它改标成独立证据。':'本次未先讲解，但右侧教材可见，其他接触和帮助情况未核实；保留这次表现，不直接确认稳定独立完成。',uses:valid},
    {id:'understanding',name:'理解与解释',belief:explains?`本次能说明原量、增加量与总量的关系${taught?'；这是刚讲解后的表现。':'。'}`:'目前没有足够的解释依据。',status:'待确认',reason:explains?(taught?'这次解释符合预设数量关系，但与刚展示的解法相近；为当堂理解提供局部依据，仍需核对能否自行解释。':'这次解释符合预设数量关系，提供局部支持；接触背景未核实，仍需核对能否自行解释。'):a.fractionCase==='bare'?'答案正确不代替解释；没有写理由不直接判为不会解释。':'自由输入、未提交、判定未决或已作废依据均不套用预写的正向结论。',uses:text?[text]:[]},
    {id:'transfer',name:'迁移',belief:graph?.result==='错误'?'本次图示题把增加量误当成总量。':graph?.result==='正确'&&a.fractionCase!=='bare'?'本次长度图中能解释总量关系；结论仅限这一种表示。':'尚无充分的图示迁移依据。',status:graph?.result==='错误'?'需加强':'待确认',reason:graph?.result==='错误'?'图中原长与新增部分已给全；作答只求新增部分，与求总长的要求不符。':graph?.result==='正确'&&a.fractionCase!=='bare'?`保留这次新表示下的局部支持；只有一张图，${taught?'且刚接受同类教学':'接触背景未核实'}，不据此确认稳定迁移。`:'换数字不构成图示迁移，数值答案也不能证明读懂了图中关系。',uses:graph?[graph]:[]},
    {id:'retention',name:'延迟保持',belief:'本次没有延迟后的表现。',status:'待确认',reason:'没有发生约定间隔后的新检测，不因为检测结束或时间流逝增加保持证据。',uses:[]},
  ];
  return rows.filter(r=>claim?.aspects.some(p=>p.id===r.id&&p.applicable));
}
