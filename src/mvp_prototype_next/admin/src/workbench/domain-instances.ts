import { reactive } from 'vue';
import { domainPresets } from './domain-mock';

export interface TaskInstance {
  id:string; taskId:string; domainId:string; question:string; parameters:string;
  answer:string; explanation:string; source:'自动生成'|'导入'; sourceNote:string;
  figure?:'triangle'|'garden';
}
const parameters:Record<string,string>={fraction:'q = 80 升\nr = 1/4',geometry:'b = 12 厘米\nh = 7 厘米',composite:'L = 20 米\nW = 12 米\nq = 8 米\nr = 1/4\nh = 6 米',part:'q = 80 升\nr = 1/4'};
export const taskInstances=reactive<TaskInstance[]>(domainPresets.map((t,index)=>({
  id:'TI-'+String(index+1).padStart(3,'0'),taskId:t.id,domainId:'DOM-MATH',question:t.question,
  parameters:parameters[t.id]||'',answer:t.answer,explanation:t.working.join('\n'),source:'导入',sourceNote:'预置题目（mock）',
  figure:t.id==='geometry'?'triangle':t.id==='composite'?'garden':undefined,
})));
const answers:Record<string,[string,string]>={
  fraction:['52 本','增加量：40 × 3/10 = 12（本）\n最终数量：40 + 12 = 52（本）'],
  geometry:['20 平方厘米','三角形面积：10 × 4 ÷ 2 = 20（平方厘米）'],
  composite:['432 平方米','扩建后的底：10 × (1 + 1/5) = 12（米）\n绿地面积：12 × 8 ÷ 2 = 48（平方米）\n其余面积：30 × 16 − 48 = 432（平方米）'],
  part:['4 米','剪下的长度：12 × 1/3 = 4（米）'],
};
export function generatedInstance(taskId:string,domainId:string):TaskInstance|undefined {
  const preset=domainPresets.find(t=>t.id===taskId),sample=preset?.cases[0],answer=answers[taskId];
  if(!sample||!answer)return;
  return {id:'',taskId,domainId,question:sample.text,parameters:sample.bindings.map(([k,v])=>k+' = '+v).join('\n'),answer:answer[0],explanation:answer[1],source:'自动生成',sourceNote:'固定生成样例（mock）'};
}
