// Content-review mock contract. Source statements, model definitions and learner state stay separate.
import { clone, id, domainData, saveEntity, collectKnowledge, type Instance } from './domain';
import type { ImportDraft } from './imports';
import { samples, reviewCatalog } from './review-fixtures';

export interface Expression { op:string; value?:string; args?:Expression[] }
export interface Chart { chartType:'bar'|'line'|'pie'; title:string; categories:string[]; unit:string; precision:number; axis:{min:number;max:number;step:number}; series:{name:string;values:number[];color:string}[]; colors:string[] }
export interface ReviewBlock {
  id:string; type:'text'|'formula'|'table'|'chart'|'shapes'|'unsupported'; page:number; rect:number[];
  text:string; lines:string[]; unit:string; headers:string[]; rows:string[][];
  chart:Chart; shapes:{shape:string;dot:string}[]; gap:string;
}
export type PartRole='question'|'answer'|'solution'|'knowledge'|'note';
export interface ReviewPart { id:string; role:PartRole; name:string; blocks:ReviewBlock[]; templateId:string; reason:string; parameters:Record<string,string> }
export interface ReviewItem {
  id:string; title:string; chapter:string; kind:'task'|'knowledge'; parts:ReviewPart[];
  original:ReviewPart[]; reviewed:string; matched:string; history:{at:string;action:string;before:ReviewPart[];after:ReviewPart[]}[];
  sourceNote:string; instanceId:string;
}
export interface ReviewState { selected:string; items:ReviewItem[]; pages:number[]; domainId:string }
export const roles:Record<PartRole,string>={question:'题面',answer:'教材答案',solution:'教材解法',knowledge:'知识表述',note:'教材旁注'};
export const blockNames={text:'文字',formula:'公式／演算',table:'表格',chart:'统计图',shapes:'图形序列',unsupported:'待补内容'};
export function blankBlock(type:ReviewBlock['type'],page:number,rect=[0,0,1,1]):ReviewBlock {
  return {id:id('CONTENT'),type,page,rect:[...rect],text:'',lines:[''],unit:'',headers:['项目','数值'],rows:[['','']],
    chart:{chartType:'bar',title:'',categories:['类别1'],unit:'',precision:2,axis:{min:0,max:10,step:2},series:[{name:'系列1',values:[0],color:'#4f81bd'}],colors:['#4f81bd','#e28036','#999999','#ffc000']},shapes:[{shape:'circle',dot:'none'}],gap:''};
}
export function newPart(role:PartRole,name=roles[role]):ReviewPart{return {id:id(role==='solution'?'SI':'PART'),role,name,blocks:[],templateId:'',reason:'',parameters:{}};}
export function newItem(title:string,chapter:string,kind:ReviewItem['kind']):ReviewItem {
  return {id:id('ITEM'),title,chapter,kind,parts:[newPart(kind==='task'?'question':'knowledge')],original:[],reviewed:'',matched:'',history:[],sourceNote:'',instanceId:id('TI')};
}
export const contentSignature=(item:ReviewItem)=>JSON.stringify({title:item.title,kind:item.kind,parts:item.parts.map(({templateId,reason,parameters,...p})=>p)});
export const contentReviewed=(item:ReviewItem)=>!!item.reviewed&&item.reviewed===contentSignature(item);
export function changed(item:ReviewItem,before:ReviewPart[],action:string){
  item.history.unshift({at:new Date().toLocaleString('zh-CN'),action,before:clone(before),after:clone(item.parts)});
  item.reviewed='';item.matched='';
}
export function moveBlocks(item:ReviewItem,fromId:string,toId:string,keys:string[]){
  const from=item.parts.find(p=>p.id===fromId),to=item.parts.find(p=>p.id===toId);
  if(!from||!to||from===to||!keys.length)throw Error('请选择要移动的内容和不同的接收位置');
  const before=clone(item.parts),selected=from.blocks.filter(b=>keys.includes(b.id));
  to.blocks.push(...selected);from.blocks=from.blocks.filter(b=>!keys.includes(b.id));changed(item,before,'移动内容到'+to.name);
}
export function splitSolution(item:ReviewItem,partId:string,keys:string[],name:string){
  const part=item.parts.find(p=>p.id===partId);
  if(!part||part.role!=='solution'||!keys.length||keys.length>=part.blocks.length||!name.trim())throw Error('填写新解法名称，选择部分内容，并为原解法保留内容');
  const before=clone(item.parts),next=newPart('solution',name.trim());next.blocks=part.blocks.filter(b=>keys.includes(b.id));
  part.blocks=part.blocks.filter(b=>!keys.includes(b.id));item.parts.splice(item.parts.indexOf(part)+1,0,next);changed(item,before,'拆分教材解法：'+name);return next;
}
export function blockIssues(b:ReviewBlock):string[]{
  const errors:string[]=[];
  if(b.gap.trim())errors.push(b.gap);
  if(!Number.isFinite(b.page)||b.page<1||b.rect.length!==4||b.rect.some(n=>!Number.isFinite(n))||b.rect[0]<0||b.rect[1]<0||b.rect[2]<=0||b.rect[3]<=0||b.rect[0]+b.rect[2]>1.001||b.rect[1]+b.rect[3]>1.001)errors.push('请框选有效的原页出处');
  if(b.type==='unsupported')errors.push('这部分内容仍待补齐');
  if(b.type==='text'&&!b.text.trim())errors.push('文字为空');
  if(b.type==='formula'){if(!b.lines.length)errors.push('请填写算式');for(const line of b.lines){try{parseFormula(line);}catch{errors.push('公式无法解析：'+line);}}}
  if(b.type==='table'&&(!b.headers.length||b.headers.some(h=>!h.trim())||!b.rows.length||b.rows.some(r=>r.length!==b.headers.length)))errors.push('请补齐表头，检查每行的列数');
  if(b.type==='chart'){
    const c=b.chart;
    if(!c.title.trim()||!c.unit.trim()||!c.categories.length||c.categories.some(s=>!s.trim())||!c.series.length||c.series.some(s=>!s.name.trim()||s.values.length!==c.categories.length||s.values.some(v=>!Number.isFinite(v)||v<0)))errors.push('请补齐图名、单位、类别及每组数值');
    if(c.chartType==='pie'&&(c.unit!=='%'||c.series.length!==1||Math.abs(c.series[0].values.reduce((a,v)=>a+v,0)-100)>.11))errors.push('占比图需要一组百分比数据，合计应约为100%；请核对，不自动改值');
    if(c.chartType!=='pie'&&(!Number.isFinite(c.axis.min)||!Number.isFinite(c.axis.max)||!Number.isFinite(c.axis.step)||c.axis.min!==0||c.axis.max<=0||c.axis.step<=0||(c.axis.max-c.axis.min)/c.axis.step>100||c.series.some(s=>s.values.some(v=>v>c.axis.max))))errors.push('请检查坐标轴：本轮从0起，最大值覆盖数据，刻度数量不超过100');
    if(!Number.isInteger(c.precision)||c.precision<0||c.precision>4)errors.push('小数位数需在0—4之间');
  }
  if(b.type==='shapes'&&(!b.shapes.length||b.shapes.some(s=>!['circle','ellipse','triangle','square','pentagon','hexagon'].includes(s.shape)||!['none','center_like'].includes(s.dot))))errors.push('请核对图形种类与标记；其他位置的点暂需保留缺口');
  return [...new Set(errors)];
}
export function reviewIssues(item:ReviewItem,pages:number[]){
  const parts=item.parts.filter(p=>p.role!=='note');
  return [...(!item.title.trim()?['请填写内容标题']:[]),...(!parts.length?['尚无内容']:[]),...parts.flatMap(p=>[...(!p.blocks.length?[p.name+'为空；无教材解法可移除空解法']:[]),...p.blocks.flatMap(b=>[...blockIssues(b),...(!pages.includes(b.page)?['缺少第'+b.page+'页原件']:[])])])];
}
// Small non-evaluating parser: displaying an intentionally wrong equation must remain possible.
export function parseFormula(input:string):Expression {
  const source=input.trim().replace(/^=/,'').replace(/\s+/g,'').replaceAll('−','-').replaceAll('*','×');
  const tokens=source.match(/\d+(?:\.\d+)?|[A-Za-z]+|[()+\-×÷/=]/g)||[];
  if(!tokens.length||tokens.join('')!==source)throw Error('只支持数字、变量、分数、四则运算与括号；单位请单独填写');
  let index=0;
  function atom():Expression {
    const token=tokens[index++];
    if(token==='('){const value=equation();if(tokens[index++]!==')')throw Error('缺少右括号');return {op:'group',args:[value]};}
    if(token==='-')return {op:'subtract',args:[{op:'number',value:'0'},atom()]};
    if(!token||!/^([A-Za-z]+|\d+(\.\d+)?)$/.test(token))throw Error('缺少数值');
    return {op:/^[A-Za-z]/.test(token)?'variable':'number',value:token};
  }
  function fraction():Expression{let value=atom();while(tokens[index]==='/'){index++;value={op:'fraction',args:[value,atom()]};}return value;}
  function product():Expression{let value=fraction();while(['×','÷'].includes(tokens[index])){const op=tokens[index++]==='×'?'multiply':'divide';value={op,args:[value,fraction()]};}return value;}
  function sum():Expression{let value=product();while(['+','-'].includes(tokens[index])){const op=tokens[index++]==='+'?'add':'subtract';value={op,args:[value,product()]};}return value;}
  function equation():Expression{let value=sum();while(tokens[index]==='='){index++;value={op:'equal',args:[value,sum()]};}return value;}
  const result=equation();if(index!==tokens.length)throw Error('公式有多余字符或括号');return result;
}
export function expressionText(e:Expression):string {
  if(e.value!==undefined)return e.value;
  const args=(e.args||[]).map(expressionText);
  if(e.op==='group')return '('+args[0]+')';
  return args.join(({fraction:'/',multiply:' × ',divide:' ÷ ',add:' + ',subtract:' - ',equal:' = '} as Record<string,string>)[e.op]||' ? ');
}
export function itemText(item:ReviewItem,roles:PartRole[]){return item.parts.filter(p=>roles.includes(p.role)).flatMap(p=>p.blocks.map(b=>b.type==='formula'?b.lines.join('\n'):b.type==='chart'?b.chart.title:b.type==='table'?b.headers.join(' / '):b.text)).join('\n');}
export function targetRows(item:ReviewItem){return item.parts.filter(p=>['question','solution','knowledge'].includes(p.role));}
export function definitions(role:PartRole,domainId:string){return (role==='question'?domainData.tasks:role==='solution'?domainData.methods:domainData.knowledge).filter(d=>d.domainId===domainId);}
export function matchingSignature(item:ReviewItem,domainId:string){
  const task=domainData.tasks.find(t=>t.id===item.parts.find(p=>p.role==='question')?.templateId&&t.domainId===domainId);
  return JSON.stringify({content:contentSignature(item),domainId,rows:targetRows(item).map(p=>({id:p.templateId,parameters:p.parameters,definition:definitions(p.role,domainId).find(d=>d.id===p.templateId)})),methods:task?.methods.map(id=>domainData.methods.find(m=>m.id===id)),kc:task?collectKnowledge(task.methods,domainId):null});
}
export function matchingIssues(item:ReviewItem,domainId:string){
  const errors:string[]=[];if(!contentReviewed(item))errors.push('请先核对当前内容');
  const task=domainData.tasks.find(t=>t.id===item.parts.find(p=>p.role==='question')?.templateId&&t.domainId===domainId);
  for(const p of targetRows(item)){
    if(!definitions(p.role,domainId).some(d=>d.id===p.templateId))errors.push(p.name+'尚未匹配');
    if(p.role==='solution'&&!task?.methods.includes(p.templateId))errors.push(p.name+'不属于当前任务模板');
  }
  if(task){if(!task.methods.length)errors.push('任务模板至少需要一个方法定义；不等于教材必须提供解法实例');for(const p of task.parameters.filter(p=>p.role==='题目已给定'))if(!item.parts.find(p=>p.role==='question')?.parameters[p.symbol]?.trim())errors.push('请填写模板参数 '+p.symbol+' 的对应值');}
  return [...new Set(errors)];
}
export function saveReviewMapping(item:ReviewItem,domainId:string,importId:string){
  const errors=matchingIssues(item,domainId);if(errors.length)return errors;
  if(item.kind==='task'){
    const question=item.parts.find(p=>p.role==='question')!;
    const value:Instance={id:item.instanceId,domainId,taskId:question.templateId,version:0,question:itemText(item,['question']),bindings:clone(question.parameters),table:null,answer:itemText(item,['answer']),source:'教材导入',sourceNote:item.sourceNote||'教材原页核对（mock）',checkedSignature:'',checkedAt:'',
      solutions:item.parts.filter(p=>p.role==='solution').map(p=>({id:p.id,taskInstanceId:item.instanceId,methodId:p.templateId,working:p.blocks.map(b=>b.type==='formula'?b.lines.join('\n'):b.text).join('\n'),origin:'教材原有',sourceNote:'教材原有解法；核对中人工校正（mock）'})),reviewContent:clone(item.parts),reviewSource:{importId,itemId:item.id}};
    saveEntity(domainData.instances,value);
  }
  item.matched=matchingSignature(item,domainId);return [];
}
export const mappingConfirmed=(item:ReviewItem,domainId:string)=>contentReviewed(item)&&!!item.matched&&item.matched===matchingSignature(item,domainId)&&!matchingIssues(item,domainId).length;
export function seedReviewDefinitions(domainId:string){
  const ids=Object.fromEntries(reviewCatalog.map(d=>[d.id,domainId+'-REVIEW-'+d.id]));
  for(const d of reviewCatalog){
    const base={id:ids[d.id],domainId,name:d.title,version:0};
    if(d.kind==='KnowledgeComponent'&&!domainData.knowledge.some(x=>x.id===base.id))saveEntity(domainData.knowledge,{...base,description:d.definition,conditions:'本轮样例适用范围',example:'',prerequisites:[]});
    if(d.kind==='SolutionTemplate'&&!domainData.methods.some(x=>x.id===base.id))saveEntity(domainData.methods,{...base,description:d.definition,conditions:'按教材给定条件和方法范围核对',inputs:'本题的已知条件',output:'求解过程或说明',steps:[],kc:d.kcIds.map(k=>ids[k]),ending:{success:'达到本任务要求',stop:'条件不足时停止'}});
    if(d.kind==='TaskTemplate'&&!domainData.tasks.some(x=>x.id===base.id))saveEntity(domainData.tasks,{...base,summary:d.definition,goal:d.definition,responsibility:'完成本题要求',requirements:[],parameters:d.id==='TT-CHAIN'?['A','r','s'].map((symbol,i)=>({symbol,name:['气象人数','摄影相对气象的比例','航模相对摄影的比例'][i],kind:'数值',role:'题目已给定' as const,condition:'按教材给定值'})):[],relations:d.definition,variations:[],exclusions:'超出本定义的任务另行建模',methods:d.solutionIds.map(k=>ids[k])});
  }
}
export function initializeReview(draft:ImportDraft):ReviewState {
  if(draft.contentReview)return draft.contentReview;
  const items:ReviewItem[]=draft.reviewExamples?samples.map(s=>{
    const item=newItem(s.title,s.chapter,'task');item.id=s.id;item.sourceNote=s.sourceNote;
    item.parts=s.parts.map(p=>({...clone(p),id:id(p.role==='solution'?'SI':'PART'),blocks:p.blocks.map(b=>({...clone(b),id:id('CONTENT')})),templateId:'',reason:'',parameters:{}}));item.original=clone(item.parts);return item;
  }):(draft.integration?.entries||[]).map(e=>{
    const item=newItem(e.title,draft.book.units.flatMap(u=>u.chapters).find(c=>c.id===e.chapterId)?.name||'未分章',e.knowledgeOnly?'knowledge':'task');item.id=e.id;
    const add=(part:ReviewPart,text:string)=>{if(text.trim())part.blocks.push({...blankBlock('text',e.pages[0]||49),text});};
    if(e.knowledgeOnly){for(const k of e.knowledgeItems||[])add(item.parts[0],k.name+'\n'+k.meaning);}
    else{add(item.parts[0],e.conditions);add(item.parts[0],e.question);if(e.answer){const p=newPart('answer');add(p,e.answer);item.parts.push(p);}
      for(const s of e.solutionInstances||[]){const p=newPart(s.origin==='教材原有'?'solution':'note',s.name);add(p,s.working);item.parts.push(p);}
      for(const v of e.taskInstance?.visuals||[]){const b=blankBlock(v.kind==='table'?'table':'unsupported',e.pages[0]||49);b.text=v.description;b.gap=v.kind==='table'?'':'旧稿图形需对照原页补齐结构';if(v.table){b.headers=clone(v.table.headers);b.rows=clone(v.table.rows);}item.parts[0].blocks.push(b);}}
    item.sourceNote='旧稿内容迁入核对；原记录保留。';item.original=clone(item.parts);return item;
  });
  const pages=[...new Set(draft.files.map(f=>Number(f.id.replace('BNU-PAGE-',''))).filter(Number.isFinite))].sort((a,b)=>a-b);
  draft.contentReview={selected:items[0]?.id||'',items,pages,domainId:draft.book.domainId};
  return draft.contentReview;
}
