import { reactive, watch } from 'vue';
export type InputCheck={id:string;original:string;corrected:string;reason:string;at:string};
type Panel={open:boolean;original:string;corrected:string;reason:string;confirmed:boolean};
type State={panels:Record<string,Panel>;log:Record<string,InputCheck[]>};
const key='deermind-phase4-check-input-v1';
function restore():State{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d?.panels&&d.log)return d;}catch{}return {panels:{},log:{}};}
export const checkInputs=reactive(restore());
export const checkInputWarning=reactive({text:''});
export function openInputCheck(id:string,draft:string){checkInputs.panels[id]={open:true,original:draft,corrected:draft,reason:'',confirmed:false};}
export function closeInputCheck(id:string){delete checkInputs.panels[id];}
export function confirmInputCheck(id:string):InputCheck|undefined{
 const p=checkInputs.panels[id];if(!p?.open||!p.confirmed||!p.corrected.trim()||!p.reason.trim())return;
 const entry={id:crypto.randomUUID(),original:p.original,corrected:p.corrected.trim(),reason:p.reason.trim(),at:new Date().toISOString()};
 (checkInputs.log[id]??=[]).push(entry);closeInputCheck(id);return entry;
}
export function resetCheckInputs(){checkInputs.panels={};checkInputs.log={};}
watch(checkInputs,()=>{try{localStorage.setItem(key,JSON.stringify(checkInputs));}catch{checkInputWarning.text='输入核对暂未保存，刷新可能丢失。';}},{deep:true});
