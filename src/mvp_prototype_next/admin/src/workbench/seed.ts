import type { AdminState, Aspect, ModelObject, Kind, Space } from './model';
import { objectKey } from './model';
const stamp = '2026-10-20T09:00:00+08:00';
function obj(id:string, kind:Kind, space:Space, name:string, summary:string, fields:Record<string,string>={}, relations:ModelObject['relations']=[], extra:Partial<ModelObject>={}):ModelObject {
  const model = ({ task:'Task Model', solution:'Solution Model', kc:'Knowledge Component Model', claim:'Learner State Model', 'evidence-rule':'Evidence Model', 'inference-rule':'Inference Model', observation:'Observation Model', policy:'Interaction Policy', action:'Action Model', evidence:'Evidence Model', belief:'Learner State Model', assessment:'Inference Model' } as Record<string,string>)[kind] || '材料、目标与采用关系';
  return {id,version:1,kind,space,model,name,summary,status:'published',source:'人工编写的后台走查示例；不是正式教材或真实学习者数据',fields,relations,at:stamp,...(space==='Domain'?{domainId:'DOM-MATH'}:{}),...extra};
}
const aspects:Aspect[] = [
  {key:'independent',label:'独立完成',applicable:true,criterion:'自行确定参照量、建立数量关系并计算；允许读题帮助，不允许代列关系式。',evidence:'记录实际帮助及发生顺序；有提示的正确答案不自动构成独立完成的反证或支持。'},
  {key:'understanding',label:'理解与解释',applicable:true,criterion:'能说明分率以哪个量为参照，并解释乘除选择。',evidence:'学习者自己的解释、辨析或图示；复述已展示答案不足以确认。'},
  {key:'transfer',label:'迁移',applicable:true,criterion:'从已学文字情境转到未见过的表格表征，能独立识别同一数量关系。',evidence:'明确先前接触、实际变化和帮助；只换数字不能自动算迁移。'},
  {key:'retention',label:'延迟保持',applicable:true,criterion:'在约定延迟窗口重新完成同类任务；本示例以 7 天作为待校准的演示条件。',evidence:'保留间隔时间及期间练习、帮助；仅经过 7 天不是能力证据。'},
];
export function seed():AdminState {
  const objects:ModelObject[] = [
    obj('KC-001','kc','Domain','分率的参照量','一个分率总是相对于特定参照量。',{定义:'“增加四分之一”是相对于原量；必须明确所比较的两个量。',适用范围:'分数应用中的部分、整体和变化关系'}),
    obj('KC-002','kc','Domain','分数乘法的意义','求一个量的几分之几。',{定义:'量 × 分率得到相应部分量。'},[{label:'先修知识',ref:'KC-001'}]),
    obj('KC-003','kc','Domain','分数除法的意义','已知部分量及其分率，求对应整体。',{定义:'已知 a 是整体的 r，则整体为 a ÷ r，r 不为零。'},[{label:'先修知识',ref:'KC-002'}]),
    obj('KC-004','kc','Domain','等量关系与方程','用未知数表达数量关系并保持等式成立。',{定义:'根据等量关系列方程，并以等式性质求解。'}),
    obj('T-001','task','Domain','已知原量与增减分率，求变化后的量','参数化任务；不同题目可以提供同一类任务的表现。',{完成责任:'识别原量为参照量，建立数量关系并求变化后的量。',参数范围:'原量 V > 0；增加 r > 0；减少时 0 < r < 1；数值在小学分数计算范围内。',表征与情境:'文字、线段图、表格；可更换物品及单位。',排除范围:'不含连续两次变化及百分率之间的相对变化。'},[{label:'可用方法',ref:'S-001'},{label:'任务理解依赖',ref:'KC-001'}]),
    obj('T-002','task','Domain','已知变化后的量与分率，求原量','需要识别变化后量与原量的关系。',{完成责任:'自行选择算术或方程方法求原量。',参数范围:'变化后量 W > 0；增加 r > 0；减少时 0 < r < 1。',表征与情境:'文字及图示。',排除范围:'不含两个不同参照量的连续变化。'},[{label:'可用方法',ref:'S-002'},{label:'可用方法',ref:'S-004'},{label:'任务理解依赖',ref:'KC-001'}]),
    obj('T-003','task','Domain','求一个量的几分之几','可以作为其他任务求解中的子任务。',{完成责任:'执行分数乘法并保留单位。',参数范围:'正有理数量与非负分率。',排除范围:'不把执行计算等同于能够解释上位任务。'},[{label:'可用方法',ref:'S-003'},{label:'任务理解依赖',ref:'KC-002'}]),
    obj('T-004','task','Domain','求解 ax = b','方程方法中的子任务。',{完成责任:'利用等式性质求出 x。',参数范围:'a > 0，b > 0。'},[{label:'可用方法',ref:'S-005'},{label:'任务理解依赖',ref:'KC-004'}]),
    obj('S-001','solution','Domain','原量加减变化量','先求变化量，再与原量相加减。',{适用条件:'已知原量 V 和增减分率 r；求变化后的量。',方法:'变化量 = V × r；变化后的量 = V ± V × r。',责任边界:'方法步骤是规范参照，不能当成学习者实际采用了该过程。'},[{label:'适用任务',ref:'T-001'},{label:'分解为子任务',ref:'T-003'},{label:'方法依赖',ref:'KC-002'}]),
    obj('S-002','solution','Domain','整体分率除法','将变化后的量除以相对原量的整体分率。',{适用条件:'原量未知，变化后的量和分率已知；减少时分率必须小于 1。',方法:'原量 = W ÷ (1 ± r)。'},[{label:'适用任务',ref:'T-002'},{label:'方法依赖',ref:'KC-001'},{label:'方法依赖',ref:'KC-003'}]),
    obj('S-003','solution','Domain','分数乘法计算','计算量与分率的乘积。',{适用条件:'量与分率的含义已确定。',方法:'相乘、约分、保留单位。'},[{label:'适用任务',ref:'T-003'},{label:'方法依赖',ref:'KC-002'}]),
    obj('S-004','solution','Domain','设原量为未知数列方程','通过等量关系求原量。',{适用条件:'原量未知，学习目标允许方程法。',方法:'设原量 x，列 x ± rx = W，再解方程。'},[{label:'适用任务',ref:'T-002'},{label:'分解为子任务',ref:'T-004'},{label:'方法依赖',ref:'KC-004'},{label:'方法依赖',ref:'KC-001'}]),
    obj('S-005','solution','Domain','等式两边同除系数','在 a 不为零时得到 x=b/a。',{适用条件:'a 不为零。',方法:'等式两边同除以 a。'},[{label:'适用任务',ref:'T-004'},{label:'方法依赖',ref:'KC-004'}]),
    obj('CL-001','claim','Evaluation','原量增减任务的多维能力声明','针对同一任务、同一组条件维护一个多维 Claim。',{任务范围:'T-001 的参数和表征范围。',方法条件:'允许 S-001；不替学习者确定参照量或列式。',支持边界:'可读题，不提供数量关系提示。',质量要求:'结果正确、单位正确，所声明方面满足对应条件。'},[{label:'精确绑定任务版本',ref:'T-001@1'},{label:'证据解释规则',ref:'ER-001'},{label:'推断规则',ref:'IR-001'}],{aspects:structuredClone(aspects)}),
    obj('CL-002','claim','Evaluation','求原量任务的多维能力声明','方法任选其一；一次使用算术法不证明掌握方程法。',{任务范围:'T-002 的参数和表征范围。',方法条件:'任选 S-002 或 S-004；不得从一种方法成功推断另一种方法及其 KC 已掌握。',支持边界:'可读题，不代列式。',质量要求:'结果及数量关系正确；其余方面按各自条件取证。'},[{label:'精确绑定任务版本',ref:'T-002@1'},{label:'证据解释规则',ref:'ER-001'},{label:'推断规则',ref:'IR-001'}],{aspects:structuredClone(aspects)}),
    obj('ER-001','evidence-rule','Evaluation','依据实际表现与帮助解释证据','将观察解释为对具体 Claim 方面的支持、反证或不具诊断性。',{独立完成:'实质提示后的正确结果不能直接支持独立完成；也不能仅因求助判为能力不足。',理解与解释:'使用学习者自己的表达，区分复述与解释。',迁移与保持:'只有变化或时间条件满足时，才形成对应方面证据。',维护方式:'在评估模型管理中导入定义包并保存；首版不提供通用在线规则编辑器。'}),
    obj('IR-001','inference-rule','Evaluation','保留证据条件与不确定性的推断','同源证据不重复计数；未检测的方面保持未知。',{输入:'已有 Belief、适用 Evidence、实际帮助、时间和来源依赖。',输出:'同一 Claim 的分方面判断及不确定性，不计算四维平均掌握率。',维护方式:'在评估模型管理中导入定义包并保存；首版不提供通用在线规则编辑器。'}),
    obj('MAT-001','material','Learning','分数应用·后台走查材料','独立的合成章节材料，用来核对管理员操作；不替换学生端六下教材。',{来源:'人工编写示例，不是实际 OCR 或正式教材导入。',内容:'包含“已知原量求变化后量”和“已知变化后量求原量”。'},[{label:'包含章节',ref:'CH-001'}]),
    obj('CH-001','chapter','Learning','分数的应用','本次准备和修订的示例章节。',{原始材料:'水箱原有 80 升水，增加原量的四分之一，现在有多少升？\n另题：水量增加四分之一后是 100 升，原有多少升？',核对文本:'两题的参照量均为原量；答案分别是 100 升和 80 升。',待核对:'需确认文字、单位、参照量及参考解法；不能把示例当成已识别的扫描件。'},[{label:'所属材料',ref:'MAT-001'},{label:'章节映射',ref:'MAP-001'},{label:'可选目标',ref:'TG-001'}]),
    obj('MAP-001','mapping','Learning','分数应用章节映射','明确列出对应任务、方法及映射依据。',{映射依据:'第一题对应 T-001；第二题对应 T-002。允许算术法与已学过的方程法。',核对说明:'示例基线；修改后的映射需核对原材料及任务责任。'},[{label:'教材章节',ref:'CH-001'},{label:'映射任务',ref:'T-001'},{label:'映射任务',ref:'T-002'},{label:'允许方法',ref:'S-001'},{label:'允许方法',ref:'S-002'},{label:'允许方法',ref:'S-004'}]),
    obj('TG-001','target','Learning','分数应用·章节学习目标','采用明确任务、方法和评价方面；达标标准变化不等于能力变化。',{方法选择:'T-001 使用 S-001；T-002 可任选 S-002 或 S-004。',达标条件:'独立完成与理解解释有充分支持；迁移和延迟保持达到各自定义条件。',裁剪依据:'本示例保留四个方面；如裁剪或增加，须说明依据、适用范围和影响。'},[{label:'适用章节',ref:'CH-001'},{label:'采用 Claim',ref:'CL-001@1'},{label:'采用 Claim',ref:'CL-002@1'},{label:'允许方法',ref:'S-001'},{label:'允许方法',ref:'S-002'},{label:'允许方法',ref:'S-004'}],{requiredAspects:['independent','understanding','transfer','retention']}),
  ];
  const adopted = Object.fromEntries(objects.map(o=>[o.id,o.version]));
  for(const o of objects) o.referenceVersions={...adopted};
  const spaces = [
    {id:'LS-001',name:'校内数学·示例空间',studentId:'ST-001',studentName:'学生 A（示例）',chapters:['CH-001'],material:'MAT-001',target:'TG-001',adopted:{...adopted},history:[]},
    {id:'LS-002',name:'校外数学·示例空间',studentId:'ST-001',studentName:'学生 A（示例）',chapters:['CH-001'],material:'MAT-001',target:'TG-001',adopted:{...adopted},history:[]},
    {id:'LS-003',name:'校内数学·示例空间',studentId:'ST-002',studentName:'学生 B（示例）',chapters:['CH-001'],material:'MAT-001',target:'TG-001',adopted:{...adopted},history:[]},
  ];
  const activities:AdminState['activities'] = [
    {id:'ACT-001',name:'提示后完成原量增减题',ls:'LS-001',at:'2026-10-20T09:10:00+08:00',versions:{...adopted},note:'故意保留一条错误 Evidence，用来走查复核；不能据此声称真实系统出现了该错误。',objects:['OBS-001@1','POL-001@1','ACTION-001@1','EV-001@1','BL-001@1','TA-001@1'],facts:[
      {id:'F-001',at:'09:10:00',actor:'学生',kind:'求助',text:'原来 80 升，增加四分之一，我不知道怎么算。'},
      {id:'F-002',at:'09:10:04',actor:'DeerMind',kind:'已展示的提示',text:'把 80 升当作原量，先算 80 × 1/4，再加回 80。',object:'ACTION-001@1'},
      {id:'F-003',at:'09:10:28',actor:'学生',kind:'作答',text:'80 × 1/4 = 20，80 + 20 = 100 升。',object:'OBS-001@1'},
    ]},
    {id:'ACT-002',name:'独立处理求原量问题',ls:'LS-001',at:'2026-10-20T09:20:00+08:00',versions:{...adopted},note:'单次表现只提供局部依据；迁移和保持尚未检测。',objects:['OBS-002@1','EV-002@1','BL-002@1'],facts:[{id:'F-004',at:'09:20:00',actor:'DeerMind',kind:'题目',text:'增加四分之一后为 100 升，原有多少升？'},{id:'F-005',at:'09:21:00',actor:'学生',kind:'独立作答',text:'原量是 100 ÷ (1 + 1/4) = 80 升。增加的四分之一以原量为单位一。',object:'OBS-002@1'}]},
    {id:'ACT-003',name:'请求讲解，尚未产生个人作答',ls:'LS-003',at:'2026-10-20T10:00:00+08:00',versions:{...adopted},note:'此路径尚无可解释的作答，合法未形成 Evidence 和 Belief，不能当成系统丢失数据。',objects:[],facts:[{id:'F-006',at:'10:00:00',actor:'学生',kind:'请求',text:'请讲讲为什么要找单位一。'}]},
  ];
  objects.push(
    obj('OBS-001','observation','Interaction','提示后的正确作答','保留学生列式和已有帮助。',{事实:'80 × 1/4 = 20，80 + 20 = 100 升。',校验:'计算结果可确认；在列式前已展示实质提示。',来源位置:'ACT-001 / F-003'},[{label:'实际帮助',ref:'ACTION-001@1'}],{status:'recorded'}),
    obj('POL-001','policy','Interaction','响应当前求助','学生明确请求帮助，允许提供当前题的讲解。',{请求:'我不知道怎么算。',决策:'提供参照量和列式提示；提示后的作答不据此视为独立完成。'},[{label:'执行结果',ref:'ACTION-001@1'}],{status:'recorded'}),
    obj('ACTION-001','action','Interaction','实际展示列式提示','实际展示时间早于学生作答。',{计划:'提示参照量和列式。',实际展示:'80 × 1/4，再加回 80。',展示状态:'已展示（示例事实）',时间:'09:10:04'},[],{status:'recorded'}),
    obj('EV-001','evidence','Evaluation','待复核：将提示后正确解释为独立支持','合成的错误解释，保留供管理员定位。',{方面:'independent',解释结果:'支持独立完成',解释依据:'答案和过程正确；本示例错误地漏掉了实质帮助。',实际条件:'作答前已有列式提示',有效性:'待人工核对；不是已经确认的真实故障'},[{label:'来源 Observation',ref:'OBS-001@1'},{label:'评价 Claim',ref:'CL-001@1'},{label:'采用规则',ref:'ER-001@1'}],{status:'recorded'}),
    obj('BL-001','belief','Evaluation','学生 A · 原量增减任务','同一 Claim 的分方面认识。',{学习空间:'LS-001',有效性:'示例当前结果；有关独立完成的依据有待复核',前次变化:'独立完成从“证据不足”变为“有支持”；待核查这次变化。',更新时间:'2026-10-20 09:10'},[{label:'针对 Claim',ref:'CL-001@1'},{label:'推断规则',ref:'IR-001@1'},{label:'依据 Evidence',ref:'EV-001@1'}],{status:'recorded',states:aspects.map(a=>({key:a.key,judgment:a.key==='independent'?'有支持':'证据不足',uncertainty:a.key==='independent'?'需核对帮助条件':'未观察到满足条件的表现',evidence:a.key==='independent'?['EV-001@1']:[],note:a.key==='retention'?'尚未进行延迟检测':'不能由其他方面补齐'}))}),
    obj('TA-001','assessment','Evaluation','学生 A · 章节目标评价','依据目标要求和有效 Belief 的派生判断。',{学习空间:'LS-001',结果:'尚不能确认达标',依据:'迁移及保持等方面缺少证据；独立方面另有待复核线索。'},[{label:'采用目标',ref:'TG-001@1'},{label:'依据 Belief',ref:'BL-001@1'}],{status:'recorded'}),
    obj('OBS-002','observation','Interaction','求原量的作答与解释','学生独立给出算术法并说明参照量。',{事实:'100 ÷ (1 + 1/4) = 80 升；以原量为单位一。',帮助:'本次未提供实质提示。',来源位置:'ACT-002 / F-005'},[],{status:'recorded'}),
    obj('EV-002','evidence','Evaluation','求原量表现的局部支持','同一份作答同时涉及独立完成和解释，不计为两份独立样本。',{方面:'independent、understanding',解释结果:'有局部支持',条件:'使用 S-002；不能据此推断使用 S-004 或掌握其专属 KC。'},[{label:'来源 Observation',ref:'OBS-002@1'},{label:'评价 Claim',ref:'CL-002@1'},{label:'采用规则',ref:'ER-001@1'}],{status:'recorded'}),
    obj('BL-002','belief','Evaluation','学生 A · 求原量任务','独立与解释有局部支持，其余方面未知。',{学习空间:'LS-001',有效性:'示例有效',前次变化:'独立与解释由未知变为局部支持；并非普遍可靠性结论。'},[{label:'针对 Claim',ref:'CL-002@1'},{label:'依据 Evidence',ref:'EV-002@1'}],{status:'recorded',states:aspects.map(a=>({key:a.key,judgment:['independent','understanding'].includes(a.key)?'局部支持':'证据不足',uncertainty:'仅有一次可观察表现',evidence:['independent','understanding'].includes(a.key)?['EV-002@1']:[],note:'没有独立的 KC 能力状态'}))}),
  );
  if(new Set(objects.map(objectKey)).size !== objects.length) throw Error('重复的示例对象');
  return {schema:3,revision:0,drafts:[],changes:[],annotations:[],domains:[{id:'DOM-MATH',name:'数学',scope:'数量关系、数学运算及问题求解。',description:'当前包含分数应用的后台走查示例；领域不绑定具体教材或学习空间。',createdAt:stamp}],objects,spaces,activities,issues:[],preparations:[{chapter:'CH-001',reviewed:false,note:''}],invalidated:{},access:[]};
}
