// Scripted prototype conversations only. No model call or arbitrary semantic extraction.
import { clone, id } from './domain';
import { adoptReparse, reparseCandidate, type MaterialFlow, type ParsedElement } from './material-flow';

export interface MaterialReference { ids:string[]; title:string; chapter:string }
export interface MaterialCandidate {
  before:ParsedElement[]; after:ParsedElement[]; prompt:string;
  status:'pending'|'adopted'|'discarded'|'superseded';
}
export interface AssistantMessage {
  id:string; role:'user'|'assistant'; text:string; reference?:MaterialReference;
  candidate?:MaterialCandidate; retry?:string;
}
export interface MaterialAssistantState {
  messages:AssistantMessage[]; reference:MaterialReference|null; input:string; collapsed:boolean;
}
export function assistantState(flow:MaterialFlow):MaterialAssistantState {
  if(!flow.assistant)flow.assistant={messages:[{id:id('MSG'),role:'assistant',text:'已载入这次导入的解析结果（mock）。请在右侧核对题目、教材解法和知识。发现问题时，点击“请助手修正”带入内容，也可以引用整章讨论。这里只修正解析内容，入库与章节关联仍由你选择。'}],reference:null,input:'',collapsed:false};
  return flow.assistant;
}
export function referenceElements(flow:MaterialFlow,elements:ParsedElement[],chapter:string){
  const state=assistantState(flow);state.collapsed=false;
  state.reference={ids:elements.map(e=>e.id),title:elements.length===1?elements[0].title:chapter+' · 本章内容',chapter};
}
export function sendToAssistant(flow:MaterialFlow,text:string,retry=false){
  const state=assistantState(flow),prompt=text.trim();if(!prompt)return;
  const reference=state.reference?clone(state.reference):undefined;
  state.messages.push({id:id('MSG'),role:'user',text:prompt,reference});state.input='';
  const reply=(text:string,extra:Partial<AssistantMessage>={})=>state.messages.push({id:id('MSG'),role:'assistant',text,reference,...extra});
  if(!reference?.ids.length){reply('请先在右侧选择需要讨论的内容，或点击“与助手讨论本章”。浏览章节不会自动改变对话引用。');return;}
  const before=flow.elements.filter(e=>reference.ids.includes(e.id));
  if(before.length!==reference.ids.length){reply('引用内容已发生变化，请重新选择当前内容后继续。');return;}
  if(prompt.includes('模拟处理失败')&&!retry){reply('本次读取失败（mock），原内容和已有候选均已保留。可以重试。',{retry:prompt});return;}
  if(before.some(e=>['C06','MAT-CIRCLES'].includes(e.itemId))){reply('已核对当前可见书页，题目引用的附页没有提供，不能猜测图形尺寸或隐藏关系。请使用对话区的“补充材料”提供对应附页后继续核对；本次不生成可采用的补全结果。');return;}
  const supported=before.filter(e=>['C02','C03','C05','MAT-GROUPS','MAT-ERROR','MAT-CHARTS'].includes(e.itemId));
  if(!supported.length||!/(拆|分开|解法|图|漏|公式|算式|单位|核对|检查|纠正|修正|重新|解析|还原|模拟处理失败)/.test(prompt)){
    reply('这是固定情境原型，尚未接入真实Agent。可以演示拆分两种解法、核对错误算式和补齐统计图；其他要求先保留在对话中，不伪造修改结果。');return;
  }
  // Only supersede a candidate in the same explicitly referenced scope.
  const previous=[...state.messages].reverse().find(m=>m.candidate?.status==='pending'&&JSON.stringify(m.reference?.ids)===JSON.stringify(reference.ids));
  const working=previous?.candidate?.after||before;
  const projected={...flow,elements:[...flow.elements.filter(e=>!reference.ids.includes(e.id)),...working]};
  const after=working.flatMap(e=>reparseCandidate(projected,e));
  if(previous?.candidate)previous.candidate.status='superseded';
  const charts=after.flatMap(e=>e.blocks).filter(b=>b.type==='chart').length;
  const summary=charts?'统计图按原页补齐并核对数据、轴、图例与单位。':after.some(e=>e.kind==='solution')?'两种解法分别列出，仍指向同一道题。':after.some(e=>['C03','MAT-ERROR'].includes(e.itemId))?'已核对公式结构，保留原书用于辨错的错误演算。':'已核对题干、条件和问题，教材解法没有混入题面。';
  reply((previous?'已在上一版候选上继续核对。':'已生成修正候选。')+summary+'这是一组预设mock结果，请查看右侧内容后决定是否采用。',
    {candidate:{before:clone(previous?.candidate?.before||before),after:clone(after),prompt,status:'pending'}});
}
export function acceptCandidate(flow:MaterialFlow,message:AssistantMessage):string {
  const c=message.candidate;if(!c||c.status!=='pending')return '该候选已处理。';
  if(c.before.some(e=>JSON.stringify(flow.elements.find(x=>x.id===e.id))!==JSON.stringify(e)))return '源内容已经变化，请重新引用当前内容后核对，不能覆盖后来的修正。';
  adoptReparse(flow,c.before,c.after,c.prompt);c.status='adopted';
  // A stale reference is cleared, never silently retargeted to a different element.
  const state=assistantState(flow);
  if(state.reference?.ids.some(key=>!flow.elements.some(e=>e.id===key)))state.reference=null;
  return '';
}
