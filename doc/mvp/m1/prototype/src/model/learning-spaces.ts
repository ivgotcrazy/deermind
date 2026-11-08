// Read-only demonstration snapshots. This module does not write to the student or definition stores.
export const aspects = [
  {id:'independent',name:'独立'}, {id:'explanation',name:'理解与解释'},
  {id:'transfer',name:'迁移'}, {id:'retention',name:'保持'},
] as const;
export type Aspect = typeof aspects[number]['id'];
export type Result = '已达标'|'需加强'|'待确认';
export type Category = '交流与内容'|'操作与作答'|'活动过程'|'空间与课程'|'评价与系统';
export const categories:Category[] = ['交流与内容','操作与作答','活动过程','空间与课程','评价与系统'];
export interface SpaceEvent {
  id:string; sequence:number; occurredAt:string; recordedAt:string; category:Category;
  type:string; actor:string; summary:string; chapter:string; activity:string;
  fields:{label:string;value:string}[]; causes:string[]; cells:string[];
  table?:{caption:string;columns:string[];rows:string[][]};
}
export interface GoalCell {
  key:string; aspect:Aspect; required:boolean; requirement:string; status:Result;
  reason:string; updatedAt:string; eventId:string; processing?:string;
}
export interface SpaceTask {
  id:string; claim:string; name:string; chapter:string; mode:'all'|'any';
  methods:{id:string;name:string;execution:string;cells:GoalCell[]}[];
}
export interface LearningSpace {
  id:string;name:string;student:string;account:string;book:string;bookVersion:string;
  target:string;targetVersion:string;adoptedAt:string;description:string;
  chapters:{id:string;name:string;content:string;question:string;formula:string;pages:number[]}[];
  tasks:SpaceTask[];events:SpaceEvent[];
}
const chapters = [
  {id:'fractions',name:'分数的应用',content:'围绕原量、增加比例和新量建立关系；章节示例映射到比例增加任务。',question:'书架原有 80 本书，增加原来的四分之一后，共有多少本？',formula:'80 + 80 × ¼ = 100；80 × (1 + ¼) = 100',pages:[49,50]},
  {id:'statistics',name:'数据的表示（综合应用）',content:'阅读表格和统计图，识别统计对象、单位及比例关系。',question:'根据题目给定的表格与统计图读取数据，说明数据对应的统计对象。',formula:'部分量 ÷ 总量 = 所占比例',pages:[91,92,93]},
];
const standards:Record<Aspect,string> = {
  independent:'在“增加四分之一”范围内，完成 2 道不同新题；无当题提示，列式与结果正确。',
  explanation:'结合这 2 道题说明四分之一以哪个量为参照，以及本方法为何能得到新量。',
  transfer:'至少 1 道新题使用此前未练过的表格呈现；能识别原量和增加比例，并正确求解、解释。',
  retention:'独立与理解要求达标至少 7×24 小时后，完成 1 道新题；无当题帮助且能正确求解。',
};
function task(id:string,name:string,chapter:string,methodNames:string[]):SpaceTask {
  return {id,claim:'CLAIM-'+id+'@1',name,chapter,mode:'all',methods:methodNames.map((name,i)=>({
    id:id+'-S'+(i+1),name,execution:chapter==='fractions'?(i===0?'先求原量的四分之一，再与原量相加。':'把新量表示为原量的 5/4，再求新量。'):'读取对应行列或图中标记，保持统计对象和单位一致。',
    cells:aspects.map(a=>({key:id+'-S'+(i+1)+':'+a.id,aspect:a.id,required:true,requirement:chapter==='fractions'?standards[a.id]:'结合本章数据阅读任务，'+({independent:'独立读取并解释 2 组数据。',explanation:'说明统计对象、单位及图表表达的含义。',transfer:'在未练过的图表表达中准确读取数据。',retention:'达标 7 天后再用新数据检测。'}[a.id]),status:'待确认',reason:'尚无满足本项要求的有效评价。',updatedAt:'',eventId:''})),
  }))};
}
function buildSpace(id:string,student:string,account:string,name:string,scenario:'full'|'new'|'other'):LearningSpace {
  const s:LearningSpace={id,student,account,name,book:'北师大版数学六年级上册',bookVersion:'教材采用版本 v1',target:scenario==='other'?'数据阅读与解释':'四分之一理解与求解',targetVersion:'目标采用版本 v1',adoptedAt:'2026-10-30 09:00:00',description:scenario==='other'?'在选定图表阅读任务中进行检测与解释。':'仅针对增加四分之一；两种方法分别满足所选的四方面要求。不据此推断整个分数章节已掌握。',chapters:structuredClone(chapters),tasks:[],events:[]};
  const fraction=task('TT-QUARTER','已知原量和增加比例，求新量','fractions',['先求增加量，再求新量','按原量的 5/4 倍计算']);
  const statistics=task('TT-DATA','读取图表并解释数据','statistics',['读取数据并核对统计对象']);
  statistics.methods[0].cells.filter(c=>c.aspect==='transfer'||c.aspect==='retention').forEach(c=>c.required=false);
  s.tasks=scenario==='other'?[statistics]:[fraction];
  const cell=(aspect:Aspect)=>fraction.methods[0].cells.find(c=>c.aspect===aspect)!;
  const key=(a:Aspect)=>cell(a).key;
  const ref=(n:string)=>id+'-'+n;
  function event(n:string,time:string,category:Category,type:string,actor:string,summary:string,fields:Record<string,string>,causes:string[]=[],cells:string[]=[],activity='',chapter='fractions',recordedAt=time){
    const e:SpaceEvent={id:ref(n),sequence:s.events.length+1,occurredAt:time,recordedAt,category,type,actor,summary,fields:Object.entries(fields).map(([label,value])=>({label,value})),causes:causes.map(ref),cells,activity,chapter};s.events.push(e);return e.id;
  }
  event('001',s.adoptedAt,'空间与课程','空间创建','学生','创建学习空间',{学生:student+' · '+account,空间:name},[],[],'','');
  event('002',s.adoptedAt,'空间与课程','教材与目标采用','学生','选用教材与学习目标',{教材:s.book+' · v1',目标:s.target+' · v1',采用前:'尚未选用',采用后:'教材和目标 v1；范围由目标确定'},['001'],[],'','');
  if(scenario==='full'){
    event('003','2026-11-01 09:00:00','交流与内容','学生消息','学生','请讲解一个量增加四分之一',{消息:'我不知道增加四分之一是什么意思，可以讲一下吗？'},['002'],[], 'ACT-01 讲解');
    event('004','2026-11-01 09:00:01','活动过程','活动开始','Interaction','进入讲解活动',{活动:'ACT-01；顶层讲解',运行状态:'进行中',当前节点:'明确问题与目标'},['003'],[],'ACT-01 讲解');
    event('004A','2026-11-01 09:00:30','活动过程','节点进入','Interaction','进入讲解与互动节点',{活动:'ACT-01 讲解',节点:'明确问题与目标 → 讲解与互动',依据:'学生请求已明确，选择四分之一概念解释。'},['004'],[],'ACT-01 讲解');
    event('005','2026-11-01 09:01:00','交流与内容','系统内容已展示','DeerMind','用 80 本书说明增加量',{内容:'把原来的 80 本看作 4 份，增加其中 1 份。先算增加量，再加回原量。',公式:'80 ÷ 4 = 20；80 + 20 = 100',显示情况:'内容完整展示'},['004'],[],'ACT-01 讲解');
    event('005A','2026-11-01 09:03:00','交流与内容','学生消息','学生','我想试着做两题',{消息:'讲解看懂了，我想试着做两题。'},['005'],[],'ACT-01 讲解');
    event('005B','2026-11-01 09:03:01','活动过程','子活动开始','Interaction','讲解中进入检测活动',{活动:'ACT-02 检测',父活动:'ACT-01 讲解',当前节点:'准备检测轮'},['005A'],[],'ACT-02 检测');
    event('006','2026-11-01 09:04:00','活动过程','检测轮开始','Interaction','开始新题检测 R1',{活动:'ACT-02 检测，父活动 ACT-01 讲解',检测轮:'R1',题目:'原有 120 本书，增加四分之一后有多少本？',规则:'未结束检测轮前不得给当题提示'},['005B'],[],'ACT-02 检测');
    event('007','2026-11-01 09:05:00','操作与作答','答案提交','学生','120 本书：提交 150 本并解释',{题目:'原有 120 本书，增加四分之一后有多少本？',作答:'120 ÷ 4 = 30；120 + 30 = 150。四分之一以原来 120 本为参照。',帮助:'本轮未展示当题提示；此前看过 80 本书的讲解。',检测轮:'R1'},['006'],[],'ACT-02 检测');
    event('008','2026-11-01 09:05:01','活动过程','检测轮结束','Interaction','R1 已提交，停止收集本轮作答',{检测轮:'R1',结束原因:'答案提交',后续:'继续下一轮'},['007'],[],'ACT-02 检测');
    event('009','2026-11-01 09:06:00','活动过程','检测轮开始','Interaction','开始新题检测 R2',{检测轮:'R2',题目:'原有 64 厘米彩带，增加四分之一后有多少厘米？'},['008'],[],'ACT-02 检测');
    event('010','2026-11-01 09:07:00','操作与作答','答案提交','学生','64 厘米：提交 80 厘米并解释',{题目:'原有 64 厘米彩带，增加四分之一后有多少厘米？',作答:'64 ÷ 4 = 16；64 + 16 = 80。增加的是原来的四分之一，求总量要加回原量。',帮助:'本轮未提供当题提示。',检测轮:'R2'},['009'],[],'ACT-02 检测');
    event('011','2026-11-01 09:07:01','活动过程','检测轮结束','Interaction','R2 已结束',{检测轮:'R2',结束原因:'答案提交'},['010'],[],'ACT-02 检测');
    event('012','2026-11-01 09:07:04','评价与系统','评价完成','Evaluation','两道新题支持方法一的独立求解与解释',{Claim:fraction.claim,方法:fraction.methods[0].name,评价方面:'独立、理解与解释',Evidence:'EVD-01：两道新题作答与检测轮帮助记录',Belief:'BLF-01：支持本方法在当前任务范围的独立求解与解释；未推及方法二、迁移或保持。',结果:'求解正确，解释符合本例试用标准'},['007','010','008','011'],[key('independent'),key('explanation')],'ACT-02 检测');
    const first=event('013','2026-11-01 09:07:05','评价与系统','目标状态更新','Evaluation','方法一的独立与理解已达标',{目标:s.target+' · v1',变化:'独立：待确认 → 已达标；理解与解释：待确认 → 已达标',依据:'两道不同新题，无当题帮助，求解和解释均满足要求',未覆盖:'方法二、表格迁移、延迟保持'},['012'],[key('independent'),key('explanation')],'ACT-02 检测');
    for(const aspect of ['independent','explanation'] as Aspect[])Object.assign(cell(aspect),{status:'已达标',reason:'两道不同新题均独立完成，并正确说明参照量与加回原量的理由。',eventId:first,updatedAt:'2026-11-01 09:07:05'});
    event('013A','2026-11-01 09:07:06','活动过程','子活动结束','Interaction','两轮检测完成，返回讲解',{活动:'ACT-02 检测',运行状态:'已结束',返回活动:'ACT-01 讲解'},['013'],[],'ACT-02 检测');
    event('013B','2026-11-01 09:07:07','交流与内容','系统内容已展示','DeerMind','反馈当前结果与尚未检测的方面',{内容:'你能独立求出增加后的数量，并解释原因。表格题、另一种方法和隔一段时间再做的情况还没有确认。'},['013A'],[],'ACT-01 讲解');
    event('013C','2026-11-01 09:07:08','活动过程','活动结束','Interaction','结束本次讲解',{活动:'ACT-01 讲解',当前节点:'结束',结束原因:'本次讲解与反馈完成'},['013B'],[],'ACT-01 讲解');
    event('013D','2026-11-08 09:09:00','评价与系统','主动任务生成','系统','建议做一道延迟保持检测',{任务:'PT-01 保持检测',依据:'独立与理解达标后已超过 7×24 小时，保持尚待确认。'},['013'],[key('retention')]);
    event('013E','2026-11-08 09:09:30','操作与作答','主动任务回应','学生','接受保持检测建议',{任务:'PT-01',回应:'开始'},['013D']);
    event('013F','2026-11-08 09:09:31','活动过程','活动开始','Interaction','开始顶层保持检测活动',{活动:'ACT-03 检测',父活动:'无（顶层活动）',当前节点:'准备检测轮'},['013E'],[],'ACT-03 保持检测');
    event('014','2026-11-08 09:10:00','活动过程','检测轮开始','Interaction','开始延迟保持检测 R3',{检测轮:'R3',活动:'ACT-03 系统建议的保持检测（顶层）',间隔:'距独立与理解达标已超过 7×24 小时',题目:'原有 48 升水，增加四分之一后有多少升？'},['013F'],[],'ACT-03 保持检测');
    event('015','2026-11-08 09:11:00','操作与作答','答案提交','学生','48 升水：只提交增加量 12 升',{题目:'原有 48 升水，增加四分之一后有多少升？',作答:'48 ÷ 4 = 12，所以是 12 升。',帮助:'本轮没有当题帮助。',检测轮:'R3'},['014'],[],'ACT-03 保持检测');
    event('016','2026-11-08 09:11:01','活动过程','检测轮结束','Interaction','R3 已提交',{检测轮:'R3',结束原因:'答案提交'},['015'],[],'ACT-03 保持检测');
    event('017','2026-11-08 09:11:03','评价与系统','评价完成','Evaluation','保持检测评价通过',{Claim:fraction.claim,方法:fraction.methods[0].name,评价方面:'保持',Evidence:'EVD-02：48 升水的作答',Belief:'BLF-02：支持本方法的延迟保持',判断:'判定通过'},['015','016'],[key('retention')],'ACT-03 保持检测');
    event('018','2026-11-08 09:11:04','评价与系统','目标状态更新','Evaluation','当时将保持改为已达标',{目标:s.target+' · v1',变化:'保持：待确认 → 已达标',依据:'当时引用 EVD-02 / BLF-02'},['017'],[key('retention')],'ACT-03 保持检测');
    event('019','2026-11-08 09:15:00','评价与系统','评价结果纠正','Evaluation','撤销错误解释并追加更正',{被纠正记录:ref('017')+'、'+ref('018'),原因:'12 升是增加量，题目要求新量 60 升；原解释不成立。',处理:'保留原始作答与历史评价；新解释替代旧解释作为当前评价依据。'},['017','018'],[key('retention')],'ACT-03 保持检测');
    event('020','2026-11-08 09:15:01','评价与系统','评价完成','Evaluation','重新判断：遗漏加回原量',{Claim:fraction.claim,方法:fraction.methods[0].name,评价方面:'保持',Evidence:'EVD-03：引用原始作答及纠正原因；替代 EVD-02 的解释',Belief:'BLF-03：本次延迟题未正确求新量，不能支持保持',结果:'本次保持检测不满足标准；此前两题表现作为历史保留'},['015','019'],[key('retention')],'ACT-03 保持检测');
    const corrected=event('021','2026-11-08 09:15:02','评价与系统','目标状态更新','Evaluation','保持更正为需加强',{目标:s.target+' · v1',变化:'保持：已达标 → 需加强',依据:'EVD-03 / BLF-03；本次未加回原量',其他方面:'先前独立与理解结果保留，后续新证据可再次评价。'},['020'],[key('retention')],'ACT-03 保持检测');
    Object.assign(cell('retention'),{status:'需加强',reason:'延迟新题只求出增加量，未求出新量。旧的通过结果已被后续纠正。',updatedAt:'2026-11-08 09:15:02',eventId:corrected});
    event('021A','2026-11-08 09:15:03','交流与内容','系统内容已展示','DeerMind','反馈保持检测的更正结果',{内容:'刚才的判断需要更正：12 升是增加量，求新量还要加回 48 升，应该是 60 升。保持这项目前需要加强。'},['021'],[],'ACT-03 保持检测');
    event('021B','2026-11-08 09:15:04','活动过程','活动结束','Interaction','结束本次保持检测',{活动:'ACT-03 检测',运行状态:'已结束',结束原因:'本轮已完成并反馈'},['021A'],[],'ACT-03 保持检测');
    event('021C','2026-11-08 09:15:05','评价与系统','主动任务结束','系统','保持检测建议已执行',{任务:'PT-01',结果:'已执行，不代表已达标'},['021B']);
    event('021D','2026-11-08 09:19:00','交流与内容','学生消息','学生','我还想试试表格题',{消息:'我还想试试表格题。'},['021C'],[],'ACT-04 迁移检测');
    event('021E','2026-11-08 09:19:01','活动过程','活动开始','Interaction','开始顶层迁移检测活动',{活动:'ACT-04 检测',父活动:'无（顶层活动）',当前节点:'准备检测轮'},['021D'],[],'ACT-04 迁移检测');
    event('022','2026-11-08 09:20:00','活动过程','检测轮开始','Interaction','开始表格迁移检测 R4',{检测轮:'R4',活动:'ACT-04 检测（顶层）',题目:'表格给出原有 32 千克、增加比例 1/4，求新量。'},['021E'],[],'ACT-04 迁移检测');
    event('023','2026-11-08 09:21:00','交流与内容','学生消息','学生','我没懂这个表，可以给点提示吗？',{消息:'我没懂这个表，可以给点提示吗？'},['022'],[],'ACT-04 迁移检测');
    event('024','2026-11-08 09:21:01','操作与作答','求助请求受理','Interaction','识别本轮求助意图',{原消息:ref('023'),请求:'结束当前检测轮并请求讲解',说明:'同一消息的意图记录，不是第二份能力证据。'},['023'],[],'ACT-04 迁移检测');
    event('025','2026-11-08 09:21:02','活动过程','检测轮结束','Interaction','R4 因求助结束，未提交答案',{检测轮:'R4',结束原因:'学生求助',结果:'未提交；不作为独立通过或答错',草稿:'32 × 1/4（未提交）'},['024'],[],'ACT-04 迁移检测');
    event('026','2026-11-08 09:21:03','活动过程','子活动开始','Interaction','检测轮结束后进入讲解',{活动:'ACT-05 讲解',父活动:'ACT-04 迁移检测',返回方式:'讲解结束后回到上层检测，下一题使用新检测轮'},['025'],[],'ACT-05 讲解');
    event('027','2026-11-08 09:21:04','交流与内容','系统内容已展示','DeerMind','解释表格中的原量与增加比例',{内容:'32 千克是原量，1/4 是相对原量的增加比例。先求增加量，再加回原量。',展示条件:'R4 已结束后才展示提示。'},['026'],[],'ACT-05 讲解');
    event('028','2026-11-08 09:24:00','活动过程','子活动结束','Interaction','讲解结束，返回检测活动',{活动:'ACT-05 讲解',运行状态:'已结束',返回活动:'ACT-04 迁移检测'},['027'],[],'ACT-05 讲解');
    event('029','2026-11-08 09:25:00','活动过程','检测轮开始','Interaction','换一道表格题，开始 R5',{检测轮:'R5',题目:'表格：原有 40 千克，增加比例 1/4，求新量。',帮助背景:'已讲过相同表格表达，不能当作首次迁移。'},['028'],[],'ACT-04 迁移检测');
    event('030','2026-11-08 09:26:00','操作与作答','答案提交','学生','表格新题提交 50 千克',{题目:'表格：原有 40 千克，增加比例 1/4，求新量。',作答:'40 ÷ 4 = 10；40 + 10 = 50 千克。',帮助:'本轮未提示，但此前刚讲解过同类表格表达。',检测轮:'R5'},['029'],[],'ACT-04 迁移检测');
    event('031','2026-11-08 09:26:01','活动过程','检测轮结束','Interaction','R5 已提交',{检测轮:'R5',结束原因:'答案提交'},['030'],[],'ACT-04 迁移检测');
    event('032','2026-11-08 09:26:05','评价与系统','评价失败','Evaluation','新作答评价未完成',{失败步骤:'生成评价结果',影响:'不产生新 Evidence 或 Belief，不覆盖已有目标状态。',等待处理:'保留作答，等待后续评价；本页不提供重试执行。'},['030','031'],[key('transfer')],'ACT-04 迁移检测');
    cell('transfer').processing='新作答评价失败';
    cell('transfer').reason='尚无有效的首次表格迁移评价；求助轮未独立完成，随后已练过同类表格。';
    // A late-recorded event deliberately has an earlier occurrence time.
    event('033','2026-11-08 09:21:05','交流与内容','展示中断','Interaction','补录：图示未完成显示',{内容:'表格辅助图示加载中断，文字提示已经显示。',影响:'不声称学生已看到完整图示。'},['027'],[],'ACT-05 讲解','fractions','2026-11-08 09:27:00');
    for(const [n,amount] of [['022','32'],['029','40'],['030','40']]){
      s.events.find(e=>e.id===ref(n))!.table={caption:'当时题面中的表格',columns:['原有数量（千克）','增加比例','增加后数量（千克）'],rows:[[amount,'1/4','？']]};
    }
  }
  return s;
}
function freeze<T>(value:T):T {
  if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;
}
export const learningSpaces = freeze([
  buildSpace('LS-001','林晓','student-001','校内数学','full'),
  buildSpace('LS-002','林晓','student-002','校内数学','new'),
  buildSpace('LS-003','林晓','student-001','数据阅读专项','other'),
]);
export function taskResult(t:SpaceTask):Result {
  const methodResults=t.methods.map(m=>{const cells=m.cells.filter(c=>c.required);return !cells.length?'待确认':cells.every(c=>c.status==='已达标')?'已达标':cells.some(c=>c.status==='需加强')?'需加强':'待确认';});
  if(t.mode==='any')return methodResults.includes('已达标')?'已达标':methodResults.every(r=>r==='需加强')?'需加强':'待确认';
  return methodResults.every(r=>r==='已达标')?'已达标':methodResults.includes('需加强')?'需加强':'待确认';
}
export function latestLearning(s:LearningSpace){return s.events.filter(e=>e.actor==='学生'&&(e.category==='交流与内容'||e.type==='答案提交')).map(e=>e.occurredAt).sort().at(-1)||'尚未开始学习';}
export function latestEvaluation(s:LearningSpace){return s.events.filter(e=>e.type==='目标状态更新').map(e=>e.recordedAt).sort().at(-1)||'尚无评价结果';}
export function relatedEvents(s:LearningSpace,key:string):Set<string>{
  const ids=new Set<string>();
  function add(e:SpaceEvent){if(ids.has(e.id))return;ids.add(e.id);for(const id of e.causes){const cause=s.events.find(x=>x.id===id);if(cause&&cause.type!=='目标状态更新')add(cause);}}
  s.events.filter(e=>e.cells.includes(key)).forEach(add);return ids;
}
export function linkedCells(s:LearningSpace,eventId:string):string[]{
  const result=new Set<string>(),visited=new Set<string>();
  function visit(id:string){if(visited.has(id))return;visited.add(id);const e=s.events.find(e=>e.id===id);e?.cells.forEach(k=>result.add(k));s.events.filter(e=>e.causes.includes(id)&&e.category==='评价与系统').forEach(e=>visit(e.id));}
  visit(eventId);return [...result];
}
