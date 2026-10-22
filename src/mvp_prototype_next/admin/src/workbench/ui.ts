import { ref } from 'vue';
import { blankDefinition, latest, resolve, state, clone } from './store';
import { go, route } from './navigation';
import type { Kind, ModelObject } from './model';
export const preview=ref<{ref:string;scope:string}|null>(null);
export const editor=ref<{object:ModelObject;baseVersion:number;draftId?:string;package?:boolean}|null>(null);
export function newObject(kind:Kind,domain='',parent=''){editor.value={object:blankDefinition(kind,domain,parent),baseVersion:0};}
export function editObject(reference:string){const original=resolve(reference);if(!original)return;const current=latest(original.id)!;editor.value={object:clone(current),baseVersion:current.version};}
export function editDraft(id:string){const d=state.drafts.find(d=>d.id===id);if(d)editor.value={object:clone(d.object),baseVersion:d.baseVersion,draftId:d.id,package:['claim','evidence-rule','inference-rule'].includes(d.object.kind)};}
export function importObject(object:ModelObject){editor.value={object,baseVersion:object.version-1,package:true};}

export function ownerLocation(o:ModelObject){return o.space==='Domain'?{page:'domain',values:{domain:o.domainId,filter:o.kind}}:o.space==='Evaluation'?{page:'evaluation',values:{filter:o.kind}}:o.kind==='target'?{page:'targets',values:{id:o.id}}:{page:'textbooks',values:{id:o.kind==='mapping'?o.relations.find(r=>r.label==='教材章节')?.ref.split('@')[0]:o.id}};}
export function editInOwner(ref:string){const o=resolve(ref);if(!o)return;const target=ownerLocation(o);go(target.page,{...target.values,returnTo:route.returnTo});editObject(ref);}
