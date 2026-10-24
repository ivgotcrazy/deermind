<script setup lang="ts">
import CourseApplication from './CourseApplication.vue';
import TextbookImportWorkspace from './TextbookImportWorkspace.vue';
import ImportedScanPage from './ImportedScanPage.vue';
import MaterialReader from '../../../shared/MaterialReader.vue';
import { textbookImports, newImport } from '../workbench/textbook-import';
import { computed, ref, watch, nextTick } from 'vue';
import { route, go, setQuery, back } from '../workbench/navigation';
import { domainMock, collectKnowledge } from '../workbench/domain-mock';
import { evaluationMock } from '../workbench/evaluation-mock';
import { textbookMock, textbookNavigation, emptyChapter, emptyTextbook, mockId, recordBookChange, type MaterialChapter, type MaterialUnit, type SourceLocation, type MaterialSource } from '../workbench/textbook-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';
import ChapterMappingPanel from './ChapterMappingPanel.vue';

const copy=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
const location=window.location;
const importDraft=computed(()=>textbookImports.find(d=>d.book.id===route.id));
const book=computed(()=>textbookMock.books.find(b=>b.id===route.id));
const chapters=computed(()=>book.value?.units.flatMap(u=>u.chapters)||[]);
const chapter=computed(()=>chapters.value.find(c=>c.id===route.chapter));
const unit=computed(()=>book.value?.units.find(u=>u.chapters.some(c=>c.id===route.chapter)));
const domainName=(id:string)=>domainMock.domains.find(d=>d.id===id)?.name||'未关联领域';
const rows=computed(()=>textbookMock.books.filter(b=>(!route.domain||b.domainId===route.domain)&&[b.name,b.publisher,b.edition,b.grade].join(' ').toLowerCase().includes(route.q.trim().toLowerCase())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10))),page=computed(()=>Math.min(route.p,pages.value));
const nav=computed(()=>textbookNavigation[route.id]||{query:'',expanded:[]});
watch(()=>book.value?.id,()=>{if(book.value&&!textbookNavigation[book.value.id])textbookNavigation[book.value.id]={query:'',expanded:book.value.units.slice(0,1).map(u=>u.id)};},{immediate:true});
watch(()=>unit.value?.id,id=>{if(id&&!nav.value.expanded.includes(id))nav.value.expanded.push(id);},{immediate:true});
const units=computed(()=>book.value?.units.map(u=>({...u,chapters:u.name.includes(nav.value.query)?u.chapters:u.chapters.filter(c=>c.name.includes(nav.value.query))})).filter(u=>u.chapters.length||!nav.value.query)||[]);
const tabs=[{id:'content',name:'章节内容'},{id:'mapping',name:'领域映射'},{id:'readiness',name:'准备情况'}];
const tab=computed(()=>tabs.some(t=>t.id===route.tab)?route.tab:'content');
const source=computed(()=>chapter.value?.locations.find(s=>s.id===route.source)||(!route.source?chapter.value?.locations[0]:undefined));
const fileName=(id:string)=>book.value?.sources.find(f=>f.id===id)?.name||'来源文件缺失';
const sourceTitle=(s:SourceLocation)=>`${s.printedPage?'书页 '+s.printedPage:'文件第 '+s.filePage+' 页'} · ${s.label}`;
const taskName=(id:string)=>domainMock.tasks.find(t=>t.id===id)?.name||'任务不存在';
const claims=computed(()=>evaluationMock.claims.filter(c=>c.domainId===book.value?.domainId&&chapter.value?.mappings.some(m=>m.taskId===c.taskId)));
const sourceValid=(s:SourceLocation)=>!!book.value?.sources.some(f=>f.id===s.fileId)&&Number.isInteger(s.filePage)&&s.filePage>0&&!!s.label.trim()&&!!s.text.trim();
const mappingReady=computed(()=>!!chapter.value?.mappings.length&&chapter.value.mappings.every(m=>{
  const t=domainMock.tasks.find(t=>t.id===m.taskId&&t.domainId===book.value?.domainId);
  return t&&m.methods.length&&m.methods.every(id=>t.methods.includes(id))&&m.sources.length&&m.sources.every(id=>chapter.value?.locations.some(s=>s.id===id&&sourceValid(s)))&&m.reason.trim()&&!collectKnowledge(m.methods,book.value!.domainId).issues.length;
}));
const readiness=computed(()=>[
  {name:'来源定位',ready:!!chapter.value?.locations.length&&chapter.value.locations.every(sourceValid),detail:'文件、文件页码、书页码或题目位置及来源摘录。'},
  {name:'内容整理',ready:!!chapter.value?.content.trim(),detail:'本章供讲解和核对使用的整理内容。'},
  {name:'内容核对',ready:!!chapter.value?.checked,detail:chapter.value?.reviewNote||'尚未记录核对结果。'},
  {name:'任务与方法映射',ready:mappingReady.value,detail:'明确选择 Task、方法和来源，方法依赖可汇总；不等于语义正确性已验证。'},
]);
const notice=ref('');
function openBook(id:string){go('textbooks',{id,returnTo:window.location.hash});}
function selectChapter(id:string){setQuery({chapter:id,tab:tab.value,source:''});}
function locate(id:string){setQuery({tab:'content',source:id});nextTick(()=>document.getElementById('chapter-source')?.scrollIntoView({block:'start',behavior:'smooth'}));}
function toggleUnit(id:string){const i=nav.value.expanded.indexOf(id);if(i<0)nav.value.expanded.push(id);else nav.value.expanded.splice(i,1);}
function openClaim(id:string){go('evaluation',{id,tab:'definition',returnTo:window.location.hash});}
function tabKey(event:KeyboardEvent,i:number){const n=event.key==='ArrowRight'?(i+1)%tabs.length:event.key==='ArrowLeft'?(i+tabs.length-1)%tabs.length:-1;if(n<0)return;event.preventDefault();setQuery({tab:tabs[n]!.id});document.getElementById('chapter-tab-'+tabs[n]!.id)?.focus();}
type Editor='book'|'unit'|'chapter'|'content'|'source'|'file'|'review';
const editor=ref<Editor|null>(null),error=ref(''),errorNode=ref<HTMLElement>();
const bookDraft=ref(emptyTextbook()),unitDraft=ref<MaterialUnit>({id:'',name:'',chapters:[]}),chapterDraft=ref<MaterialChapter>(emptyChapter()),unitId=ref('');
const sourceDraft=ref<SourceLocation>({id:'',fileId:'',filePage:1,printedPage:'',label:'',text:''});
const fileDraft=ref<MaterialSource>({id:'',name:'',kind:'PDF'}),reviewChecked=ref(false),reviewNote=ref('');
const title=computed(()=>({book:'编辑教材信息',unit:unitDraft.value.id?'编辑单元':'新增单元',chapter:chapterDraft.value.id===chapter.value?.id?'编辑章节':'新增章节',content:'编辑整理内容',source:chapter.value?.locations.some(s=>s.id===sourceDraft.value.id)?'编辑来源定位':'添加来源定位',file:'添加来源文件',review:'记录内容核对结果'}[editor.value||'book']));
watch(()=>route.id+':'+route.chapter,()=>{editor.value=null;notice.value='';});
function start(kind:Editor){editor.value=kind;error.value='';}
function editBook(){bookDraft.value=copy(book.value!);start('book');}
function startImport(){go('textbooks',{tab:'import',source:newImport(route.domain)});}
function resumeImport(id:string){go('textbooks',{tab:'import',source:id});}
function editUnit(value?:MaterialUnit){unitDraft.value=value?copy(value):{id:'',name:'',chapters:[]};start('unit');}
function editChapter(value?:MaterialChapter,parent=unit.value?.id||book.value?.units[0]?.id||''){chapterDraft.value=value?copy(value):emptyChapter();unitId.value=parent;start('chapter');}
function editContent(){chapterDraft.value=copy(chapter.value!);start('content');}
function editSource(value?:SourceLocation){sourceDraft.value=value?copy(value):{id:mockId('LOC'),fileId:book.value?.sources[0]?.id||'',filePage:1,printedPage:'',label:'',text:''};start('source');}
function addFile(){fileDraft.value={id:mockId('SOURCE'),name:'',kind:'PDF'};start('file');}
function editReview(){reviewChecked.value=chapter.value!.checked;reviewNote.value=chapter.value!.reviewNote;start('review');}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}
function finish(change:string){recordBookChange(book.value!,change);editor.value=null;notice.value='已保存：'+change+'。';}
function save(){
  error.value='';
  if(editor.value==='book'){
    if(!bookDraft.value.name.trim())return fail('请填写教材名称。');
    if(!domainMock.domains.some(d=>d.id===bookDraft.value.domainId))return fail('请选择教材关联的领域。');
    const {name,publisher,edition,grade,subject,domainId,sourceNote}=bookDraft.value;Object.assign(book.value!,{name,publisher,edition,grade,subject,domainId,sourceNote});return finish('教材信息');
  }
  if(!book.value)return;
  if(editor.value==='unit'){
    if(!unitDraft.value.name.trim())return fail('请填写单元名称。');
    const u=book.value.units.find(u=>u.id===unitDraft.value.id);
    if(u)u.name=unitDraft.value.name;else{const id=mockId('UNIT');book.value.units.push({id,name:unitDraft.value.name,chapters:[]});nav.value.expanded.push(id);}
    return finish('教材单元');
  }
  if(editor.value==='chapter'){
    if(!chapterDraft.value.name.trim())return fail('请填写章节名称。');
    const parent=book.value.units.find(u=>u.id===unitId.value);if(!parent)return fail('请选择所属单元。');
    const current=chapters.value.find(c=>c.id===chapterDraft.value.id);
    if(current){current.name=chapterDraft.value.name;const old=book.value.units.find(u=>u.chapters.includes(current))!;if(old.id!==parent.id){old.chapters=old.chapters.filter(c=>c.id!==current.id);parent.chapters.push(current);}}
    else parent.chapters.push(copy(chapterDraft.value));
    if(!nav.value.expanded.includes(parent.id))nav.value.expanded.push(parent.id);
    nav.value.query='';finish('章节目录');setQuery({chapter:chapterDraft.value.id,source:''});return;
  }
  if(editor.value==='file'){
    if(!fileDraft.value.name.trim())return fail('请填写来源文件名称。');book.value.sources.push(copy(fileDraft.value));return finish('来源文件登记');
  }
  if(!chapter.value)return;
  if(editor.value==='content'){chapter.value.content=chapterDraft.value.content;chapter.value.checked=false;chapter.value.reviewNote='整理内容已修改，请重新核对。';return finish('章节整理内容');}
  if(editor.value==='source'){
    if(!sourceValid(sourceDraft.value))return fail('请补齐来源文件、有效的文件页码、位置名称和来源摘录。');
    const index=chapter.value.locations.findIndex(s=>s.id===sourceDraft.value.id);if(index<0)chapter.value.locations.push(copy(sourceDraft.value));else chapter.value.locations[index]=copy(sourceDraft.value);
    chapter.value.checked=false;chapter.value.reviewNote='来源定位或摘录已修改，请重新核对。';finish('来源定位');setQuery({source:sourceDraft.value.id});return;
  }
  if(editor.value==='review'){
    if(!reviewNote.value.trim())return fail('请记录核对依据或仍需处理的疑点。');
    if(reviewChecked.value&&(!chapter.value.content.trim()||!chapter.value.locations.length||!chapter.value.locations.every(sourceValid)))return fail('来源定位与整理内容尚未完整，不能标记为已核对。');
    chapter.value.checked=reviewChecked.value;chapter.value.reviewNote=reviewNote.value;finish('内容核对结果');
  }
}
</script>

<template><TextbookImportWorkspace v-if="route.tab==='import'"/><div v-else class="wb-page textbook-workspace">
  <template v-if="!route.id">
    <header class="page-header"><div><button v-if="route.returnTo.startsWith('#/observed-')" class="text-link" @click="back('objects')">← 返回观测来源</button><h2>教材管理</h2><p class="page-desc">整理教材目录与内容，明确每章的任务、方法和来源依据。</p></div><button class="btn primary" @click="startImport">导入教材</button></header>
    <section v-if="textbookImports.some(d=>d.state!=='applied')" class="panel import-drafts"><h3>尚未完成的导入</h3><div v-for="d in textbookImports.filter(d=>d.state!=='applied').slice(0,5)" :key="d.id" class="section-heading"><span>{{d.book.name||'未命名教材'}} · {{['选择扫描件','识别整理','内容核对','模型关联','目标与应用'][d.step]}}</span><button class="btn" :aria-label="'继续导入 '+(d.book.name||'未命名教材')" @click="resumeImport(d.id)">继续导入</button></div></section>
    <div class="toolbar"><label class="search-label">搜索教材<input :value="route.q" type="search" placeholder="名称、出版社、版次或年级" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})"/></label><label>领域<select :value="route.domain" aria-label="领域" @change="setQuery({domain:($event.target as HTMLSelectElement).value,p:1})"><option value="">全部领域</option><option v-for="d in domainMock.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><span class="muted">{{rows.length}} 本教材</span></div>
    <section class="table-card"><table class="data-table textbook-list"><thead><tr><th>教材</th><th>出版社 / 版次</th><th>学科与领域</th><th>整理进度</th><th></th></tr></thead><tbody><tr v-for="b in rows.slice((page-1)*10,page*10)" :key="b.id"><td><button class="text-link item-name" @click="openBook(b.id)">{{b.name}}</button><small>{{b.grade||'年级未登记'}}</small></td><td>{{b.publisher||'出版社未登记'}}<small>{{b.edition||'版次未登记'}}</small></td><td>{{b.subject||'学科未登记'}}<small>{{domainName(b.domainId)}}</small></td><td>{{b.units.flatMap(u=>u.chapters).length}} 个章节<small>{{b.units.flatMap(u=>u.chapters).filter(c=>c.checked).length}} 章内容已核对 · {{b.units.flatMap(u=>u.chapters).filter(c=>c.mappings.length).length}} 章已有映射</small></td><td><button class="text-link" :aria-label="'管理'+b.name" @click="openBook(b.id)">管理 →</button></td></tr></tbody></table><p v-if="!rows.length" class="empty">没有符合条件的教材。</p></section>
    <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page<=1" @click="setQuery({p:page-1})">上一页</button><span>{{page}} / {{pages}}</span><button class="btn" :disabled="page>=pages" @click="setQuery({p:page+1})">下一页</button></div>
  </template>
  <template v-else-if="book">
    <header class="page-header book-header"><div><button class="text-link" @click="back('textbooks')">← {{route.returnTo.startsWith('#/students')?'返回学生状态':route.returnTo.startsWith('#/objects')?'返回空间观测':route.returnTo.startsWith('#/activity?')?'返回交互审查':route.returnTo.startsWith('#/targets?')?'返回学习目标':route.returnTo.startsWith('#/learning-spaces?')?'返回学习空间':'返回教材列表'}}</button><h2>{{book.name}}</h2><p class="page-desc">{{book.publisher||'出版社未登记'}} · {{book.edition||'版次未登记'}} · {{book.grade||'年级未登记'}} · {{domainName(book.domainId)}}</p></div><button class="btn" @click="editBook">编辑教材信息</button></header>
    <p v-if="importDraft"><button class="btn" @click="resumeImport(importDraft.id)">继续导入整理</button></p><CourseApplication :book-id="book.id"/>
<div class="book-layout">
      <aside class="book-directory" aria-label="教材目录"><div class="directory-top"><strong>教材目录</strong><button class="text-link" @click="editUnit()">新增单元</button></div><input v-model="nav.query" aria-label="查找章节" type="search" placeholder="查找单元或章节"/><button class="overview-link" :class="{active:!route.chapter}" @click="setQuery({chapter:'',source:''})">教材概览</button>
        <nav aria-label="章节导航"><div v-for="u in units" :key="u.id" class="directory-unit"><div class="unit-heading"><button class="unit-toggle" :aria-expanded="nav.expanded.includes(u.id)||!!nav.query" @click="toggleUnit(u.id)"><span>{{nav.expanded.includes(u.id)||nav.query?'▾':'▸'}}</span>{{u.name}}<small>{{u.chapters.length}}</small></button><button class="text-link unit-edit" :aria-label="'编辑单元 '+u.name" @click="editUnit(book.units.find(x=>x.id===u.id))">编辑</button></div><div v-if="nav.expanded.includes(u.id)||nav.query" class="unit-chapters"><button v-for="c in u.chapters" :key="c.id" :class="{active:route.chapter===c.id}" :aria-current="route.chapter===c.id?'page':undefined" @click="selectChapter(c.id)">{{c.name}}<span v-if="!c.content" class="pending-dot" title="待整理"></span></button><button class="add-chapter" :aria-label="'在'+u.name+'新增章节'" @click="editChapter(undefined,u.id)">＋ 新增章节</button></div></div><p v-if="!units.length" class="empty">{{nav.query?'没有匹配的章节。':'尚无单元，可先新增。'}}</p></nav>
      </aside>
      <div class="chapter-workspace">
        <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
        <template v-if="!route.chapter">
          <section class="panel"><h3>教材概览</h3><p class="muted">{{book.sourceNote||'尚未登记来源说明。'}}</p><div class="book-summary"><div><strong>{{chapters.length}}</strong><span>章节</span></div><div><strong>{{chapters.filter(c=>c.checked).length}}</strong><span>内容已核对</span></div><div><strong>{{chapters.filter(c=>c.mappings.length).length}}</strong><span>已有任务映射</span></div></div><p class="muted">已有映射表示登记了任务关系，不表示覆盖完整或学生已经掌握。</p></section>
          <section class="panel"><div class="section-heading"><h3>来源文件</h3><button class="btn" @click="addFile">添加来源文件</button></div><table class="data-table"><thead><tr><th>文件</th><th>类型</th><th>已定位片段</th></tr></thead><tbody><tr v-for="f in book.sources" :key="f.id"><td>{{f.name}}</td><td>{{f.kind}}</td><td>{{chapters.flatMap(c=>c.locations).filter(s=>s.fileId===f.id).length}}</td></tr></tbody></table><p v-if="!book.sources.length" class="muted">尚未登记来源文件。</p></section>
          <details><summary>本次修改记录 · {{book.history.length}} 条</summary><p class="muted">修改记录与教材的印刷版次分开；本次预览不更新真实学习空间。</p><div v-for="(h,i) in book.history" :key="i" class="list-row"><span>{{h.change}}</span><span>{{h.at}}</span></div></details>
        </template>
        <template v-else-if="chapter">
          <header class="chapter-header"><div><p class="muted">{{unit?.name}}</p><h3>{{chapter.name}}</h3></div><button class="btn" @click="editChapter(chapter)">编辑章节</button></header>
          <div class="chapter-tabs" role="tablist" aria-label="章节工作区"><button v-for="(t,i) in tabs" :id="'chapter-tab-'+t.id" :key="t.id" role="tab" :aria-selected="tab===t.id" :aria-controls="'chapter-panel-'+t.id" :tabindex="tab===t.id?0:-1" :class="{active:tab===t.id}" @click="setQuery({tab:t.id})" @keydown="tabKey($event,i)">{{t.name}}</button></div>
          <div :id="'chapter-panel-'+tab" role="tabpanel" :aria-labelledby="'chapter-tab-'+tab">
            <template v-if="tab==='content'">
              <div class="content-pair"><section id="chapter-source" class="panel source-panel"><div class="section-heading"><h3>教材来源</h3><button class="btn" @click="editSource()">添加来源定位</button></div><label v-if="chapter.locations.length">位置<select :value="source?.id||''" aria-label="来源位置" @change="setQuery({source:($event.target as HTMLSelectElement).value})"><option v-if="!source" value="">请选择来源</option><option v-for="s in chapter.locations" :key="s.id" :value="s.id">{{sourceTitle(s)}}</option></select></label>
                <template v-if="source"><div class="source-address"><span>{{fileName(source.fileId)}}</span><strong>文件第 {{source.filePage}} 页{{source.printedPage?' · 书页 '+source.printedPage:''}} · {{source.label}}</strong><button class="text-link" @click="editSource(source)">编辑来源定位</button></div><img v-if="source.image" :src="source.image" :alt="'真实教材第'+source.printedPage+'页'" style="width:100%"/><ImportedScanPage v-else-if="importDraft?.pages.some(p=>p.id===source!.id)" :fixture="importDraft.pages.find(p=>p.id===source!.id)!.fixture"/><div v-else class="source-sheet" :class="{located:!!route.source}" tabindex="0"><span class="mock-stamp">原页内容示意 · Mock</span><h4>{{source.label}}</h4><p>{{source.text}}</p><footer>{{source.printedPage||'未标书页码'}}</footer></div></template>
                <p v-else class="empty">{{route.source?'这个来源位置不存在，请重新选择。':'尚无来源定位。添加文件页码与例题、练习位置。'}}</p>
              </section><section class="panel prepared-panel"><div class="section-heading"><h3>整理内容</h3><button v-if="chapter.items" class="btn" @click="resumeImport(importDraft!.id)">打开整理工作区</button><button v-else class="btn" @click="editContent">编辑整理内容</button></div><MaterialReader v-if="chapter.items" :items="chapter.items" :related-items="chapters.flatMap(c=>c.items||[])"/><p v-else class="content-text">{{chapter.content||'尚未整理。本章内容可以在对照来源后补充。'}}</p><div class="review-row"><span class="badge" :class="chapter.checked?'green':'amber'">{{chapter.checked?'内容已核对':'待核对'}}</span><button class="text-link" @click="editReview">记录核对结果</button></div><p class="muted">{{chapter.reviewNote||'尚未记录核对结果。'}}</p></section></div>
            </template>
            <ChapterMappingPanel v-else-if="tab==='mapping'" :key="chapter.id" :book="book" :chapter="chapter" @locate="locate"/>
            <template v-else>
              <section class="table-card"><table class="data-table readiness-table"><thead><tr><th>准备项</th><th>情况</th><th>依据</th></tr></thead><tbody><tr v-for="r in readiness" :key="r.name"><td>{{r.name}}</td><td><span class="badge" :class="r.ready?'green':'amber'">{{r.ready?'已具备':'待补充'}}</span></td><td>{{r.detail}}</td></tr></tbody></table></section><p class="muted">这里反映材料准备情况，不是审批步骤，也不表示已接通正式教学或评价。</p>
              <section class="panel claim-reference"><div class="section-heading"><h3>可参考的评价定义</h3><button class="text-link" @click="go('targets',{filter:book.id,chapter:chapter.id,returnTo:location.hash})">前往目标管理 →</button></div><p class="muted">按本章映射任务查找当前 Claim，供配置学习目标时参考；不自动采用，也不把“存在 Claim”当成达标。</p><table class="data-table"><thead><tr><th>Task Claim</th><th>对应任务</th><th>评价方面</th></tr></thead><tbody><tr v-for="c in claims" :key="c.id"><td><button class="text-link" @click="openClaim(c.id)">{{c.name}} ↗</button></td><td>{{taskName(c.taskId)}}</td><td>{{c.aspects.filter(a=>a.applicable).map(a=>a.name).join('、')}}</td></tr></tbody></table><p v-if="!claims.length" class="muted">当前任务尚无可参考的 Claim，或本章还没有任务映射。</p></section>
            </template>
          </div>
        </template>
        <section v-else class="panel"><h3>章节不存在</h3><p>请从本教材目录重新选择章节。</p><button class="btn" @click="setQuery({chapter:'',source:''})">返回教材概览</button></section>
      </div>
    </div>
  </template>
  <section v-else class="panel"><h2>未找到这本教材</h2><p>当前为新的交互示例，请从教材列表选择。导入草稿及已应用内容保存在本浏览器。</p><button class="btn" @click="go('textbooks')">返回教材列表</button></section>

  <WorkbenchDialog v-if="editor" :title="title" wide @close="editor=null"><form @submit.prevent="save" novalidate><p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
    <template v-if="editor==='book'">
      <label>教材名称<input v-model="bookDraft.name" maxlength="160"/></label><div class="field-pair"><label>出版社 / 编写方<input v-model="bookDraft.publisher" placeholder="内部教材可填写编写机构"/></label><label>教材版次<input v-model="bookDraft.edition" placeholder="例如：2025 年第 1 版"/></label></div><div class="field-pair"><label>年级 / 适用对象<input v-model="bookDraft.grade"/></label><label>学科<input v-model="bookDraft.subject"/></label></div><label>关联领域<select v-model="bookDraft.domainId" aria-label="关联领域" :disabled="editor==='book'&&chapters.some(c=>c.mappings.length)"><option value="">请选择</option><option v-for="d in domainMock.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><p v-if="editor==='book'&&chapters.some(c=>c.mappings.length)" class="muted">已有章节映射，不能在这里直接替换关联领域。</p><label>来源说明<textarea v-model="bookDraft.sourceNote" rows="2"/></label>
    </template>
    <label v-else-if="editor==='unit'">单元名称<input v-model="unitDraft.name"/></label>
    <template v-else-if="editor==='chapter'"><label>所属单元<select v-model="unitId" aria-label="所属单元"><option v-for="u in book?.units" :key="u.id" :value="u.id">{{u.name}}</option></select></label><label>章节名称<input v-model="chapterDraft.name"/></label><p class="muted">章节内容、来源定位及领域映射分别在章节工作区维护。</p></template>
    <template v-else-if="editor==='content'"><p class="muted">当前章节：{{chapter?.name}}。修改后需要重新核对内容。</p><label>整理内容<textarea v-model="chapterDraft.content" rows="12"/></label></template>
    <template v-else-if="editor==='source'"><label>来源文件<select v-model="sourceDraft.fileId" aria-label="来源文件"><option v-for="f in book?.sources" :key="f.id" :value="f.id">{{f.name}}</option></select></label><div class="field-pair"><label>文件页码<input v-model.number="sourceDraft.filePage" type="number" min="1" step="1"/></label><label>印刷书页码<input v-model="sourceDraft.printedPage" placeholder="可留空；与文件页码分开"/></label></div><label>页内位置<input v-model="sourceDraft.label" placeholder="例如：例 2、练习 3 或第二段"/></label><label>来源摘录（Mock 预览）<textarea v-model="sourceDraft.text" rows="5"/></label><p class="muted">这里演示页内定位，不修改原文件；来源摘录仅用于当前 mock。</p></template>
    <template v-else-if="editor==='file'"><label>文件名称<input v-model="fileDraft.name" placeholder="例如：补充练习.pdf"/></label><label>来源类型<select v-model="fileDraft.kind"><option>PDF</option><option>扫描图片</option><option>手工录入</option></select></label><p class="muted">登记示例来源后，可在章节中添加具体页码和位置。</p></template>
    <template v-else><label>核对结果<select v-model="reviewChecked" aria-label="核对结果"><option :value="false">仍待核对 / 有未解决疑点</option><option :value="true">本章内容已核对</option></select></label><label>核对依据与疑点<textarea v-model="reviewNote" rows="5"/></label><p class="muted">仅记录内容核对，不审批发布，也不评价学生。</p></template>
    <div class="dialog-footer button-row"><button type="button" class="btn" @click="editor=null">取消</button><button class="btn primary" type="submit">保存</button></div>
  </form></WorkbenchDialog>
</div></template>

<style scoped>
.textbook-workspace{max-width:1600px}.textbook-list th:first-child{width:30%}.textbook-list th:nth-child(2){width:23%}.textbook-list th:last-child{width:80px}.item-name{font-size:14px;font-weight:600}.book-header h2{margin-top:10px}.book-header{align-items:center}.book-layout{display:grid;grid-template-columns:236px minmax(0,1fr);gap:24px;align-items:start}.book-directory{position:sticky;top:16px;max-height:calc(100vh - 120px);display:flex;flex-direction:column;background:#fff;border:1px solid #e1e8ed;border-radius:9px;padding:14px 10px;min-width:0}.directory-top{display:flex;align-items:center;justify-content:space-between;font-size:14px;margin:0 6px 10px}.book-directory input{font-size:12px;margin:0 0 12px}.book-directory nav{overflow:auto;min-height:0}.overview-link{display:block;padding:10px 9px;border:0;border-radius:5px;color:#5c7465;background:transparent;text-align:left;font-size:13px;margin-bottom:8px}.overview-link.active,.unit-chapters button.active{background:#eaf3ed;color:#245d40;font-weight:600}.unit-heading{display:flex;align-items:center;gap:6px}.unit-toggle{display:flex;align-items:baseline;gap:6px;padding:12px 4px;border:0;background:none;text-align:left;color:#405a4b;font-size:13px;flex:1;min-width:0}.unit-toggle small{margin-left:auto;color:#85968a}.unit-edit{font-size:11px}.directory-unit+.directory-unit{border-top:1px solid #eef2ef}.unit-chapters{padding:0 0 8px 14px}.unit-chapters>button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:transparent;border:0;border-radius:5px;font-size:12px;line-height:1.7;padding:9px 8px;color:#637b6b}.unit-chapters>button:hover,.overview-link:hover{background:#f2f7f3}.pending-dot{width:5px;height:5px;background:#beac7b;border-radius:50%;flex-shrink:0;margin-left:auto}.unit-chapters .add-chapter{color:#87998c;padding:6px 8px}.chapter-workspace{min-width:0}.chapter-header{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:10px}.chapter-header h3{font-size:21px;color:#294b38;margin:4px 0}.chapter-header p{margin:0}.chapter-tabs{display:flex;gap:26px;border-bottom:1px solid #dbe5df;margin:18px 0 20px}.chapter-tabs button{padding:10px 2px 13px;border:0;border-bottom:3px solid transparent;background:none;color:#6b7e72;font-size:14px}.chapter-tabs button.active{color:#286246;font-weight:600;border-bottom-color:#2d6a4f}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:12px}.section-heading h3{margin:0}.section-heading>.btn{flex-shrink:0}.book-summary{display:flex;gap:42px;margin:24px 0}.book-summary>div{display:flex;align-items:baseline;gap:10px;font-size:12px;color:#728779}.book-summary strong{font-size:26px;font-weight:500;color:#315b42}.content-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}.content-pair .panel{padding:18px}.source-address{display:flex;flex-direction:column;gap:7px;font-size:12px;color:#6b7d71;margin:14px 0}.source-address strong{font-weight:500;color:#405c4b}.source-sheet{background:#fcfbf7;border:1px solid #e4e1d7;padding:22px 20px;min-height:260px;line-height:2;scroll-margin:20px}.source-sheet.located{border-color:#83ac92;box-shadow:0 0 0 2px #e5f0e8}.source-sheet p,.content-text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.95}.source-sheet h4{margin:16px 0 12px}.source-sheet footer{text-align:center;font-size:12px;color:#9b9d8e;margin-top:32px}.mock-stamp{font-size:11px;color:#9a9988}.source-panel{scroll-margin-top:16px}.review-row{display:flex;justify-content:space-between;align-items:center;gap:12px;border-top:1px solid #edf1ee;padding-top:18px;margin-top:24px}.prepared-panel .content-text{margin:16px 0 30px}.readiness-table th:first-child{width:145px}.readiness-table th:nth-child(2){width:90px}.claim-reference{margin-top:24px}.claim-reference .muted{margin:8px 0 16px}.saved-note{font-size:13px;color:#2d6a4f}.field-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px}.dialog-footer{justify-content:flex-end}.import-source{background:#f5f8f6;border:1px solid #e0e8e2;border-radius:8px;padding:16px;margin-bottom:18px}.import-source .section-heading{font-size:14px}@media(max-width:1350px){.book-layout{grid-template-columns:215px minmax(0,1fr);gap:18px}.content-pair{grid-template-columns:1fr}.book-summary{gap:26px}.book-summary>div{flex-direction:column;gap:0}.chapter-header h3{font-size:19px}}@media(max-width:900px){.book-layout{grid-template-columns:185px minmax(0,1fr);gap:14px}.book-directory{padding:10px 6px}.unit-edit{font-size:10px}.field-pair{grid-template-columns:1fr;gap:0}.book-summary{gap:22px}.textbook-list{min-width:600px}.table-card{overflow:auto}}
</style>
