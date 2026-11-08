import { reactive, ref } from 'vue';
import { copyTeaching, type TeachingBlueprint, type TeachingStage, type TeachingTransition, type TeachingRule, type TeachingStrategy } from './teaching-mock';
export type ActivityKind = 'explanation' | 'question' | 'assessment' | 'free';
export const activityNames:Record<ActivityKind,string>={explanation:'讲解',question:'答疑',assessment:'检测',free:'自由交谈'};

type ActivityRule = {
  name: string;
  condition: string;
  requirement: string;
};

type ActivityStrategy = {
  name: string;
  when: string;
  suggestion: string;
};

type ActivityDefinition = {
  kind: ActivityKind;
  name: string;
  purpose: string;
  boundary: string;
  rules: ActivityRule[];
  strategies: ActivityStrategy[];
};

export const activityDefinitions: Record<Exclude<ActivityKind, 'explanation'>, ActivityDefinition> = {
  question: {
    kind: 'question',
    name: '答疑活动',
    purpose: '围绕学生提出的一个独立疑问，定位问题、回应问题，并在需要时回到原活动。',
    boundary: '同一问题的连续澄清留在本活动内；只有必须系统说明前提时才创建讲解子活动。答疑不直接形成 Evidence 或 Belief。',
    rules: [
      { name: '局部追问不碎裂', condition: '学生围绕同一疑问继续追问，没有独立目标和返回需要。', requirement: '留在本答疑活动中澄清或回应，不强行创建新的子活动。' },
      { name: '不把提问当成能力结论', condition: '学生提出问题或说“没懂”。', requirement: '只记录实际表达与回应，不直接写入能力判断。' },
      { name: '恢复原主线', condition: '答疑作为父活动的子活动结束。', requirement: '按返回规则恢复、结束或替换父活动，并保留暂停点。' },
    ],
    strategies: [
      { name: '直接澄清', when: '问题范围明确，学生需要的是一处解释或辨析。', suggestion: '直接回应关键关系，不制造不必要的完整课程。' },
      { name: '追问定位', when: '学生只表达“不会”或“没懂”，不足以确定问题。', suggestion: '只问会影响回应的一两个澄清问题。' },
      { name: '升级为讲解', when: '回答依赖尚未建立的前提或完整方法。', suggestion: '暂停答疑，建立讲解子活动；讲解结束后回到本答疑。' },
    ],
  },
  assessment: {
    kind: 'assessment',
    name: '检测活动',
    purpose: '在明确范围、帮助条件和题目计划下，取得可解释的学生表现。',
    boundary: '检测活动可含多个检测轮；原子性属于检测轮。检测轮中不讲解、不答疑、不泄露答案或方法。',
    rules: [
      { name: '检测轮原子性', condition: '检测轮正在进行。', requirement: '只展示题面和作答入口；不嵌入讲解、答疑、答案或实质提示。' },
      { name: '求助先结束本轮', condition: '学生在检测轮中请求实质帮助。', requirement: '结束当前轮，保留已提交内容和草稿，取消原题单尚未开始轮次；之后才创建讲解或答疑子活动。' },
      { name: '帮助后使用新轮', condition: '获得实质帮助后仍需确认。', requirement: '使用未见答案的新题建立新检测轮，不恢复旧轮，也不把受助作答写回旧轮。' },
      { name: '暂停不泄露帮助', condition: '学生只是暂时退出，未请求实质帮助。', requirement: '可暂停并保存当前轮，不展示新方法、答案或反馈。' },
    ],
    strategies: [
      { name: '首次诊断', when: '当前缺少此范围的有效表现。', suggestion: '先取得少量、范围明确的表现，不用一长串同类题替代诊断。' },
      { name: '针对性确认', when: '已有部分表现，但某个方面或方法仍缺少条件合适的记录。', suggestion: '只安排能补足当前缺口的新题。' },
      { name: '延迟保持确认', when: '已有初步结果，且到达明确的延迟观察时点。', suggestion: '另起新轮，并保留时间与帮助条件。' },
    ],
  },
  free: {
    kind: 'free',
    name: '自由交谈活动',
    purpose: '承接闲聊、产品使用问题和暂未能确认的意图，使持续聊天中的每条交流都有归属。',
    boundary: '不产生学习表现、Evidence、Belief 或主动任务；识别出明确学习意图后才转入学习活动。',
    rules: [
      { name: '不产生评价输入', condition: '活动类型为自由交谈。', requirement: '不得把消息解释为学习表现、Evidence、Belief 或主动任务依据。' },
      { name: '明确意图才转交', condition: '系统推测消息可能与学习有关。', requirement: '意图不明确时先澄清，不静默切换成讲解、答疑或检测。' },
    ],
    strategies: [
      {name:'简短回应',when:'学生希望闲聊或了解产品操作。',suggestion:'先直接回应，不把普通交流扩展成一堂课。'},
      {name:'必要澄清',when:'尚不能确定学生是闲聊还是需要学习帮助。',suggestion:'只澄清影响下一步的关键意图，不反复要求确认。'},
      {name:'自然收束',when:'问题已回应，学生没有继续交流的请求。',suggestion:'简短结束或返回父活动，不强行推荐学习任务。'},
    ],
  },
};

type ManagedKind=Exclude<ActivityKind,'explanation'>;
type ActivityModel={revision:number;blueprint:TeachingBlueprint;rules:TeachingRule[];strategies:TeachingStrategy[];activityRules:string[];activityStrategies:string[];history:{version:number;at:string;change:string}[]};
function node(id:string,name:string,purpose:string,inputs:string,actions:string,outputs:string,blocked:string,rules:string[]=[],strategies:string[]=[]):TeachingStage{
  return {id,name,purpose,inputs,approach:actions,actions,outputs,blocked,rules,strategies,routing:{when:'收到学生回应、形成节点结果或子活动返回后判断；暂停和结束请求优先处理。',otherwise:'在允许动作内继续回应或等待必要输入；不能可靠继续时按本节点处理保留未决项，不自动重复或宣称成功。'}};
}
function edge(from:string,to:string,label:string,condition:string):TeachingTransition{return {id:from+'-'+to,from,to,label,condition,basis:'学生实际请求、当前节点记录及活动规则；子活动路径以返回记录为准。'};}
function rule(id:string,name:string,when:string,requirement:string):TeachingRule{return {id,name,when,requirement,basis:'M1 已确认的活动边界；本页为 mock 配置，尚未执行语义规则检查。',enabled:true,version:1};}

function initialModel(kind:ManagedKind):ActivityModel{
  const source=activityDefinitions[kind];
  const rules:TeachingRule[]=[
    rule('stop','尊重暂停与结束','学生要求暂停或结束。','立即停止新增动作，保留当前位置与未决项；可从任意节点暂停或带未决项结束，不要求先完成流程。'),
    rule('boundary','活动与评价边界','开展本活动或调用子活动。',source.boundary+' 子活动使用自身配置，父活动保留返回位置；系统约束始终生效。'),
    rule('conflict','无法可靠继续时停止','内容无法核实，或规则发生冲突。','停止受影响动作，说明限制、澄清或保留未决项结束；不得自行放宽规则。'),
    ...source.rules.map((r,i)=>rule('rule-'+i,r.name,r.condition,r.requirement)),
  ];
  const strategies:TeachingStrategy[]=source.strategies.map((s,i)=>({id:'strategy-'+i,name:s.name,purpose:s.suggestion,when:s.when,avoid:kind==='assessment'?'不得在进行中的检测轮提供方法、提示或答案。':'请求明确且当前方式已足够时，不增加额外步骤。',inputs:kind==='assessment'?'检测目的、目标条件、已有表现、题目接触与帮助记录。':'学生原话、当前问题、关联材料和父活动上下文。',organization:s.suggestion,help:kind==='assessment'?'只在检测轮之外安排帮助；轮中实质求助先结束该轮。':'遵守本节点允许动作；需要子活动时保存原问题与返回位置。',observe:kind==='assessment'?'作答、实际帮助、接触条件、轮次结束原因；不从求助直接判断能力。':'实际问题、回应、追问与是否仍有未解决内容；不直接转为能力结论。',adjust:'条件不适用时改用其他合规方式，不要求命中推荐；无法继续则按节点处理。',end:'本次目的已回应、需要转交，或学生选择暂停、结束。',basis:'M1 活动策略示例；实际效果待后续验证。',examples:kind==='question'?'学生问增加四分之一为何以原量为基准，先回应这一疑点。':kind==='assessment'?'检测一个量增加四分之一；帮助后另用新题、新轮确认。':'学生问如何打开教材时说明操作；明确要求讲解后再转交。',enabled:true,version:1}));
  let stages:TeachingStage[],transitions:TeachingTransition[],activityRules:string[],activityStrategies:string[]=[];
  const common=['stop','boundary','conflict'];
  if(kind==='question'){
    stages=[
      node('locate','定位问题','确定本次要回应的疑问。','学生问题、题目或材料、父活动暂停点。','问题明确直接进入回应；只澄清影响回答的信息，不强制先提问。','原始问题、已确定范围和必要上下文。','信息不足时请求必要补充；无法获得时保留原问题并暂停或结束。', ['rule-0'],['strategy-1']),
      node('respond','回应问题','围绕原问题给出可理解的回应。','原始疑问、领域依据、已有回应与帮助记录。','直接说明、举例或对比；同一疑问留在本活动。需系统说明或独立子问题时调用子活动；需检测时先征得同意。','回应、追问、未解决疑问及下一步理由。','无法核实时说明限制；不以学生说懂了替代能力评价。可带未决项结束。',[],['strategy-0']),
      node('help-child','调用讲解或子答疑','处理影响回答的前提或具有独立目标的子问题。','原问题、子问题、已提供帮助和返回“回应问题”的位置。','保存原问题，调用讲解或答疑子活动；等待期间不继续父活动回应。','子活动结束原因、实际帮助、结果及未决项。','子活动暂停时父活动保持等待；未解决或失败时返回原问题说明限制，不自动再次调用。',[],['strategy-2']),
      node('check-child','调用检测','以符合条件的表现确认当前疑问涉及的学习情况。','明确检测目的、范围及学生同意；返回“回应问题”的位置。','交由检测子活动组织轮次；接收完成或取消的返回记录，不在本节点执行检测。','检测返回结果、帮助条件和可用评价。','没有题目或条件不足时不启动；暂停则等待，取消或未评价时如实返回原问题。'),
      node('return','收束答疑','说明原问题处理到哪里，交回父活动或结束。','回应、子活动结果、未决项及父活动位置。','仅总结已知结果；有父活动且仍需继续时交还主线，不自动开启另一堂课。','本次答疑结果、未解决内容和返回安排。','未解决也可以结束，明确保留问题，不宣称已经理解。',['rule-2']),
    ];
    transitions=[edge('start','locate','收到疑问','学生提出独立疑问或父活动转入答疑。'),edge('locate','respond','范围明确','已有足够信息回应，不要求额外澄清。'),edge('locate','return','暂不能回答','无法获得必要信息，或学生希望结束。'),edge('respond','locate','继续澄清','同一问题的追问需要重新确定卡点。'),edge('respond','help-child','需要子活动','需要系统补充前提或处理有独立目标的子疑问。'),edge('help-child','respond','返回原问题','子活动完成、取消或失败并已返回；暂停时仍等待。'),edge('respond','check-child','同意检测','有必要通过表现确认且学生同意检测。'),edge('check-child','respond','检测返回','检测子活动已经返回，保留未评价或未解决情况。'),edge('respond','return','收束问题','本次已回应或学生选择停止，不以掌握为结束条件。'),edge('return','end','结束答疑','记录结果与未决项，存在父活动时交回原位置。')];
    activityRules=[...common,'rule-1'];activityStrategies=['strategy-0'];
  }else if(kind==='assessment'){
    stages=[
      node('prepare','准备检测','明确目的、范围、负担及帮助边界。','学生请求或已接受的系统建议、目标、题目和接触记录。','说明安排并确认意愿；选择可用题目。延迟保持可作为启动理由，不强制学生开始。','确认后的计划、题目与帮助条件。','条件不足或题目不可用时停止准备，说明原因；不得无题开测或宣称失败。',[],['strategy-0','strategy-2']),
      node('round','检测轮','在明确条件下记录一次作答过程。','本轮题目、作答入口、已确认的检测条件。','展示题面、接收作答、处理不含解题信息的技术确认；暂停或结束本轮。实质求助先结束本轮，不提供提示。','原作答或未提交草稿、时间、实际帮助、结束原因。','题目或技术条件有问题时终止受影响轮次，不判学生答错。普通暂停保存原轮且不泄露内容。',['rule-0','rule-1','rule-3']),
      node('dispose','轮后处理','根据已结束轮次确定下一步。','结束记录、剩余计划、学生请求与可用 Evaluation 结果。','无实质帮助时可继续原计划；求助后取消原题单未开始部分并调用帮助；帮助后重新确认新题新轮。','下一步安排、关联轮次与未检测部分。','评价尚未返回时标明待确认；没有继续必要或学生不愿继续则汇总，不盲目加题。',['rule-2'],['strategy-1']),
      node('help-child','调用讲解或答疑','为已结束的检测轮提供帮助。','已结束轮次、原题及作答、具体求助和返回“轮后处理”的位置。','创建关联该轮的讲解或答疑子活动；保留旧轮原始表现，等待子活动返回。','实际帮助、子活动结果和未解决内容。','子活动暂停时等待；失败或取消后返回轮后处理；不可恢复旧轮或把受助订正写回旧轮。',['rule-2']),
      node('complete','汇总反馈','结束本次检测并反馈实际结果。','已结束轮次、未检测部分、实际帮助及可用评价。','展示 Evaluation 已返回的结果与限制；无结果则说明尚未形成评价，交回父活动或结束。','检测汇总、评价来源与未决项。','缺少评价不妨碍结束活动；只报告已知记录，不自行宣布掌握或目标达成。'),
    ];
    stages[1].routing={when:'仅在本轮提交、停止、技术终止或因实质求助结束后转移。',otherwise:'继续等待作答；普通暂停保存当前轮，不展示新提示、答案或反馈。未结束本轮不能进入轮后处理或调用子活动。'};
    transitions=[edge('start','prepare','接受检测','学生主动发起或接受系统检测建议。'),edge('prepare','round','条件具备','目的、范围、首轮题目、帮助边界和学生意愿已确认。'),edge('prepare','complete','取消或不可用','学生取消或必要条件无法满足，未开始部分保持未检测。'),edge('round','dispose','本轮已结束','已提交、停止、技术终止或因求助结束；求助时先保存记录并取消原题单未开始部分。'),edge('dispose','round','继续原计划','没有实质帮助且仍有适用题目，学生同意继续。'),edge('dispose','help-child','请求轮后帮助','本轮已结束且学生希望讲解或答疑。'),edge('help-child','dispose','帮助返回','子活动完成、取消或失败并已返回；暂停时等待。'),edge('dispose','prepare','重新安排','受助后仍有检测必要且学生愿意，重新确认新题、新轮，不恢复旧轮或旧题单。'),edge('dispose','complete','结束检测','计划完成、没有继续必要或学生选择结束。'),edge('complete','end','反馈完成','保留原始表现、未检测部分与评价限制后结束。')];
    activityRules=common;
  }else{
    stages=[
      node('converse','交流与澄清','回应非学习内容并识别明确请求。','学生原话、当前产品上下文和可能的父活动。','普通交流、说明使用方法、必要澄清；学习意图明确时直接转交，不反复确认。','实际交流和已确认的学习意图，不形成能力判断。','不确定意图时继续澄清或等待；无法可靠回答时说明限制，不强行转入教学。',[],['strategy-1']),
      node('handoff','转交学习活动','将明确学习意图交给相应活动。','讲解、答疑或检测请求、相关材料、父活动与返回位置。','顶层交流结束后建立新的顶层学习活动；若是子活动且请求属于原任务则返回父活动。更换学习内容时明确原主线暂停或结束。','新活动引用或返回安排、原活动保留方式。','转交失败时回到交流说明原因；未成功建立或返回前不显示已转交。'),
      node('summary','收束交流','自然结束或交回父活动。','实际交流、学生意愿和父活动位置。','简短收束；有父活动则恢复或保持其暂停，不强制追加学习任务。','结束原因和返回结果。','没有学习结果无需补充评价；学生停止时直接保留记录结束。',[],['strategy-2']),
    ];
    transitions=[edge('start','converse','普通交流','消息暂不构成明确的学习活动请求。'),edge('converse','handoff','学习意图明确','学生已明确希望讲解、答疑或检测；不再重复要求确认。'),edge('converse','summary','自然结束','交流已足够或学生希望结束。'),edge('handoff','converse','转交未完成','缺少必要材料、创建失败或意图改变，需要说明或澄清。'),edge('handoff','end','转交完成','已建立新活动或完成返回安排，并明确原主线的去向。'),edge('summary','end','结束交流','已记录结束或返回安排。')];
    activityRules=[...common,'rule-0','rule-1'];activityStrategies=['strategy-0'];
  }
  return {revision:1,blueprint:{name:source.name,purpose:source.purpose,stages,transitions,startRouting:{when:'收到学生明确请求或接受系统建议后判断。',otherwise:'等待必要输入，不自行启动活动。'}},rules,strategies,activityRules,activityStrategies,history:[]};
}

function loadWorkspace(kind:ManagedKind){
  const key='m1-activity-model-'+kind+'-v1',initial=initialModel(kind),error=ref('');
  let value=initial,migrationNotice='';
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'null');
    if(saved){if(!Array.isArray(saved.blueprint?.stages)||!Array.isArray(saved.rules)||!Array.isArray(saved.strategies)||!Array.isArray(saved.activityRules)||!Array.isArray(saved.activityStrategies))throw Error();value=saved;}
    else{
      // Retain authored content from the earlier editor; revised flow defaults supply missing paths.
      const legacy=JSON.parse(localStorage.getItem('m1-activity-definition-'+kind)||'null');
      if(legacy){
        for(const n of legacy.states||[]){const current=value.blueprint.stages.find(s=>s.id===n.id);if(current){current.name=n.name;current.purpose=n.purpose;current.inputs=n.inputs;current.outputs=n.outputs;}}
        for(const [i,r] of (legacy.rules||[]).entries()){const current=value.rules.find(r=>r.id==='rule-'+i);if(current){current.name=r.name;current.when=r.condition;current.requirement=r.requirement;}}
        for(const [i,s] of (legacy.strategies||[]).entries()){const current=value.strategies.find(s=>s.id==='strategy-'+i);if(current){current.name=s.name;current.when=s.when;current.organization=s.suggestion;}}
        migrationNotice='已继承旧版节点名称、目的、输入输出及规则、策略内容；流程与允许动作按本轮方案补齐，旧配置仍保留在浏览器中。';
      }
    }
  }catch{error.value='已保存的活动配置无法读取，本页暂用默认配置。';}
  const model=reactive(value),draft=ref(copyTeaching(model.blueprint));
  function record(change:string){model.revision++;model.history.unshift({version:model.revision,at:new Date().toLocaleString('sv-SE',{hour12:false}),change});try{localStorage.setItem(key,JSON.stringify(model));error.value='';}catch{error.value='保存失败，请保留当前页面，配置尚未持久保存。';}}
  return {model,draft,error,record,migrationNotice};
}
const workspaces:Partial<Record<ManagedKind,ReturnType<typeof loadWorkspace>>>={};
export function getActivityWorkspace(kind:ManagedKind){return workspaces[kind]??=(loadWorkspace(kind));}
