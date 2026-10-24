import { reactive } from 'vue';
import type { Span, SemanticEvent } from '../types';
import { learningSpaces, type SpaceActivity, type MockLearningSpace } from './learning-space-mock';

export type Execution = 'completed'|'failed'|'interrupted'|'running';
export type Review = 'unreviewed'|'question'|'recorded';
export const executionNames:Record<Execution,string>={completed:'处理完成',failed:'处理失败',interrupted:'已中断',running:'处理中'};
export const reviewNames:Record<Review,string>={unreviewed:'未复核',question:'有疑点',recorded:'已记录复核'};
export interface AuditRef { kind:'claim'|'task'|'solution'|'target'|'chapter'|'requirement'|'evidence'|'observation'; id:string }
export interface AspectChange { aspect:string; before:string; after:string; reason:string; evidenceIds:string[] }
export interface GoalResult { id:string; before:string; after:string; reason:string }
export interface AuditStep extends Span {
  detail:{owner:string;fields?:{label:string;value:string}[];refs?:AuditRef[];checks?:{name:string;passed:boolean;reason:string}[];candidate?:Record<string,unknown>;prompt?:string;response?:string;tokens?:{input:number;output:number};changes?:AspectChange[];results?:GoalResult[];actions?:{name:string;selected:boolean;reason:string}[]};
  children?:AuditStep[];
}
export interface AuditRound {
  id:string; name:string; trigger:string; execution:Execution; messageIndices:number[]; contextIndices:number[];
  help:string; duration:number; steps:AuditStep[]; events:SemanticEvent[];
  observation:{id:string;text:string;support:string;messageIndex:number}|null;
  evidenceIds:string[]; changes:AspectChange[]; results:GoalResult[];
}
export interface ActivityAudit {
  activityId:string; claimId:string; taskId:string; methodIds:string[]; requirementIds:string[];
  execution:Execution; review:Review; reviewNotes:{at:string;review:Review;text:string}[];
  snapshot:MockLearningSpace['adopted']; rounds:AuditRound[];
}
const space=learningSpaces[0]!;
const copy=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
const field=(label:string,value:string)=>({label,value});
const ref=(kind:AuditRef['kind'],id:string):AuditRef=>({kind,id});
const step=(id:string,type:Span['type'],label:string,duration:number,detail:AuditStep['detail'],status:Span['status']='success'):AuditStep=>({spanId:id,type,label,startTime:0,duration,status,detail});
function timed(steps:AuditStep[]){let cursor=0;for(const s of steps){s.startTime=cursor;for(const c of s.children||[])c.startTime=cursor;cursor+=s.duration;}return cursor;}
function observed(roundId:string,messageIndex:number,text:string,support:string,retry=false){
  const observation={id:'OBS-'+roundId,text,support,messageIndex};
  const generate=(suffix:string,wrong=false)=>{
    const candidate={source:'学生消息 '+(messageIndex+1),performance:text,support:wrong?'独立完成':support};
    const parent=step(roundId+'-'+suffix,'observation.generate',suffix==='retry'?'重新生成观察候选':'生成观察候选',1100,{owner:'AI Reasoning · 候选生成',candidate,fields:[field('来源',candidate.source),field('实际帮助上下文',support)]});
    parent.children=[step(parent.spanId+'-llm','llm.invoke','LLM 调用：'+(suffix==='retry'?'修正帮助条件':'理解当前输入'),1000,{owner:'AI Reasoning · 模型调用',fields:[field('模型','演示模型，未实际调用'),field('temperature','0.2（演示值）')],tokens:{input:480,output:110},prompt:'结合当前学生输入和之前实际展示的帮助，描述本次表现，不把受助完成写成独立完成。\n输入：'+text+'\n帮助：'+support,response:JSON.stringify(candidate,null,2)})];
    return parent;
  };
  const steps=[generate('generate',retry)];
  if(retry){steps.push(step(roundId+'-reject','observation.validate','校验候选：拒绝',200,{owner:'AI Reasoning · 语义校验',checks:[{name:'帮助条件一致',passed:false,reason:'上一轮已展示关系与列式提示，不能认定本轮独立完成。'}],fields:[field('提交结果','候选被拒绝，尚未形成 Observation。')]},'failed'),generate('retry'));}
  steps.push(step(roundId+'-check','observation.validate','校验候选：通过',200,{owner:'AI Reasoning · 语义校验',checks:[{name:'输入与来源',passed:true,reason:'描述与指定学生输入一致。'},{name:'实际帮助',passed:true,reason:support}]}),step(roundId+'-commit','observation.commit','提交 Observation',100,{owner:'Interaction · Observation',fields:[field('Observation',observation.id),field('观察内容',text),field('实际帮助',support),field('提交权限','由 Interaction 接收通过校验的观察候选。')],refs:[ref('observation',observation.id)]}));
  return {observation,steps};
}
function evaluate(roundId:string,claimId:string,evidenceIds:string[],changes:AspectChange[],results:GoalResult[]):AuditStep[]{
  const claim=space.adopted.claims.find(c=>c.id===claimId)!;
  const evidence=evidenceIds.map(id=>space.activities.flatMap(a=>a.evidence).find(e=>e.id===id)!);
  return [
    step(roundId+'-evidence','evidence.interpret','解释 Evidence',750,{owner:'Evaluation · Evidence',fields:[field('Task Claim',claim.name+' · v'+claim.version),field('关联 Observation','OBS-'+roundId),...evidence.map(e=>field(claim.aspects.find(a=>a.id===e.aspectId)!.name+' · '+e.id,e.meaning)),field('计数边界','同一次作答即使支持多个方面，也不是多份独立样本。')],refs:[ref('claim',claimId),ref('observation','OBS-'+roundId),...evidenceIds.map(id=>ref('evidence',id))]}),
    step(roundId+'-belief','belief.infer','更新 Task Belief',500,{owner:'Evaluation · Learner State',fields:[field('判断对象',claim.name+' · 同一 Claim 的各个方面'),field('边界','保留实际方法、帮助和证据范围；不更新个人 KC 状态。')],changes,refs:[ref('claim',claimId),...Array.from(new Set(changes.flatMap(c=>c.evidenceIds))).map(id=>ref('evidence',id))]}),
    step(roundId+'-assessment','target.assess','比较目标学习要求',200,{owner:'Evaluation · TargetAssessment',fields:[field('采用目标',space.adopted.target.name+' · v1'),field('结果性质','比较目标要求与个人判断，不改写 Belief；以下为预写结果。')],results,refs:[ref('target',space.adopted.target.id),...results.map(r=>ref('requirement',r.id))]}),
  ];
}
const unchanged=(aspect:string):AspectChange=>({aspect,before:'尚未形成判断',after:'尚未形成判断',reason:'没有适用表现，不从其他方面补齐。',evidenceIds:[]});
const eventFor=(s:AuditStep):SemanticEvent|null=>{
  const type=({'observation.commit':'observation','policy.evaluate':'policy','action.execute':'action','evidence.interpret':'evidence','belief.infer':'belief','target.assess':'assessment'} as Record<string,SemanticEvent['type']>)[s.type];
  if(s.status==='failed'&&s.type==='observation.validate')return {id:s.spanId+'-event',spanId:s.spanId,type:'observation',label:s.label,status:'rejected',detail:'候选未提交；后续重新生成。'};
  return type?{id:s.spanId+'-event',spanId:s.spanId,type,label:s.label,status:type==='policy'?'selected':type==='belief'||type==='assessment'?'updated':'committed',detail:s.detail.owner+' · 人工编写的过程示例'}:null;
};
function round(id:string,name:string,trigger:string,messageIndices:number[],contextIndices:number[],help:string,steps:AuditStep[],observation:AuditRound['observation'],evidenceIds:string[]=[],changes:AspectChange[]=[],results:GoalResult[]=[]):AuditRound{
  return {id,name,trigger,execution:'completed',messageIndices,contextIndices,help,steps,observation,evidenceIds,changes,results,duration:timed(steps),events:steps.map(eventFor).filter((e):e is SemanticEvent=>!!e)};
}
const a1=space.activities.find(a=>a.id==='SPACE-ACT-001')!;
const first=observed('F-R1',0,'学生请求讲解增加后的数量，尚无个人作答。','本轮开始时尚未提供提示。');
first.steps.push(step('F-R1-policy','policy.evaluate','选择讲解提示',400,{owner:'Interaction · Policy',fields:[field('当前意图','请求讲解，而非独立检测。'),field('采用目标','围绕原量与增加量的关系提供帮助。'),field('个人认识','尚无独立表现，不据此拒绝求助。')],actions:[{name:'提示参照量与计算关系',selected:true,reason:'直接响应当前求助。'},{name:'继续要求独立作答',selected:false,reason:'学生已经明确求助。'}],refs:[ref('task','fraction'),ref('solution','S1-A'),ref('target','TARGET-MATH')]}),step('F-R1-action','action.execute','展示列式提示',200,{owner:'Interaction · Action',fields:[field('选定方法','先求增加量，再加回原量（S1-A）。'),field('计划展示',a1.messages[1]!.text),field('已展示内容（示例）',a1.messages[1]!.text),field('展示依据','本活动消息 2 为预写已展示事实；其后作答必须保留受助条件。')],refs:[ref('solution','S1-A')]}));
const second=observed('F-R2',2,a1.messages[2]!.text,'第 1 轮已展示关键关系和列式提示。',true);
const fchanges=[{aspect:'independent',before:'尚未形成判断',after:'只有受助完成记录，独立表现待确认',reason:'提示后的正确作答不能支持独立完成，也不因求助形成反证。',evidenceIds:['SPACE-EV-001']},unchanged('understanding'),unchanged('transfer'),unchanged('retention')];
const fresults=space.adopted.target.claims[0]!.requirements.map(r=>({id:r.id,before:'待确认',after:'待确认',reason:'本章采用方法与 Claim 方法范围待核对；内容缺口不等于学生未掌握。'}));
second.steps.push(...evaluate('F-R2','CLAIM-FRACTION',['SPACE-EV-001'],fchanges,fresults));
const a2=space.activities.find(a=>a.id==='SPACE-ACT-002')!,g2=observed('G-R1',1,a2.messages[1]!.text,'题目给出底与对应高，未给公式或计算提示。');
const g2changes=[{aspect:'independent',before:'尚未形成判断',after:'对给定底高的独立计算有局部支持',reason:'只有本次给定底高条件下的表现，不外推到解释、迁移或保持。',evidenceIds:['SPACE-EV-002']},unchanged('understanding'),unchanged('transfer'),unchanged('retention')];
const g2results=space.adopted.target.claims[1]!.requirements.map(r=>({id:r.id,before:'待确认',after:'待确认',reason:'本次计算提供局部依据，尚未确认稳定满足要求。'}));
g2.steps.push(...evaluate('G-R1','CLAIM-GEOMETRY',['SPACE-EV-002'],g2changes,g2results));
const a3=space.activities.find(a=>a.id==='SPACE-ACT-003')!,g3=observed('E-R1',1,a3.messages[1]!.text,'学生先作答并解释，后续讲解尚未展示。');
const g3changes=[{aspect:'independent',before:g2changes[0]!.after,after:space.judgments[0]!.judgment,reason:space.judgments[0]!.uncertainty,evidenceIds:['SPACE-EV-002','SPACE-EV-003']},{aspect:'understanding',before:'尚未形成判断',after:space.judgments[1]!.judgment,reason:space.judgments[1]!.uncertainty,evidenceIds:['SPACE-EV-004']},unchanged('transfer'),unchanged('retention')];
const g3results=space.adopted.target.claims[1]!.requirements.map(r=>({id:r.id,before:'待确认',after:space.assessments.find(a=>a.requirementId===r.id)?.status||'待确认',reason:space.assessments.find(a=>a.requirementId===r.id)?.reason||'没有相应表现，仍待确认。'}));
g3.steps.push(...evaluate('E-R1','CLAIM-GEOMETRY',['SPACE-EV-003','SPACE-EV-004'],g3changes,g3results),step('E-R1-policy','policy.evaluate','选择公式理由讲解',400,{owner:'Interaction · Policy',fields:[field('当前表现','计算正确，但学生表示只能记住公式。'),field('个人判断输入',g3changes[1]!.after),field('目标要求','解释为什么底乘高后需要除以二（REQ-G2）。')],actions:[{name:'用拼图解释公式理由',selected:true,reason:'补充当前表现中缺少的原理解释。'},{name:'继续增加同类计算题',selected:false,reason:'当前疑点是解释，不只是计算。'}],refs:[ref('claim','CLAIM-GEOMETRY'),ref('requirement','REQ-G2')]}),step('E-R1-action','action.execute','展示针对性讲解',200,{owner:'Interaction · Action',fields:[field('计划展示',a3.messages[2]!.text),field('已展示内容（示例）',a3.messages[2]!.text),field('先后关系','此讲解发生在本轮作答与评价之后，不倒算成作答前帮助。'),field('后续判断','尚无讲解后的新作答，不能立即把理解改为已掌握。')],refs:[ref('solution','S2-A')]}));
const audit=(activityId:string,claimId:string,taskId:string,methodIds:string[],rounds:AuditRound[],review:Review):ActivityAudit=>({activityId,claimId,taskId,methodIds,requirementIds:space.adopted.target.claims.find(c=>c.claimId===claimId)!.requirements.map(r=>r.id),execution:'completed',review,reviewNotes:[],snapshot:copy(space.adopted),rounds});
export const activityAudits=reactive<Record<string,ActivityAudit>>({
  [a1.id]:audit(a1.id,'CLAIM-FRACTION','fraction',['S1-A'],[
    round('F-R1','请求讲解并获得提示','学生求助',[0,1],[],'提示在本轮展示，下一轮开始时已构成实际帮助。',first.steps,first.observation),
    round('F-R2','提示后作答与评价','学生提交答案',[2],[0,1],'关键提示已在第 1 轮展示。',second.steps,second.observation,['SPACE-EV-001'],fchanges,fresults),
  ],'question'),
  [a2.id]:audit(a2.id,'CLAIM-GEOMETRY','geometry',['S2-A'],[round('G-R1','独立作答与评价','学生提交答案',[1],[0],a2.help,g2.steps,g2.observation,['SPACE-EV-002'],g2changes,g2results)],'unreviewed'),
  [a3.id]:audit(a3.id,'CLAIM-GEOMETRY','geometry',['S2-A'],[round('E-R1','作答解释、评价与反馈','学生提交答案与解释',[1,2],[0],a3.help,g3.steps,g3.observation,['SPACE-EV-003','SPACE-EV-004'],g3changes,g3results)],'recorded'),
});
activityAudits[a1.id]!.reviewNotes=[{at:'2026-10-24 18:00',review:'question',text:'观察候选的帮助误判已通过重试修正。仍需核对教材只采用 S1-A，而 Claim 允许 S1-A、S1-B 的配置差异；不能直接修改学生能力判断。'}];
activityAudits[a3.id]!.reviewNotes=[{at:'2026-10-24 18:00',review:'recorded',text:'核对示例：计算与解释分别评价，讲解发生在学生回答之后；尚未采集讲解后的独立表现。'}];
export const auditActivities=()=>learningSpaces.flatMap(space=>space.activities.map(activity=>({space,activity,audit:activityAudits[activity.id]})));
export const findAuditActivity=(id:string)=>auditActivities().find(row=>row.activity.id===id);
export function findAuditStep(steps:AuditStep[],id:string):AuditStep|undefined{for(const s of steps){if(s.spanId===id)return s;const child=findAuditStep(s.children||[],id);if(child)return child;}}
export function evidenceOrigin(spaceId:string,id:string){const s=learningSpaces.find(s=>s.id===spaceId);for(const a of s?.activities||[]){const evidence=a.evidence.find(e=>e.id===id);if(evidence)return {activity:a,evidence};}}
export const requirementIn=(audit:ActivityAudit,id:string)=>audit.snapshot.target.claims.flatMap(c=>c.requirements).find(r=>r.id===id);
export const activityText=(activity:SpaceActivity)=>activity.messages.map(m=>m.text).join(' ');
