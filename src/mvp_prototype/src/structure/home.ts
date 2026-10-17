import { chapterOf, requirementState } from './data';
import { state } from './state';

// Frozen presentation references, never inferred from clicks, free text or new answers.
export const homeReference = {
  id:'HOME-REF-01', date:'2026-10-17', chapter:'fractions',
  title:'先弄清：为什么要除以比较标准？',
  reason:'参考记录中，你能找出比较标准；解释“为什么用它作除数”时，还需要提示。',
  duration:'约 5 分钟',
  question:'甲有 12 张卡片，乙有 9 张。甲比乙多几分之几？为什么？',
  answer:'以乙的 9 张为标准，相差 3 张。提示后写出 3÷9=1/3，但还没有说明为什么除以 9。',
  help:'作答前已提示“把乙的 9 张看作一整份”。',
  scope:'这条预写参考只说明本题的受助表现；不能推出整章不会，也不能证明独立掌握。',
};
// Authored presentation examples consistent with the existing requirement-state fixtures.
// These are not generated from local sessions and do not assert observed learner progress.
export const chapterFeedback:Record<string,{strength:string;attention:string;unknown:string;next:string}>={
 fractions:{
  strength:'能找出比较中的标准量，也能求增加或减少后的数量。',
  attention:'解释为什么用这个量作除数、处理分数混合运算，还需要加强。',
  unknown:'图与算式能否相互表达、是否会检查结果，还没有足够依据。',
  next:'先把比较标准和除数的关系讲清楚，再通过新的问题检查理解。',
 },
 circle:{
  strength:'能辨认圆心、半径和直径，也能说明面积公式的含义。',
  attention:'解释直径为什么等于两条半径时，还需要帮助。',
  unknown:'能否独立运用周长公式，目前还不能确定。',
  next:'结合图形，把同一个圆中半径与直径的关系说清楚。',
 },
 ratio:{
  strength:'能说清一个比的前项和后项分别表示什么。',
  attention:'怎样通过除法理解比值，还需要进一步弄清楚。',
  unknown:'换一种叙述后能否保持比较顺序，还没有足够依据。',
  next:'把比的两个对象与除法中的两个数量对应起来。',
 },
};
export function hasReference(learner='S0001',space='school'){
  return space==='school'&&(learner!=='S0001'||state.home.reference==='available');
}
export function displayRequirementState(learner:string,index:number,space='school'){
  return hasReference(learner,space)?requirementState(learner,index):'待确认';
}
export function chapterCounts(chapter:string,learner='S0001',space='school'){
  const definition=chapterOf(chapter);
  return ['已达标','需加强','待确认'].map(status=>definition?.requirements.filter((_,i)=>displayRequirementState(learner,i,space)===status).length||0);
}
export function topic(chapter:string){return ({fractions:'找准比较标准',circle:'理解半径与直径',ratio:'说清比的顺序'} as Record<string,string>)[chapter]||chapterOf(chapter)?.name||'本次学习';}
export function activityTime(timestamp?:number){
  if(!timestamp)return '此前学习 · 具体时间未记录';
  return `最近学习 ${new Date(timestamp).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})}`;
}
