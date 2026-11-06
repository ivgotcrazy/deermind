import { domainData, id } from './domain';
import { addDomainExample } from './domain-example';
import { imports, newImport, loadSample, finishRecognition } from './imports';
import { initializeFlow, chapters } from './material-flow';
import { blankClaim, blankTarget, blankRequirement, requirementBasis, defaultAspectRule, evaluationData, saveDefinition, type Claim, type Criterion } from './evaluation';

function entry(id:string,name:string,input:string,basis:string,met:string,counter:string,insufficient:string,examples=''):Criterion {
  return {id,name,input,basis,met,counter,insufficient,examples};
}
function configureMethod(c:Claim,methodId:string,criteria:string[],explanation:string){
  c.executions.push({methodId,criteria});
  for(const aspect of c.aspects){
    const rule=defaultAspectRule(methodId,aspect.id);
    if(aspect.id==='explanation')rule.judgment=explanation;
    c.rules.push(rule);
  }
}
// Explicit opt-in. A separate sample leaves previously opened or edited examples intact.
export function loadEvaluationExample(){
  const exampleId='TARGET-M1-QUARTER-SEPARATE';
  const existing=evaluationData.targets.find(t=>t.id===exampleId);
  if(existing)return existing;
  const domainId=addDomainExample();
  domainData.domains.find(d=>d.id===domainId)!.name='小学数学 · 方法判据样例';
  const task=domainData.tasks.find(t=>t.domainId===domainId&&t.parameters.some(p=>p.symbol==='W'))!;
  const [first,second]=task.methods;
  const step=domainData.methods.find(m=>m.id===first)!.steps.find(s=>s.divided)!;
  const child=blankClaim(domainId,step.taskId);
  child.name='求一个量的几分之几';
  child.criteria=[
    entry('P1','计算对应部分','基准量、分率和乘法过程','子任务要求 Δ = V × r','选对基准量并求出对应部分及单位。','把新量或其他数量当作基准量。','只给出最终新量，看不到这一步所求的部分。','80 × 1/4 = 20 本。'),

  ];
  configureMethod(child,step.solutionId,['P1'],'能指出对应的整体，并解释为什么基准量乘分率得到对应的部分。');
  saveDefinition(evaluationData.claims,child,'载入子任务的乘法判据');
  const c=blankClaim(domainId,task.id);
  c.name='比例增加任务的理解与求解';
  c.criteria=[
    entry('F1','新量与单位正确','作答结果、单位和实例参考','Task 的新量与单位要求','结果满足原量、增加比例与新量的关系。','把增加量作为最终的新量。','仅浏览题目或没有最终数量。','80 本增加四分之一，新量为 100 本。'),

    entry('FA','把子方法的增加量用于求新量','子方法输出和父层算式','先求增加量，再加原量','把返回的增加量与原量相加，求得新量。','求出增加量后直接作为最终结果。','没有可识别的本层处理过程。','子方法返回 20，本层计算 80 + 20 = 100。'),
    entry('FB1','按新量倍数计算','倍数与运算过程','W = V × (1 + r)','自行确定新量倍数并乘原量。','只乘增加比例便作为新量。','只有最终数值，看不出方法。'),

  ];
  configureMethod(c,first,['F1','FA'],'能指出增加分率以原量为整体，并解释为什么要把增加量加回原量。');
  configureMethod(c,second,['F1','FB1'],'能解释 1 代表原量整体，r 代表增加分率，所以新量是原量的 1＋r 倍。');
  const claim=saveDefinition(evaluationData.claims,c,'载入比例增加任务的方法与判据')!;
  const importId=newImport(),d=imports.find(x=>x.id===importId)!;
  d.book.domainId=domainId;loadSample(d);finishRecognition(d);
  d.book.name='分数的应用 · 目标配置样例（mock）';
  d.book.sourceNote+=' 本副本用于自编比例增加目标走查；关联和目标不是自动提取或全章覆盖结论。';
  const flow=initializeFlow(d),chapter=chapters(flow)[0];
  flow.links[chapter]=[{taskId:task.id,methodIds:[...task.methods]}];
  const t=blankTarget();Object.assign(t,{id:exampleId,name:'增加四分之一：理解、求解与后续检查',bookId:d.book.id,chapters:[chapter]});
  const r=blankRequirement();Object.assign(r,{id:id('REQ'),claimId:claim.id,claimVersion:claim.version,name:'能自己算出增加四分之一后的数量，并说明为什么',chapters:[chapter],scope:'只取 r=1/4；原量为正，单位一致，离散数量满足整量条件。不代表任意增加比例或整章达标。',methods:[...task.methods],checked:true});
  r.standards=[
    {aspectId:'independent',text:'2 道不同的新题，无当题实质帮助，均正确求解。订正、重试和同题重复不计为第二道新题。'},
    {aspectId:'explanation',text:'上述 2 道题均能解释四分之一的参照整体，以及原量、增加量、新量的关系；只答对数值不足。'},
    {aspectId:'transfer',text:'上述 2 道题中至少 1 道使用此前未练过的表格呈现，能够正确理解并求解、解释；记录此前学习表征。'},
    {aspectId:'retention',text:'独立完成与解释达标所用的最近一次合格表现至少 7×24 小时后，用 1 道未见解法的新题检查求解和解释。记录期间正常学习与帮助；未知背景不能宣称无强化保持。'},
  ];r.criteriaBasis=requirementBasis(claim,r);t.requirements=[r];
  return saveDefinition(evaluationData.targets,t,'载入已确认的四分之一试用标准')!;
}
