import { textbookData } from './data';
import type { MaterialItem } from '../../shared/material-content';

export type LearningJudgment = '已达标' | '需加强' | '待确认';
export type PageId = 'home' | 'status' | 'textbook' | 'errorbook';
export interface RequirementView {
  id: string; name: string; status: LearningJudgment; standard: string; reason: string; questionIds: string[];
}
export interface ChapterView {
  id: string; name: string; unit: string; description: string; conclusion: string;
  requirements: RequirementView[]; explain: boolean; test: boolean; unavailable?: string; items?: MaterialItem[];
}
export interface AttemptView {
  id: string; at?: string; answer: string; result: '正确' | '错误' | '待判定';
  help: '独立作答' | '受助作答' | '帮助情况未确认'; detail: string; activityId?: string;
  ended: boolean; invalid?: string;
}
export interface QuestionView {
  id: string; chapterId: string; text: string; source: '外部录入' | '讲解练习' | '检测';
  attempts: AttemptView[]; note?: string; figure?: 'length'; quantity?: number;
}
export interface ActivityView {
  id: string; chapterId: string; title: string; detail: string; at: string; endedAt?: string;
  kind: '讲解' | '检测'; finished: boolean; partial?: boolean; learningDates: string[];
}
export interface StudentCourse {
  id: string; title: string; target: string; asOf: string; chapters: ChapterView[];
  questions: QuestionView[]; activities: ActivityView[]; note: string; todayMinutes?: number;
}
export const stateClass = (state: string) => state === '已达标' ? 'met' : state === '需加强' ? 'needs' : 'unknown';
export const states: LearningJudgment[] = ['已达标', '需加强', '待确认'];
export const counts = (rows: RequirementView[]) => states.map(status => ({status, count: new Set(rows.filter(r => r.status === status).map(r => r.id)).size}));
export const wasWrong = (q: QuestionView) => q.attempts.some(a => a.result === '错误' && !a.invalid);
export const latestAttempt = (q: QuestionView) => q.attempts[q.attempts.length-1];
export const dateOf = (value?: string) => value?.slice(0, 10);
export function inPeriod(at: string | undefined, days: number, asOf: string) {
  if (!at) return days === 0;
  const day = dateOf(at)!;
  if (day > asOf) return false;
  if (!days) return true;
  const start = new Date(asOf + 'T00:00:00+08:00');
  start.setUTCDate(start.getUTCDate() - days + 1);
  return day >= new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai'}).format(start);
}
export function periodLabel(days: number, asOf: string) {
  if (!days) return '全部日期（含作答日期未知）';
  const start = new Date(asOf + 'T00:00:00+08:00');
  start.setUTCDate(start.getUTCDate() - days + 1);
  return new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai'}).format(start) + ' — ' + asOf;
}
export function activityStats(course: StudentCourse, days: number) {
  const lectures = course.activities.filter(a => a.kind === '讲解' && a.learningDates.length && inPeriod(a.at, days, course.asOf));
  const tests = course.activities.filter(a => a.kind === '检测' && a.finished && a.endedAt && inPeriod(a.endedAt, days, course.asOf) && course.questions.some(q => q.attempts.some(t => t.activityId === a.id && t.answer)));
  const dates = [...new Set(course.activities.flatMap(a => a.learningDates).filter(d => inPeriod(d, days, course.asOf)))].sort().reverse();
  return {lectures, tests, dates, wrong: course.questions.filter(wasWrong)};
}
export function answerStats(course: StudentCourse, chapterId: string, days: number) {
  const attempts = course.questions.filter(q => !chapterId || q.chapterId === chapterId).flatMap(q => q.attempts.map(a => ({...a, questionId:q.id, text:q.text}))).filter(a => inPeriod(a.at, days, course.asOf));
  const eligible = attempts.filter(a => !a.invalid && a.ended && a.help === '独立作答' && a.result !== '待判定');
  return {attempts, eligible, correct:eligible.filter(a => a.result === '正确'), excluded:attempts.filter(a => !eligible.includes(a))};
}

const attempt = (id:string, at:string|undefined, answer:string, result:AttemptView['result'], help:AttemptView['help'], activityId:string, detail=''):AttemptView => ({id, at, answer, result, help, activityId, detail, ended:true});
const questions: QuestionView[] = [
  {id:'Q-LENGTH',chapterId:'c4-3',text:'一条绳子原来长48米，增加原长的四分之一后，现在长多少米？',source:'外部录入',attempts:[
    attempt('A1','2026-10-22 16:00','48 × 1/4 = 12米。','错误','独立作答','DEMO-OLD','12米是增加量，尚未求总长。'),
    attempt('A2','2026-10-24 18:00','48 + 12 = 60米。','正确','受助作答','DEMO-L1','看过讲解后的订正，原作答仍保留。')],note:'已讲解 · 已订正'},
  {id:'Q-BOOKS',chapterId:'c4-3',text:'图书角原有80本书，新增原有数量的四分之一。现在有多少本？说明理由。',source:'检测',attempts:[attempt('A3','2026-10-25 18:03','80 × 1/4 = 20，80 + 20 = 100本。新增的20本要加回原有80本。','正确','独立作答','DEMO-T1')]},
  {id:'Q-BOXES',chapterId:'c4-3',text:'仓库原有36箱货物，又运来原有数量的四分之一。现在共有多少箱？',source:'检测',attempts:[attempt('A4','2026-10-25 18:07','36 ÷ 4 = 9，36 + 9 = 45箱。','正确','独立作答','DEMO-T1')]},
  {id:'Q-EXPLAIN',chapterId:'c4-3',text:'原有40本书，增加四分之一。为什么可以算40 × (1 + 1/4)？',source:'检测',attempts:[attempt('A5','2026-10-27 18:05','1表示原来的40本，1/4是以这40本为整体的增加比例，合起来是50本。','正确','独立作答','DEMO-T2')]},
  {id:'Q-GRAPH',chapterId:'c4-3',text:'图中原长为80米，新增一段是原长的四分之一。现在的总长是多少米？请说明理由。',source:'检测',figure:'length',attempts:[attempt('A6','2026-10-27 18:08','80 × 1/4 = 20米。','错误','独立作答','DEMO-T2','只计算了新增段，没有把图中的原长算入总长。')]},
  {id:'Q-PENDING',chapterId:'c4-3',text:'甲比乙多四分之一，乙比甲少几分之几？请解释。',source:'外部录入',attempts:[attempt('A7',undefined,'我觉得是四分之一。','待判定','帮助情况未确认','','原作答日期未知；仍需核对题面与解释。')]},
  {id:'Q-NEW',chapterId:'c4-3',text:'一件商品先提价十分之一，再降价十分之一，价格回到原来了吗？',source:'外部录入',attempts:[],note:'尚未作答，可以直接求助。'},
  {id:'Q-TEMP',chapterId:'c1-1',text:'早晨气温为零下3℃，升高5℃后是多少？',source:'讲解练习',attempts:[attempt('A8','2026-10-23 18:05','2℃。','正确','受助作答','DEMO-L0','刚看过温度计示意图。')]},
];
const requirements: RequirementView[] = [
  {id:'R1',name:'在文字题中求出增加的部分',status:'已达标',standard:'在规定的单步数量增加文字题中，自己找出原量并正确计算增加量。',reason:'两次文字题都正确找到了原量和增加比例。',questionIds:['Q-BOOKS','Q-BOXES']},
  {id:'R2',name:'在文字题中求出增加后的总量',status:'已达标',standard:'在约定的文字情境下区分增加量与总量，正确计算并保留单位。',reason:'早期曾漏加原量；后续两次不同文字题能自行把增加量加回原量。此判断不包含图示迁移。',questionIds:['Q-LENGTH','Q-BOOKS','Q-BOXES']},
  {id:'R3',name:'说明为什么要加上原来的量',status:'已达标',standard:'用自己的话解释原量、增加量和总量的关系，能够说明列式中每一项的意义。',reason:'后续检测中能解释1与1/4各表示什么，并说明新增部分为何要加回原量。',questionIds:['Q-BOOKS','Q-EXPLAIN']},
  {id:'R4',name:'换成长度图仍能求出总量',status:'需加强',standard:'从规定的长度图中识别原长与新增段，求出完整总长。',reason:'图示题只算出了新增的20米，漏加了原来的80米。',questionIds:['Q-GRAPH']},
  {id:'R5',name:'比较两个量时正确选择参照量',status:'待确认',standard:'改变比较方向后能重新选择整体并解释两个比例为何不同。',reason:'目前只有一份尚待核对的外部作答，不能判断是否达到要求。',questionIds:['Q-PENDING']},
  {id:'R6',name:'间隔后仍能自己解决同类题',status:'待确认',standard:'满足所选目标约定的间隔与帮助条件，再完成相应任务。',reason:'尚无约定间隔后的新检测；时间过去了不等于已保持。',questionIds:[]},
];
export function demoCourse(id:string, title:string):StudentCourse {
  if(id !== 'math-6b')return {id,title,target:'尚未选择学习目标',asOf:'2026-10-29',chapters:[],questions:[],activities:[],note:'此空间尚未准备内容与学习记录。',todayMinutes:12};
  return {id,title:'数学 · 六年级下册',target:'比例应用与相关基础 · 示例学习目标',asOf:'2026-10-29',todayMinutes:12,
    note:'示例数据 · 统计截至 2026-10-29；不代表真实学习结果。',questions,
    chapters:textbookData.units.flatMap(u=>u.chapters.map(ch=>({id:ch.id,name:ch.name,unit:u.name,description:ch.description.replace('（当前章节）',''),
      conclusion:ch.id==='c4-3'?'文字题中已能求出总量；换成长度图时，还容易只算增加的部分。':ch.id==='c1-1'?'有受助后的练习记录，还需要看自己作答的表现。':'评价要求尚未准备，暂不作个人判断。',
      requirements:ch.id==='c4-3'?requirements:ch.id==='c1-1'?[{id:'R-N1',name:'自己解释并计算温度的变化',status:'待确认' as const,standard:'根据正负数的含义说明气温变化，独立完成计算。',reason:'当前只有看过图示后的练习，独立表现仍待确认。',questionIds:['Q-TEMP']}]:[],
      explain:true,test:ch.id==='c4-3'||ch.id==='c1-1',unavailable:ch.id!=='c4-3'&&ch.id!=='c1-1'?'检测要求尚未准备，仍可以请求讲解。':undefined}))),
    activities:[
      {id:'DEMO-L2',chapterId:'c4-3',title:'从图中找出原长与新增段',detail:'上次停在：图中的20米表示什么；对话和草稿已保留。',at:'2026-10-28 18:00',kind:'讲解',finished:false,learningDates:['2026-10-28','2026-10-29']},
      {id:'DEMO-T2',chapterId:'c4-3',title:'说明数量关系，试一题长度图',detail:'两次作答：一次正确，一次错误。',at:'2026-10-27 18:00',endedAt:'2026-10-27 18:10',kind:'检测',finished:true,learningDates:['2026-10-27']},
      {id:'DEMO-T1',chapterId:'c4-3',title:'数量增加的文字题检测',detail:'两次作答均正确，依据仅限当时的文字情境。',at:'2026-10-25 18:00',endedAt:'2026-10-25 18:10',kind:'检测',finished:true,learningDates:['2026-10-25']},
      {id:'DEMO-L1',chapterId:'c4-3',title:'区分增加量与总量',detail:'讲解后订正了48米绳子的题目。',at:'2026-10-24 18:00',kind:'讲解',finished:true,learningDates:['2026-10-24']},
      {id:'DEMO-L0',chapterId:'c1-1',title:'用温度计理解正负数',detail:'看图后完成了温度变化练习。',at:'2026-10-23 18:00',kind:'讲解',finished:true,learningDates:['2026-10-23']},
    ]};
}
