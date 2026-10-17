import { reactive, watch } from 'vue';
import type { Capture } from './captureState';
import fixture from '../../mvp_foundation/examples/product-flow-fixtures.json';

export type HelpRequest = { id: number; spaceId?:string; spaceName?:string; prompt: string; answer: string; mode: 'hint'|'explain'; sample: boolean; expanded: boolean; hidden: boolean; input?:Capture; helpShown?:'hint'|'explain' };
export type Candidate = { name: string; responsibility: string; conditions: string; solution_ref: string; knowledge_ref: string };
type ReviewState = {
  version: 1;
  problemDraft: { prompt:string; answer:string; mode:'hint'|'explain'; sample:boolean; input?:Capture };
  requests: HelpRequest[];
  maintenance: { issueId?:string; candidate:Candidate; checkedFingerprint:string; review:'pending'|'pass'|'fail'|'unresolved'; reason:string; approvedFingerprint:string; published:Candidate|null; adopted:boolean; audit:string[] };
};
const storageKey = 'deermind-phase4-product-flows-v1';
const initial = ():ReviewState => ({
  version:1, problemDraft:{prompt:'',answer:'',mode:'explain',sample:false}, requests:[],
  maintenance:{candidate:{name:fixture.definition.name,responsibility:fixture.definition.responsibility,conditions:fixture.definition.conditions,solution_ref:fixture.definition.solution_ref,knowledge_ref:fixture.definition.knowledge_ref},checkedFingerprint:'',review:'pending',reason:'',approvedFingerprint:'',published:null,adopted:false,audit:[]},
});
function restore():ReviewState {
  try {
    const data=JSON.parse(localStorage.getItem(storageKey)||'null');
    if(data?.version===1&&data.problemDraft&&Array.isArray(data.requests)&&data.maintenance?.candidate&&Array.isArray(data.maintenance.audit))return data;
  } catch { /* This is disposable local demo state, not a learner record. */ }
  return initial();
}
export const flows=reactive<ReviewState>(restore());
export const storageStatus=reactive({warning:''});
watch(flows,()=>{try{localStorage.setItem(storageKey,JSON.stringify(flows));}catch{storageStatus.warning='当前浏览器无法保存这轮演示，刷新后可能丢失。';}},{deep:true});
export function resetFlows(){const fresh=initial();delete flows.maintenance.issueId;delete flows.problemDraft.input;Object.assign(flows.maintenance,fresh.maintenance);Object.assign(flows.problemDraft,fresh.problemDraft);flows.requests=[];}
export const fingerprint=(candidate:Candidate)=>JSON.stringify(candidate);
export { fixture };
