import { ref } from 'vue';
export interface LiveSession {id:string;scope:{space:string;label:string;source?:string};model:string;phase:string;pending:boolean;error:boolean;createdAt:string;updatedAt:string;title:string;turns:number}
export interface LiveTurn {id:string;role:string;text?:string;displayText?:string;at:string;action?:string;blocks?:{type:string;text?:string;title?:string;prompt?:string;answer?:string;state?:string;steps?:string[];[key:string]:unknown}[];metrics?:{ms:number;calls:unknown[]}}
export interface LiveDetail extends Omit<LiveSession,'turns'|'error'|'pending'> {turns:LiveTurn[];error:null|{message:string};pending:null|{startedAt:string};revision:number}
export const sessions=ref<LiveSession[]>([]), loading=ref(false), liveError=ref(''), unreadable=ref<{id:string;reason:string}[]>([]);
export async function request<T>(url:string):Promise<T> {const r=await fetch(url,{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'无法读取会话');return d;}
export async function loadSessions(){loading.value=true;liveError.value='';try{const d=await request<{items:LiveSession[];unreadable:{id:string;reason:string}[]}>('/api/live/admin/sessions');sessions.value=d.items;unreadable.value=d.unreadable;}catch(e){liveError.value=e instanceof Error?e.message:'读取失败';}finally{loading.value=false;}}
