import { domainMock, blankDomainTask } from './domain-mock';
import { evaluationMock, blankClaim } from './evaluation-mock';

// A finite model candidate for the actual two-stage proportion example, not OCR inference.
export function ensureTextbookModel(){
  if(domainMock.tasks.some(t=>t.id==='fraction-chain'))return;
  domainMock.knowledge.push({id:'K-FRACTION-ASSOC',domainId:'DOM-MATH',name:'分数连乘与结合律',description:'连续求部分量可以依次计算，也可以先合并相乘的比例。',prerequisites:['K-PART']});
  domainMock.methods.push(
    {id:'S-CHAIN-A',domainId:'DOM-MATH',name:'逐层求部分量',description:'先求中间数量，再求其对应部分。',conditions:'两层比例的参照量明确。',inputs:[['初始量','q'],['两层比例','r、s']],output:'最终部分量 qrs',kc:['K-REF'],steps:[{title:'第一层部分量',detail:'用 q 和 r 求中间量。',decomposed:true,solutionId:'S0'},{title:'第二层部分量',detail:'用中间量和 s 求最终量。',decomposed:true,solutionId:'S0'}]},
    {id:'S-CHAIN-B',domainId:'DOM-MATH',name:'先合并比例再求部分量',description:'将两层比例相乘，得到相对初始量的比例。',conditions:'两层比例对应同一条包含关系。',inputs:[['初始量','q'],['两层比例','r、s']],output:'最终部分量 qrs',kc:['K-REF','K-FRACTION-ASSOC'],steps:[{title:'合并比例',detail:'最终量相对于初始量的比例为 r × s。'},{title:'求最终部分量',detail:'使用合并后的比例。',decomposed:true,solutionId:'S0'}]},
  );
  const task=blankDomainTask('DOM-MATH');Object.assign(task,{id:'fraction-chain',label:'连续比例',name:'连续求一个量的几分之几',summary:'初始量与两层部分关系已知，求最终部分量。',goal:'求最终量 q × r × s',responsibility:'区分两层参照量，组织数量关系并完成计算。',output:'最终数量、单位与推理过程。',parameters:[{symbol:'q',name:'初始量',type:'数量',role:'已知量',condition:'正数'},{symbol:'r、s',name:'两层比例',type:'比例',role:'已知量',condition:'0 < r、s ≤ 1'}],relations:[{meaning:'最终部分占中间量的 s，中间量占初始量的 r',expression:'m = q × r; t = m × s',given:'通过情境给出两层参照关系。'}],variations:'数量、合法比例、情境与图文表征。',exclusions:'不含按比例增加或求剩余量；不能将两层比例相加。',methods:['S-CHAIN-A','S-CHAIN-B'],availableMethods:['S-CHAIN-A','S-CHAIN-B'],question:'求两层比例关系下的最终人数。',answer:'3 人',working:['12 × 1/3 × 3/4 = 3'],checks:['两层参照量清楚'],cases:[]});domainMock.tasks.push(task);
  const claim=blankClaim();Object.assign(claim,{id:'CLAIM-CHAIN',domainId:'DOM-MATH',taskId:task.id,name:'连续比例关系求解',description:'针对两层部分关系，分别考察四个方面；以下标准为本轮交互候选。',scope:task.summary,responsibility:task.responsibility,conditions:'题目图文完整，记录已展示的提示和解法。',quality:task.output,methods:[...task.methods],methodMode:'any',methodNote:'允许采用一种方法，不由一种方法成功推断全部方法。',support:'题目只展示条件与问题；提示、图示推理和解法另行记录。',updatedAt:new Date().toLocaleString('sv-SE'),history:[{version:1,at:new Date().toLocaleString('sv-SE'),change:'真实教材整理所用的 mock 评价候选'}]});
  const criteria=['自行区分两层参照量，计算最终数量。','解释两步计算的含义，或说明为什么可以先合并比例。','在未见过的图文情境中识别相同的两层比例关系；仅改数字不算迁移。','在约定的延迟后再次完成同类任务，并记录期间的练习和帮助。'];
  claim.aspects.forEach((a,i)=>{a.criterion=criteria[i]!;a.evidence='保留原题、学生过程、实际帮助与接触历史。';});
  claim.inference={...evaluationMock.claims[0]!.inference};evaluationMock.claims.push(claim);
}
