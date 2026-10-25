import { reactive } from 'vue';
import { domainMock } from './domain-mock';

// Editable interaction fixtures, not learner states or an evaluation engine.
export interface ClaimAspect { id:string; name:string; applicable:boolean; criterion:string; evidence:string; reason:string; custom?:boolean }
export interface ClaimRule { id:string; aspectId:string; observation:string; effect:'support'|'counter'|'neutral'; condition:string; meaning:string }
export interface EvaluationClaim {
  id:string; domainId:string; taskId:string; name:string; description:string;
  scope:string; responsibility:string; conditions:string; quality:string;
  methods:string[]; methodMode:'any'|'all'; methodNote:string; support:string;
  aspects:ClaimAspect[]; rules:ClaimRule[];
  inference:{aggregation:string; conflict:string; missing:string; time:string; output:string};
  version:number; updatedAt:string; history:{version:number;at:string;change:string}[];
}
export const defaultAspectNames={independent:'独立完成',understanding:'理解与解释',transfer:'迁移',retention:'延迟保持'};
export const effectNames={support:'支持',counter:'反证',neutral:'不具诊断性'};
export const inferenceFields={aggregation:'证据如何综合',conflict:'相互矛盾的证据',missing:'证据不足或条件不明',time:'时间与再次练习',output:'输出的能力认识'};
export function blankClaim():EvaluationClaim {
  return {id:'CLAIM-'+crypto.randomUUID().slice(0,8).toUpperCase(),domainId:'',taskId:'',name:'',description:'',scope:'',responsibility:'',conditions:'',quality:'',methods:[],methodMode:'any',methodNote:'',support:'',aspects:Object.entries(defaultAspectNames).map(([id,name])=>({id,name,applicable:true,criterion:'',evidence:'',reason:''})),rules:[],inference:{aggregation:'',conflict:'',missing:'',time:'',output:''},version:1,updatedAt:'',history:[]};
}
const inference:EvaluationClaim['inference']={
  aggregation:'按 Claim 的各个方面分别综合适用证据，保留实际方法、帮助和共同来源。同一次作答支持多个方面时，不把它计作多个独立样本。',
  conflict:'保留相反表现及其条件，比较题目变化、方法与帮助是否可比。存在尚不能解释的冲突时降低确定性，不用一次成功覆盖先前失败。',
  missing:'未检测、条件不明或只有受助表现时，相关方面保持证据不足；不从其他方面的成功补齐，也不自动记为能力不足。',
  time:'延迟保持只使用满足所设间隔、且练习与帮助记录清楚的表现。记录期间再次学习；单纯经过时间既不是支持证据，也不自动构成失败。',
  output:'形成同一 Claim 下各方面的判断、条件、不确定性和证据来源。单次成功只形成局部支持，不计算四维平均掌握率，不生成 KC 掌握状态。',
};
function example(taskId:string,id:string,name:string,criteria:string[],evidence:string[],explanation:string):EvaluationClaim {
  const task=domainMock.tasks.find(t=>t.id===taskId)!;
  const claim=blankClaim();
  Object.assign(claim,{id,domainId:task.domainId,taskId,name,description:explanation,scope:'在关联任务模板规定的参数、表征及适用边界内评价。',responsibility:task.responsibility,conditions:'题意、必要条件和单位可辨认；实际方法、已获帮助及此前接触情况有记录。',quality:task.output+' 计算与数量关系均正确，不能仅根据最终答案推断过程。',methods:[...task.methods],methodMode:'any',methodNote:'保留学生实际采用的方法与过程。一次采用某方法成功，不证明其他方法或它们专属的 KC 已掌握。',support:'允许读题、重述词义；不替学生确定关键关系、选择方法或给出中间结果。',inference:{...inference},updatedAt:'2026-10-24 09:00',history:[{version:1,at:'2026-10-24 09:00',change:'初始交互示例'}]});
  claim.aspects.forEach((a,i)=>{a.criterion=criteria[i]!;a.evidence=evidence[i]!;});
  claim.rules=[
    {id:id+'-E1',aspectId:'independent',observation:'作答与解题过程',effect:'support',condition:'未获实质提示；承担该任务所需工作，过程可核对且结果正确。',meaning:'为本次任务的独立完成提供支持；不能由一次表现确认稳定掌握。'},
    {id:id+'-E2',aspectId:'independent',observation:'求助后的作答',effect:'neutral',condition:'关键关系、方法或中间结果已被提示，随后作答正确。',meaning:'记录受助完成；本次结果不能直接证明独立完成，也不能仅因求助形成反证。'},
    {id:id+'-E3',aspectId:'independent',observation:'独立作答中的错误',effect:'counter',condition:'题意与输入已核对，且过程明确显示关键关系判断错误；排除识别争议。',meaning:'对相应独立完成要求形成局部反证；不推断其他方面全部失败。'},
    {id:id+'-E4',aspectId:'understanding',observation:'解释或辨析',effect:'support',condition:'满足本 Claim 的理解与解释标准；学生给出自己的理由，没有直接复述刚展示的解释。',meaning:'支持理解与解释方面；保留学生原话及实际帮助。'},
    {id:id+'-E5',aspectId:'transfer',observation:'变化条件下的作答',effect:'support',condition:'满足本 Claim 的迁移标准；实际变化在任务范围内，未见过当前变式且无关键关系提示。',meaning:'只支持本次明确变化范围内的迁移，不外推到任意新情境。'},
    {id:id+'-E6',aspectId:'retention',observation:'延迟后的再次作答',effect:'support',condition:'满足本 Claim 的延迟保持标准；约定间隔已到，期间练习、帮助及本次作答可核对。',meaning:'为该间隔和期间练习条件下的保持提供支持，不声称永久掌握。'},
  ];
  return claim;
}
export const evaluationMock=reactive({claims:[
  example('fraction','CLAIM-FRACTION','增加后的数量求解','自行识别增加比例的参照量，建立关系并求出最终数量。|用自己的话说明为什么要把增加量加回原量，或解释 1+r 的含义。|从已学的水量文字题转到未见过的长度示意图，在无关系提示时仍能建模；不是只更换数字。|本示例暂以间隔 7 天再次独立完成同类任务为条件，记录期间练习和帮助；间隔是可修改的演示值。'.split('|'),[
    '保留完整列式、结果、单位及帮助发生顺序。','记录学生自己的解释；仅说“按公式算”不足以确认。','记录已见题目、变化之处和本次过程，确认变化在任务范围内。','记录两次时间、期间学习情况和再次作答过程。',
  ],'评价学生处理一次按比例增加任务的能力；四个方面分别取证。'),
  example('geometry','CLAIM-GEOMETRY','三角形面积求解','自行识别底与对应高，选择面积关系并正确计算。|说明为什么使用对应高、为什么面积要除以二，并辨别斜边不能直接当作高。|面对未见过的旋转图形或外部高，仍能识别正确的底高配对并求面积。|在约定延迟后重新识别底高并计算；本示例暂设 7 天，记录期间练习和提示。'.split('|'),[
    '记录底高选择、算式、面积单位及是否给过公式提示。','保留解释、图示或错误方法辨析；答案正确不替代解释。','保留原图和新图的变化、先前接触情况与本次选择过程。','保留间隔、再次学习情况与延迟作答。',
  ],'评价面积计算及对底高关系的理解，不包含先推导未知高度的任务。'),
  example('composite','CLAIM-COMPOSITE','扩建后剩余面积求解','自行组织尺寸变化、面积计算及剩余区域关系，完成整个任务。|解释每个中间量的意义，以及为何采用整体相减或区域分割。|在合法尺寸及角落位置变化后，重新组织步骤求解；不能只重复记忆的数值步骤。|间隔后仍能自主组织完整解法；本示例暂设 7 天，并记录期间是否练习了同一题。'.split('|'),[
    '记录方法选择、中间量、单位和完整步骤；单独算对子步骤不代表完成整体。','保留步骤依赖与区域关系的解释，不仅检查最终面积。','记录图形变化、方法适用条件及学生实际组织过程。','保留间隔与题目接触记录，区分记住原题和再次完成任务。',
  ],'评价递归综合任务的组织与求解；不自动把子任务或 KC 状态设为已掌握。'),
]});
export function saveClaim(value:EvaluationClaim,change:string){
  const current=evaluationMock.claims.find(c=>c.id===value.id);
  const next=JSON.parse(JSON.stringify(value)) as EvaluationClaim;
  next.version=current?current.version+1:1;
  next.updatedAt=new Date().toLocaleString('sv-SE',{hour12:false});
  next.history=[{version:next.version,at:next.updatedAt,change},...(current?.history||[])];
  if(current)Object.assign(current,next);else evaluationMock.claims.unshift(next);
}
