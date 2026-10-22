import type { Span, SemanticEvent } from '../types';

// Authored process examples, not runtime logs. References point to the existing
// workbench examples; never use these scripts to enrich real sessions.
export interface ReviewStep extends Span {
  detail: {
    owner: string; input?: string; output?: string; reason?: string; refs?: string[];
    checks?: {name:string;passed:boolean;reason:string}[];
    candidates?: {name:string;selected:boolean;reason:string}[];
    model?: string; temperature?: number; tokens?: {input:number;output:number};
    prompt?: string; response?: string; authority?: string; standing?: string;
    before?: Record<string,string>; candidate?: Record<string,unknown>;
  };
  children?: ReviewStep[];
}
export interface ReviewTrace {status:'normal'|'partial'|'idle';duration:number;spans:ReviewStep[];events:SemanticEvent[];note:string}
const step=(spanId:string,type:Span['type'],label:string,startTime:number,duration:number,detail:ReviewStep['detail'],status:Span['status']='success',children?:ReviewStep[]):ReviewStep=>({spanId,type,label,startTime,duration,status,detail,children});
const call=(id:string,label:string,start:number,duration:number,prompt:string,response:string)=>step(id,'llm.invoke',label,start,duration,{owner:'AI Reasoning · 调用记录',model:'示例模型（未实际调用）',temperature:0.2,tokens:{input:420,output:86},prompt,response});
const before={independent:'证据不足',understanding:'证据不足',transfer:'证据不足',retention:'证据不足'};
const event=(id:string,spanId:string,type:SemanticEvent['type'],label:string,status:SemanticEvent['status'],detail:string):SemanticEvent=>({id,spanId,type,label,status,detail});
export const reviewTraces:Record<string,ReviewTrace>={
  'ACT-001':{
    status:'partial',duration:33000,note:'故意保留错误 Evidence 的复核案例。候选校验拒绝与重试是补充的演示步骤；不代表真实系统已经采集这些日志。活动时长包含等待学生作答的空白区间。',
    spans:[
      step('a1-policy','policy.evaluate','决定如何响应求助',0,1500,{owner:'Interaction · Policy',input:'学生：原来 80 升，增加四分之一，我不知道怎么算。',output:'提供参照量和列式提示。',reason:'明确请求讲解，允许提供帮助；其后作答不能自动认定为独立完成。',refs:['POL-001@1'],candidates:[{name:'提供列式提示',selected:true,reason:'响应当前求助。'},{name:'继续要求独立作答',selected:false,reason:'不符合本次明确求助。'}]}),
      step('a1-action','action.execute','执行并展示提示',1500,2500,{owner:'Interaction · Action',input:'提供参照量和列式提示。',output:'把 80 升当作原量，先算 80 × 1/4，再加回 80。',reason:'示例事实 F-002 记录已展示；09:10:04 早于后续作答。',refs:['ACTION-001@1']}),
      step('a1-generate','observation.generate','生成观察候选',28000,1000,{owner:'AI Reasoning · Candidate',input:'F-003：80 × 1/4 = 20，80 + 20 = 100 升；同时提供 F-002 的帮助上下文。',output:'候选 CAND-A1：结果正确，独立完成。',candidate:{id:'CAND-A1',type:'ObservationCandidate',source:['F-003','F-002'],correct:true,support:'independent'}},'success',[
        call('a1-call1','LLM 调用：理解作答',28000,950,'依据原始作答和此前实际帮助描述表现，不能抹去支持条件。','{"candidate":"CAND-A1","correct":true,"support":"independent"}'),
      ]),
      step('a1-reject','observation.validate','校验候选：拒绝',29000,200,{owner:'AI Reasoning · Validation',input:'CAND-A1',output:'拒绝候选；不提交 Observation。',checks:[{name:'计算事实一致',passed:true,reason:'结果为 100 升。'},{name:'帮助条件一致',passed:false,reason:'实际已提供列式提示，候选却宣称独立完成。'}]},'failed'),
      step('a1-retry','observation.generate','重新生成观察候选',29200,1100,{owner:'AI Reasoning · Candidate',input:'原输入与校验拒绝原因。',output:'候选 CAND-A2：列式提示后的正确作答。',candidate:{id:'CAND-A2',type:'ObservationCandidate',source:['F-003','F-002'],correct:true,support:'受助'}},'success',[
        call('a1-call2','LLM 调用：修正观察',29200,1050,'修正 CAND-A1：实际已提供列式提示，描述受助条件，不推断独立能力。','{"candidate":"CAND-A2","correct":true,"support":"受助","fact":"80 × 1/4 = 20，80 + 20 = 100 升"}'),
      ]),
      step('a1-validate','observation.validate','校验修正候选：通过',30300,200,{owner:'AI Reasoning · Validation',input:'CAND-A2',output:'候选满足本次观察合同。',checks:[{name:'计算事实一致',passed:true,reason:'保留原始计算。'},{name:'帮助条件一致',passed:true,reason:'明确描述实质提示，不据此认定独立。'}]}),
      step('a1-commit','observation.commit','提交 Observation',30500,100,{owner:'Interaction · Observation',input:'通过校验的 CAND-A2。',output:'OBS-001@1',authority:'由 Interaction 的提交边界写入正式观察（示例）。',standing:'committed；只承诺观察合同，不承诺后续评价必然正确。',refs:['OBS-001@1']}),
      step('a1-evidence','evidence.interpret','解释 Evidence',30600,1100,{owner:'Evaluation · Evidence Model',input:'OBS-001@1、CL-001@1、ER-001@1。',output:'EV-001@1：支持独立完成。',reason:'本例故意保留误判：忽略实际帮助。处理完成不等于语义正确；应结合 F-002/F-003 复核。',refs:['EV-001@1','OBS-001@1','CL-001@1','ER-001@1']},'partial'),
      step('a1-belief','belief.infer','推断 Task Belief',31700,900,{owner:'Evaluation · Learner State / Inference',input:'同一 Task Claim 的先前认识及 EV-001@1。',output:'独立方面从证据不足变为有支持；其依据有待复核，其余方面保持未知。',before,refs:['BL-001@1','IR-001@1']},'partial'),
      step('a1-assess','target.assess','派生目标评价',32600,400,{owner:'Evaluation · 目标评价',input:'TG-001@1 与相应 Belief。',output:'尚不能确认达标。',refs:['TA-001@1','TG-001@1']}),
    ],
    events:[
      event('a1-e1','a1-policy','policy','选择列式提示','selected','POL-001@1'),
      event('a1-e2','a1-action','action','提示已展示（示例事实）','committed','ACTION-001@1 / F-002'),
      event('a1-e3','a1-reject','observation','候选被拒绝','rejected','CAND-A1 没有形成 Observation。'),
      event('a1-e4','a1-commit','observation','受助作答被提交','committed','OBS-001@1'),
      event('a1-e5','a1-evidence','evidence','错误解释待复核','committed','EV-001@1；提交不等于解释正确。'),
      event('a1-e6','a1-belief','belief','同一 Claim 的方面状态更新','updated','BL-001@1；不生成 KC Belief。'),
      event('a1-e7','a1-assess','assessment','目标尚不能确认达标','updated','TA-001@1'),
    ],
  },
  'ACT-002':{
    status:'normal',duration:64000,note:'独立作答与解释提供局部支持。时长包含等待学生作答；不是模型调用延迟。',
    spans:[
      step('a2-start','turn.start','题目与作答上下文',0,100,{owner:'Interaction · 输入',input:'F-004：增加四分之一后为 100 升，原有多少升？',output:'等待学生作答。'}),
      step('a2-generate','observation.generate','理解作答与解释',60000,1200,{owner:'AI Reasoning · Candidate',input:'F-005：100 ÷ (1 + 1/4) = 80 升；以原量为单位一。',output:'独立使用算术法，解释参照量。'},'success',[
        call('a2-call','LLM 调用：理解作答',60000,1150,'保留学生的实际方法与支持条件；未观察到的方法不作推断。','{"method":"S-002","support":"独立","answer":"80 升","explanation":"以原量为单位一"}'),
      ]),
      step('a2-check','observation.validate','校验候选：通过',61200,200,{owner:'AI Reasoning · Validation',input:'当前候选与 F-004/F-005。',output:'观察合同通过。',checks:[{name:'输入来源一致',passed:true,reason:'作答与解释均来自学生。'},{name:'支持条件一致',passed:true,reason:'本次未提供实质提示。'}]}),
      step('a2-commit','observation.commit','提交 Observation',61400,100,{owner:'Interaction · Observation',output:'OBS-002@1',authority:'Interaction 提交边界（示例）。',standing:'committed',refs:['OBS-002@1']}),
      step('a2-evidence','evidence.interpret','解释 Evidence',61500,1300,{owner:'Evaluation · Evidence Model',input:'OBS-002@1、CL-002@1。',output:'独立与解释有局部支持；同一份作答不计为两份独立样本。',reason:'采用 S-002 不能证明 S-004 或其专属 KC 已掌握。',refs:['EV-002@1','OBS-002@1','CL-002@1']}),
      step('a2-belief','belief.infer','推断 Task Belief',62800,1200,{owner:'Evaluation · Learner State / Inference',output:'独立与解释由未知变为局部支持，迁移和延迟保持证据不足。',before,refs:['BL-002@1']}),
    ],
    events:[event('a2-e1','a2-commit','observation','提交独立作答','committed','OBS-002@1'),event('a2-e2','a2-evidence','evidence','一份作答支持两个方面','committed','EV-002@1'),event('a2-e3','a2-belief','belief','局部认识更新','updated','BL-002@1')],
  },
  'ACT-003':{status:'idle',duration:0,note:'只记录了讲解请求，尚无系统输出及个人作答；不能将未形成评价判作运行失败。',spans:[],events:[]},
};
export function findStep(spans:ReviewStep[],id:string):ReviewStep|undefined {
  for(const s of spans){if(s.spanId===id)return s;const found=findStep(s.children||[],id);if(found)return found;}
}
export const traceStatus:Record<string,string>={normal:'处理完成',partial:'待复核',idle:'尚无评价',unknown:'步骤未记录',saved:'已保存',pending:'待收束',error:'有错误记录',ended:'已结束'};
export function downloadTrace(name:string,value:unknown){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
