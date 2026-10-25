import { auditActivities, executionNames, type AuditStep } from './activity-review-mock';
import { observationSections, observationData, observationMetrics, dateMatches, type ObservationSection, type ObservationRecord } from './runtime-observation';

export const overviewGroups=[
  {id:'execution',name:'执行问题',note:'按活动计数，汇总已记录的失败或中断过程（含后续已恢复的情况）；校验拒绝单独查看，不计为整轮失败。'},
  {id:'review',name:'审查疑点',note:'所选活动当前仍标为有疑点的人工意见；未复核不等于存在错误。'},
  {id:'configuration',name:'内容与条件',note:'当前内容准备、引用条件与采用差异；不随日期回退，不代表学生能力不足。'},
  {id:'evidence',name:'评价依据',note:'当前已记录的证据缺口；不是执行故障，也不自动启动检测。'},
] as const;
export type OverviewGroup=typeof overviewGroups[number]['id'];
export interface OverviewAttention {id:string;group:OverviewGroup;title:string;summary:string;status:string;scopeIds:string[];time:string;page:string;values:Record<string,string>}
const flatten=(steps:AuditStep[]):AuditStep[]=>steps.flatMap(s=>[s,...flatten(s.children||[])]);

export function overviewData(scope:string,range:string,since:string,until:string){
  const activities=auditActivities().filter(r=>(!scope||r.space.id===scope)&&dateMatches(r.activity.at,range,since,until)).sort((a,b)=>b.activity.at.localeCompare(a.activity.at));
  const modules=observationSections.map(section=>{
    const data=observationData(section.id,scope);
    const period=data.records.filter(r=>r.current||dateMatches(r.at,range,since,until));
    return {...section,data,period,metrics:observationMetrics(section.id,data,period)};
  });
  const records=(section:ObservationSection)=>modules.find(m=>m.id===section)!.period;
  const count=(section:ObservationSection,kind:string)=>records(section).filter(r=>r.kind===kind).length;
  const attention:OverviewAttention[]=[];
  for(const {space,activity,audit} of activities){
    if(!audit)continue;
    const failedRounds=audit.rounds.filter(r=>r.execution==='failed'||r.execution==='interrupted');
    const failedSteps=audit.rounds.flatMap(r=>flatten(r.steps).filter(s=>s.status==='failed'&&s.type!=='observation.validate').map(step=>({round:r.id,step})));
    if(audit.execution==='failed'||audit.execution==='interrupted'||failedRounds.length||failedSteps.length)attention.push({id:'execution:'+activity.id,group:'execution',title:activity.name,status:executionNames[audit.execution],summary:['已记录处理状态：'+executionNames[audit.execution],...failedRounds.map(r=>r.name+'：'+executionNames[r.execution]),...failedSteps.map(s=>s.step.label+'失败'),'不代表学生是否达标。'].join('；'),scopeIds:[space.id],time:'活动开始 '+activity.at,page:'activity',values:{id:activity.id,round:failedSteps[0]?.round||failedRounds[0]?.id||'',span:failedSteps[0]?.step.spanId||''}});
    if(audit.review==='question')attention.push({id:'review:'+activity.id,group:'review',title:activity.name,status:'人工标记疑点',summary:audit.reviewNotes[0]?.text||'尚未记录具体原因。',scopeIds:[space.id],time:audit.reviewNotes[0]?'复核于 '+audit.reviewNotes[0].at:'复核时间未记录',page:'activity',values:{id:activity.id,tab:'handling'}});
  }
  const addRecord=(r:ObservationRecord,section:ObservationSection,group:OverviewGroup)=>{
    if(attention.some(a=>a.id===r.id))return;
    attention.push({id:r.id,group,title:r.title,summary:r.summary,status:r.status,scopeIds:r.scopeIds,time:r.current?'当前快照':r.at,page:'objects',values:{tab:section,id:r.id}});
  };
  for(const section of ['Domain','Learning','Evolution'] as const)for(const r of records(section).filter(r=>r.attention))addRecord(r,section,'configuration');
  for(const r of records('Evaluation').filter(r=>r.kind==='证据缺口'))addRecord(r,'Evaluation','evidence');
  const rounds=activities.flatMap(r=>r.audit?.rounds||[]);
  const requirements=modules.find(m=>m.id==='Evaluation')!.data.totalRequirements;
  return {activities,modules,attention,rounds,
    students:new Set(activities.map(r=>r.space.studentId)).size,spaces:new Set(activities.map(r=>r.space.id)).size,
    executions:Object.entries(executionNames).map(([id,name])=>({id,name,value:activities.filter(r=>r.audit?.execution===id).length})),
    unrecorded:activities.filter(r=>!r.audit).length,
    evidence:count('Evaluation','Evidence'),beliefs:count('Evaluation','Belief 更新'),assessments:count('Evaluation','目标评价'),
    calls:count('Reasoning','模型调用'),rejected:records('Reasoning').filter(r=>r.kind==='语义校验'&&r.status==='候选被拒绝').length,
    goals:['已达标','需加强','待确认'].map(name=>({name,count:requirements.filter(r=>r.status===name).length})),
  };
}

// Daily buckets share the activity-start-date convention used by interaction review.
export function overviewTrend(rows:ReturnType<typeof auditActivities>,range:string,since:string,until:string){
  const local=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const days=rows.map(r=>r.activity.at.slice(0,10)).sort(),today=local(new Date());
  let start=days[0]||today,end=days[days.length-1]||today;
  if(range==='custom'){start=since||start;end=until||end;}
  else if(range&&range!=='all'){end=today;const d=new Date(today+'T12:00:00');d.setDate(d.getDate()-(range==='7days'?6:range==='30days'?29:0));start=local(d);}
  const floor=new Date(end+'T12:00:00');floor.setDate(floor.getDate()-13);
  const clipped=start<local(floor);if(clipped)start=local(floor);
  const result:{day:string;activities:number;rounds:number}[]=[];
  const cursor=new Date(start+'T12:00:00');
  while(local(cursor)<=end&&result.length<14){const day=local(cursor),matches=rows.filter(r=>r.activity.at.startsWith(day));result.push({day,activities:matches.length,rounds:matches.reduce((sum,r)=>sum+(r.audit?.rounds.length||0),0)});cursor.setDate(cursor.getDate()+1);}
  return {days:result,clipped};
}
