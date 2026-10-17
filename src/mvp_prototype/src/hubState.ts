import { computed, reactive, watch } from 'vue';
import { flows } from './foundationState';
import { journey, examBusy, newPlan } from './journeyState';
import { capture, clearCapture } from './captureState';
type Draft = typeof flows.problemDraft;
type Hub = { current:string; drafts:Record<string,string>; messages:Record<string,string[]>; helpDrafts:Record<string,Draft>; captures:Record<string,typeof capture> };
const key='deermind-phase4-home-v1';
const initial=():Hub=>({current:'demo',drafts:{},messages:{},helpDrafts:{},captures:{}});
function restore():Hub{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(typeof d?.current==='string'&&d.drafts&&d.messages&&d.helpDrafts)return {...d,captures:d.captures||{}};}catch{}return initial();}
export const hub=reactive(restore());
export const hubWarning=reactive({text:''});
export const contexts=computed(()=>[{id:'demo',name:'章节／求助演示空间'},...journey.courses.map(c=>({id:c.id,name:c.name}))]);
if(!contexts.value.some(c=>c.id===hub.current))hub.current='demo';
export const currentContext=computed(()=>contexts.value.find(c=>c.id===hub.current)!);
watch(hub,()=>{try{localStorage.setItem(key,JSON.stringify(hub));}catch{hubWarning.text='首页草稿未能保存，刷新可能丢失。';}},{deep:true});
export function selectContext(id:string){
 if(id===hub.current||!contexts.value.some(c=>c.id===id)||examBusy.value)return;
 hub.helpDrafts[hub.current]=JSON.parse(JSON.stringify(flows.problemDraft));
 hub.captures[hub.current]=JSON.parse(JSON.stringify(capture));
 hub.current=id;
 const next=hub.helpDrafts[id]||{prompt:'',answer:'',mode:'explain',sample:false};
 delete flows.problemDraft.input;Object.assign(flows.problemDraft,JSON.parse(JSON.stringify(next)));
 clearCapture();if(hub.captures[id])Object.assign(capture,JSON.parse(JSON.stringify(hub.captures[id])));
 if(id!=='demo'&&journey.selectedCourse!==id){newPlan();journey.selectedCourse=id;journey.selectedUnits=[...(journey.courses.find(c=>c.id===id)?.units||[])];}
}
export function resetHub(){Object.assign(hub,initial());}
