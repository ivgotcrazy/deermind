import { domainData, blankTask, blankMethod, blankKnowledge, blankInstance, id, instanceSignature } from './domain';
import { blankClaim, defaultAspectRule, evaluationData } from './evaluation';

export function loadDvtExample(){
  const old=domainData.domains.find(d=>d.exampleKey==='dvt-v1');if(old)return old.id;
  const domainId=id('DOM');
  domainData.domains.push({id:domainId,name:'小学数学 · 理解 d=v×t',scope:'速度、时间与路程的关系',description:'独立的新模型 mock，不覆盖既有领域和教材。',version:1,exampleKey:'dvt-v1'});
  const kc=[
    ['路程','沿运动路径经过的长度。','明确路径及长度单位。'],
    ['时间','运动经历的时长。','区分时刻和时长，统一单位。'],
    ['速度','单位时间通过的路程。','区分恒定速度与平均速度。'],
    ['乘法的意义','同样大小的量按次数累加，可以用乘法表示。','对应相同单位量和次数。'],
    ['乘除互逆','商乘非零除数等于被除数。','作为除数的量不为零。'],
    ['匀速路程关系','速度恒定时，路程等于速度乘经过时间。','速度恒定且单位相容；除以 t 的推导要求 t>0。'],
  ].map(([name,description,conditions])=>({...blankKnowledge(domainId),name,description,conditions,version:1}));
  domainData.knowledge.push(...kc);
  const foundations=kc.slice(0,5).map(k=>{
    const t={...blankTask(domainId),version:1,name:'理解'+k.name,summary:k.description,goal:'解释'+k.name,responsibility:'解释含义，判断适用与不适用的例子并说明理由。',relations:k.conditions,exclusions:'不以记住词语或只报数值代替理解。',requirements:[{deliverable:'解释与正反例判断',criterion:'含义、理由及适用条件正确。'}]};
    const m={...blankMethod(domainId),version:1,name:'用情境对照解释'+k.name,description:'对照定义和条件说明例子是否成立。',conditions:k.conditions,procedure:'指出对应量；解释其含义；比较一个正例与一个反例并说明理由。',kc:[k.id]};
    t.methods=[m.id];domainData.methods.push(m);domainData.tasks.push(t);return t;
  });
  const a={...blankMethod(domainId),version:1,name:'按单位时间累积解释',description:'每单位时间通过 v 的路程，经过 t 个时间单位，累积为 v×t。',conditions:'速度恒定，速度与时长的时间单位一致。',procedure:'解释速度中的“每单位时间”；用等长时间段或分数时间段说明累积；写出 d=v×t；核对单位及恒速条件。',kc:[0,1,2,3,5].map(i=>kc[i].id)};
  const b={...blankMethod(domainId),version:1,name:'从速度定义变形解释',description:'由 v=d/t，两边乘 t 得到 d=v×t，说明乘除互逆。',conditions:'t>0 且速度恒定；若使用平均速度，须明确是整个所问时段的平均值。',procedure:'解释 v=d/t；说明 t>0；两边乘 t；核对各量单位。t=0 单独说明 d=0，不做除法。',kc:[0,1,2,4,5].map(i=>kc[i].id)};
  domainData.methods.push(a,b);
  const task={...blankTask(domainId),version:1,name:'理解 d=v×t',summary:'解释关系、依据和成立条件，不只是代入计算。',goal:'理解匀速运动的路程关系',responsibility:'解释量、相乘理由和单位，判断关系何时适用。',relations:'速度恒定，单位相容；d、v、t 表示路程、速度及经过时间。',exclusions:'不把变速运动某时刻的速度当作全程速度；只报答案不算解释。',requirements:[{deliverable:'关系解释与条件判断',criterion:'解释乘积意义或变形依据、单位及恒速条件，指出变速反例。'}],methods:[a.id,b.id],prerequisites:foundations.map((t,i)=>({taskId:t.id,reason:'为关系解释提供'+kc[i].name+'的基础。',methodIds:i===3?[a.id]:i===4?[b.id]:[]}))};
  domainData.tasks.push(task);
  const q={...blankInstance(task),version:1,question:'汽车以60千米/时匀速行驶3小时。请解释 d=60×3 的含义与依据；如果途中速度变化，使用这个式子需要什么条件？',answer:'180千米；60为每小时路程，3为小时数；变速时60须明确为整个时段的平均速度。',sourceNote:'自编 mock，非教材原题。',solutions:[a,b].map((m,i)=>({id:id('REF'),taskInstanceId:'',methodId:m.id,origin:'系统生成' as const,sourceNote:'预写 mock，未调用 LLM。',working:i?'v=d/t，t=3>0，因此 d=v×t=180。变速时须明确平均速度。':'每小时60千米，3小时累积60+60+60=180千米。需恒速或明确全程平均速度。'}))};
  q.solutions.forEach(s=>s.taskInstanceId=q.id);q.checkedSignature=instanceSignature(q);q.checkedAt=new Date().toISOString();domainData.instances.push(q);
  const c=blankClaim(domainId,task.id);c.name=task.name;c.version=1;
  c.criteria=[{id:id('CR'),name:'解释关系与条件',input:'题面、原始解释及帮助记录',basis:'当前 Task 的责任与实际方法',met:'解释各量、单位及方法依据，并指出适用条件。',counter:'只报180或以变速中的瞬时速度代替全程速度。',insufficient:'没有解释或方法无法辨认。',examples:'只算出180不能证明理解。'}];
  for(const m of [a,b]){c.executions.push({methodId:m.id,criteria:[c.criteria[0].id]});for(const aspect of c.aspects){const r=defaultAspectRule(m.id,aspect.id);if(aspect.id==='explanation')r.judgment='解释所用方法的依据，并说明恒速、单位及非零时长条件。';c.rules.push(r);}}
  evaluationData.claims.push(c);return domainId;
}
