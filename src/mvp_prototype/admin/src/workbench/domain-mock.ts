import { reactive } from 'vue';
import { mockTasks, mockMethods, mockKnowledge, type MockTask, type MockMethod } from './task-editor-mock';

export type DomainKind = 'task' | 'solution' | 'kc';
export interface DomainTask extends MockTask { domainId:string }
export interface DomainMethod extends Omit<MockMethod,'steps'> { domainId:string; conditions:string; steps:{title:string;detail:string;decomposed?:boolean;solutionId?:string}[] }
export interface DomainKnowledge { id:string; domainId:string; name:string; description:string; prerequisites:string[] }
export const domainKinds={task:{name:'任务模板',english:'TaskTemplate'},solution:{name:'方法模板',english:'SolutionTemplate'},kc:{name:'知识成分',english:'KnowledgeComponent'}};
export const domainTaskTabs=reactive<Record<string,string>>({});
export const domainMock=reactive({
  domains:[{id:'DOM-MATH',name:'数学',scope:'数量关系、几何与综合应用',description:'用任务、方法和知识成分共同描述数学领域。'}],
  tasks:JSON.parse(JSON.stringify(mockTasks)).map((t:MockTask)=>({...t,methods:[...t.availableMethods],domainId:'DOM-MATH'})) as DomainTask[],
  methods:JSON.parse(JSON.stringify(mockMethods)).map((m:MockMethod)=>({...m,conditions:'在关联任务规定的条件内使用。',steps:m.steps.map(({title,detail})=>({title,detail,solutionId:''})),domainId:'DOM-MATH'})) as DomainMethod[],
  knowledge:mockKnowledge.map(k=>({...k,domainId:'DOM-MATH',prerequisites:[] as string[]})) as DomainKnowledge[],
});
domainMock.tasks.push({id:'part',domainId:'DOM-MATH',label:'分数基础',name:'求一个量的几分之几',summary:'已知基准量和比例，求这个比例对应的数量。',goal:'求比例对应的数量 Δ',responsibility:'识别基准量\n理解比例对应的数量\n使用分数乘法计算',output:'给出对应数量及单位。',parameters:[{symbol:'q',name:'基准量',type:'数量',role:'已知量',condition:'q > 0'},{symbol:'r',name:'比例',type:'比例',role:'已知量',condition:'正有理数，无量纲'},{symbol:'Δ',name:'比例对应的数量',type:'数量',role:'最终输出',condition:'与 q 同类型、同单位'}],relations:[{meaning:'对应数量与基准量的比例为 r',expression:'Δ / q = r',given:'说明基准量及所求的比例，不直接给出乘法式。'}],variations:'合法数值、数量类型及情境。',exclusions:'不把对应数量误当成增加后的总量。',methods:['S0'],availableMethods:['S0'],question:'水箱中有80升水，用去其中的四分之一。用去了多少升？',answer:'20 升',working:['用去的水量：80 × 1/4 = 20（升）'],checks:['所求为比例对应的部分，不是剩余水量。'],cases:[{label:'符合模板',text:'一根绳子长12米，剪下全长的三分之一。剪下多少米？',verdict:'符合模板',bindings:[['q','12 米'],['r','1/3'],['Δ','剪下的长度']],reasons:['基准量与比例均已知，求对应部分。']},{label:'不符合模板',text:'一根绳子长12米，剪下三分之一后还剩多少米？',verdict:'仅对应局部计算',bindings:[['所求','剩余长度']],reasons:['求出剪下部分只是其中一步，不能代替整个任务。']}]});
domainMock.methods.push({id:'S0',conditions:'基准量与比例已知，所求为对应部分的数量。',domainId:'DOM-MATH',name:'使用分数乘法求对应数量',description:'将基准量乘以比例，得到对应部分的数量。',inputs:[['基准量','q'],['比例','r']],output:'对应数量 → Δ',steps:[{title:'求对应部分',detail:'Δ = q × r。'}],kc:['K-REF','K-PART']});
const method=(id:string)=>domainMock.methods.find(m=>m.id===id)!;
method('S1-A').kc=['K-REF'];
method('S1-A').conditions='已知原量与相对原量的增加比例。';
Object.assign(method('S1-A').steps[0]!,{decomposed:true,solutionId:'S0'});
method('S1-B').kc=['K-REF','K-GROW'];
method('S1-B').conditions='增加比例以原量为基准，可把原量视为 1。';
method('S2-A').conditions='底与对应高已知，长度单位一致。';
method('S3-A').kc=['K-RECT','K-AREA'];
method('S3-A').conditions='扩建后的花坛仍完全位于长方形花园内。';
Object.assign(method('S3-A').steps[0]!,{decomposed:true,solutionId:'S1-A'});
Object.assign(method('S3-A').steps[1]!,{decomposed:true,solutionId:'S2-A'});
method('S3-B').kc=['K-RECT','K-TRI','K-AREA','K-HEIGHT'];
method('S3-B').conditions='花坛位于角落，两直角边沿花园相邻边，可分割剩余区域。';
Object.assign(method('S3-B').steps[0]!,{decomposed:true,solutionId:'S1-B'});
domainMock.knowledge.find(k=>k.id==='K-PART')!.prerequisites=['K-REF'];
domainMock.knowledge.find(k=>k.id==='K-GROW')!.prerequisites=['K-REF'];
domainMock.knowledge.find(k=>k.id==='K-TRI')!.prerequisites=['K-HEIGHT','K-AREA'];

// Reference questions are fixed mock outputs, separate from editable definitions.
export const domainPresets:MockTask[]=JSON.parse(JSON.stringify(domainMock.tasks));
export function blankDomainTask(domainId:string):DomainTask {
  return {id:'T-'+Date.now(),domainId,label:'',name:'',summary:'',goal:'',responsibility:'',output:'',parameters:[],relations:[],variations:'',exclusions:'',methods:[],availableMethods:[],question:'',answer:'',working:[],checks:[],cases:[]};
}

export interface KnowledgeSource { methodId:string; direct:boolean; indirect:boolean }
export function collectKnowledge(methodIds:string[],domainId:string){
  const rows=new Map<string,{knowledge:DomainKnowledge;sources:KnowledgeSource[]}>(),issues=new Set<string>();
  function visit(id:string,root:string,path:string[]){
    const m=domainMock.methods.find(m=>m.id===id&&m.domainId===domainId);
    if(!m){issues.add('有引用的方法尚未补齐。');return;}
    if(path.includes(id)){issues.add('方法存在循环引用，知识汇总未完整。');return;}
    for(const kcId of m.kc){
      const knowledge=domainMock.knowledge.find(k=>k.id===kcId&&k.domainId===domainId);
      if(!knowledge){issues.add('有知识定义尚未补齐。');continue;}
      if(!rows.has(kcId))rows.set(kcId,{knowledge,sources:[]});
      const row=rows.get(kcId)!;
      let source=row.sources.find(s=>s.methodId===root);
      if(!source){source={methodId:root,direct:false,indirect:false};row.sources.push(source);}
      if(path.length)source.indirect=true;else source.direct=true;
    }
    for(const step of m.steps){
      if(step.solutionId)visit(step.solutionId,root,[...path,id]);
      else if(step.decomposed)issues.add(m.name+'：有子方法尚未指定。');
    }
    if(!m.kc.length&&!m.steps.some(s=>s.solutionId))issues.add(m.name+'：知识依据尚未补齐。');
  }
  for(const id of new Set(methodIds))visit(id,id,[]);
  return {rows:[...rows.values()],issues:[...issues]};
}
