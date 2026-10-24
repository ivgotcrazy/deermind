import type { MockLearningSpace } from '../admin/src/workbench/learning-space-mock';

// Browser-local interaction fixtures only. No LLM, semantic classifier or inference engine.
export type CourseSnapshot = MockLearningSpace['adopted'];
export interface Question {
  id:string; taskId:string; domainId:string; question:string; parameters:string; answer:string; explanation:string;
  source:string; sourceNote:string; version:number; parentId?:string; variation?:string; methods?:string[];
  figure?:'triangle'|'garden'|'length'; quantity?:number; checkedAt?:string;
}
export interface Course { id:string; snapshot:CourseSnapshot; appliedAt:string }
export interface CourseSpace { id:string; name:string; courseId:string; createdAt:string; history:{at:string;description:string}[] }
export interface QuestionUse {
  id:string; activityId:string; spaceId:string; at:string; purpose:'讲解'|'练习'|'检测'; question:Question;
  answer?:string; result?:'正确'|'错误'|'待确认'; help:string;
}
export interface LessonMessage { id:string; actor:'学生'|'DeerMind'; text:string; at:string; useId?:string }
export interface Lesson {
  id:string; spaceId:string; chapterId:string; snapshot:CourseSnapshot; at:string;
  stage:'explaining'|'practice'|'offer'|'testing'|'finished'; messages:LessonMessage[];
  useIds:string[]; practiceId?:string; testIds:string[]; testQuestions?:Question[]; current:number; draft:string; endReason?:string;
}
export interface FlowState { questions:Question[]; courses:Course[]; spaces:CourseSpace[]; lessons:Lesson[]; uses:QuestionUse[] }
export const FLOW_KEY='deermind-next-learning-flow-v1';
const event='deermind-learning-flow';
export const copy=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
export const now=()=>new Date().toLocaleString('sv-SE',{hour12:false});
export const uid=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8).toUpperCase();
export function readFlow():FlowState {
  const text=localStorage.getItem(FLOW_KEY);
  return text?JSON.parse(text):{questions:[],courses:[],spaces:[],lessons:[],uses:[]};
}
export function changeFlow(run:(state:FlowState)=>void){
  const state=readFlow();run(state);localStorage.setItem(FLOW_KEY,JSON.stringify(state));window.dispatchEvent(new Event(event));
}
export function subscribeFlow(run:(state:FlowState)=>void){
  const update=()=>run(readFlow()),storage=(e:StorageEvent)=>{if(e.key===FLOW_KEY)update();};
  window.addEventListener(event,update);window.addEventListener('storage',storage);
  return ()=>{window.removeEventListener(event,update);window.removeEventListener('storage',storage);};
}
export function saveQuestion(q:Question){
  let saved:Question;
  changeFlow(s=>{const index=s.questions.findIndex(x=>x.id===q.id),old=s.questions[index];
    saved={...copy(q),id:q.id||uid('TI'),version:(old?.version||0)+1,checkedAt:now()};
    if(index<0)s.questions.unshift(saved);else s.questions[index]=saved;
  });return saved!;
}
export function applyCourse(snapshot:CourseSnapshot){
  changeFlow(s=>{
    const id=snapshot.book.id+'::'+snapshot.target.id,course={id,snapshot:copy(snapshot),appliedAt:now()};
    const index=s.courses.findIndex(c=>c.id===id);if(index<0)s.courses.push(course);else s.courses[index]=course;
    s.spaces.filter(x=>x.courseId===id).forEach(x=>x.history.unshift({at:now(),description:`管理员应用教材 v${snapshot.book.revision}、目标 v${snapshot.target.revision}；原活动保留当时内容。`}));
  });
}
export function createSpace(courseId:string){
  const course=readFlow().courses.find(c=>c.id===courseId);if(!course)throw Error('请先选择可用教材和目标。');
  const space:CourseSpace={id:uid('FLOW-SPACE'),name:course.snapshot.book.name,courseId,createdAt:now(),history:[{at:now(),description:'学生选用教材和目标；章节在每次学习时选择。'}]};
  changeFlow(s=>s.spaces.push(space));return space;
}
export function chapterReady(b:CourseSnapshot,chapterId:string){
  const chapter=b.book.units.flatMap(u=>u.chapters).find(c=>c.id===chapterId);
  const explain=!!chapter?.content.trim()&&!!chapter.checked&&chapter.mappings.some(m=>m.methods.length>0);
  const selection=b.target.claims.find(x=>x.requirements.some(r=>r.chapterIds.includes(chapterId))&&b.claims.some(c=>c.id===x.claimId&&chapter?.mappings.some(m=>m.taskId===c.taskId)));
  const claim=b.claims.find(c=>c.id===selection?.claimId),mapping=chapter?.mappings.find(m=>m.taskId===claim?.taskId);
  const methods=!!claim?.methods.length&&(claim.methodMode==='all'?claim.methods.every(id=>mapping?.methods.includes(id)):claim.methods.some(id=>mapping?.methods.includes(id)));
  const test=explain&&!!selection?.requirements.length&&methods&&selection.requirements.filter(r=>r.chapterIds.includes(chapterId)).every(r=>r.standard.trim()&&r.aspectIds.length&&r.aspectIds.every(id=>claim?.aspects.some(a=>a.id===id&&a.applicable&&a.criterion.trim()&&a.evidence.trim())));
  return {explain,test,scripted:!!chapter?.mappings.some(m=>m.taskId==='fraction'),reason:!explain?'讲解内容和方法尚待准备':!test?'检测标准或方法条件尚待补齐':''};
}
export function fractionQuestion(quantity:number,source:string,figure=false):Question {
  return {id:uid('TI'),domainId:'DOM-MATH',taskId:'fraction',version:1,quantity,source,sourceNote:'分数增加问题的固定 mock 生成器；不调用模型。',parameters:`原量 = ${quantity}\n增加分率 = 1/4`,
    question:figure?`图中原长为 ${quantity} 米，延长部分是原长的四分之一。现在总长是多少米？请说明理由。`:`原来有 ${quantity} 本书，又增加了原来数量的四分之一。现在有多少本？请写出答案和思路。`,
    answer:String(quantity*1.25),explanation:`增加量：${quantity} × 1/4 = ${quantity/4}；总量：${quantity} + ${quantity/4} = ${quantity*1.25}。原来的量仍要保留。`,methods:['S1-A'],variation:figure?'文字转为长度示意图':'数值变化，不单独认定为迁移',figure:figure?'length':undefined,checkedAt:now()};
}
function message(a:Lesson,actor:LessonMessage['actor'],text:string){a.messages.push({id:uid('MSG'),actor,text,at:now()});}
function show(s:FlowState,a:Lesson,q:Question,purpose:QuestionUse['purpose']){
  const use:QuestionUse={id:uid('USE'),activityId:a.id,spaceId:a.spaceId,at:now(),purpose,question:copy(q),help:purpose==='讲解'?'完整讲解':s.uses.some(u=>u.activityId===a.id&&u.purpose==='讲解')?'此前刚接受同类讲解；本题尚未提供提示':'本题尚未提供提示；其他接触背景未验证'};
  s.uses.push(use);a.useIds.push(use.id);a.messages.push({id:uid('MSG'),actor:'DeerMind',text:q.question,at:now(),useId:use.id});return use;
}
export function beginLesson(spaceId:string,chapterId:string,mode:'lesson'|'test'='lesson'){
  let id='';changeFlow(s=>{
    const space=s.spaces.find(x=>x.id===spaceId),course=s.courses.find(c=>c.id===space?.courseId);if(!course)throw Error('课程不存在。');
    const ready=chapterReady(course.snapshot,chapterId);if(!(mode==='test'?ready.test:ready.explain)||!ready.scripted)throw Error('本章暂未准备这条 mock 学习流程。');
    const active=s.lessons.find(x=>x.spaceId===spaceId&&x.stage==='testing');if(active)throw Error('请先完成或结束当前检测。');
    const a:Lesson={id:uid('FLOW-ACT'),spaceId,chapterId,snapshot:copy(course.snapshot),at:now(),stage:mode==='test'?'offer':'explaining',messages:[],useIds:[],testIds:[],current:0,draft:''};id=a.id;s.lessons.push(a);
    if(mode==='lesson'){
      message(a,'学生','请讲解一个量增加四分之一后是多少。');
      let q=s.questions.find(x=>x.taskId==='fraction'&&x.quantity===80);if(!q){q=fractionQuestion(80,'学习中生成');q.sourceNote+=' 首次用于例题讲解。';s.questions.push(q);}show(s,a,q,'讲解');
      message(a,'DeerMind',`先求增加的部分：80 × 1/4 = 20。原来的 80 本仍然在，所以总量是 80 + 20 = 100 本。\n这次先分清“增加多少”和“增加后多少”，不用一次学完整章。`);
    }else message(a,'学生','我想检测这一节。');
  });return id;
}
export function practice(activityId:string){changeFlow(s=>{
  const a=s.lessons.find(x=>x.id===activityId)!;if(a.stage!=='explaining')return;
  let q=s.questions.find(x=>x.taskId==='fraction'&&x.quantity===60);if(!q){q=fractionQuestion(60,'学习中生成');s.questions.push(q);}a.practiceId=show(s,a,q,'练习').id;a.stage='practice';
});}
export function offerTest(activityId:string){changeFlow(s=>{const a=s.lessons.find(x=>x.id===activityId)!;if(a.stage==='explaining'||a.stage==='finished'){a.stage='offer';a.endReason=undefined;}});}
export function startTest(activityId:string){changeFlow(s=>{
  const a=s.lessons.find(x=>x.id===activityId)!;if(a.stage!=='offer')return;
  if(!chapterReady(a.snapshot,a.chapterId).test)throw Error('当前活动采用的检测依据尚未准备。');
  const seen=new Set(s.uses.filter(u=>u.spaceId===a.spaceId).map(u=>u.question.id));
  // This finite fixture demonstrates selection and generation; it is not a general item selector.
  let first=s.questions.find(q=>q.taskId==='fraction'&&q.domainId===a.snapshot.book.domainId&&q.quantity===120&&!q.figure&&!seen.has(q.id));
  if(!first){let quantity=120;while(s.uses.some(u=>u.spaceId===a.spaceId&&u.question.quantity===quantity&&!u.question.figure))quantity+=20;first=fractionQuestion(quantity,'学习中生成');s.questions.push(first);}
  let second=s.questions.find(q=>q.taskId==='fraction'&&q.domainId===a.snapshot.book.domainId&&q.quantity===48&&q.figure==='length'&&!seen.has(q.id));
  if(!second){let quantity=48;while(s.uses.some(u=>u.spaceId===a.spaceId&&u.question.quantity===quantity&&u.question.figure==='length'))quantity+=8;second=fractionQuestion(quantity,'学习中生成',true);second.parentId=first.id;s.questions.push(second);}
  a.testIds=[first.id,second.id];a.testQuestions=copy([first,second]);a.current=0;a.stage='testing';a.draft='';show(s,a,first,'检测');
});}
export function submitAnswer(activityId:string,answer:string,result:QuestionUse['result']){changeFlow(s=>{
  const a=s.lessons.find(x=>x.id===activityId)!;if(!answer.trim()||!['practice','testing'].includes(a.stage))return;
  const use=a.stage==='practice'?s.uses.find(u=>u.id===a.practiceId):s.uses.filter(u=>u.activityId===a.id&&u.purpose==='检测').slice(-1)[0];if(!use||use.answer)return;
  use.answer=answer.trim();use.result=result;a.draft='';message(a,'学生',answer.trim());
  if(a.stage==='practice'){message(a,'DeerMind',result==='错误'?`这次练习的判定示例是“错误”。${use.question.explanation}`:result==='正确'?'这次练习的判定示例是“正确”。这只是当堂表现，还不能确认稳定掌握。':'本次答案尚未判定，先保留原作答。');a.stage='explaining';}
  else {a.current++;if(a.current<a.testIds.length)show(s,a,a.testQuestions?.[a.current]||s.questions.find(q=>q.id===a.testIds[a.current])!,'检测');else{a.stage='finished';a.endReason='完成';message(a,'DeerMind','本次检测已完成。下面分别查看题目结果和学习要求的判断。');}}
});}
export function endLesson(activityId:string,help=false){changeFlow(s=>{
  const a=s.lessons.find(x=>x.id===activityId)!;if(a.stage==='finished')return;
  const use=s.uses.filter(u=>u.activityId===a.id&&u.purpose!=='讲解'&&!u.answer).slice(-1)[0];
  if(help&&use&&a.stage==='practice'){use.help+='；练习中求助并获得完整讲解';message(a,'学生','这道练习我需要帮助。');message(a,'DeerMind',`${use.question.explanation}\n这次没有提交答案，不判错。可以继续讲解，或准备一次检测。`);a.stage='explaining';a.draft='';return;}
  a.stage='finished';a.endReason=help?'求助后结束':'主动结束';
  if(help&&use){use.help+='；本次求助后获得完整讲解';message(a,'学生','结束并求助。');message(a,'DeerMind',`本次检测已结束，未提交的题目不判错。\n${use.question.explanation}`);}
});}
export function sendLessonMessage(activityId:string,text:string){changeFlow(s=>{
  const a=s.lessons.find(x=>x.id===activityId)!;if(a.stage==='testing'||!text.trim())return;
  message(a,'学生',text.trim());message(a,'DeerMind','这是固定内容的交互走查，不调用真实模型理解这句话。例题中增加的是原来的四分之一，原来的整份还在；你可以继续练习，或准备一次短检测。');
});}
export function lessonUses(s:FlowState,a:Lesson){return s.uses.filter(u=>u.activityId===a.id);}
export function lessonFeedback(s:FlowState,a:Lesson){
  const rows=lessonUses(s,a).filter(u=>u.purpose==='检测'),answered=rows.filter(u=>u.answer),correct=answered.filter(u=>u.result==='正确').length;
  return {answered:answered.length,correct,total:a.testIds.length,unknown:answered.filter(u=>u.result==='待确认').length,
    summary:`已提交 ${answered.length}/${a.testIds.length} 题；${correct} 题判为正确${answered.some(u=>u.result==='待确认')?'，部分尚待判定':''}（mock）。`,
    aspects:[['独立完成',answered.length?'已保留当堂作答和实际帮助，稳定独立完成仍待确认。':'尚无检测作答。'],['理解与解释','原始思路已保留；本原型不做真实语义评价，待确认。'],['迁移','图示变化与接触历史已记录；不因换数字或答案正确直接认定迁移。'],['延迟保持','本次未取得延迟后的表现，待确认。']]};
}
