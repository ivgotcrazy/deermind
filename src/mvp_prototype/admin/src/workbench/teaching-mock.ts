import { reactive, ref } from 'vue';

export interface TeachingStage { id:string; name:string; purpose:string; inputs:string; approach:string; outputs:string; strategies:string[] }
export interface TeachingTransition { id:string; from:string; to:string; label:string; condition:string; basis:string }
export interface TeachingBlueprint { name:string; purpose:string; stages:TeachingStage[]; transitions:TeachingTransition[] }
export interface TeachingStrategy {
  id:string; name:string; purpose:string; when:string; avoid:string; inputs:string;
  organization:string; help:string; observe:string; adjust:string; end:string;
  basis:string; examples:string; enabled:boolean; version:number;
}
export interface TeachingRule { id:string; name:string; when:string; requirement:string; basis:string; enabled:boolean; version:number }
export const copyTeaching=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
export const newTeachingId=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8);

const strategies:TeachingStrategy[]=[
  {id:'foundation',name:'概念建立与回补',purpose:'理解完成当前任务所需的基础关系，再返回原来的学习重点。',when:'学生的实际回应显示必要的基础含义尚不清楚，且这影响当前任务。',avoid:'只是记录不足，或困难来自识别、读图与输入问题；不要据此从头补整章。',inputs:'当前问题、学生原话、相关知识与此前帮助；不借用其他学习空间的个人记录。',organization:'先处理一个基础关系，用分组、图示或具体情境呈现，再联系数学表达。邀请学生指认、画图或解释。',help:'允许直接示范和解释；逐渐让学生承担关键判断。',observe:'学生能否在另一个简单例子中表现出该关系，而非复述刚给出的数值。',adjust:'仍困难时更换表征、减少同时处理的关系；基础已有支持后返回原任务。',end:'当前基础关系足以支持继续尝试；或需要暂停、另行处理未解决部分。',basis:'参考 IES 分数教学指南中的概念与计算联系；具体切换条件为待验证设计。',examples:'12 个圆点平均分成 3 组，联系 12×1/3=4；再尝试表示 18 的 1/3。',enabled:true,version:1},
  {id:'example',name:'示范与例题讲解',purpose:'理解方法怎样组织，以及关键步骤为什么成立。',when:'具备必要基础，但尚不知道如何组织求解过程。',avoid:'学生已经能够自行完成和解释；不必重复完整示范。',inputs:'当前任务、允许使用的 Solution、知识依据、学生卡点。',organization:'围绕一个关键问题展示步骤与理由；随后留出部分工作让学生接手。',help:'可展示完整示范；保留实际展示内容，之后不能把复现直接当作独立完成。',observe:'学生能否接手关键步骤，并说明中间量或方法的意义。',adjust:'能接手时减少示范；发现概念困难时采用基础回补或对比辨析。',end:'可以转入尝试；或本次疑问已回应，学生选择暂不练习。',basis:'示例学习与支架逐步消退研究；本配置尚未经过真实教学验证。',examples:'先求摄影人数，再求航模人数；解释第二步为何使用摄影人数。',enabled:true,version:1},
  {id:'contrast',name:'对比辨析',purpose:'识别决定理解、判断或方法选择的关键差异。',when:'学生能理解比较材料，但对关键条件存在混淆；或结果正确而理由尚不足以说明关键关系。',avoid:'比较材料所需的基础尚不清楚；已经能解释差异；主要困难只是计算执行。',inputs:'当前目标、学生表现、实际帮助、可用的比较材料及其领域依据。',organization:'通常呈现两个具有关键差异的例子，保持其他条件尽量接近。请学生指出区别或作出选择，再围绕其回应解释。不是每次都必须先提问。',help:'可重述条件、突出对应位置、提供图示或直接解释。学生要求直接讲解时回应其请求，不让她反复猜。',observe:'学生能否指出关键差异，并说明该差异怎样影响方法或结果；允许画图、指认和朴素表达。',adjust:'部分理解时处理尚存疑点；基础关系缺失时转入概念回补；能解释但执行困难时采用引导练习；已能应用时考虑变化任务。',end:'本次辨析目的已有相应表现支持，可以尝试新任务；或需要改用策略、暂停或结束。结束策略不等于正式达标。',basis:'比较学习与自我解释研究。适用范围需结合领域；本策略的选择、切换和结束条件是待验证设计。',examples:'同样保留气象 12 人、摄影占 1/3，对比“航模是摄影的 3/4”和“航模是气象的 3/4”。两者分别为 3 人和 9 人。第二题是辨析材料，不直接计作连续两级关系任务的完成证据。',enabled:true,version:1},
  {id:'practice',name:'引导练习',purpose:'让学生逐渐自行完成任务，按需减少帮助。',when:'已获得必要说明，但自行完成仍需要支持。',avoid:'发现关键概念尚不理解时，不应只增加同类题。',inputs:'练习目的、题目、已有表现与允许的帮助。',organization:'先让学生尝试，根据实际卡点反馈；保留原始表现和订正，随后减少不必要的提示。',help:'练习可以逐题反馈、提示和讲解；实际帮助应记录。',observe:'撤去相应提示后能否自行完成关键工作。',adjust:'计算困难针对计算反馈；关键关系不明返回讲解；可以尝试且愿意检查时准备检测。',end:'本次练习目的得到支持，或需要换策略、停止或检测。',basis:'支架支持与逐步撤去帮助；不以固定连续正确次数宣布掌握。',examples:'30 本书，科技书占 2/5，其中动物类占 1/2。保留学生确定两层参照量的过程。',enabled:true,version:1},
  {id:'transfer',name:'变化与迁移练习',purpose:'在明确变化的条件下应用已有理解。',when:'熟悉条件下已有理解和表现，需要学习或检查新的表达与情境。',avoid:'只换数字却声称广泛迁移；同时引入不必要的新知识或不清楚的图示。',inputs:'本次变化范围、任务边界、已见题目、实际帮助与当前目的。',organization:'明确改变的是表征、情境或信息组织。教学练习可以提供支持；检测时遵守检测帮助条件。',help:'记录是否突出过关键区域、解释过关系；不把受助表现当作无提示迁移。',observe:'能否在这次明确的新条件下识别关系并应用。',adjust:'出现错误先核对题意和呈现；关系混淆时回到辨析或回补。',end:'本次变化条件下已有足够信息，或已找到需要进一步教学的具体问题。',basis:'多种表征与比较学习的设计参考；本次成功不代表任意迁移或持久掌握。',examples:'40 平方米花坛，图中 3/5 种花，其中一半种玫瑰，求玫瑰面积。',enabled:true,version:1},
  {id:'retention',name:'间隔巩固',purpose:'在间隔后检验并加强保持。',when:'已有初步学习结果，且到了需要再次观察的适当时点。',avoid:'在同一轮立即重复作答，就宣称已经验证持久性。',inputs:'时间间隔、期间学习与帮助、当前目标及相关表现。',organization:'先尝试回忆和应用，再按需反馈与补教。',help:'区分回忆前后提供的帮助。',observe:'在明确的间隔和帮助条件下能否再次完成。',adjust:'依据实际困难补教；不因时间流逝直接判定能力下降。',end:'本次观察和必要反馈完成，或学生选择停止。',basis:'间隔学习与提取练习；具体间隔尚未确定。',examples:'后续另一次使用中，重新检查连续两级数量关系。当前蓝图不增加预约或推送。',enabled:false,version:1},
];

const blueprint:TeachingBlueprint={name:'有明确学习重点的教学',purpose:'用于章节讲解与问题求助；根据学生情况跳过、返回或展开阶段，不要求一次讲完整章。',stages:[
  {id:'focus',name:'明确本次学习重点',purpose:'把请求收束为当前先处理的学习问题。',inputs:'学生请求、当前课程目标、教材或题目。',approach:'请求明确时直接采用；范围较大时与学生确定先处理的重点，不改写正式达标标准。',outputs:'本次重点、目标引用及暂未处理的范围。',strategies:[]},
  {id:'entry',name:'确定学习起点',purpose:'依据已有信息选择从哪里开始。',inputs:'当前重点、已有 Belief、近期表现与帮助记录。',approach:'优先使用已有信息；只澄清会影响选择的关键问题，不强制前测。未知不等于不会。',outputs:'选择的起点、依据及尚不清楚的部分。',strategies:[]},
  {id:'teach',name:'讲解与互动',purpose:'理解本次关键问题，并获得尝试应用的基础。',inputs:'当前疑问、相关 Task / Solution / KC、实际表现和帮助。',approach:'每次处理一个关键问题，由学生选择继续、追问或尝试。需要时在本阶段内切换教法。',outputs:'实际展示内容、学生回应、实际帮助及尚未解决的疑问。',strategies:['foundation','example','contrast']},
  {id:'practice',name:'练习与应用',purpose:'通过尝试应用逐渐接手关键工作。',inputs:'练习目的、合适题目、允许的帮助和先前表现。',approach:'练习可逐题反馈、提示和补充解释；变化任务应明确变化范围。',outputs:'原始作答、订正、实际帮助与下一步需要。',strategies:['practice','transfer']},
  {id:'check',name:'检测与反馈',purpose:'在明确条件下获取表现，结束后统一反馈。',inputs:'检测目的、范围、题目、帮助条件及学生同意。',approach:'开始前说明安排；进行中不泄露对错。实质求助先结束整个检测，再返回教学；未做部分保持未检测。',outputs:'已测与未测内容、原作答、帮助条件及适用的 Evaluation 结果或未决项。',strategies:[]},
  {id:'summary',name:'总结本次学习',purpose:'说明实际完成了什么、哪些尚不能判断。',inputs:'本次教学、练习、检测及有效评价结果。',approach:'区分听过、受助完成与符合检测条件的表现；学生可以选择后续行动。',outputs:'学生可读的小结、待验证部分与可选下一步；结束不自动达标。',strategies:[]},
],transitions:[
  {id:'start-focus',from:'start',to:'focus',label:'开始',condition:'学生发起或接受本次学习。',basis:'学生请求及当前空间。'},
  {id:'focus-entry',from:'focus',to:'entry',label:'重点明确',condition:'本次先处理的问题已经明确。',basis:'本次学习重点。'},
  {id:'entry-teach',from:'entry',to:'teach',label:'需要讲解',condition:'请求或实际表现指向一个需要解释或回补的问题。',basis:'当前请求、表现、相关 Belief 及实际帮助。'},
  {id:'entry-practice',from:'entry',to:'practice',label:'先尝试',condition:'已有信息支持可以尝试，或学生希望先做一做。',basis:'学生意愿及当前可用信息，不要求先证明掌握。'},
  {id:'entry-check',from:'entry',to:'check',label:'直接检验',condition:'希望验证，检测目的及题目条件明确，学生同意开始。',basis:'检测安排和学生选择。'},
  {id:'teach-practice',from:'teach',to:'practice',label:'愿意尝试',condition:'已提供必要说明，学生愿意尝试。',basis:'实际讲解及学生回应，不把听过当掌握。'},
  {id:'teach-summary',from:'teach',to:'summary',label:'暂不练测',condition:'本次疑问已回应，学生选择暂不练习或检测。',basis:'实际内容与学生选择；未检验部分明确保留。'},
  {id:'practice-teach',from:'practice',to:'teach',label:'返回讲解',condition:'表现暴露具体疑问，或学生请求帮助。',basis:'原始作答和求助；不从一个错误推断全部能力不足。'},
  {id:'practice-check',from:'practice',to:'check',label:'同意检测',condition:'有明确检测目的、可用题目和帮助条件，学生同意开始。',basis:'本次检测安排、范围及选择。'},
  {id:'practice-summary',from:'practice',to:'summary',label:'先到这里',condition:'本次可以收束，学生暂不继续检测。',basis:'实际练习记录，保留帮助与未检测范围。'},
  {id:'check-teach',from:'check',to:'teach',label:'结束后补教',condition:'该次检测已经结束，存在具体问题且学生愿意继续教学；实质求助也须先结束检测。',basis:'检测结束原因、已提交与未做部分、求助请求。'},
  {id:'check-summary',from:'check',to:'summary',label:'结束并反馈',condition:'检测已经结束，本次可以收束。',basis:'有效表现与适用评价；不足时如实保留未决。'},
  {id:'summary-end',from:'summary',to:'end',label:'结束本次',condition:'本次结果和待验证部分已说明。',basis:'本次小结；不自动宣布持久掌握。'},
]};

export const teachingSceneBlueprint=copyTeaching(blueprint);
export const teachingSceneStrategies=copyTeaching(strategies);
export const teachingBlueprintDraft=ref(copyTeaching(blueprint));
export const teachingMock=reactive({revision:1,blueprint,strategies,rules:[
  {id:'meaning',name:'说明关键关系',when:'进行概念或方法讲解时。',requirement:'说明关键步骤为什么成立，不能只有计算过程；允许图示、动作和朴素表达。',basis:'概念与计算联系的教学参考。',enabled:true,version:1},
  {id:'support',name:'根据表现调整帮助',when:'学生尝试完成任务时。',requirement:'能接手时减少帮助；持续困难时调整解释或材料，不机械追加相同题目。',basis:'支架支持与逐步撤去帮助的设计参考。',enabled:true,version:1},
  {id:'repeat',name:'避免无目的重复',when:'已完成一轮解释或练习后。',requirement:'再次讲解或出题应说明具体目的；信息不足不等于学生不会。',basis:'控制负担；当前执行条件仍待验证。',enabled:true,version:1},
  {id:'selection',name:'按当前目标和表现选择',when:'多种策略都可能适用，或需要切换策略时。',requirement:'结合当前目标、学生请求、实际表现与已提供的帮助选择，不按策略列表顺序取第一项。只澄清会改变选择的关键问题。',basis:'DeerMind 当前教学设计假设；不把局部判断写为新的能力状态。',enabled:true,version:1},
] as TeachingRule[],history:[{version:1,at:'初始示例',change:'建立默认教学蓝图、六类策略和通用规则。'}]});

export function recordTeachingChange(change:string){
  teachingMock.revision++;
  teachingMock.history.unshift({version:teachingMock.revision,at:new Date().toLocaleString('sv-SE',{hour12:false}),change});
}
export function validateTeachingBlueprint(value:TeachingBlueprint):string {
  if(!value.name.trim()||!value.purpose.trim())return '请填写蓝图名称与用途。';
  if(!value.stages.length)return '蓝图至少需要一个教学阶段。';
  const ids=new Set(['start','end',...value.stages.map(s=>s.id)]);
  for(const s of value.stages){
    if(!s.name.trim()||!s.purpose.trim()||!s.inputs.trim()||!s.outputs.trim())return `请补齐「${s.name||'未命名阶段'}」的名称、目的、输入与结果。`;
    if(s.strategies.some(id=>!teachingMock.strategies.some(x=>x.id===id)))return `「${s.name}」引用了不存在的策略。`;
  }
  for(const e of value.transitions){
    if(!ids.has(e.from)||!ids.has(e.to)||e.from==='end'||e.to==='start'||e.from===e.to)return '有连接的起点或终点不正确，请修正后保存。';
    if(!e.label.trim()||!e.condition.trim()||!e.basis.trim())return '请补齐每条连接的名称、转移条件和判断依据。';
  }
  function reachable(start:string,reverse=false){const seen=new Set([start]),queue=[start];while(queue.length){const id=queue.shift()!;for(const e of value.transitions){const from=reverse?e.to:e.from,to=reverse?e.from:e.to;if(from===id&&!seen.has(to)){seen.add(to);queue.push(to);}}}return seen;}
  const entering=reachable('start'),leaving=reachable('end',true);
  for(const s of value.stages){if(!entering.has(s.id))return `「${s.name}」无法从开始到达，请补齐连接。`;if(!leaving.has(s.id))return `「${s.name}」没有通往结束的路径，请补齐连接。`;}
  return '';
}

export interface TeachingSceneStep { id:string; stage:string; strategy?:string; title:string; student:string; tutor:string; reason:string; observe:string; evidence:string; next?:string; choices?:{label:string;next:string}[] }
export interface TeachingScene { id:string; name:string; starting:string; path:string; steps:TeachingSceneStep[] }
// Authored walkthroughs, not a semantic classifier or a real tutoring execution.
export const teachingScenes:TeachingScene[]=[
  {id:'foundation',name:'基础含义不清楚',starting:'学生问：“三分之一是 3 个人吗？”已有记录不足以说明原因。',path:'确定起点 → 基础回补 → 练习 → 检测或收束',steps:[
    {id:'entry',stage:'entry',title:'先找到当前卡点',student:'三分之一是 3 个人吗？',tutor:'我们先看看“12 人的三分之一”表示什么。',reason:'当前回应指向分数含义的疑问；先不增加第二层关系。',observe:'能否理解平均分成 3 份，再取其中 1 份。',evidence:'这是本轮教学切入点，不创建 KC 掌握评分。',next:'teach'},
    {id:'teach',stage:'teach',strategy:'foundation',title:'用分组解释，再联系算式',student:'一共 12 个，分成 3 组。',tutor:'每组有 4 个。取其中 1 组，就是 12 的三分之一：12×1/3=4。你可以在图中指出这一组。',reason:'采用概念回补；比较复杂条件的基础尚不充分，暂不使用对比辨析。',observe:'学生是否能在不同数量中表示同一个分数关系。',evidence:'图示和关键结果已经给出，后续复述不算独立完成。',next:'practice'},
    {id:'practice',stage:'practice',strategy:'practice',title:'换一个简单数量，让学生尝试',student:'18 的三分之一是 6，因为分成 3 组，每组 6 个。',tutor:'你说明了“平均分成 3 份，取 1 份”。回到原题，我们再看摄影小组这 4 人的四分之三。',reason:'基础表现提供局部支持，可以返回原任务；不能由此认定两层关系已经掌握。',observe:'第二个分数对应的是哪一组人。',evidence:'18 人的单层问题只是回补练习，不计为完成原来的两层任务。',choices:[{label:'能说明两层关系，愿意检测',next:'check'},{label:'仍把第二个分数用于 12 人',next:'contrast'},{label:'今天先到这里',next:'summary'}]},
    {id:'contrast',stage:'teach',strategy:'contrast',title:'根据新困难切换为对比辨析',student:'第二步不是 12×3/4 吗？',tutor:'我们比较“摄影人数的四分之三”和“气象人数的四分之三”。这两句话指的是同一组人吗？',reason:'基础分数关系已有表现，新的困难在参照数量，返回讲解并采用对比辨析。',observe:'能否指出 4 人和 12 人分别属于哪一组。',evidence:'仍处于教学期，比较材料和提示都要保留。',next:'summary'},
    {id:'check',stage:'check',title:'同意后，检验新的文字题',student:'我想试试。30 本书，科技书占 2/5，动物类占科技书的 1/2，所以是 6 本。',tutor:'本次单题检测结束。你先求出 12 本科技书，再取其中的一半，参照关系与结果正确。',reason:'在讲解和练习后取得新的表现；单题检测结束后才反馈。',observe:'关系说明、实际帮助及题目接触情况。',evidence:'预写表现只用于走查；正式结论由 Evaluation 依据实际条件形成。',next:'summary'},
    {id:'summary',stage:'summary',title:'如实总结，不补造掌握结论',student:'今天先到这里。',tutor:'这次处理了分数所指的数量。保留你实际完成的练习与帮助；尚未检测的方面继续保留，延迟保持也还没有检验。',reason:'按实际经过的路径收束，不把未经过的分支当作已经发生。',observe:'是否还有学生希望继续处理的疑问。',evidence:'结束教学不自动更新全部能力方面。'},
  ]},
  {id:'explanation',name:'会算但解释不清',starting:'学生算出 3 人，理由是“看到两个分数就乘起来”。',path:'确定起点 → 对比辨析 → 新题练习 → 收束',steps:[
    {id:'entry',stage:'entry',title:'正确结果不代表理由已经明确',student:'12×1/3×3/4=3。看到两个分数就乘起来。',tutor:'你得到了 3 人。我们再看看第二个分数描述的是哪一组人数。',reason:'需要确认关键关系；不能仅因这句话就断定不理解。',observe:'学生能否指认、画图或解释参照数量。',evidence:'当前问题是解释信息不足，不是正式的能力失败结论。',next:'contrast'},
    {id:'contrast',stage:'teach',strategy:'contrast',title:'只改变一个关键条件',student:'两道题有什么不同？',tutor:'两题都保留气象 12 人、摄影占 1/3。A：航模是摄影的 3/4。B：航模是气象的 3/4。两题的 3/4 分别针对谁？',reason:'基础材料可理解，采用对比辨析聚焦参照数量。',observe:'能否说明 A 对应摄影人数，B 对应气象人数。',evidence:'B 是辨析材料，不作为连续两级关系任务的检测成绩。',choices:[{label:'能指出 4 人与 12 人的区别',next:'practice'},{label:'仍认为两种说法相同',next:'foundation'},{label:'希望直接听解释',next:'explain'}]},
    {id:'foundation',stage:'teach',strategy:'foundation',title:'同一阶段内换教法',student:'我还是觉得都是 12 的四分之三。',tutor:'先看两组图：气象是 12 人，摄影是其中的 4 人。我们把“摄影的四分之三”圈在这 4 人里面。',reason:'辨析没有解决疑问，改用具体图示建立关系，不让学生反复猜。',observe:'是否能把题干中的对象对应到图中。',evidence:'阶段仍是讲解与互动；策略由对比辨析切换为概念回补。',next:'practice'},
    {id:'explain',stage:'teach',strategy:'contrast',title:'响应直接讲解请求',student:'直接给我讲清楚吧。',tutor:'A 针对摄影的 4 人，算 4×3/4=3；B 针对气象的 12 人，算 12×3/4=9。区别不在分数，而在分数对应的数量。',reason:'对比策略允许直接解释，不强制猜答案；当前是在策略内调整帮助。',observe:'学生是否愿意用新题尝试。',evidence:'关键关系和结果已经展示，后续须记录帮助。',next:'practice'},
    {id:'practice',stage:'practice',strategy:'practice',title:'用新题尝试应用',student:'30 本书，科技书是 12 本，动物类是这 12 本的一半，所以是 6 本。',tutor:'这次你说明了两层数量关系。我们保留你的原始过程和之前获得的帮助。',reason:'从辨析转入练习，观察是否能够在新题中运用关系。',observe:'关键工作由谁完成，而不只检查最终数字。',evidence:'练习反馈可以即时给出；没有自动开展正式检测。',next:'summary'},
    {id:'summary',stage:'summary',title:'结束本次辨析与练习',student:'我明白这两种说法的区别了。',tutor:'这次重点是分清每个分数对应的数量。已经完成的表现会保留；图示迁移和延迟保持仍需其他适用表现。',reason:'本次可收束，未进行的检测不补算。',observe:'本次疑问是否得到回应。',evidence:'不从一次练习推出全面、持久掌握。'},
  ]},
  {id:'transfer',name:'已理解，检验迁移',starting:'已有表现支持熟悉文字条件下的计算与解释，学生希望试试图示题。',path:'确定起点 → 图示检测 → 总结或结束检测后补教',steps:[
    {id:'entry',stage:'entry',title:'跳过重复讲解',student:'摄影是 4 人，第二步求这 4 人的四分之三。我想试试换成图的题。',tutor:'可以。这次用一道图示题检查数量关系，结束后反馈。你愿意开始吗？',reason:'已有信息支持进入尝试，不再重复完整示范。',observe:'学生是否同意检测安排。',evidence:'本情境预设学生同意；不把系统邀请当作自动开测。',next:'check'},
    {id:'check',stage:'check',title:'图示条件下的单题检测',student:'我开始作答。',tutor:'花坛共 40 平方米，5 个等面积区域中有 3 个种花；种花区域的一半种玫瑰。玫瑰占多少平方米？请说明。',reason:'本次变化是信息表征，不只是更换数字。检测进行中不提示关键关系或泄露对错。',observe:'是否把“一半”用于种花区域。',evidence:'真实界面中的可见上文与帮助需要记录，不能默认完全独立。',choices:[{label:'12 平方米，并解释清楚',next:'success'},{label:'20 平方米，参照数量混淆',next:'contrast'},{label:'图示存在歧义',next:'material'},{label:'请求讲解，先结束检测',next:'help'}]},
    {id:'success',stage:'summary',title:'检测结束后给出有限反馈',student:'40×3/5=24，24 的一半是 12 平方米。',tutor:'本次单题检测结束。你说明了图中的两层数量关系；这支持本次图示条件下的表现，不能据此判断所有迁移或持久性。',reason:'本次可以收束，没有必要为了流程完整而补一段讲解。',observe:'后续需要验证的变化或延迟条件。',evidence:'属于预设反馈示例，没有执行真实 Evaluation。'},
    {id:'contrast',stage:'teach',strategy:'contrast',title:'结束检测后返回教学',student:'我提交 40×1/2=20；一半是整个花坛的一半。',tutor:'这次单题检测已结束。我们来对比“整个花坛的一半”和“种花区域的一半”：两句话圈出的范围有什么不同？',reason:'学生提交及说明暴露参照关系困难；先结束检测，再切换到讲解与对比辨析。',observe:'能否区分整个区域与局部区域。',evidence:'原作答保留；讲解后的订正不能改写原检测记录。',next:'summary'},
    {id:'material',stage:'check',title:'先处理材料问题',student:'图上标记不清楚，分不出一半指哪里。',tutor:'先核对图示。这次预设分支确认材料有歧义，相关题目暂不能形成能力结论；修正后再安排新的检查。',reason:'材料问题不归因于能力不足；不把修正后的重答偷偷当作原题无帮助表现。',observe:'图示和文字是否清楚、一致。',evidence:'保留未决及原因，不判错、不宣布迁移不足。',next:'summary'},
    {id:'help',stage:'teach',strategy:'example',title:'求助先结束本次检测',student:'我不会看这个图，请给我讲讲。',tutor:'这次检测先结束，未提交的部分保持未检测。先找种花区域：它占整个花坛的 3/5，再看其中的一半。',reason:'实质求助先结束检测；现在可以示范，但不恢复原检测继续凑结果。',observe:'学生能否跟上表征与数量关系。',evidence:'只记录实际提供的帮助；求助本身不是能力失败证据。',next:'summary'},
    {id:'summary',stage:'summary',title:'保留本次结果与未决部分',student:'今天先到这里。',tutor:'本次图示检查和实际帮助分别保留。材料有争议、未作答或教学后的表现各按实际情况记录，延迟保持仍未检查。',reason:'根据实际分支总结，不覆盖原始作答或未决状态。',observe:'学生是否需要另一次学习机会。',evidence:'教学结束不等于全部方面达标。'},
  ]},
];
