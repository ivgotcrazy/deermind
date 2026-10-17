import { computed, reactive, watch } from 'vue';
import { journey } from './journeyState';
type Thread={id:string;owner:string;child:string;space:string;deleted:boolean;entries:{text:string;at:string}[]};
type State={actor:string;spaces:Record<string,string>;drafts:Record<string,string>;threads:Thread[];active:Record<string,string>};
const key='deermind-phase4-parent-v1';
const initial=():State=>({actor:'PARENT-DEMO-1',spaces:{},drafts:{},threads:[],active:{}});
function restore():State{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d?.actor&&d.spaces&&d.drafts&&Array.isArray(d.threads)&&d.active)return d;}catch{}return initial();}
export const parentState=reactive(restore());
export const parentWarning=reactive({text:''});
export const activeParent=computed(()=>journey.accounts.profiles.find(p=>p.id===parentState.actor&&p.role==='parent'));
export const currentParentLinked=computed(()=>!!activeParent.value&&journey.accounts.links.some(l=>l.parent===parentState.actor&&l.child==='CHILD-DEMO-1'&&l.active));
export const parentScope=(space:string)=>JSON.stringify([parentState.actor,'CHILD-DEMO-1',space]);
export function visibleThreads(space:string){return currentParentLinked.value?parentState.threads.filter(t=>!t.deleted&&t.owner===parentState.actor&&t.child==='CHILD-DEMO-1'&&t.space===space):[];}
export function sendParentMessage(space:string){
 const scope=parentScope(space),text=parentState.drafts[scope]?.trim();if(!text||!currentParentLinked.value)return;
 let t=visibleThreads(space).find(t=>t.id===parentState.active[scope]);
 if(!t){t={id:crypto.randomUUID(),owner:parentState.actor,child:'CHILD-DEMO-1',space,deleted:false,entries:[]};parentState.threads.push(t);parentState.active[scope]=t.id;}
 t.entries.push({text,at:new Date().toISOString()});parentState.drafts[scope]='';
}
export function removeParentThread(space:string,id:string){
 const t=visibleThreads(space).find(t=>t.id===id);if(!t)return;t.deleted=true;
 const scope=parentScope(space);if(parentState.active[scope]===id){delete parentState.active[scope];delete parentState.drafts[scope];}
}
export function resetParent(){Object.assign(parentState,initial());}
watch(parentState,()=>{try{localStorage.setItem(key,JSON.stringify(parentState));}catch{parentWarning.text='家长咨询未能保存，刷新可能丢失。';}},{deep:true});
