import { domainMock, collectKnowledge } from './domain-mock';
import { evaluationMock, defaultAspectNames } from './evaluation-mock';
import { textbookMock } from './textbook-mock';
import { targetMock } from './target-mock';
import { learningSpaces, spaceChapters, spaceClaims, spaceRequirements, assessmentFor, requirementIssues, adoptedDefinitions, courseKnowledge, type MockLearningSpace } from './learning-space-mock';
import { auditActivities, executionNames, reviewNames, type AuditStep } from './activity-review-mock';

export const observationSections=[
  {id:'Domain',name:'Domain Space',title:'领域使用与依赖',description:'查看任务与方法的实际引用，核对课程采用和依赖依据。'},
  {id:'Learning',name:'Learning Space',title:'课程采用与准备情况',description:'查看所选课程范围、内容缺口和采用版本，不合并个人能力。'},
  {id:'Evaluation',name:'Evaluation Space',title:'评价变化与证据依据',description:'查看分方面判断、目标结果及未决依据，追溯相应活动。'},
  {id:'Interaction',name:'Interaction Space',title:'交互状态与实际行动',description:'核对已记录轮次的帮助、上下文、决策和实际展示。'},
  {id:'Reasoning',name:'AI Reasoning',title:'候选处理与调用记录',description:'查看候选、校验、重试与提交；以下均为预写处理脚本。'},
  {id:'Evolution',name:'模型变更',title:'定义变更与采用差异',description:'查看直接保存的修改和现有空间的采用差异；不运行自动演化或审核发布。'},
] as const;
export type ObservationSection=typeof observationSections[number]['id'];
export interface ObservationLink { label:string; page:string; values:Record<string,string> }
export interface ObservationRecord {
  id:string; kind:string; title:string; summary:string; status:string; at:string; current:boolean;
  scopeIds:string[]; attention:boolean; source:string; fields:[string,string][]; links:ObservationLink[]; raw?:unknown;
}
export interface ObservationMetric {label:string;value:number|string;note:string}
const aspect=(id:string)=>(defaultAspectNames as Record<string,string>)[id]||id;
const unique=<T,>(values:T[])=>[...new Set(values)];
const json=(value:unknown)=>JSON.stringify(value,null,2);
const initialDomain=JSON.parse(JSON.stringify(domainMock)) as typeof domainMock;
const link=(label:string,page:string,values:Record<string,string>):ObservationLink=>({label,page,values});
const record=(value:Partial<ObservationRecord>&Pick<ObservationRecord,'id'|'kind'|'title'|'summary'>):ObservationRecord=>({status:'已记录',at:'',current:false,scopeIds:[],attention:false,source:'当前共用的人工示例',fields:[],links:[],...value});
const spaceLink=(s:MockLearningSpace,tab='overview',extra:Record<string,string>={})=>link('查看学习空间 →','learning-spaces',{id:s.id,tab,...extra});
const claimLink=(id:string)=>link('查看当前 Claim →','evaluation',{id,tab:'definition'});
const domainLink=(kind:string,id:string)=>{const objects=kind==='task'?domainMock.tasks:kind==='solution'?domainMock.methods:domainMock.knowledge;return link('查看当前定义 →','domain',{domain:objects.find(o=>o.id===id)?.domainId||'DOM-MATH',filter:kind,id});};
const taskName=(s:MockLearningSpace,id:string)=>s.adopted.domain.tasks.find(t=>t.id===id)?.name||id;
function flatten(steps:AuditStep[]):AuditStep[]{return steps.flatMap(s=>[s,...flatten(s.children||[])]);}
function definitionLink(kind:string,id:string):ObservationLink{
  return kind==='教材'?link('查看当前教材 →','textbooks',{id}):kind==='学习目标'?link('查看当前目标 →','targets',{id}):kind==='Task Claim'?claimLink(id):domainLink(({Task:'task',Solution:'solution',KC:'kc'} as Record<string,string>)[kind]||kind,id);
}
export function dateMatches(at:string,range:string,since:string,until:string){
  if(!range||range==='all')return true;if(!at)return false;
  const day=at.slice(0,10);if(range==='custom')return (!since||day>=since)&&(!until||day<=until);
  const end=new Date(),start=new Date(end);start.setDate(start.getDate()-(range==='7days'?6:range==='30days'?29:0));
  const local=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  return day>=local(start)&&day<=local(end);
}
export function observationData(section:ObservationSection,scope:string){
  const contexts=learningSpaces.filter(s=>!scope||s.id===scope),ids=contexts.map(s=>s.id);
  const activities=auditActivities().filter(a=>ids.includes(a.space.id));
  const records:ObservationRecord[]=[],catalog:ObservationRecord[]=[];
  const totalRequirements=contexts.flatMap(s=>spaceRequirements(s).map(r=>({space:s,...r,status:assessmentFor(s,r.requirement.id).status})));
  const changed=contexts.flatMap(s=>adoptedDefinitions(s).filter(d=>d.changed).map(d=>({space:s,definition:d})));
  const add=(r:Parameters<typeof record>[0])=>records.push(record(r));
  for(const s of contexts){
    if(section==='Learning'){
      const requirements=spaceRequirements(s),chapters=spaceChapters(s);
      const unprepared=chapters.filter(ch=>!ch.mappings.length||!ch.checked);
      add({id:'course:'+s.id,kind:'课程采用',title:s.studentName+' · '+s.name,status:s.activities.length?'已有活动记录':'尚无活动记录',summary:`已选 ${chapters.length} 章，${unprepared.length} 章内容或映射待核对。没有活动不等于未掌握。`,current:true,scopeIds:[s.id],fields:[['教材与目标',`${s.adopted.book.name} · v${s.adopted.book.revision}\n${s.adopted.target.name} · v${s.adopted.target.revision}`],['所选章节',chapters.map(c=>c.name).join('、')],['课堂进度',s.classroom?s.classroom.chapterIds.map(id=>chapters.find(ch=>ch.id===id)?.name||id).join('、')+'；确认于 '+s.classroom.confirmedAt:'未确认'],['适用要求',requirements.map(r=>r.requirement.name).join('\n')],['最近活动',s.activities[0]?.at||'尚无记录']],links:[spaceLink(s,'course')],raw:{chapterIds:s.chapterIds,bookVersion:s.adopted.book.revision,targetVersion:s.adopted.target.revision}});
      for(const [i,h] of s.history.entries())add({id:'course-history:'+s.id+':'+i,kind:'课程采用记录',title:s.studentName+' · '+s.name,status:'已记录',summary:h.description,at:h.at,scopeIds:[s.id],source:'学习空间共用的采用历史',fields:[['操作人',h.actor],['变更记录',h.description]],links:[spaceLink(s)],raw:h});
      for(const ch of unprepared)add({id:'preparation:'+s.id+':'+ch.id,kind:'内容准备',title:ch.name,status:ch.mappings.length?'内容待核对':'映射待补',summary:ch.reviewNote||'该章节尚无 Task 与方法映射。不能据此评价学生。',current:true,attention:true,scopeIds:[s.id],source:'教材采用快照中的核对标记与映射记录',fields:[['内容核对',ch.checked?'已核对':'未确认'],['映射任务',ch.mappings.map(m=>taskName(s,m.taskId)).join('、')||'未映射'],['影响边界','只有依赖这些内容或定义的行为需要核对；不把准备缺口记为学生未掌握。']],links:[spaceLink(s,'course',{chapter:ch.id}),link('查看当前教材章节 →','textbooks',{id:s.adopted.book.id,chapter:ch.id,tab:'mapping'})],raw:ch});
    }
    if(section==='Learning'||section==='Evaluation')for(const c of spaceClaims(s)){
      const rows=spaceRequirements(s).filter(r=>r.selection.claimId===c.id);
      const issues=unique(rows.flatMap(r=>requirementIssues(s,r.requirement.id)));
      if(issues.length)add({id:'conditions:'+s.id+':'+c.id,kind:'定义条件',title:c.name+'：采用条件待核对',status:'配置待核对',summary:issues.join('；'),current:true,attention:true,scopeIds:[s.id],source:'已有课程映射与 Claim 引用检查；不是模型自动诊断',fields:[['Claim 方法条件',(c.methodMode==='any'?'任选一种：':'分别覆盖：')+c.methods.join('、')],['采用内容',issues.join('\n')],['涉及的学习要求',rows.map(r=>r.requirement.name).join('\n')],['与个人状态的区别','保留个人表现；配置差异不等于学生能力不足，也不自动裁剪 Claim。']],links:[spaceLink(s,'requirements',{claim:c.id}),claimLink(c.id),link('查看当前目标要求 →','targets',{id:s.adopted.target.id,claim:c.id})]});
    }
    if(section==='Evaluation')for(const c of spaceClaims(s)){
      const judgments=s.judgments.filter(j=>j.claimId===c.id);
      catalog.push(record({id:'state:'+s.id+':'+c.id,kind:'当前 Task Belief',title:c.name,summary:judgments.length?judgments.map(j=>aspect(j.aspectId)+'：'+j.judgment).join('；'):'尚无个人判断，不借用其他空间。',current:true,scopeIds:[s.id],source:'学习空间共用的分方面个人判断示例',fields:c.aspects.filter(a=>a.applicable).map(a=>{const j=judgments.find(j=>j.aspectId===a.id);return [a.name,j?j.judgment+'\n'+j.uncertainty+'\n依据：'+j.evidenceIds.join('、'):'尚未形成判断；'+a.evidence];}),links:[spaceLink(s,'requirements',{claim:c.id}),claimLink(c.id)],raw:judgments}));
    }
  }
  for(const row of activities){
    const {space:s,activity:a,audit}=row;if(!audit)continue;
    const trace=(round='',span='',tab='process')=>link('追溯活动步骤 →','activity',{id:a.id,round,span,tab});
    const c=audit.snapshot.claims.find(c=>c.id===audit.claimId)!;
    if(section==='Domain'){
      const snapshotSpace={...s,adopted:audit.snapshot},knowledge=courseKnowledge(snapshotSpace,audit.methodIds);
      add({id:'use:'+a.id,kind:'活动引用',title:taskName(snapshotSpace,audit.taskId),summary:a.name+'；记录引用方法 '+audit.methodIds.join('、'),status:'已记录引用',at:a.at,scopeIds:[s.id],fields:[['任务',audit.taskId+' · '+taskName(snapshotSpace,audit.taskId)],['采用方法',audit.methodIds.map(id=>audit.snapshot.domain.methods.find(m=>m.id===id)?.name||id).join('、')],['方法递归关联 KC',knowledge.rows.map(k=>k.name).join('、')],['边界','KC 只经方法依赖汇总；活动引用不证明学生掌握所有方法及其 KC。']],links:[trace('','','definitions'),domainLink('task',audit.taskId)],raw:{task:audit.snapshot.domain.tasks.find(t=>t.id===audit.taskId),methodIds:audit.methodIds}});
    }
    if(section==='Interaction'&&(audit.review==='question'||audit.reviewNotes.length>0))add({id:'review:'+a.id,kind:'人工复核',title:a.name,status:reviewNames[audit.review],summary:audit.reviewNotes[0]?.text||'已有人工标记，具体原因尚未记录。',at:audit.reviewNotes[0]?.at||a.at,attention:audit.review==='question',scopeIds:[s.id],source:'交互审查中已记录的人工复核意见',fields:[['执行状态',executionNames[audit.execution]],['审查情况',reviewNames[audit.review]],['复核记录',audit.reviewNotes.map(n=>n.at+' · '+n.text).join('\n')]],links:[trace('','','handling')]});
    for(const r of audit.rounds){
      const common={at:a.at,scopeIds:[s.id],source:'与交互审查共用的预写轮次；时间采用所属活动日期'};
      if(section==='Interaction'){
        add({...common,id:'context:'+a.id+':'+r.id,kind:'交互状态快照',title:r.name,status:executionNames[r.execution],summary:r.help,fields:[['快照位置',a.id+' / '+r.id+' · 本轮收束后的已记录上下文'],['触发',r.trigger],['本轮目标上下文',audit.snapshot.target.name+'；涉及 '+audit.requirementIds.join('、')],['实际帮助',r.help],['评价结果引用',r.evidenceIds.join('、')||'本轮没有 Evidence'],['持续活动状态','未记录活动是否仍在进行、检测是否开启或其他有效约束；不从“本轮处理完成”推断整个活动结束。']],links:[trace(r.id)]});
        if(r.observation)add({...common,id:'observation:'+r.observation.id,kind:'Observation',title:r.observation.id,status:'已提交',summary:r.observation.text,fields:[['观察内容',r.observation.text],['实际帮助',r.observation.support],['原始输入',a.messages[r.observation.messageIndex]?.text||'未记录']],links:[trace(r.id,r.id+'-commit')],raw:r.observation});
      }
      if(section==='Evaluation'){
        for(const e of a.evidence.filter(e=>r.evidenceIds.includes(e.id)))add({...common,id:'evidence:'+e.id,kind:'Evidence',title:c.name+' · '+aspect(e.aspectId),status:'已记录解释',summary:e.meaning,fields:[['Evidence',e.id],['Claim 版本',c.id+' · v'+c.version],['方面',aspect(e.aspectId)],['解释',e.meaning],['实际帮助',r.help],['来源 Observation',r.observation?.id||'未记录']],links:[trace(r.id,r.id+'-evidence'),claimLink(c.id)],raw:e});
        if(r.changes.length)add({...common,id:'belief:'+a.id+':'+r.id,kind:'Belief 更新',title:c.name,status:'分方面记录',summary:r.changes.filter(c=>c.before!==c.after).map(c=>aspect(c.aspect)+'：'+c.after).join('；')||'本轮保留原判断',fields:[['Claim',c.id+' · v'+c.version],...r.changes.map(c=>[aspect(c.aspect),c.before+' → '+c.after+'\n'+c.reason+'\n依据：'+(c.evidenceIds.join('、')||'未形成相应证据')] as [string,string])],links:[trace(r.id,r.id+'-belief'),spaceLink(s,'requirements',{claim:c.id})],raw:r.changes});
        if(r.results.length)add({...common,id:'assessment:'+a.id+':'+r.id,kind:'目标评价',title:audit.snapshot.target.name,status:'已记录比较',summary:r.results.map(result=>`${audit.snapshot.target.claims.flatMap(x=>x.requirements).find(x=>x.id===result.id)?.name||result.id}：${result.after}`).join('；'),fields:r.results.map(result=>[audit.snapshot.target.claims.flatMap(x=>x.requirements).find(x=>x.id===result.id)?.name||result.id,result.before+' → '+result.after+'\n'+result.reason]),links:[trace(r.id,r.id+'-assessment'),link('查看当前目标 →','targets',{id:audit.snapshot.target.id,claim:c.id})],raw:r.results});
      }
      for(const step of flatten(r.steps)){
        const kinds:Record<string,string>=section==='Reasoning'?{'observation.generate':'候选生成','observation.validate':'语义校验','observation.commit':'结果提交','llm.invoke':'模型调用'}:section==='Interaction'?{'policy.evaluate':'Policy 决策','action.execute':'Action 执行'}:{};
        const kind=kinds[step.type];if(!kind)continue;
        const failed=step.status==='failed';
        add({...common,id:'step:'+step.spanId,kind,title:step.label,status:failed?(step.type==='observation.validate'?'候选被拒绝':'步骤失败'):step.type==='observation.commit'?'已提交':'步骤完成',summary:(step.detail.checks?.filter(c=>!c.passed).map(c=>c.reason).join('；'))||step.detail.fields?.[0]?.value||step.detail.owner,attention:failed,source:failed?'预写步骤的明确拒绝记录；不是自动发现的新问题':common.source,fields:[['执行归属',step.detail.owner],['所属活动与轮次',a.id+' / '+r.id],['整轮执行状态',executionNames[r.execution]],['本步结果',step.label],...(step.detail.fields||[]).map(f=>[f.label,f.value] as [string,string]),...(step.detail.checks||[]).map(c=>[c.name,(c.passed?'通过：':'拒绝：')+c.reason] as [string,string]),...(step.detail.actions||[]).map(a=>[a.name,(a.selected?'已选择：':'未选择：')+a.reason] as [string,string])],links:[trace(r.id,step.spanId)],raw:step.detail});
      }
    }
  }
  // This authored follow-up gap is tied to the same performance and feedback, not inferred by a diagnostic engine.
  if(section==='Evaluation')for(const {space:s,activity:a,audit} of activities.filter(a=>a.activity.id==='SPACE-ACT-003')){
    if(!audit)continue;
    add({id:'gap:'+a.id,kind:'证据缺口',title:'讲解后的理解尚未再验证',status:'证据待补',summary:'独立计算已有支持，公式理由需加强；现有示例没有讲解后的新独立解释。',current:true,scopeIds:[s.id],attention:true,source:'预写待核对项；依据现有个人判断和该活动的先作答、后讲解顺序',fields:[['已知表现',s.judgments.filter(j=>j.claimId===audit.claimId).map(j=>aspect(j.aspectId)+'：'+j.judgment).join('\n')],['保留的未知','没有后续独立解释，不因已经讲解而确认理解改善。'],['状态边界','这是证据缺口，不是调用失败，也不自动触发测验。']],links:[link('查看评价依据 →','activity',{id:a.id,tab:'evaluation',round:'E-R1'}),spaceLink(s,'requirements',{claim:audit.claimId})]});
  }
  if(section==='Learning'||section==='Evolution')for(const {space:s,definition:d} of changed)add({id:'adoption:'+s.id+':'+d.id,kind:'采用差异',title:d.name,status:'当前定义已有变化',summary:s.studentName+' · '+s.name+' 仍保留原采用内容；未自动更新。',current:true,attention:true,scopeIds:[s.id],source:'当前目录与已保存采用快照的内容比较；不同不等于错误',fields:[['对象',d.kind+' · '+d.id],['空间采用',d.version],['目录当前',d.currentVersion],['影响边界','仅说明采用内容不同。是否需要更新、个人认识是否需要重新处理，尚未自动判定。']],links:[spaceLink(s),definitionLink(d.kind,d.id)],raw:{adopted:d.value,current:d.current??null}});
  if(section==='Evolution'){
    const sources=[...evaluationMock.claims.map(c=>({id:c.id,name:c.name,kind:'Task Claim',entries:c.history})),...textbookMock.books.map(b=>({id:b.id,name:b.name,kind:'教材',entries:b.history.map((h,i)=>({...h,version:b.revision-i}))})),...targetMock.targets.map(t=>({id:t.id,name:t.name,kind:'学习目标',entries:t.history.map((h,i)=>({...h,version:t.revision-i}))}))];
    for(const source of sources){const adopting=contexts.filter(s=>adoptedDefinitions(s).some(d=>d.id===source.id));if(scope&&!adopting.length)continue;
      for(const h of source.entries)add({id:'change:'+source.id+':'+h.version,kind:h.version===1?'定义建立':'定义修改',title:source.name+' · v'+h.version,status:'已保存记录',summary:h.change,at:h.at,scopeIds:adopting.map(s=>s.id),source:'对应管理页面共用的修改历史',fields:[['对象',source.kind+' · '+source.id],['修改说明',h.change],['记录版本','v'+h.version],['采用空间',adopting.map(s=>s.studentName+' · '+s.name).join('；')||'当前范围没有采用空间'],['记录边界','仅有版本和修改说明，未保存操作者及完整中间版本；不伪造历史差异。']],links:[definitionLink(source.kind,source.id)]});
    }
    for(const [kind,current,baseline] of [['Task',domainMock.tasks,initialDomain.tasks],['Solution',domainMock.methods,initialDomain.methods],['KC',domainMock.knowledge,initialDomain.knowledge]] as const)for(const obj of current){
      const previous=baseline.find(x=>x.id===obj.id);if(json(previous)===json(obj))continue;
      const adopting=contexts.filter(s=>adoptedDefinitions(s).some(d=>d.id===obj.id));if(scope&&!adopting.length)continue;
      add({id:'domain-change:'+obj.id,kind:'当前内容差异',title:obj.name,status:'修改时间未记录',summary:'与初始领域示例不同；领域编辑尚未保存逐次修改历史。',current:true,scopeIds:adopting.map(s=>s.id),fields:[['记录边界','展示当前内容与初始示例的差异，不编造修改时间、操作者或中间版本。']],links:[definitionLink(kind,obj.id)],raw:{initial:previous??null,current:obj}});
    }
  }
  if(section==='Domain'){
    const definitions=[...domainMock.tasks.map(t=>({id:t.id,name:t.name,kind:'Task',value:t,methods:t.methods})),...domainMock.methods.map(m=>({id:m.id,name:m.name,kind:'Solution',value:m,methods:[m.id]})),...domainMock.knowledge.map(k=>({id:k.id,name:k.name,kind:'KC',value:k,methods:[]}))];
    for(const d of definitions){const adopting=contexts.filter(s=>adoptedDefinitions(s).some(x=>x.id===d.id));if(scope&&!adopting.length)continue;
      const knowledge=d.kind!=='KC'?collectKnowledge(d.methods,d.value.domainId):null;
      if(d.kind==='Task'&&!d.methods.length)knowledge?.issues.push('任务尚未关联方法，无法汇总知识依据。');
      catalog.push(record({id:'definition:'+d.id,kind:d.kind,title:d.name,summary:`${adopting.length} 个空间引用；${knowledge?knowledge.rows.length+' 个经方法递归关联的 KC':'不维护个人 KC 状态'}`,current:true,scopeIds:adopting.map(s=>s.id),source:'当前领域目录；采用内容仍以各空间快照为准',fields:[['对象',d.kind+' · '+d.id],['采用空间',adopting.map(s=>s.studentName+' · '+s.name).join('；')||'暂无'],['方法依赖',knowledge?knowledge.rows.map(k=>k.knowledge.name+'（来自 '+k.sources.map(x=>x.methodId).join('、')+'）').join('\n'):'KC 不直接绑定 Task；从方法查看使用依据。'],['引用检查',knowledge?.issues.join('；')||'当前未记录依赖缺口']],links:[definitionLink(d.kind,d.id),...adopting.map(s=>spaceLink(s))],raw:d.value}));
      if(knowledge?.issues.length)add({id:'dependency:'+d.id,kind:'依赖引用',title:d.name,status:'引用待补',summary:knowledge.issues.join('；'),current:true,attention:true,scopeIds:adopting.map(s=>s.id),source:'既有领域引用检查',fields:[['依据',knowledge.issues.join('\n')]],links:[definitionLink(d.kind,d.id)]});
    }
  }
  if(section==='Learning'||section==='Evaluation')for(const s of contexts)for(const d of adoptedDefinitions(s).filter(d=>section==='Learning'?['教材','学习目标'].includes(d.kind):d.kind==='Task Claim'))catalog.push(record({id:'adopted:'+s.id+':'+d.id,kind:d.kind,title:d.name,status:d.changed?'当前目录有变化':'采用内容已记录',summary:s.studentName+' · '+s.name+' · '+d.version,current:true,scopeIds:[s.id],source:'空间已采用定义快照',fields:[['采用版本',d.version],['当前目录',d.currentVersion],['版本边界','此处查看空间已采用内容；管理页面显示当前定义，二者不会自动同步。']],links:[spaceLink(s,section==='Evaluation'?'requirements':'course',section==='Evaluation'?{claim:d.id}:{}),definitionLink(d.kind,d.id)],raw:d.value}));
  return {records,catalog,contexts,totalRequirements,activities,changed};
}
export function observationMetrics(section:ObservationSection,data:ReturnType<typeof observationData>,period:ObservationRecord[]):ObservationMetric[]{
  const n=(kind:string)=>period.filter(r=>r.kind===kind).length;
  const metric=(label:string,value:number|string,note:string)=>({label,value,note});
  if(section==='Domain')return [metric('期间任务引用',n('活动引用'),'按活动计数，不等于学生掌握'),metric('涉及 Task',unique(period.filter(r=>r.kind==='活动引用').map(r=>r.links.find(l=>l.page==='domain')?.values.id)).length,'所选时间内按 Task 去重'),metric('当前采用空间',data.contexts.filter(s=>adoptedDefinitions(s).some(d=>d.kind==='Task')).length,'当前范围内，非期间新增'),metric('当前依赖待补',data.records.filter(r=>r.kind==='依赖引用').length,'引用检查，不诊断教学效果')];
  if(section==='Learning')return [metric('当前学习空间',data.contexts.length,'保持个人记录隔离'),metric('内容准备项',data.records.filter(r=>r.kind==='内容准备').length,'按空间与章节计数'),metric('条件待核对',data.records.filter(r=>r.kind==='定义条件').length,'按空间与 Claim 计数'),metric('采用内容有变化',data.changed.length,'不同不等于必须更新')];
  if(section==='Evaluation')return [metric('期间 Evidence',n('Evidence'),'同源表现不重复当作独立样本'),metric('期间 Belief 更新',n('Belief 更新'),'每轮 Claim 更新记录，不是能力项数'),metric('当前待确认要求',data.totalRequirements.filter(r=>r.status==='待确认').length,'按空间与要求计数，不等于不会'),metric('当前需加强要求',data.totalRequirements.filter(r=>r.status==='需加强').length,'来自已记录的目标比较')];
  if(section==='Interaction')return [metric('期间轮次快照',n('交互状态快照'),'不是当前在线或进行中的活动数'),metric('期间决策',n('Policy 决策'),'选定动作不等于已经展示'),metric('期间实际行动',n('Action 执行'),'以已记录执行结果为准'),metric('人工标记疑点',period.filter(r=>r.kind==='人工复核'&&r.attention).length,'复核时间落在所选期间')];
  if(section==='Reasoning')return [metric('示例候选生成',n('候选生成'),'包含重试；不是正式日志'),metric('示例校验拒绝',period.filter(r=>r.kind==='语义校验'&&r.status==='候选被拒绝').length,'拒绝一次候选不等于整轮失败'),metric('示例结果提交',n('结果提交'),'提交不证明语义一定正确'),metric('示例模型调用',n('模型调用'),'未实际调用，不用于性能评价')];
  return [metric('期间定义修改',n('定义修改'),'当前管理页保存的修改记录'),metric('期间定义建立',n('定义建立'),'初始示例或本次临时新建'),metric('当前采用差异',data.changed.length,'按空间与定义计数'),metric('修改时间未记录',n('当前内容差异'),'仅显示当前内容差异，不纳入期间次数')];
}
