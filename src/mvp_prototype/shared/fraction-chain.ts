import type { Lesson, Question, QuestionUse, FlowState } from './learning-flow';

// Authored interaction examples, not an evaluator. Exact fixture matching prevents
// these conclusions being attached to arbitrary text entered during a walkthrough.
export const chainTask='fraction-chain';
export const chainCases={mixed:'文字能解释，图示仍需帮助',supported:'两题均能说明参照量',unclear:'答案信息不足'};
export type ChainCase=keyof typeof chainCases;
export const chainRequirements:Record<string,{name:string;standard:string}>={
  independent:{name:'能自行解决两层部分关系的问题',standard:'没有本题或紧邻同类解法帮助时，自行确定两层参照量并正确计算；仅有刚听完讲解后的表现，保持待确认。'},
  understanding:{name:'能解释文字题中的两层参照量',standard:'在新的文字题中，用自己的话说明两个分数分别对应哪个量、每一步求什么；允许此前学习过同类讲解，本题不提示关键关系。此要求不覆盖图示迁移。'},
  transfer:{name:'换成区域图也能找准参照量',standard:'在本例规定的等分区域图中，先识别中间区域，再求其一部分，并说明理由；仅在文字题换数字不算达到。结论限于这类图示。'},
  retention:{name:'隔一段时间后仍能完成',standard:'需要约定间隔后的新表现，并保留期间帮助和练习背景。本次当堂样例没有这类记录，保持待确认。'},
};
export const isChainLesson=(a:Lesson)=>a.snapshot.book.units.flatMap(u=>u.chapters).find(c=>c.id===a.chapterId)?.mappings.some(m=>m.taskId===chainTask)||false;
export const chainOpening='先看每个分数是“谁的几分之几”。气象小组有 12 人，摄影小组是气象小组的 1/3，所以摄影有 12 × 1/3 = 4 人。航模小组是摄影小组的 3/4，所以航模有 4 × 3/4 = 3 人。第二个分数对应的是摄影的 4 人，不能直接把它当成气象的 12 人的 3/4。';
export const chainFollowups=[
  {label:'为什么第二次用 4，不用 12？',reply:'因为题目说“航模小组是摄影小组的 3/4”。先找到摄影的 4 人，再把这 4 人看成一整份，取其中的 3/4。若用 12 × 3/4，求到的是气象小组人数的 3/4，参照量换错了。'},
  {label:'能不能先算两个分数？',reply:'可以。摄影占气象的 1/3，航模又占摄影的 3/4，所以航模占气象的 1/3 × 3/4 = 1/4。再算 12 × 1/4 = 3 人。这对应另一种解法：先合并比例，再求部分量。两种解法都要保持同一条参照关系。'},
  {label:'为什么月季不是整块苗圃的一半？',reply:'图里先把整块分成5列，其中3列是花区，所以花区为 40 × 3/5 = 24 平方米。上下各一半是在这3列花区内分的，月季只有 24 × 1/2 = 12 平方米。右侧2列不属于花区，不能把它们也算进“一半”的参照量。这段帮助发生在检测结束后，不改写你刚才的原作答或评价。'},
];
export function chainQuestion(kind:'example'|'practice'|'text'|'diagram'):Question {
  const q={
    example:{quantity:12,question:'气象小组有 12 人。摄影小组人数是气象小组的 1/3，航模小组人数是摄影小组的 3/4。航模小组有多少人？',answer:'3 人',explanation:'12 × 1/3 = 4（人）；4 × 3/4 = 3（人）。也可用 12 × (1/3 × 3/4) = 3（人）。'},
    practice:{quantity:24,question:'手工社团有 24 人，其中 1/3 参加纸艺组，纸艺组的 3/4 制作纸花。制作纸花的有多少人？请说明两个分数分别对应谁。',answer:'6 人',explanation:'纸艺组：24 × 1/3 = 8（人）；纸花组：8 × 3/4 = 6（人）。第二个分数以纸艺组为参照量。'},
    text:{quantity:30,question:'图书角有 30 本书，其中 2/5 是科普书，科普书的 1/2 是动物类。动物类有多少本？请说明两个分数分别对应哪个量。',answer:'6 本',explanation:'科普书：30 × 2/5 = 12（本）；动物类：12 × 1/2 = 6（本）。2/5 对应全部 30 本，1/2 对应科普书的 12 本。'},
    diagram:{quantity:40,question:'整块苗圃面积为 40 平方米，分成面积相等的 5 列，其中 3 列为花区。花区分为面积相等的上下两部分，上半部种月季。月季区面积是多少？请结合图说明参照量。',answer:'12 平方米',explanation:'花区占整块苗圃的 3/5：40 × 3/5 = 24（平方米）。月季区占花区的 1/2：24 × 1/2 = 12（平方米），不是整块苗圃的一半。'},
  }[kind];
  return {id:'CHAIN-'+kind.toUpperCase(),taskId:chainTask,domainId:'DOM-MATH',version:1,...q,
    parameters:kind==='text'?'q=30，r=2/5，s=1/2':kind==='diagram'?'q=40，r=3/5，s=1/2':`q=${q.quantity}，r=1/3，s=3/4`,
    source:kind==='example'?'教材':'学习中生成',sourceNote:kind==='example'?'北师大版六上，第49—50页；原题的文字整理。':'固定 mock 候选；展示已检查保存的结果，不运行生成或归类模型。',
    methods:['S-CHAIN-A','S-CHAIN-B'],variation:kind==='diagram'?'从文字数量关系变为嵌套区域图；不以换数字冒充迁移':'数值与情境变化',figure:kind==='diagram'?'nested':undefined,
  };
}
const answers:Record<ChainCase,{answer:string;result:QuestionUse['result']}[]>={
  mixed:[
    {answer:'30 × 2/5 = 12，12 × 1/2 = 6 本。2/5 是全部书的几分之几，1/2 是科普书的几分之几。',result:'正确'},
    {answer:'40 × 1/2 = 20 平方米。上面是一半，所以用整块的 40 来算。',result:'错误'},
  ],
  supported:[
    {answer:'30 × 2/5 = 12，12 × 1/2 = 6 本。2/5 对应全部书，1/2 对应科普书；也可先算 2/5 × 1/2，再乘 30。',result:'正确'},
    {answer:'40 × 3/5 = 24，24 × 1/2 = 12 平方米。先找花区，图中月季占花区的一半，不是整块苗圃的一半。',result:'正确'},
  ],
  unclear:[{answer:'应该是 6，我还没写过程。',result:'待确认'},{answer:'我还没看清图中的哪一块。',result:'待确认'}],
};
export const chainAnswer=(a:Lesson)=>answers[a.reviewCase||'mixed'][a.current];
export interface ChainAspect {id:string;name:string;status:'已达标'|'需加强'|'待确认';belief:string;reason:string;evidence:number[];next:string}
export function chainAssessment(s:FlowState,a:Lesson):{matched:boolean;rows:ChainAspect[]} {
  const uses=s.uses.filter(u=>u.activityId===a.id&&u.purpose==='检测');
  const taught=s.uses.some(u=>u.activityId===a.id&&u.purpose==='讲解');
  const expected=answers[a.reviewCase||'mixed'];
  const matched=a.endReason==='完成'&&uses.length===2&&uses.every((u,i)=>u.answer===expected[i]!.answer&&u.result===expected[i]!.result);
  const pending=(!matched?'输入不属于完整预设场景；没有调用模型解释本次作答。':'尚无足够依据。');
  const rows:ChainAspect[]=[
    {id:'independent',name:'独立完成',status:'待确认',belief:taught?'本题未给步骤提示，但刚接受同类讲解。':'本题未给步骤提示；其他接触背景尚未完整核对。',reason:taught?'尚不能确认离开刚才讲解后仍能自行完成同类任务。':'单次作答和未完整核对的接触背景，尚不足以确认稳定独立完成。',evidence:[],next:'以后在未提供同类解法的条件下再观察。'},
    {id:'understanding',name:'理解与解释',status:'待确认',belief:'解释依据不足。',reason:pending,evidence:[],next:'请说明每一步求什么，两个分数分别以谁为参照。'},
    {id:'transfer',name:'迁移',status:'待确认',belief:'图示情境的表现尚不能判断。',reason:pending,evidence:[],next:'先确认图中区域和输入，再观察能否建立两层关系。'},
    {id:'retention',name:'延迟保持',status:'待确认',belief:'本次没有间隔一段时间后的表现。',reason:'同一活动内做完几道题不能证明持久保持。',evidence:[],next:'后续在约定间隔后观察；本轮不自动安排提醒。'},
  ];
  if(matched&&a.reviewCase!=='unclear'){
    Object.assign(rows[1]!,{status:'已达标',belief:'能在刚学过的文字情境中解释两层参照量。',reason:'第1题的原作答明确说明两个分数对应的量，满足本次目标的文字解释要求；不外推到所有表征。',evidence:[0],next:'保留解释过程，在其他表征中再检验。'});
    if(a.reviewCase==='supported')Object.assign(rows[2]!,{status:'已达标',belief:'本次区域图中也能建立两层部分关系。',reason:'第2题先求花区，再以花区为参照求月季区；满足本次目标限定的区域图要求，不表示已具备普遍迁移能力。',evidence:[1],next:'后续可用其他适用情境继续观察，不重复宣称整章掌握。'});
    else Object.assign(rows[2]!,{status:'需加强',belief:'换成区域图时，把第二层参照量错当成整块苗圃。',reason:'第2题直接用40乘1/2，跳过花区的3/5；与区域图要求不符。文字解释有支持，但该图示条件下仍需帮助。',evidence:[1],next:'讲清图中“花区的一半”，再做不同图示的练习。'});
  }
  return {matched,rows};
}
