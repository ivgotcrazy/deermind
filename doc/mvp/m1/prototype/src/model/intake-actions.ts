// Row-level mock actions. Extracting a definition does not import the source instance.
import { blankTask, blankMethod, blankStep, blankKnowledge, blankInstance, clone, collection, domainData, id, saveEntity, type Task, type Method, type Knowledge } from './domain';
import { catalog, elementProblems, elementResult, elementText, initializeFlow, isImported, type IntakeGroup, type ParsedElement } from './material-flow';
import { newPart } from './review-content';
import type { ImportDraft } from './imports';

export function rowResult(draft:ImportDraft,request:IntakeGroup,e:ParsedElement){
  return request.result[e.id]||(isImported(initializeFlow(draft),e)?elementResult(initializeFlow(draft),e.id):undefined);
}
function finishRows(request:IntakeGroup){
  request.status=request.elements.every(e=>request.result[e.id]||request.removed?.includes(e.id))?'done':'pending';
}
function canProcess(draft:ImportDraft,request:IntakeGroup,e:ParsedElement):string[]{
  if(request.status!=='pending'||request.removed?.includes(e.id)||!request.elements.some(x=>x.id===e.id))return ['这项内容已处理或已移出待入库列表。'];
  if(rowResult(draft,request,e))return ['这项内容已经处理，不需要重复操作。'];
  if(!domainData.domains.some(d=>d.id===draft.book.domainId))return ['所属领域不存在。'];
  return elementProblems(e).length?['内容尚未完整解析，请返回教材助手说明问题并修正。']:[];
}
export function templateCandidate(draft:ImportDraft,request:IntakeGroup,e:ParsedElement):Task|Method|null {
  if(e.kind==='knowledge')return null;
  const saved=collection(e.kind==='question'?'task':'solution').find(t=>t.id===request.templates?.[e.id]&&t.domainId===draft.book.domainId);
  if(saved)return clone(saved) as Task|Method;
  const recipe=catalog.find(c=>c.id===e.recipe);if(!recipe)return null;
  if(e.kind==='question'){
    const task:Task={...blankTask(draft.book.domainId),name:recipe.title,summary:recipe.definition,goal:recipe.definition,responsibility:'完成题目要求',relations:recipe.definition,requirements:[{deliverable:'结果及必要的说明',criterion:'符合任务条件与要求'}],exclusions:'超出任务定义时另行归类'};
    if(e.recipe==='TT-CHAIN')task.parameters=['A','r','s'].map((symbol,i)=>({symbol,name:['原量','第一层比例','第二层比例'][i],kind:'数值',role:'题目已给定',condition:'按题目给定值'}));
    return task;
  }
  const step=blankStep();Object.assign(step,{title:'执行方法',detail:recipe.definition,inputs:'当前任务的给定条件',output:'求解过程及结果',next:'$success'});
  return {...blankMethod(draft.book.domainId),name:recipe.title,description:recipe.definition,procedure:recipe.definition,conditions:'适用于所关联任务的给定条件',inputs:'题目条件',output:'解题过程及结果',steps:[step],
    kc:recipe.kcIds.flatMap(key=>{const name=catalog.find(c=>c.id===key)?.title;return domainData.knowledge.filter(k=>k.domainId===draft.book.domainId&&k.name===name).map(k=>k.id);}),ending:{success:'完成任务要求并检查结果',stop:'条件不足或不适用时停止'}};
}
export function saveTemplate(draft:ImportDraft,request:IntakeGroup,e:ParsedElement,value:Task|Method):string[]{
  const issues=canProcess(draft,request,e);if(issues.length)return issues;
  if(e.kind==='knowledge'||value.domainId!==draft.book.domainId||!value.name.trim()||!('goal' in value?value.goal:value.description).trim())return ['请补齐名称和定义说明。'];
  const kind=e.kind==='question'?'task':'solution';
  if(collection(kind).some(t=>t.domainId===value.domainId&&t.name===value.name&&t.id!==value.id))return ['已有同名定义，请返回后直接关联已有定义。'];
  if('goal' in value)saveEntity(domainData.tasks,{...value,summary:value.goal});else saveEntity(domainData.methods,value);
  (request.templates??={})[e.id]=value.id;return [];
}
export function knowledgeCandidate(draft:ImportDraft,e:ParsedElement):Knowledge {
  const recipe=catalog.find(c=>c.id===e.recipe);
  return {...blankKnowledge(draft.book.domainId),name:recipe?.title||e.title,description:recipe?.definition||elementText(e),conditions:'按知识定义与适用条件使用'};
}
export function addKnowledge(draft:ImportDraft,request:IntakeGroup,e:ParsedElement,value:Knowledge,existingId:string):string[]{
  const issues=canProcess(draft,request,e);if(issues.length)return issues;
  if(e.kind!=='knowledge')return ['当前内容不是知识成分。'];
  let target=domainData.knowledge.find(k=>k.id===existingId&&k.domainId===draft.book.domainId);
  if(existingId&&!target)return ['请选择当前领域中的知识成分。'];
  if(!existingId){
    if(value.domainId!==draft.book.domainId||!value.name.trim()||!value.description.trim())return ['请补齐知识名称与定义。'];
    if(domainData.knowledge.some(k=>k.domainId===value.domainId&&k.name===value.name))return ['已有同名知识，请选择复用，避免重复添加。'];
    target=saveEntity(domainData.knowledge,value);
  }
  request.result[e.id]={objectId:target!.id,templateId:''};finishRows(request);return [];
}
export function parentInstance(draft:ImportDraft,request:IntakeGroup,e:ParsedElement){
  const parent=request.elements.find(q=>q.id===e.taskElementId)||initializeFlow(draft).elements.find(q=>q.id===e.taskElementId);
  const result=parent?rowResult(draft,request,parent):undefined;
  return result?domainData.instances.find(q=>q.id===result.objectId&&q.domainId===draft.book.domainId):undefined;
}
export function templateOptions(draft:ImportDraft,request:IntakeGroup,e:ParsedElement){
  if(e.kind==='question')return domainData.tasks.filter(t=>t.domainId===draft.book.domainId);
  return domainData.methods.filter(m=>m.domainId===draft.book.domainId);
}
export function suggestedTemplate(draft:ImportDraft,request:IntakeGroup,e:ParsedElement){
  const old=elementResult(initializeFlow(draft),e.id),recipe=catalog.find(c=>c.id===e.recipe);
  const options=templateOptions(draft,request,e);
  return options.find(t=>t.id===old?.templateId)?.id||options.find(t=>t.id===request.templates?.[e.id])?.id||options.find(t=>t.name===recipe?.title)?.id||'';
}
export function associateElement(draft:ImportDraft,request:IntakeGroup,e:ParsedElement,templateId:string,classification='match'):string[]{
  const issues=canProcess(draft,request,e);if(issues.length)return issues;
  if(classification!=='match')return [classification==='mismatch'?'责任、条件或方法不匹配，不能保存关联。':'归属尚未确认，不能保存关联。'];
  const flow=initializeFlow(draft),domainId=draft.book.domainId;
  if(e.kind==='question'){
    const task=domainData.tasks.find(t=>t.id===templateId&&t.domainId===domainId);if(!task)return ['请选择当前领域中的任务。'];
    const previous=elementResult(flow,e.id),old=domainData.instances.find(q=>q.id===previous?.objectId&&q.domainId===domainId);
    if(old&&old.taskId!==task.id)return ['这道题已经入库，请沿用原有任务。'];
    const q=old?clone(old):blankInstance(task);
    q.question=elementText(e);q.source='教材导入';q.sourceNote=draft.book.name+' · '+e.chapter+' · '+e.sourceNote;q.reviewSource={importId:draft.id,itemId:e.itemId};q.checkedSignature='';q.checkedAt='';
    if(e.recipe==='TT-CHAIN')q.bindings={A:'12',r:'1/3',s:'3/4'};
    q.reviewContent=[{...newPart('question'),id:e.id,blocks:clone(e.blocks)},...(q.reviewContent||[]).filter(p=>p.role!=='question')];
    saveEntity(domainData.instances,q);request.result[e.id]={objectId:q.id,templateId:task.id};
  }else if(e.kind==='solution'){
    const parent=parentInstance(draft,request,e);if(!parent)return ['请先关联所属题目。'];
    const method=domainData.methods.find(m=>m.id===templateId&&m.domainId===domainId),task=domainData.tasks.find(t=>t.id===parent.taskId&&t.domainId===domainId);
    if(!method||!task)return ['请选择有效的方法。'];
    if(!task.methods.includes(method.id)){
      // The association dialog explicitly confirms adopting this method for the task.
      saveEntity(domainData.tasks,{...task,methods:[...task.methods,method.id]});
    }
    const q=clone(parent),previous=elementResult(flow,e.id),solutionId=previous?.objectId||id('REF');
    const solution={id:solutionId,taskInstanceId:q.id,methodId:method.id,working:elementText(e),origin:'教材原有' as const,sourceNote:draft.book.name+' · '+e.sourceNote};
    const index=q.solutions.findIndex(s=>s.id===solutionId);if(index<0)q.solutions.push(solution);else q.solutions[index]=solution;
    q.reviewContent=[...(q.reviewContent||[]).filter(p=>p.id!==e.id),{...newPart('solution',e.title),id:e.id,templateId:method.id,blocks:clone(e.blocks)}];q.checkedSignature='';q.checkedAt='';
    saveEntity(domainData.instances,q);request.result[e.id]={objectId:solutionId,templateId:method.id};
  }else return ['知识成分请使用添加操作。'];
  finishRows(request);return [];
}
export function deletionRows(draft:ImportDraft,request:IntakeGroup,e:ParsedElement){
  if(rowResult(draft,request,e))return [];
  return request.elements.filter(x=>(x.id===e.id||x.taskElementId===e.id)&&!request.removed?.includes(x.id)&&!rowResult(draft,request,x));
}
export function deletePendingElement(draft:ImportDraft,request:IntakeGroup,e:ParsedElement):string[]{
  if(request.status!=='pending'||rowResult(draft,request,e))return ['已处理内容不能从待入库入口删除。'];
  const removed=deletionRows(draft,request,e).map(x=>x.id);request.removed=[...new Set([...(request.removed||[]),...removed])];finishRows(request);return [];
}
