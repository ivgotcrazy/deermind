import { computed, reactive, watch } from 'vue';
import fixture from '../../mvp_foundation/examples/operations-fixture.json';
export type TaskState='unknown'|'failed'|'unresolved'|'processing'|'completed';
type Task={id:string;label:string;state:TaskState;attempts:number;reconciled:boolean;audit:string[]};
type Ops={alias:string;model:string;saved:string;checked:string;available:boolean;tasks:Task[]};
const initial=():Ops=>({alias:'演示模型服务',model:'未选定的模型',saved:'',checked:'',available:false,tasks:fixture.tasks.map(t=>({id:t.id,label:t.label,state:t.state as TaskState,attempts:1,reconciled:t.state==='failed',audit:[]}))});
const key='deermind-phase4-operations-v1';
function restore():Ops{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d?.tasks&&typeof d.alias==='string'&&typeof d.saved==='string')return d;}catch{}return initial();}
export const ops=reactive(restore());
export const opsWarning=reactive({text:''});
export const configFingerprint=computed(()=>JSON.stringify([ops.alias.trim(),ops.model.trim()]));
export const configReady=computed(()=>!!ops.saved&&ops.saved===configFingerprint.value&&ops.checked===ops.saved&&ops.available);
watch(ops,()=>{try{localStorage.setItem(key,JSON.stringify(ops));}catch{opsWarning.text='后台走查状态未保存，刷新可能丢失。';}},{deep:true});
export function saveConfig(){if(!ops.alias.trim()||!ops.model.trim())return;ops.saved=configFingerprint.value;ops.checked='';ops.available=false;}
export function checkConfig(available:boolean){if(!ops.saved||ops.saved!==configFingerprint.value)return;ops.checked=ops.saved;ops.available=available;}
export function reconcile(t:Task,result:'found'|'absent'|'unknown'){
 if(!['unknown','processing'].includes(t.state))return;
 t.reconciled=result!=='unknown';t.state=result==='found'?'completed':result==='absent'?'failed':'unknown';
 t.audit.push(`预写查询结果：${result==='found'?'原结果已存在，只恢复状态':result==='absent'?'原请求确认未提交，可检查重试条件':'仍然无法确定，继续保持未知'}；未新增学习表现或展示`);
}
export function retry(t:Task,result:'completed'|'failed'|'unresolved'){
 if(t.state!=='failed'||!t.reconciled||!configReady.value)return;
 t.attempts++;t.state=result;t.audit.push(`原任务第 ${t.attempts} 次尝试；预写结果 ${result}；任务标识保持，不新增学生作答或帮助展示`);
}
export function resetOperations(){Object.assign(ops,initial());}
export {fixture as operationsFixture};
