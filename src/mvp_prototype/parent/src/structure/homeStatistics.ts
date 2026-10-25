// UI reference events, separate from local conversations and synthetic history search.
export type ActivityEvent = {
 id:string; learner:string; space:string; activity:string; title:string; day:string|null;
 kind:'teaching_display'|'check_display'|'answer_submitted'|'check_ended'|'login';
 submittedAnswers?:number;
};
export type ProblemHistory = {
 id:string; learner:string; space:string; title:string; hidden?:boolean;
 attempts:{outcome:'wrong'|'correct'|'pending'|'unanswered';source:string}[];
};
export const statisticsReferenceDate='2026-10-17';
const event=(id:string,activity:string,title:string,day:string|null,kind:ActivityEvent['kind'],submittedAnswers?:number):ActivityEvent=>({id,learner:'S0001',space:'school',activity,title,day,kind,submittedAnswers});
export const referenceEvents:ActivityEvent[]=[
 event('e01','lesson-old','理解单位“1”','2026-10-08','teaching_display'),
 event('e02','lesson-old','理解单位“1” · 继续','2026-10-12','teaching_display'),
 event('e03','lesson-a','找准比较标准','2026-10-12','teaching_display'),
 event('e04','lesson-a','找准比较标准 · 继续','2026-10-14','teaching_display'),
 event('e05','check-a','比较标准 · 阶段检查','2026-10-14','check_display'),
 event('e06','check-a','比较标准 · 提交作答','2026-10-14','answer_submitted'),
 event('e07','check-a','比较标准 · 检查结束','2026-10-14','check_ended',1),
 event('e08','lesson-b','比一个量多几分之几','2026-10-16','teaching_display'),
 event('e09','lesson-c','用图表示数量关系','2026-10-17','teaching_display'),
 event('e10','check-b','数量关系 · 检查','2026-10-17','check_display'),
 event('e11','check-b','数量关系 · 提交作答','2026-10-17','answer_submitted'),
 event('e12','check-b','数量关系 · 部分作答后求助结束','2026-10-17','check_ended',1),
 event('e13','check-empty','未作答便结束的检查','2026-10-17','check_ended',0),
 event('e14','login-only','仅打开产品','2026-10-13','login'),
 event('e15','lesson-unknown','早期讲解 · 日期未记录',null,'teaching_display'),
];
const problem=(id:string,title:string,source:string):ProblemHistory=>({id,learner:'S0001',space:'school',title,attempts:[{outcome:'wrong',source}]});
export const referenceProblems:ProblemHistory[]=[
 problem('HP-01','甲有 12 张卡，乙有 9 张，甲比乙多几分之几？','外部录入'),
 problem('HP-02','原价 80 元的书包降价四分之一，现价多少？','讲解练习'),
 problem('HP-03','实际用水 24 吨，比计划少五分之一，计划用水多少？','检测'),
 problem('HP-04','用线段图表示“第二天比第一天多三分之一”。','讲解练习'),
 problem('HP-05','甲数是乙数的四分之三，乙数比甲数多几分之几？','检测'),
 problem('HP-06','一根绳子用去五分之二，还剩 12 米，原来多长？','外部录入'),
 {...problem('HP-02','原价 80 元的书包降价四分之一，现价多少？','订正练习'),attempts:[{outcome:'correct',source:'订正练习'}]},
 {...problem('HP-07','图片中的分数尚未确认','外部录入'),attempts:[{outcome:'pending',source:'外部录入'}]},
 {...problem('HP-hidden','已隐藏的原始资料','外部录入'),hidden:true},
];
const validDay=(day:string|null):day is string=>!!day&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(Date.parse(`${day}T00:00:00Z`))&&new Date(`${day}T00:00:00Z`).toISOString().slice(0,10)===day;
export function calculateHomeStatistics(events:ActivityEvent[],problems:ProblemHistory[],days:7|30,through=statisticsReferenceDate,learner='S0001',space='school'){
 const fromDate=new Date(`${through}T00:00:00Z`);fromDate.setUTCDate(fromDate.getUTCDate()-days+1);const from=fromDate.toISOString().slice(0,10);
 const inWindow=(day:string|null)=>validDay(day)&&day>=from&&day<=through;
 const unique=[...new Map(events.filter(e=>e.learner===learner&&e.space===space).map(e=>[e.id,e])).values()];
 const learning=unique.filter(e=>['teaching_display','check_display','answer_submitted'].includes(e.kind)&&inWindow(e.day));
 const studyDays=[...new Set(learning.map(e=>e.day!))].sort();
 const teaching=unique.filter(e=>e.kind==='teaching_display');
 const lessons=[...new Set(teaching.map(e=>e.activity))].flatMap(id=>{
  const events=teaching.filter(e=>e.activity===id);
  // An unknown first-display date cannot be replaced by the last continuation date.
  if(events.some(e=>!validDay(e.day)))return [];
  const first=[...events].sort((a,b)=>a.day!.localeCompare(b.day!))[0]!;
  return inWindow(first.day)?[first]:[];
 });
 const checks=[...new Map(unique.filter(e=>e.kind==='check_ended'&&(e.submittedAnswers||0)>0&&inWindow(e.day)).map(e=>[e.activity,e])).values()];
 const visible=problems.filter(p=>p.learner===learner&&p.space===space&&!p.hidden);
 const wrongProblems=[...new Set(visible.map(p=>p.id))].flatMap(id=>{
  const rows=visible.filter(p=>p.id===id),attempts=rows.flatMap(p=>p.attempts);
  return attempts.some(a=>a.outcome==='wrong')?[{...rows[0]!,attempts}]:[];
 });
 return {from,through,studyDays,lessons,checks,wrongProblems,learning,
  undated:unique.filter(e=>e.kind!=='login'&&!validDay(e.day)).length};
}
