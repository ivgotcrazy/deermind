import { clone, domainData, blankTask, blankMethod, blankKnowledge, blankInstance, blankStep, saveEntity, collectKnowledge, taskDefinitionIssues, instanceIssues, instanceSignature, instanceStatus, id, type Task, type Method, type Knowledge, type Instance } from './domain';
import { visualIssues, type ContentVisual } from './content-visuals';
import { type MockTextbook, recordBookChange } from './textbook';

export type ObjectKind='kc'|'solution'|'task'|'instance';
export interface Binding { id:string; mode:'reuse'|'new'; }
export interface ExtractedKC { id:string; key:string; name:string; meaning:string; sourceNote:string; visuals?:ContentVisual[]; }
export interface ExtractedSolution {
  id:string; taskInstanceId:string; key:string; name:string; working:string; result:string;
  origin:'教材原有'|'系统生成'|'来源待确认'; sourceNote:string; visuals?:ContentVisual[];
}
export interface SemanticEntry {
  id:string; chapterId:string; title:string; sourceIds:string[]; pages:number[];
  conditions:string; question:string; knowledge:string; solutionA:string; solutionB:string; answer:string;
  visual:'ratio'|'table'|'chart'|'none'; visualMeaning:string; table:{headers:string[];rows:string[][]}|null;
  diagram?:{base:string;middle:string;end:string;value:string;r:string;s:string};
  extractionVersion?:2; taskInstance?:{id:string;kind:string;parameters:Record<string,string>;visuals?:ContentVisual[]};
  knowledgeItems?:ExtractedKC[]; solutionInstances?:ExtractedSolution[]; knowledgeOnly?:boolean;
  visualsVersion?:1; teachingVisuals?:ContentVisual[]; pendingVisuals?:ContentVisual[];
  reviewed:string; bindings:Record<string,Binding>; selectedMethods:string[]; mapped:string;
}
export interface Integration {
  entries:SemanticEntry[]; selected:string;
  applications:{entryId:string;at:string;signature:string;goal:string;claim:string;teaching:string;requirements:string}[];
  notice?:string;
}
export const objectKinds:Record<ObjectKind,string>={kc:'知识成分',solution:'方法',task:'任务',instance:'具体题目'};
export const slots=[
  {key:'base',kind:'kc',name:'分率的参照整体'},
  {key:'multiply',kind:'kc',name:'求一个量的几分之几'},
  {key:'associate',kind:'kc',name:'乘法结合律'},
  {key:'methodA',kind:'solution',name:'先求中间量，再求最终量'},
  {key:'methodB',kind:'solution',name:'先合并比例，再求最终量'},
  {key:'task',kind:'task',name:'已知两层比例关系，求最终数量'},
  {key:'question',kind:'instance',name:'三个兴趣小组的人数'},
] as const;
export function objectRows(kind:ObjectKind){return kind==='kc'?domainData.knowledge:kind==='solution'?domainData.methods:kind==='task'?domainData.tasks:domainData.instances;}
export function findObject(kind:ObjectKind,id:string,domainId:string){return objectRows(kind).find(o=>o.id===id&&o.domainId===domainId);}
export function objectName(o:Task|Method|Knowledge|Instance|undefined){return o?('name' in o?o.name:o.question):'尚未关联';}
export function sourceSignature(book:MockTextbook,e:SemanticEntry){
  return JSON.stringify(book.units.flatMap(u=>u.chapters).flatMap(c=>c.items||[]).filter(i=>e.sourceIds.includes(i.id)).map(i=>({id:i.id,title:i.title,blocks:i.blocks})));
}
export function semanticSignature(book:MockTextbook,e:SemanticEntry){
  const {reviewed,bindings,selectedMethods,mapped,solutionInstances,teachingVisuals,...meaning}=e;
  return JSON.stringify({meaning,solutions:solutionInstances?.filter(s=>s.origin!=='系统生成'),source:sourceSignature(book,e)});
}
export function isReviewed(book:MockTextbook,e:SemanticEntry){return !!e.reviewed&&e.reviewed===semanticSignature(book,e);}
export function isFraction(e:SemanticEntry){return e.id==='MAT-GROUPS';}
export function isPractice(e:SemanticEntry){return e.id==='MAT-MIXED';}
export function canPropose(e:SemanticEntry){return isFraction(e)||isPractice(e)||!!e.knowledgeOnly;}
const originalA='先求摄影小组人数：12×1/3=4（人）；再求航模小组人数：4×3/4=3（人）。';
const originalB='先求航模相对气象的比例：1/3×3/4=1/4；再求人数：12×1/4=3（人）。';
export function normalizeExtraction(book:MockTextbook,integration:Integration,legacy=true){
  let changed=false;
  for(const e of integration.entries){
    if(e.extractionVersion===2)continue;
    const group=isFraction(e),prefix=book.id+'-'+e.id;
    e.taskInstance={id:e.bindings.question?.id||'TI-'+prefix,kind:group?'例题':isPractice(e)?'练习题':'教材任务',parameters:group?{A:e.diagram?.value||'12',r:e.diagram?.r||'1/3',s:e.diagram?.s||'3/4'}:{}};
    e.knowledgeItems=group?[
      {id:'KC-C-'+prefix+'-1',key:'base',name:'分率的参照整体',meaning:'分率所指的整体随数量关系改变，必须先明确参照整体。',sourceNote:'依据第49—50页数量关系归纳（mock），不是原文逐字定义。'},
      {id:'KC-C-'+prefix+'-2',key:'multiply',name:'求一个量的几分之几',meaning:'已知整体量与分率，相乘得到对应数量。',sourceNote:'依据第50页计算步骤归纳（mock）。'},
      {id:'KC-C-'+prefix+'-3',key:'associate',name:'乘法结合律',meaning:'改变连乘的结合顺序不改变积。',sourceNote:'依据第50页两种列式归纳（mock）。'},
    ]:[];
    if(e.knowledge&&(!group||e.knowledge!=='每个分率都有自己的参照整体；基准量乘分率得到对应数量；乘法结合律。'))e.knowledgeItems.push({id:'KC-C-'+prefix+'-legacy',key:'legacy',name:'原有知识表述',meaning:e.knowledge,sourceNote:'旧稿保留内容，请核对并命名。'});
    e.solutionInstances=[['methodA',e.solutionA,originalA,'先求中间量，再求最终量'],['methodB',e.solutionB,originalB,'先合并比例，再求最终量']].filter(([,working])=>working?.trim()).map(([key,working,original,name])=>({id:'SI-'+prefix+'-'+key,taskInstanceId:e.taskInstance!.id,key,name,working,result:e.answer,origin:group&&working===original&&e.pages.includes(50)?'教材原有':'来源待确认',sourceNote:group&&working===original&&e.pages.includes(50)?'教材第50页；提取为 mock。':'旧稿未记录解法来源，请核对；原内容完整保留。'}));
    if(!legacy&&isPractice(e)){
      e.title='试一试①：连续除法';e.conditions='计算 12 ÷ 4/5 ÷ 3/8。';e.question='写出计算过程和结果。';
      e.taskInstance.parameters={A:'12',b:'4/5',c:'3/8'};e.answer='';e.solutionInstances=[];
    }
    e.extractionVersion=2;e.reviewed='';e.mapped='';changed=true;
  }
  const visualChange=normalizeVisuals(book,integration);
  if(visualChange&&legacy)integration.notice='旧稿图表已按用途整理：教学辅助图不进入题面，归属不明的内容请核对。已有领域对象未自动改写。';
  if(changed&&legacy)integration.notice='旧稿已按 KC、TaskInstance 和 参考解法 展示，原文与已有引用保留。请重新核对；未记录的解法来源不会自动认作教材原有。';
}

function normalizeVisuals(book:MockTextbook,integration:Integration){
  let changed=false;
  for(const e of integration.entries){
    if(e.visualsVersion===1)continue;
    const prefix=book.id+'-'+e.id;
    if(e.taskInstance)e.taskInstance.visuals??=[];
    e.knowledgeItems?.forEach(k=>k.visuals??=[]);e.solutionInstances?.forEach(s=>s.visuals??=[]);
    e.teachingVisuals??=[];e.pendingVisuals??=[];
    const sourceItems=book.units.flatMap(u=>u.chapters).flatMap(c=>c.items||[]).filter(i=>e.sourceIds.includes(i.id));
    const tables=sourceItems.flatMap(i=>i.blocks).filter(b=>b.kind==='table'&&['data','condition','context','blank'].includes(b.role));
    for(const b of tables){
      const table={headers:[...(b.headers||[])],rows:(b.rows||[]).map(r=>[...r])};
      const v:ContentVisual={id:'FIG-'+prefix+'-'+b.id,title:b.title,kind:'table',description:b.unit||b.text||'教材给定的数据。',origin:'教材提取',sourceNote:'教材第'+b.page+'页 · '+b.title+'；提取为 mock。'+(b.issue&&!b.resolved?' 待核对：'+b.issue:''),table};
      if(e.taskInstance)e.taskInstance.visuals!.push(v);else e.pendingVisuals.push(v);
    }
    // Preserve a previously edited table instead of replacing it with a fresh source extraction.
    if(e.table){
      const old:ContentVisual={id:'FIG-'+prefix+'-old-table',title:'旧稿表格',kind:'table',description:'保留旧稿中的表格，请核对用途与来源。',origin:'来源待确认',sourceNote:'旧导入草稿，尚未明确图表归属。',table:clone(e.table)};
      if(!tables.some(b=>JSON.stringify({headers:b.headers||[],rows:b.rows||[]})===JSON.stringify(e.table)))e.pendingVisuals.push(old);
    }
    if(e.diagram){
      const d=e.diagram;
      const v:ContentVisual={id:'FIG-'+prefix+'-relation',title:'两层比例关系分析图',kind:'relation',description:e.visualMeaning,origin:'系统生成',sourceNote:'旧原型按数量关系生成的辅助图；不是原题给出的图。',nodes:[d.base+'\n'+d.value,d.middle+'\n中间量',d.end+'\n待求量'],links:['× '+d.r,'× '+d.s]};
      if(isFraction(e)&&d.base==='气象小组'&&d.middle==='摄影小组'&&d.end==='航模小组')e.teachingVisuals.push(v);
      else e.pendingVisuals.push({...v,origin:'来源待确认',sourceNote:'旧稿关系图，保留原内容；请核对用途与来源。'});
    }else if(e.id==='MAT-CHARTS'&&e.taskInstance){
      for(const b of sourceItems.flatMap(i=>i.blocks).filter(b=>b.kind==='image'&&b.role==='data'))e.taskInstance.visuals!.push({id:'FIG-'+prefix+'-'+b.id,title:b.title,kind:'description',description:b.text||b.title,origin:'教材提取',sourceNote:'教材第'+b.page+'页；原页可查，必要图形及图例尚待补绘。'});
    }else if(e.visual!=='none'&&!e.table&&e.visualMeaning.trim()){

      e.pendingVisuals.push({id:'FIG-'+prefix+'-description',title:'原有图形说明',kind:'description',description:e.visualMeaning,origin:'来源待确认',sourceNote:'旧稿图形说明，尚未确认属于题面、解法还是教学展示。'});
    }
    e.visualsVersion=1;e.reviewed='';e.mapped='';changed=true;
  }
  return changed;
}

export function prepareIntegration(book:MockTextbook):Integration {
  const entries:SemanticEntry[]=[];
  for(const chapter of book.units.flatMap(u=>u.chapters))for(const item of chapter.items||[]){
    if(item.id==='MAT-METHODS'&&(chapter.items||[]).some(i=>i.id==='MAT-GROUPS'))continue;
    const group=item.id==='MAT-GROUPS';
    const related=group?(chapter.items||[]).filter(i=>['MAT-GROUPS','MAT-METHODS'].includes(i.id)):[item];
    const blocks=related.flatMap(i=>i.blocks),table=blocks.find(b=>b.kind==='table'&&b.role!=='blank');
    entries.push({id:item.id,chapterId:chapter.id,title:item.title,sourceIds:related.map(i=>i.id),pages:[...new Set(blocks.map(b=>b.page))],
      conditions:group?'气象小组12人；摄影小组人数是气象小组的1/3；航模小组人数是摄影小组的3/4。':blocks.filter(b=>['condition','context','data'].includes(b.role)).map(b=>b.text).filter(Boolean).join('\n'),
      question:group?'航模小组有多少人？画图或说明两层数量关系，再列式求解。':blocks.filter(b=>b.role==='question').map(b=>b.text||b.title).join('\n'),
      knowledge:group?'每个分率都有自己的参照整体；基准量乘分率得到对应数量；乘法结合律。':'',
      solutionA:group?'先求摄影小组人数：12×1/3=4（人）；再求航模小组人数：4×3/4=3（人）。':'',
      solutionB:group?'先求航模相对气象的比例：1/3×3/4=1/4；再求人数：12×1/4=3（人）。':'',
      answer:group?'3人。1/3以气象小组为整体，3/4以摄影小组为整体。教材第50页两种解法。':'',
      visual:group?'ratio':item.id==='MAT-CHARTS'?'chart':table?'table':'none',
      visualMeaning:group?'第一层：摄影人数=气象人数×1/3；第二层：航模人数=摄影人数×3/4。下图重绘关系，不按原图人物个数推断人数。':item.id==='MAT-CHARTS'?'条形图和折线图采用第91页人数表；扇形图采用年龄占比表的第七次普查行。人数表单位为人，图中为亿；不混用数量与占比。':'请核对必要信息；教材引导话术不作为 DeerMind 的教学策略导入。',
      table:table?{headers:[...(table.headers||[])],rows:(table.rows||[]).map(r=>[...r])}:null,
      diagram:group?{base:'气象小组',middle:'摄影小组',end:'航模小组',value:'12 人',r:'1/3',s:'3/4'}:undefined,
      reviewed:'',bindings:{},selectedMethods:[],mapped:'',
    });
  }
  const integration:Integration={entries,selected:entries[0]?.id||'',applications:[]};
  normalizeExtraction(book,integration,false);
  const practice=entries.find(isPractice);
  if(practice){
    const index=entries.indexOf(practice);
    entries.splice(index+1,0,...[
      {suffix:'2',title:'试一试②：分数除乘混合运算',expression:'3/8 ÷ 1/10 × 5/7'},
      {suffix:'3',title:'试一试③：含括号的分数运算',expression:'4/7 × (5/8 ÷ 5/14)'},
    ].map(x=>({...clone(practice),id:'MAT-MIXED-'+x.suffix,title:x.title,conditions:'计算 '+x.expression+'。',taskInstance:{id:'TI-'+book.id+'-MIXED-'+x.suffix,kind:'练习题',parameters:{expression:x.expression}},knowledgeItems:[],solutionInstances:[],bindings:{},selectedMethods:[]})));
    entries.splice(index+3,0,{...clone(practice),id:'MAT-KNOWLEDGE-DIVISION',title:'知识：除以非零数',sourceIds:['MAT-ERROR'],conditions:'',question:'',knowledgeOnly:true,taskInstance:undefined,
      knowledgeItems:[{id:'KC-C-'+book.id+'-DIVISION',key:'division',name:'除以非零数等于乘以倒数',meaning:'除以一个不为零的数，等于乘这个数的倒数。',sourceNote:'教材第50页底部“注意哟”中的知识说明；提取为 mock。'}],solutionInstances:[],bindings:{},selectedMethods:[]});
  }
  const group=entries.find(isFraction),method=group?.solutionInstances?.find(s=>s.key==='methodA');
  if(method)method.visuals=[{id:'FIG-'+book.id+'-WORKING',title:'先求摄影人数，再求航模人数',kind:'relation',description:'按本解法的两个计算步骤重绘，含中间结果和答案。',origin:'系统生成',sourceNote:'依据教材第50页解法制作的 mock 图示，不是原书图形。',nodes:['气象 12人','摄影 4人','航模 3人'],links:['× 1/3','× 3/4']}];
  const kc=group?.knowledgeItems?.find(k=>k.key==='base');
  if(kc)kc.visuals=[{id:'FIG-'+book.id+'-KC',title:'分率必须对应一个参照整体',kind:'relation',description:'同一个“1/3”，对应的数量取决于参照整体。',origin:'系统生成',sourceNote:'知识说明用 mock 图示，非教材原图，也不属于本题题面。',nodes:['参照整体 A','对应量 A × 1/3'],links:['取整体的 1/3']}];
  return integration;
}
export function semanticIssues(book:MockTextbook,e:SemanticEntry){
  const issues:string[]=[];
  if(!e.knowledgeOnly&&!e.conditions.trim())issues.push('补齐已知条件／背景信息');
  if(!e.knowledgeOnly&&!e.question.trim())issues.push('补齐问题与作答要求');
  if(e.knowledgeItems?.some(k=>!k.name.trim()||!k.meaning.trim()))issues.push('补齐 KC 候选的名称与含义');
  for(const s of e.solutionInstances||[]){
    if(s.origin==='系统生成')continue;
    if(s.origin==='来源待确认')issues.push('解法“'+s.name+'”的来源待核对');
    if(!s.working.trim()||!s.result.trim()||!s.sourceNote.trim())issues.push('补齐解法“'+s.name+'”的过程、结果与来源');
  }
  if(e.pendingVisuals?.length)issues.push('先核对未归属的图表，不能直接进入题面');
  issues.push(...visualIssues(e.taskInstance?.visuals),...(e.knowledgeItems||[]).flatMap(k=>visualIssues(k.visuals)),...(e.solutionInstances||[]).flatMap(s=>visualIssues(s.visuals)));
  if(isFraction(e)&&![49,50].every(p=>e.pages.includes(p)))issues.push('本例题需要第49、50页，当前原件不完整');
  if(!book.domainId||!domainData.domains.some(d=>d.id===book.domainId))issues.push('先选择有效的所属领域');
  return issues;
}
export function confirmSemantic(book:MockTextbook,e:SemanticEntry){
  const issues=semanticIssues(book,e);if(issues.length)return issues;
  e.reviewed=semanticSignature(book,e);recordBookChange(book,'核对语义内容：'+e.title);return [];
}
export function proposalSlots(e:SemanticEntry):{key:string;kind:ObjectKind;name:string}[]{
  if(e.knowledgeOnly)return (e.knowledgeItems||[]).map(k=>({key:k.key,kind:'kc',name:k.name}));
  if(isFraction(e))return [...slots.filter(s=>s.kind!=='instance').map(s=>({...s})),...(e.knowledgeItems||[]).filter(k=>!slots.some(s=>s.key===k.key)).map(k=>({key:k.key,kind:'kc' as const,name:k.name})),...(e.solutionInstances||[]).filter(x=>!slots.some(s=>s.key===x.key)).map(x=>({key:x.key,kind:'solution' as const,name:x.name}))];
  if(isPractice(e))return [{key:'division',kind:'kc',name:'除以非零数等于乘以倒数'},{key:'order',kind:'kc',name:'同级运算从左到右'},{key:'methodCalc',kind:'solution',name:'从左到右计算连续除法'},{key:'task',kind:'task',name:'连续除以两个非零分数'}];
  return [...(e.knowledgeItems||[]).map(k=>({key:k.key,kind:'kc' as const,name:k.name})),{key:'task',kind:'task',name:'本题所属任务'},...(e.solutionInstances||[]).map(s=>({key:s.key,kind:'solution' as const,name:s.name}))];
}
export function instanceCandidate(book:MockTextbook,e:SemanticEntry):Instance {
  const t=domainData.tasks.find(t=>t.id===e.bindings.task?.id&&t.domainId===book.domainId);
  if(!t||!e.taskInstance)throw Error('请先匹配本题的 Task。');
  const q=blankInstance(t),existing=findObject('instance',e.bindings.question?.id,book.domainId) as Instance|undefined;
  q.id=existing?.id||e.taskInstance.id;
  Object.assign(q,{question:e.conditions+'\n'+e.question,bindings:{...e.taskInstance.parameters},table:null,visuals:clone(e.taskInstance.visuals||[]),answer:e.answer||(e.solutionInstances||[]).find(s=>s.origin!=='来源待确认')?.result||'',source:'教材导入',sourceNote:book.name+' · '+e.pages.join('、')+'页 · '+e.title+'；题目提取和归类为 mock。',solutions:(e.solutionInstances||[]).map(s=>({id:s.id,taskInstanceId:q.id,methodId:e.bindings[s.key]?.id||'',working:s.working,result:s.result,origin:s.origin,sourceNote:s.sourceNote,visuals:clone(s.visuals||[])}))});
  return q;
}
export function candidate(book:MockTextbook,e:SemanticEntry,key:string):Knowledge|Method|Task|Instance {
  const domainId=book.domainId,ref=(slot:string)=>e.bindings[slot]?.id||'';
  if(key==='question')return instanceCandidate(book,e);
  if(['division','order'].includes(key))return {...blankKnowledge(domainId),visuals:clone(e.knowledgeItems?.find(k=>k.key===key)?.visuals||[]),name:key==='division'?'除以非零数等于乘以倒数':'同级运算从左到右',description:key==='division'?'a÷b=a×(1/b)，b≠0。':'没有括号的连续乘除运算按从左到右的顺序处理。',conditions:key==='division'?'除数不得为零；运算有定义。':'仅有乘除且没有改变次序的括号。',example:key==='division'?'12÷4/5=12×5/4=15。':'12÷4/5÷3/8=(12÷4/5)÷3/8。',prerequisites:[]};
  if(key==='methodCalc')return {...blankMethod(domainId),name:'从左到右计算连续除法',description:'按原顺序逐次除以两个分数，每次用乘倒数计算。',conditions:'A、b、c 为已知有理数，b、c 不为零。',inputs:'A、b、c',output:'A÷b÷c 的结果及计算过程',kc:['division','order'].map(ref).filter(Boolean),steps:[{...blankStep(),title:'计算第一次除法',detail:'用乘倒数计算 A÷b，记录中间量 B。',inputs:'A、b',output:'B=A×(1/b)'},{...blankStep(),title:'计算第二次除法并核对',detail:'用 B÷c 继续计算，回代原式核对结果。',inputs:'B、c',output:'R=B×(1/c)'}],ending:{success:'计算过程遵循原运算次序，结果正确且约分完整。',stop:'除数为零、条件缺失或不能确定原式时停止。'}};
  if(key==='task'&&isPractice(e))return {...blankTask(domainId),name:'连续除以两个非零分数',summary:'保持原运算次序，计算 A÷b÷c。',goal:'给出计算过程与最简结果。',responsibility:'识别运算顺序，正确求倒数、计算并检查结果。',requirements:[{deliverable:'计算过程与结果',criterion:'按(A÷b)÷c计算，除数非零，约分及结果正确。'}],parameters:[{symbol:'A',name:'起始数量',kind:'数值',role:'题目已给定',condition:'有理数'},{symbol:'b',name:'第一个除数',kind:'数值',role:'题目已给定',condition:'非零分数'},{symbol:'c',name:'第二个除数',kind:'数值',role:'题目已给定',condition:'非零分数'}],relations:'R=(A÷b)÷c=A×(1/b)×(1/c)。',variations:[{target:'A、b、c',range:'有理数与非零分数',constraint:'保持两次除法和从左到右的次序。'}],exclusions:'不含改变运算次序的括号、未知数方程或其他运算。',methods:ref('methodCalc')?[ref('methodCalc')]:[]};
  if(['base','multiply','associate'].includes(key)){
    const k=blankKnowledge(domainId);
    if(key==='base')Object.assign(k,{name:'分率的参照整体',description:'分率描述一个量相对于指定整体的比例；不同关系的整体可能不同。',conditions:'表达或计算分率前须明确所指整体。',example:'摄影是气象的1/3；航模是摄影的3/4，两个整体不同。'});
    if(key==='multiply')Object.assign(k,{name:'求一个量的几分之几',description:'已知基准量与对应分率，相乘得到对应数量。',conditions:'基准量和分率已知，分率所指整体明确。',example:'12×1/3=4；4×3/4=3。',prerequisites:ref('base')?[ref('base')]:[]});
    if(key==='associate')Object.assign(k,{name:'乘法结合律',description:'改变连乘的结合顺序不改变积，(a×b)×c=a×(b×c)。',conditions:'各乘数和运算有定义；数量关系仍要分别解释。',example:'(12×1/3)×3/4=12×(1/3×3/4)。'});
    const extracted=e.knowledgeItems?.find(x=>x.key===key);if(extracted){k.name=extracted.name;k.description=extracted.meaning;k.visuals=clone(extracted.visuals||[]);}return k;
  }
  if(key==='methodA'||key==='methodB'){
    const grouped=key==='methodB',m=blankMethod(domainId);
    Object.assign(m,{name:grouped?'先合并比例，再求最终量':'先求中间量，再求最终量',description:grouped?'合并两层比例后应用于最初基准量。':'沿两层比例依次求对应数量。',conditions:'A为第一层基准量，B=A×r，C=B×s；分率对应的整体明确。',inputs:'A：基准量；r：第一层分率；s：第二层分率',output:'C：最终数量及两层关系说明',kc:['base','multiply',...(grouped?['associate']:[])].map(ref).filter(Boolean),ending:{success:'得到满足 C=(A×r)×s 的结果，单位正确，并解释两个分率各自的整体。',stop:'条件缺失、分率整体不明确或结果违反数量约束时停止并说明原因。'}});
    m.steps=grouped?[
      {...blankStep(),title:'合并两层比例',inputs:'r、s 及对应关系',output:'u=r×s',detail:'根据乘法结合律确定最终量相对于最初基准量的分率。'},
      {...blankStep(),title:'求最终数量并核对',inputs:'A、步骤1的 u',output:'C=A×u',detail:'计算结果并回到原数量关系核对单位与整量条件。'},
    ]:[
      {...blankStep(),title:'求中间量',inputs:'A、r',output:'B=A×r，供步骤2使用',detail:'以 A 为整体，求第二个量。'},
      {...blankStep(),title:'求最终量并核对',inputs:'步骤1的 B、s',output:'C=B×s',detail:'改以 B 为整体，计算第三个量并核对单位与整量条件。'},
    ];return m;
  }
  const knowledge=e.knowledgeItems?.find(k=>k.key===key);if(knowledge)return {...blankKnowledge(domainId),name:knowledge.name,description:knowledge.meaning,visuals:clone(knowledge.visuals||[])};
  const solution=e.solutionInstances?.find(s=>s.key===key);if(solution)return {...blankMethod(domainId),name:solution.name};
  if(!isFraction(e))return {...blankTask(domainId),name:e.title};
  const t=blankTask(domainId);
  Object.assign(t,{name:'已知两层比例关系，求最终数量',summary:'分别识别两层比例的整体，求第三个量。',goal:'求最终数量 C 并说明两层数量关系。',responsibility:'识别每个分率的整体，建立关系，选择方法并检验结果。',requirements:[{deliverable:'最终数量及单位',criterion:'同时满足 B=A×r、C=B×s，离散数量满足整量条件。'},{deliverable:'数量关系说明或关系图',criterion:'两层比例的参照整体正确，不能把 s 直接当作相对 A 的分率。'}],parameters:[
    {symbol:'A',name:'第一层基准量',kind:'数值',role:'题目已给定',condition:'正数量，单位明确'},
    {symbol:'r',name:'第一层分率',kind:'数值',role:'题目已给定',condition:'正有理数，以 A 为整体'},
    {symbol:'s',name:'第二层分率',kind:'数值',role:'题目已给定',condition:'正有理数，以中间量 B 为整体'},
    {symbol:'C',name:'最终量',kind:'数值',role:'需要研究或求解',condition:'单位与 A 一致'},
  ],relations:'B=A×r；C=B×s。题目给出 A、r、s。',variations:[{target:'基准量、两个分率与情境',range:'正数及明确的两层比例情境',constraint:'保持参照关系；人数等离散数量须为整数。'}],exclusions:'不含反求基准量、比例变化或三个以上层次。',methods:['methodA','methodB'].map(ref).filter(Boolean)});
  if(key==='task')return t;
  return t;
}
export function saveCandidate(book:MockTextbook,e:SemanticEntry,key:string){
  const spec=key==='question'?{kind:'instance'}:proposalSlots(e).find(s=>s.key===key)!;
  const value=candidate(book,e,key);
  if(spec.kind==='kc')saveEntity(domainData.knowledge,value as Knowledge);
  if(spec.kind==='solution')saveEntity(domainData.methods,value as Method);
  if(spec.kind==='task')saveEntity(domainData.tasks,value as Task);
  if(spec.kind==='instance'){
    const q=value as Instance,issues=instanceIssues(q);if(issues.length)throw Error(issues.join('；'));
    q.checkedSignature=instanceSignature(q);q.checkedAt=new Date().toLocaleString('zh-CN');saveEntity(domainData.instances,q);
  }
  e.bindings[key]={id:value.id,mode:'new'};e.mapped='';return value.id;
}
export function seedIntegration(book:MockTextbook,integration:Integration,mode:'partial'|'full'){
  const e=integration.entries.find(isFraction);if(!e)return;
  for(const s of slots.filter(s=>mode==='full'||s.kind==='kc')){saveCandidate(book,e,s.key);e.bindings[s.key].mode='reuse';}
  e.selectedMethods=['methodA','methodB'].map(k=>e.bindings[k]?.id).filter(Boolean);e.mapped='';
}
export function generatedSolution(book:MockTextbook,e:SemanticEntry,methodId:string):ExtractedSolution {
  const task=findObject('task',e.bindings.task?.id,book.domainId) as Task|undefined;
  if(!task?.methods.includes(methodId))throw Error('请先选择属于本题 Task 的适用方法。');
  const key=Object.keys(e.bindings).find(k=>e.bindings[k].id===methodId);
  const method=findObject('solution',methodId,book.domainId) as Method|undefined;
  if(!e.taskInstance||!method||!key)throw Error('本题或方法关联缺失。');
  let working='',result='';
  if(isFraction(e)&&['methodA','methodB'].includes(key)){working=key==='methodA'?originalA:originalB;result='3人';}
  if(isPractice(e)&&key==='methodCalc'){working='12 ÷ 4/5 ÷ 3/8\n= 12 × 5/4 ÷ 3/8\n= 15 × 8/3\n= 40。按从左到右的顺序计算，两个除数均不为零。';result='40';}
  if(!working)throw Error('此方法尚无预写生成示例，当前不运行真实 LLM。');
  return {id:id('SI'),taskInstanceId:e.taskInstance.id,key,name:method.name,working,result,origin:'系统生成',sourceNote:'系统生成（mock） · '+method.id+' v'+method.version+' · 预写示例，采用前须核对本题条件。'};
}
export function saveExtractedInstances(book:MockTextbook,e:SemanticEntry,checked:boolean){
  if(!isReviewed(book,e))return ['先确认教材提取结果'];
  let q:Instance;try{q=instanceCandidate(book,e);}catch(err){return [String(err)];}
  if(checked){
    const issues=instanceIssues(q);
    if(!q.solutions.length)issues.push('尚无参考解法；题目可以先保存为草稿。');
    if(q.solutions.some(s=>s.origin==='来源待确认'||!s.sourceNote?.trim()))issues.push('核对每份解法的来源');
    if(issues.length)return [...new Set(issues)];
    q.checkedSignature=instanceSignature(q);q.checkedAt=new Date().toLocaleString('zh-CN');
  }
  const existing=findObject('instance',e.bindings.question?.id,book.domainId) as Instance|undefined;
  if(existing&&e.bindings.question.mode==='reuse'){
    if(existing.taskId!==q.taskId||existing.question!==q.question||JSON.stringify(existing.visuals||[])!==JSON.stringify(q.visuals||[])||q.solutions.some(s=>!existing.solutions.some(old=>old.methodId===s.methodId&&old.working===s.working&&JSON.stringify(old.visuals||[])===JSON.stringify(s.visuals||[]))))return ['复用题目与当前提取结果不一致。请查看题目，核对后选择正确实例；未覆盖公共题目。'];
    return [];
  }
  saveEntity(domainData.instances,q);e.bindings.question={id:q.id,mode:'new'};e.mapped='';return [];
}
export function mappingIssues(book:MockTextbook,e:SemanticEntry){
  const issues:string[]=[];
  if(!isReviewed(book,e))issues.push('本项语义内容尚未核对，或来源／内容已有变化');
  if(e.knowledgeOnly)return [...issues,'此项只提取了 KC。可归入领域；课程使用仍需通过 Task 与 Solution 组织，不能直接将 KC 应用成学习任务。'];
  const t=domainData.tasks.find(t=>t.id===e.bindings.task?.id&&t.domainId===book.domainId);
  if(!t)issues.push('尚未选择本项 Task');else issues.push(...taskDefinitionIssues(t));
  if(!e.selectedMethods.length)issues.push('尚未选择本教材采用的方法');
  for(const id of e.selectedMethods)if(!t?.methods.includes(id))issues.push('所选方法不属于当前 Task，请在领域定义中检查关联');
  issues.push(...collectKnowledge(e.selectedMethods,book.domainId).issues);
  const q=domainData.instances.find(q=>q.id===e.bindings.question?.id&&q.domainId===book.domainId);
  if(!q)issues.push('尚未关联具体题目');
  else {
    if(q.taskId!==t?.id)issues.push('题目不属于所选 Task');
    if(instanceStatus(q)!=='可用（mock）')issues.push('题目仍需完成归类和解答检查（mock）');
    if(JSON.stringify(q.visuals||[])!==JSON.stringify(e.taskInstance?.visuals||[]))issues.push('题面图表已变化，请重新保存实例');
    if(e.selectedMethods.some(id=>!q.solutions.some(s=>s.methodId===id)))issues.push('题目缺少本教材选用方法的具体解答');
    for(const s of e.solutionInstances||[])if(!q.solutions.some(x=>x.methodId===e.bindings[s.key]?.id&&x.working===s.working&&JSON.stringify(x.visuals||[])===JSON.stringify(s.visuals||[])))issues.push('具体解法已有变化，请重新保存实例与归属');
  }
  return [...new Set(issues)];
}
export function mappingSignature(book:MockTextbook,e:SemanticEntry){
  return JSON.stringify({domain:book.domainId,semantic:semanticSignature(book,e),solutions:e.solutionInstances,bindings:e.bindings,methods:e.selectedMethods,
    task:findObject('task',e.bindings.task?.id,book.domainId),question:findObject('instance',e.bindings.question?.id,book.domainId),
    knowledge:collectKnowledge(e.selectedMethods,book.domainId).rows.map(r=>r.knowledge),
    methodsData:domainData.methods.filter(m=>e.selectedMethods.includes(m.id))});
}
export function mappingReady(book:MockTextbook,e:SemanticEntry){return !mappingIssues(book,e).length&&e.mapped===mappingSignature(book,e);}
export function saveMapping(book:MockTextbook,e:SemanticEntry){const issues=mappingIssues(book,e);if(issues.length)return issues;e.mapped=mappingSignature(book,e);recordBookChange(book,'保存教材映射：'+e.title);return [];}
