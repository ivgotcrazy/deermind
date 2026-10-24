import { reactive, watch } from 'vue';
import { textbookMock, emptyTextbook, emptyChapter, mockId, recordBookChange, type MockTextbook } from './textbook-mock';
import { targetMock, blankTarget, configurationIssues, type MockTarget } from './target-mock';
import { domainMock, collectKnowledge } from './domain-mock';
import { evaluationMock } from './evaluation-mock';
import { prepareRealBook, realBookPages } from './textbook-material-fixture';
import { ensureTextbookModel } from './textbook-model-fixture';

// Finite interaction fixtures. File contents are never uploaded or recognized.
export interface ImportFile { id:string; name:string; kind:string; size:number }
export interface ImportPage { id:string; fileId:string; filePage:number; fixture:number; chapterId:string; issue:string; resolved:boolean }
export interface TextbookImport {
  id:string; step:number; progress:number; state:'upload'|'processing'|'failed'|'review'|'applied';
  book:MockTextbook; files:ImportFile[]; pages:ImportPage[]; selectedPage:string; mappingChapterId?:string; targetId:string;
  failNext:boolean; error:string; appliedAt:string; sample?:'bnu6a';
}
const storageKey='deermind-next-textbook-import-v1';
const copy=<T,>(v:T):T=>JSON.parse(JSON.stringify(v));
const saved=JSON.parse(localStorage.getItem(storageKey)||'{"imports":[],"books":[],"targets":[]}') as {imports:TextbookImport[];books:MockTextbook[];targets:MockTarget[]};
export const textbookImports=reactive<TextbookImport[]>(saved.imports);
if(saved.imports.some(d=>d.sample==='bnu6a'))ensureTextbookModel();
for(const b of saved.books){const i=textbookMock.books.findIndex(x=>x.id===b.id);if(i<0)textbookMock.books.push(b);else textbookMock.books[i]=b;}
for(const t of saved.targets){const i=targetMock.targets.findIndex(x=>x.id===t.id);if(i<0)targetMock.targets.push(t);else targetMock.targets[i]=t;}
// A reload pauses the simulated processor; it never starts work by itself.
for(const d of textbookImports)if(d.state==='processing'){d.state='failed';d.error='识别整理已暂停，已选文件和处理进度已保留。';}
watch(()=>({imports:textbookImports,books:textbookMock.books.filter(b=>textbookImports.some(d=>d.book.id===b.id)),targets:targetMock.targets.filter(t=>textbookImports.some(d=>d.book.id===t.bookId))}),value=>localStorage.setItem(storageKey,JSON.stringify(value)),{deep:true});

export const scanFixtures=[
  {title:'按比例增加后的数量',chapter:'fraction',text:'原来有 80 本书，又增加了原来数量的四分之一。现在有多少本？\n先求增加量，再加回原量。\n80 × 1/4 = 20（本）\n80 + 20 = 100（本）',recognized:'原来有 80 本书，又增加了原来数量的九分之一。现在有多少本？\n先求增加量，再加回原量。\n80 × 1/9 = 20（本）\n80 + 20 = 100（本）',issue:'分母可能识别错误，请对照原页的 1/4。',kind:'例题与讲解'},
  {title:'用图示理解数量增加',chapter:'fraction',text:'一根绳子原长 48 米，延长部分是原长的四分之一。现在总长是多少米？\n请结合示意图说明理由。',recognized:'一根绳子原长 48 厘米，延长部分是原长的四分之一。现在总长是多少厘米？\n请结合示意图说明理由。',issue:'长度单位可能识别错误，请核对图中的“米”。',kind:'图示与练习'},
  {title:'三角形的面积',chapter:'geometry',text:'三角形的底长 12 厘米，对应高为 7 厘米。求面积。\n面积 = 底 × 高 ÷ 2\n12 × 7 ÷ 2 = 42（平方厘米）',recognized:'三角形的底长 12 厘米，对应高为 7 厘米。求面积。\n面积 = 底 × 高 ÷ 2\n12 × 7 ÷ 2 = 42（平方厘米）',issue:'',kind:'图形与例题'},
];
export function newImport(domainId=''){
  const book=emptyTextbook();book.domainId=domainId||domainMock.domains[0]?.id||'';
  const draft:TextbookImport={id:mockId('IMPORT'),step:0,progress:0,state:'upload',book,files:[],pages:[],selectedPage:'',targetId:'',failNext:false,error:'',appliedAt:''};
  textbookImports.unshift(draft);return draft.id;
}
export const importBook=(d:TextbookImport)=>textbookMock.books.find(b=>b.id===d.book.id)||d.book;
export function fillSample(d:TextbookImport){
  delete d.sample;
  d.files=[1,2,3].map(n=>({id:mockId('SOURCE'),name:'分数与面积-扫描页'+n+'.png',kind:'扫描图片',size:248000}));
  Object.assign(d.book,{name:'分数与面积·扫描教材示例',publisher:'DeerMind 自编材料',edition:'交互演示版',grade:'小学高年级',subject:'数学',sourceNote:'自编三页扫描示例，识别结果为固定 mock。'});
}
export function fillRealSample(d:TextbookImport){
  d.sample='bnu6a';ensureTextbookModel();
  d.files=realBookPages.map(page=>({id:'BNU-PAGE-'+page,name:'北师大六上-书页'+page+'.png',kind:'扫描图片',size:0}));
  Object.assign(d.book,{name:'北师大版数学六年级上册 · 书页走查',publisher:'北京师范大学出版社',edition:'用户提供的电子教材',grade:'六年级上册',subject:'数学',domainId:'DOM-MATH',sourceNote:'真实书页：49—50、91—93；电子页序为52—53、94—96。识别、整理及模型关联使用固定 mock，不代表全册已准备。'});
}
export function finishRecognition(d:TextbookImport){
  if(d.pages.length){d.state='review';d.step=2;return;}
  const b=copy(d.book);b.sources=d.files.map(f=>({id:f.id,name:f.name,kind:f.kind}));
  if(d.sample==='bnu6a'){
    prepareRealBook(b);d.pages=b.units.flatMap(u=>u.chapters).flatMap(ch=>ch.locations.map(loc=>({id:loc.id,fileId:loc.fileId,filePage:loc.filePage,fixture:0,chapterId:ch.id,issue:'',resolved:false})));
    b.history=[{at:new Date().toLocaleString('sv-SE'),change:'真实书页整理初稿（mock），等待按内容核对'}];
    textbookMock.books.unshift(b);d.book=copy(b);d.selectedPage=d.pages[0]!.id;d.state='review';d.progress=100;d.step=2;return;
  }
  const locations=d.files.flatMap(f=>Array.from({length:f.kind==='PDF'?3:1},(_,i)=>({fileId:f.id,filePage:i+1}))).slice(0,3);
  const fraction=emptyChapter();fraction.name='按比例增加后的数量';
  const geometry=emptyChapter();geometry.name='三角形的面积';
  d.pages=locations.map((loc,i)=>{
    const fixture=scanFixtures[i]!,chapter=fixture.chapter==='fraction'?fraction:geometry,id=mockId('LOC');
    chapter.locations.push({id,...loc,printedPage:String(i+6),label:fixture.kind,text:fixture.recognized});
    return {id,...loc,fixture:i,chapterId:chapter.id,issue:fixture.issue,resolved:false};
  });
  for(const ch of [fraction,geometry])ch.content=ch.locations.map(l=>l.text).join('\n\n');
  b.units=[{id:mockId('UNIT'),name:'第一单元 分数的应用',chapters:[fraction]},...(geometry.locations.length?[{id:mockId('UNIT'),name:'第二单元 图形面积',chapters:[geometry]}]:[])];
  b.history=[{at:new Date().toLocaleString('sv-SE'),change:'完成扫描件识别整理（mock），等待核对'}];
  textbookMock.books.unshift(b);d.book=copy(b);d.selectedPage=d.pages[0]!.id;d.state='review';d.progress=100;d.step=2;
}
export function pageChapter(d:TextbookImport,page:ImportPage){return importBook(d).units.flatMap(u=>u.chapters).find(c=>c.id===page.chapterId)!;}
export function pageLocation(d:TextbookImport,page:ImportPage){return pageChapter(d,page).locations.find(l=>l.id===page.id)!;}
export function savePage(d:TextbookImport,page:ImportPage,text:string,chapterId:string,label:string,printedPage:string){
  if(!text.trim()||!label.trim())throw Error('请补齐整理内容和页内位置。');
  const book=importBook(d),previous=pageChapter(d,page),next=book.units.flatMap(u=>u.chapters).find(c=>c.id===chapterId);
  if(!next)throw Error('请选择所属章节。');
  const loc=pageLocation(d,page);
  if(next.id!==previous.id){previous.locations=previous.locations.filter(l=>l.id!==page.id);next.locations.push(loc);page.chapterId=next.id;previous.mappings.forEach(m=>m.sources=m.sources.filter(id=>id!==page.id));previous.mappings=previous.mappings.filter(m=>m.sources.length);}
  Object.assign(loc,{text:text.trim(),label:label.trim(),printedPage:printedPage.trim()});page.resolved=true;
  for(const ch of [previous,next]){
    const pages=d.pages.filter(p=>p.chapterId===ch.id);
    ch.content=ch.locations.filter(l=>pages.some(p=>p.id===l.id)).map(l=>l.text).join('\n\n');
    ch.checked=pages.length>0&&pages.every(p=>p.resolved);
    ch.reviewNote=ch.checked?'本章纳入的扫描页已对照核对。':'仍有页面待核对；可以先准备其他章节。';
  }
  recordBookChange(book,'核对扫描页：'+label);
}
export function mappingIssues(d:TextbookImport){
  const book=importBook(d),chapters=book.units.flatMap(u=>u.chapters).filter(c=>c.checked&&c.mappings.length),issues:string[]=[];
  if(!chapters.length)issues.push('请先完成至少一章的内容核对和模型关联。');
  for(const ch of chapters){
    if(!ch.mappings.length){issues.push(ch.name+'：尚未关联 Task 和 Solution。');continue;}
    for(const m of ch.mappings){
      const task=domainMock.tasks.find(t=>t.id===m.taskId&&t.domainId===book.domainId);
      if(!task||!m.methods.length||m.methods.some(id=>!task.methods.includes(id))||!m.sources.length||m.sources.some(id=>!ch.locations.some(l=>l.id===id)))issues.push(ch.name+'：映射尚未完整。');
    }
    if(collectKnowledge(ch.mappings.flatMap(m=>m.methods),book.domainId).issues.length)issues.push(ch.name+'：方法依赖尚未完整。');
  }return [...new Set(issues)];
}
export function acceptMapping(d:TextbookImport,chapterId:string){
  const book=importBook(d),chapter=book.units.flatMap(u=>u.chapters).find(c=>c.id===chapterId)!;
  if(d.sample==='bnu6a'){
    if(!chapter.items?.some(i=>i.blocks.some(b=>b.id==='B-CONDITIONS')))throw Error('统计活动的 Task / Claim 尚未准备，可先完成教材内容整理，不套用分数模型。');
    if(!chapter.checked)throw Error('请先核对本课内容。');
    if(!chapter.mappings.some(m=>m.taskId==='fraction-chain'))chapter.mappings.push({id:mockId('MAP'),taskId:'fraction-chain',methods:['S-CHAIN-A','S-CHAIN-B'],sources:chapter.locations.map(l=>l.id),reason:'第49—50页的跨页例题给出两层部分关系；两种教材解法分别对应逐层求量和先合并比例。练习中的其他任务尚未建立映射。'});
    recordBookChange(book,'采用连续比例例题的 mock 模型关联');return;
  }
  const page=d.pages.find(p=>p.chapterId===chapterId),fixture=page&&scanFixtures[page.fixture];
  const task=domainMock.tasks.find(t=>t.domainId===book.domainId&&t.id===fixture?.chapter);
  const method=fixture?.chapter==='fraction'?'S1-A':'S2-A';
  if(!task?.methods.includes(method))throw Error('当前领域没有这组 mock 候选，请手动关联已有定义或前往领域管理补充。');
  if(chapter.mappings.some(m=>m.taskId===task.id))return;
  chapter.mappings.push({id:mockId('MAP'),taskId:task.id,methods:[method],sources:chapter.locations.filter(l=>d.pages.some(p=>p.id===l.id&&p.resolved)).map(l=>l.id),reason:fixture?.chapter==='fraction'?'原页明确给出原量和增加比例，求增加后的总量；采用先求增加量再相加的方法。':'原页给定底与对应高，采用底乘高除以二。'});
  recordBookChange(book,'采用已核对的映射建议：'+chapter.name);
}
export function suggestTarget(d:TextbookImport){
  const book=importBook(d),chapters=book.units.flatMap(u=>u.chapters).filter(c=>c.checked&&c.mappings.length),target=blankTarget();
  Object.assign(target,{name:book.name+'·学习目标',description:'依据本次已准备章节生成的目标建议，请核对学习要求和达标标准后应用。',bookId:book.id,chapterIds:chapters.map(c=>c.id)});
  for(const claim of evaluationMock.claims.filter(c=>c.domainId===book.domainId&&chapters.some(ch=>ch.mappings.some(m=>m.taskId===c.taskId)))){
    const applicable=chapters.filter(ch=>ch.mappings.some(m=>m.taskId===claim.taskId));
    target.claims.push({claimId:claim.id,omissionReason:'',requirements:claim.aspects.filter(a=>a.applicable).map(a=>({id:mockId('REQ'),name:claim.name+'：'+a.name,chapterIds:applicable.map(ch=>ch.id),aspectIds:[a.id],standard:a.criterion}))});
  }
  if(!target.claims.length)throw Error('关联的任务还没有 Task Claim，请先补充评价定义。');
  target.history=[{at:new Date().toLocaleString('sv-SE'),change:'从已核对章节生成目标建议（mock），待管理员确认'}];
  targetMock.targets.unshift(target);d.targetId=target.id;return target;
}
export function applicationIssues(d:TextbookImport){
  const issues=mappingIssues(d),target=targetMock.targets.find(t=>t.id===d.targetId&&t.bookId===d.book.id);
  if(!target)return [...issues,'请选择或生成本教材的学习目标。'];
  if(!target.name.trim()||!target.claims.length)issues.push('学习目标及其具体要求尚未完整。');
  for(const s of target.claims)issues.push(...configurationIssues(target,s));
  return [...new Set(issues)];
}
