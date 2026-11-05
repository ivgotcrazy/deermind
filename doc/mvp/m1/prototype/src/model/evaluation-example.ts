import { domainData, id } from './domain';
import { addDomainExample } from './domain-example';
import { imports, newImport, loadSample, finishRecognition } from './imports';
import { initializeFlow, chapters } from './material-flow';
import { blankClaim, blankTarget, blankRequirement, evaluationData, saveDefinition } from './evaluation';

// Opt-in fixture: never replaces existing domains, textbook drafts, Claims or targets.
export function loadEvaluationExample(){
  const existing=evaluationData.targets.find(t=>t.id==='TARGET-M1-QUARTER-DEMO');
  if(existing)return existing;
  const domainId=addDomainExample();
  domainData.domains.find(d=>d.id===domainId)!.name='小学数学 · 评价与目标样例';
  const task=domainData.tasks.find(t=>t.domainId===domainId&&t.parameters.some(p=>p.symbol==='W'))!;
  const c=blankClaim(domainId,task.id);
  Object.assign(c,{name:'比例增加任务的理解与求解',scope:'已知原量 V 和以原量为基准的增加比例 r，求新量并说明关系。限单次增加，含文字和表格；不含反求原量、连续增减。',methods:[...task.methods],support:'独立表现不得获得当题定位、列式、解法或答案帮助；受助练习保留记录但不能充作独立证据。按实际工具和帮助记录解释。'});
  const definitions=[
    ['自行识别原量与增加比例，选取允许的方法，正确求出新量及单位。','只有受助成功、只浏览讲解或尚未作答，不能确认独立完成。','无当题帮助时仍把增加量作为新量，或使用错误的参照整体。'],
    ['说明分率以原量为整体，解释新量为何等于原量与增加量之和；可用文字、算式或图示表达。','只有正确数值，没有可解释的理由，不足以确认理解。','明确把 1 解释成一个实物，而非原量整体，或给出与题意冲突的关系。'],
    ['在已记录的学习背景下，处理未练过但在任务范围内的表征变化，保持正确的数量关系与解释。','仅换数字或沿用已练过的同一表征，不构成所要求的迁移证据。','改变表征后误读原量或比例关系；不能推广为所有迁移能力不足。'],
    ['在先前已能独立求解并解释之后，经过目标约定的间隔，仍能在可比的新题上求解并解释；记录期间练习与帮助。','尚未到检测时间、没有后测或期间背景未知，不能宣称已保持或自然遗忘。','满足约定延迟与可比条件后仍出现相应求解或解释错误，需要保留反证。'],
  ];
  c.aspects.forEach((a,i)=>Object.assign(a,{criterion:definitions[i][0],insufficient:definitions[i][1],counter:definitions[i][2]}));
  const claim=saveDefinition(evaluationData.claims,c,'载入比例增加 Claim 样例')!;
  const importId=newImport(),d=imports.find(x=>x.id===importId)!;
  d.book.domainId=domainId;loadSample(d);finishRecognition(d);
  d.book.name='分数的应用 · 目标配置样例（mock）';
  d.book.sourceNote+=' 本副本用于自编比例增加目标走查；关联和目标不是自动提取或全章覆盖结论。';
  const flow=initializeFlow(d),chapter=chapters(flow)[0];
  flow.links[chapter]=[{taskId:task.id,methodIds:[...task.methods]}];
  const t=blankTarget();Object.assign(t,{id:'TARGET-M1-QUARTER-DEMO',name:'增加四分之一：理解、求解与后续检查',bookId:d.book.id,chapters:[chapter]});
  const r=blankRequirement();Object.assign(r,{id:id('REQ'),claimId:claim.id,claimVersion:claim.version,name:'能自己算出增加四分之一后的数量，并说明为什么',chapters:[chapter],scope:'只取 r=1/4；原量为正，单位一致，离散数量满足整量条件。不代表任意增加比例或整章达标。',methods:[...task.methods],checked:true});
  r.standards=[
    {aspectId:'independent',text:'2 道不同的新题，无当题实质帮助，均正确求解。订正、重试和同题重复不计为第二道新题。'},
    {aspectId:'explanation',text:'上述 2 道题均能解释四分之一的参照整体，以及原量、增加量、新量的关系；只答对数值不足。'},
    {aspectId:'transfer',text:'上述 2 道题中至少 1 道使用此前未练过的表格呈现，能够正确理解并求解、解释；记录此前学习表征。'},
    {aspectId:'retention',text:'独立完成与解释达标所用的最近一次合格表现至少 7×24 小时后，用 1 道未见解法的新题检查求解和解释。记录期间正常学习与帮助；未知背景不能宣称无强化保持。'},
  ];t.requirements=[r];
  return saveDefinition(evaluationData.targets,t,'载入已确认的四分之一试用标准')!;
}
