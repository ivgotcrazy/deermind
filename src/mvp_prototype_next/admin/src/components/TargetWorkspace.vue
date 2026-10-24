<script setup lang="ts">
import CourseApplication from './CourseApplication.vue';
import { computed, ref, watch, nextTick } from 'vue';
import { route as routeSource, go, setQuery, back } from '../workbench/navigation';
import { textbookMock } from '../workbench/textbook-mock';
import { domainMock } from '../workbench/domain-mock';
import { evaluationMock } from '../workbench/evaluation-mock';
import { targetMock, blankTarget, targetBook, targetClaim, allChapters, mappedChapters, configurationIssues, recordTargetChange, type MockTarget } from '../workbench/target-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';
import TargetClaimPanel from './TargetClaimPanel.vue';
const location=window.location;
const route=routeSource;
const copy=<T,>(v:T):T=>JSON.parse(JSON.stringify(v));
const target=computed(()=>targetMock.targets.find(t=>t.id===route.id));
const book=computed(()=>target.value?targetBook(target.value):undefined);
const chapters=computed(()=>target.value?allChapters(target.value.bookId).filter(ch=>target.value!.chapterIds.includes(ch.id)):[]);
const selection=computed(()=>target.value?.claims.find(s=>s.claimId===route.claim));
const taskName=(id:string)=>domainMock.tasks.find(t=>t.id===id)?.name||'任务不存在';
const claimName=(id:string)=>targetClaim(id)?.name||'Claim 不存在';
const totalRequirements=(t:MockTarget)=>t.claims.reduce((sum,s)=>sum+s.requirements.length,0);
const pending=(t:MockTarget)=>t.claims.filter(s=>configurationIssues(t,s).length).length;
const list=computed(()=>targetMock.targets.filter(t=>(!route.filter||t.bookId===route.filter)&&(!route.chapter||t.chapterIds.includes(route.chapter))&&(t.name+' '+t.description+' '+(targetBook(t)?.name||'')).toLowerCase().includes(route.q.trim().toLowerCase())));
const listPages=computed(()=>Math.max(1,Math.ceil(list.value.length/10))),listPage=computed(()=>Math.min(route.p,listPages.value));
const claimRows=computed(()=>target.value?.claims.filter(s=>(claimName(s.claimId)+' '+taskName(targetClaim(s.claimId)?.taskId||'')).toLowerCase().includes(route.q.trim().toLowerCase()))||[]);
const claimPages=computed(()=>Math.max(1,Math.ceil(claimRows.value.length/10))),claimPage=computed(()=>Math.min(route.p,claimPages.value));
const taskIds=computed(()=>[...new Set(chapters.value.flatMap(ch=>ch.mappings.map(m=>m.taskId)))]);
const candidates=computed(()=>evaluationMock.claims.filter(c=>c.domainId===book.value?.domainId&&taskIds.value.includes(c.taskId)&&!target.value?.claims.some(s=>s.claimId===c.id)));
const candidateQuery=ref('');
const filteredCandidates=computed(()=>candidates.value.filter(c=>(c.name+' '+taskName(c.taskId)).toLowerCase().includes(candidateQuery.value.toLowerCase())));
const candidatePage=ref(1),candidatePages=computed(()=>Math.max(1,Math.ceil(filteredCandidates.value.length/10)));
watch(candidateQuery,()=>candidatePage.value=1);
const notice=ref(''),editor=ref<'new'|'basic'|'scope'|'claim'|'remove'|null>(null),draft=ref<MockTarget>(blankTarget()),error=ref(''),errorNode=ref<HTMLElement>(),removeId=ref('');
const editingBook=computed(()=>textbookMock.books.find(b=>b.id===draft.value.bookId));
const scopeConflicts=computed(()=>target.value?.claims.flatMap(s=>{
  const c=targetClaim(s.claimId),next=allChapters(draft.value.bookId).filter(ch=>draft.value.chapterIds.includes(ch.id)&&ch.mappings.some(m=>m.taskId===c?.taskId));
  return !next.length||s.requirements.some(r=>r.chapterIds.some(id=>!next.some(ch=>ch.id===id)))?[claimName(s.claimId)]:[];
})||[]);
watch(()=>route.id+':'+route.claim,()=>{editor.value=null;notice.value='';});
function openTarget(id:string){go('targets',{id,returnTo:location.hash});}
function showClaim(id:string){setQuery({claim:id});nextTick(()=>document.querySelector('.page-container')?.scrollTo({top:0}));}
function openBook(chapter='',tab='mapping'){if(target.value)go('textbooks',{id:target.value.bookId,chapter,tab,returnTo:location.hash});}
function openTask(id:string){go('domain',{domain:book.value?.domainId,filter:'task',id,returnTo:location.hash});}
function openEvaluation(){go('evaluation',{domain:book.value?.domainId,returnTo:location.hash});}
function edit(kind:'new'|'basic'|'scope'|'claim'){
  draft.value=kind==='new'?blankTarget():copy(target.value!);error.value='';editor.value=kind;candidateQuery.value='';candidatePage.value=1;
  if(kind==='new'){draft.value.bookId=route.filter||(textbookMock.books.length===1?textbookMock.books[0]!.id:'');draft.value.chapterIds=allChapters(draft.value.bookId).some(ch=>ch.id===route.chapter)?[route.chapter]:[];}
}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}
function save(){
  if(editor.value==='basic'||editor.value==='new'){
    if(!draft.value.name.trim())return fail('请填写学习目标名称。');
    if(editor.value==='basic'){target.value!.name=draft.value.name.trim();target.value!.description=draft.value.description;recordTargetChange(target.value!,'修改目标基本信息');editor.value=null;notice.value='目标信息已保存。';return;}
  }
  if(!editingBook.value||!draft.value.chapterIds.length||draft.value.chapterIds.some(id=>!allChapters(draft.value.bookId).some(ch=>ch.id===id)))return fail('请选择教材和至少一个有效章节。');
  if(editor.value==='scope'&&scopeConflicts.value.length)return fail('这些 Claim 或学习要求仍引用将移除的章节：'+scopeConflicts.value.join('、')+'。请先调整要求的所属章节或移除对应引用，再缩小范围。');
  if(editor.value==='new'){
    draft.value.name=draft.value.name.trim();draft.value.history=[{at:new Date().toLocaleString('sv-SE'),change:'创建学习目标'}];const next=copy(draft.value);targetMock.targets.unshift(next);editor.value=null;go('targets',{id:next.id,returnTo:location.hash});
  }else{target.value!.chapterIds=[...draft.value.chapterIds];recordTargetChange(target.value!,'修改目标章节范围');editor.value=null;notice.value='章节范围已保存；新增章节不会自动带入 Claim 或生成学习要求。';}
}
function addClaim(id:string){if(!target.value||!candidates.value.some(c=>c.id===id))return;target.value.claims.push({claimId:id,requirements:[],omissionReason:''});recordTargetChange(target.value,'纳入 Claim：'+claimName(id));editor.value=null;showClaim(id);}
function confirmRemove(id:string){removeId.value=id;editor.value='remove';}
function remove(){if(!target.value)return;target.value.claims=target.value.claims.filter(s=>s.claimId!==removeId.value);recordTargetChange(target.value,'移除目标中的 Claim：'+claimName(removeId.value));editor.value=null;setQuery({claim:''});notice.value='已移除此目标中的 Claim 引用及其要求，共享 Claim 未删除。';}
</script>
<template><div class="wb-page target-workspace">
  <template v-if="!route.id">
    <header class="page-header"><div><button v-if="route.returnTo" class="text-link" @click="back('textbooks')">← {{route.returnTo.startsWith('#/textbooks')?'返回教材章节':'返回观测来源'}}</button><h2>目标管理</h2><p class="page-desc">选择课程范围，按 Task Claim 组织具体学习要求与达标标准。</p></div><button class="btn primary" @click="edit('new')">新建目标</button></header>
    <div class="toolbar"><label class="search-label">搜索目标<input type="search" :value="route.q" placeholder="名称、说明或教材" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})"/></label><label>教材<select :value="route.filter" aria-label="筛选教材" @change="setQuery({filter:($event.target as HTMLSelectElement).value,chapter:'',p:1})"><option value="">全部教材</option><option v-for="b in textbookMock.books" :key="b.id" :value="b.id">{{b.name}}</option></select></label><span class="muted">{{list.length}} 个目标</span></div>
    <p v-if="route.chapter" class="context-filter">当前章节：{{allChapters(route.filter).find(ch=>ch.id===route.chapter)?.name||route.chapter}} <button class="text-link" @click="setQuery({chapter:'',p:1})">查看其他章节目标</button></p>
    <section class="table-card"><table class="data-table target-list"><thead><tr><th>目标</th><th>教材 / 范围</th><th>Claim / 学习要求</th><th>配置情况</th><th></th></tr></thead><tbody><tr v-for="t in list.slice((listPage-1)*10,listPage*10)" :key="t.id"><td><button class="text-link item-name" @click="openTarget(t.id)">{{t.name}}</button><small>{{t.description}}</small></td><td>{{targetBook(t)?.name||'教材不存在'}}<small>{{t.chapterIds.length}} 个章节</small></td><td>{{t.claims.length}} 项 Claim<small>{{totalRequirements(t)}} 项学习要求</small></td><td><span class="badge" :class="!t.claims.length||pending(t)?'amber':'green'">{{!t.claims.length?'尚未选择 Claim':pending(t)?pending(t)+' 项配置待核对':'要求已填写'}}</span></td><td><button class="text-link" :aria-label="'查看目标 '+t.name" @click="openTarget(t.id)">查看 →</button></td></tr></tbody></table><p v-if="!list.length" class="empty">没有符合条件的目标，可调整筛选或新建。</p></section>
    <div v-if="listPages>1" class="pagination"><button class="btn" :disabled="listPage<=1" @click="setQuery({p:listPage-1})">上一页</button><span>{{listPage}} / {{listPages}}</span><button class="btn" :disabled="listPage>=listPages" @click="setQuery({p:listPage+1})">下一页</button></div>
  </template>
  <template v-else-if="target">
    <header class="page-header target-header"><div><button class="text-link" @click="back('targets')">← {{route.returnTo.startsWith('#/students')?'返回学生状态':route.returnTo.startsWith('#/objects')?'返回空间观测':route.returnTo.startsWith('#/activity?')?'返回交互审查':route.returnTo.startsWith('#/learning-spaces?')?'返回学习空间':'返回目标列表'}}</button><h2>{{target.name}}</h2><p class="page-desc">{{target.description||'尚未填写目标说明'}}</p><div class="target-context"><button class="text-link" @click="openBook()">{{book?.name||'教材不存在'}} ↗</button><span>{{target.chapterIds.length}} 章 · {{target.claims.length}} 项 Claim · {{totalRequirements(target)}} 项要求</span></div></div><button class="btn" @click="edit('basic')">编辑目标信息</button></header>
<CourseApplication :book-id="target.bookId" :target-id="target.id"/>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <template v-if="!route.claim">
      <section class="panel scope-panel"><div class="section-heading"><h3>教材与章节范围</h3><button class="btn" @click="edit('scope')">编辑章节范围</button></div><div class="chapter-links"><button v-for="ch in chapters" :key="ch.id" class="text-link" @click="openBook(ch.id)">{{ch.name}} ↗</button></div><p v-if="chapters.length!==target.chapterIds.length" class="callout amber">部分章节已不存在，请检查范围。</p>
        <details><summary>查看 {{taskIds.length}} 项映射任务及 Claim 准备情况</summary><table class="data-table coverage-table"><thead><tr><th>映射任务</th><th>来源章节</th><th>评价定义</th></tr></thead><tbody><tr v-for="id in taskIds" :key="id"><td><button class="text-link" @click="openTask(id)">{{taskName(id)}} ↗</button></td><td>{{chapters.filter(ch=>ch.mappings.some(m=>m.taskId===id)).map(ch=>ch.name).join('、')}}</td><td>{{evaluationMock.claims.some(c=>c.domainId===book?.domainId&&c.taskId===id)?'已有 Claim，可选择纳入':'尚无 Claim'}}<button v-if="!evaluationMock.claims.some(c=>c.domainId===book?.domainId&&c.taskId===id)" class="text-link" @click="openEvaluation">前往评估模型管理 →</button></td></tr></tbody></table><p v-if="!taskIds.length" class="muted">这些章节尚无任务映射，请先在教材管理中准备。</p><p class="muted">映射任务是候选范围，不强制全部纳入目标；未纳入的任务不会自动成为学生的达标要求。</p></details>
      </section>
      <div class="section-heading"><div><h3>Task Claim 与学习要求</h3><p class="muted">每个 Claim 分别配置要求、采用方面和达标标准。</p></div><button class="btn primary" @click="edit('claim')">纳入 Claim</button></div>
      <label class="claim-search">查找已纳入的 Claim<input type="search" :value="route.q" placeholder="Claim 或任务名称" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})"/></label>
      <section class="table-card"><table class="data-table target-claims"><thead><tr><th>Claim / 任务</th><th>对应章节</th><th>学习要求</th><th>配置情况</th><th></th></tr></thead><tbody><tr v-for="s in claimRows.slice((claimPage-1)*10,claimPage*10)" :key="s.claimId"><td><button class="text-link item-name" @click="showClaim(s.claimId)">{{claimName(s.claimId)}}</button><small>{{taskName(targetClaim(s.claimId)?.taskId||'')}}</small></td><td>{{mappedChapters(target,s.claimId).map(ch=>ch.name).join('、')||'未映射'}}</td><td>{{s.requirements.length}} 项<small>{{[...new Set(s.requirements.flatMap(r=>r.aspectIds))].map(id=>targetClaim(s.claimId)?.aspects.find(a=>a.id===id)?.name||'方面失效').join('、')||'尚未配置'}}</small></td><td><span class="badge" :class="configurationIssues(target,s).length?'amber':'green'">{{configurationIssues(target,s).length?'待核对':'要求已填写'}}</span><small>{{configurationIssues(target,s)[0]||'具体标准仍需人工核对'}}</small></td><td><button class="btn" :aria-label="'配置 '+claimName(s.claimId)" @click="showClaim(s.claimId)">配置要求</button><button class="text-link remove-claim" :aria-label="'移除 Claim '+claimName(s.claimId)" @click="confirmRemove(s.claimId)">移除</button></td></tr></tbody></table><p v-if="!claimRows.length" class="empty">{{route.q?'没有匹配的 Claim。':'尚未纳入 Claim。先从所选章节的任务中选择，再填写学习要求。'}}</p></section>
      <div v-if="claimPages>1" class="pagination"><button class="btn" :disabled="claimPage<=1" @click="setQuery({p:claimPage-1})">上一页</button><span>{{claimPage}} / {{claimPages}}</span><button class="btn" :disabled="claimPage>=claimPages" @click="setQuery({p:claimPage+1})">下一页</button></div>
      <details class="history"><summary>本次修改记录 · {{target.history.length}} 条</summary><div v-for="(h,i) in target.history" :key="i" class="list-row"><span>{{h.change}}</span><small>{{h.at}}</small></div></details><p class="muted">本页保存目标定义，不修改学生 Belief，应用更新后同步到引用空间；旧活动继续使用原记录。</p>
    </template>
    <template v-else-if="selection"><button class="text-link claim-back" @click="setQuery({claim:''})">← 返回本目标的 Claim 列表</button><TargetClaimPanel :key="selection.claimId" :target="target" :selection="selection"/></template>
    <section v-else class="panel"><h3>此 Claim 未纳入当前目标</h3><button class="btn" @click="setQuery({claim:''})">返回本目标</button></section>
  </template>
  <section v-else class="panel"><h2>未找到这个目标</h2><p>旧版目标仍保留在历史示例中；当前目标管理使用新版教材和 Claim。请从列表选择，刷新后临时创建的目标也会重置。</p><button class="btn" @click="go('targets')">返回目标列表</button></section>
  <WorkbenchDialog v-if="editor" :title="({new:'新建学习目标',basic:'编辑目标信息',scope:'编辑章节范围',claim:'从章节任务中纳入 Claim',remove:'移除目标中的 Claim'})[editor]" wide @close="editor=null">
    <template v-if="editor==='claim'"><p class="muted">仅列出当前教材所选章节中已映射任务的 Claim。纳入后仍须核对方法条件并填写具体学习要求。</p><label>查找候选 Claim<input v-model="candidateQuery" type="search" placeholder="Claim 或任务名称"/></label><table class="data-table candidate-table"><thead><tr><th>Claim / 任务</th><th>映射章节</th><th></th></tr></thead><tbody><tr v-for="c in filteredCandidates.slice((candidatePage-1)*10,candidatePage*10)" :key="c.id"><td>{{c.name}}<small>{{taskName(c.taskId)}}</small></td><td>{{mappedChapters(target!,c.id).map(ch=>ch.name).join('、')}}</td><td><button class="btn primary" :aria-label="'纳入 '+c.name" @click="addClaim(c.id)">纳入目标</button></td></tr></tbody></table><p v-if="!filteredCandidates.length" class="empty">{{candidateQuery?'没有匹配的候选。':'没有可新增的 Claim；可能已全部纳入，或尚未定义。'}}</p><div v-if="candidatePages>1" class="pagination"><button class="btn" :disabled="candidatePage<=1" @click="candidatePage--">上一页</button><span>{{candidatePage}} / {{candidatePages}}</span><button class="btn" :disabled="candidatePage>=candidatePages" @click="candidatePage++">下一页</button></div><div class="dialog-footer"><button class="btn" @click="editor=null">关闭</button></div></template>
    <template v-else-if="editor==='remove'"><p>将从“{{target?.name}}”移除“{{claimName(removeId)}}”及其 {{target?.claims.find(s=>s.claimId===removeId)?.requirements.length||0}} 项学习要求。</p><p class="muted">共享 Claim、教材映射和学习记录不会删除。</p><div class="dialog-footer button-row"><button class="btn" @click="editor=null">取消</button><button class="btn danger-btn" @click="remove">确认移除 Claim</button></div></template>
    <form v-else @submit.prevent="save" novalidate><p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
      <template v-if="editor!=='scope'"><label>目标名称<input v-model="draft.name"/></label><label>目标说明<textarea v-model="draft.description" rows="3" placeholder="说明课程范围、目的和适用对象"/></label></template>
      <template v-if="editor!=='basic'"><label>关联教材<select v-model="draft.bookId" aria-label="关联教材" :disabled="editor==='scope'" @change="draft.chapterIds=[]"><option value="">请选择</option><option v-for="b in textbookMock.books" :key="b.id" :value="b.id">{{b.name}}</option></select></label><p class="muted">选定范围后，从章节映射中选择 Task Claim；没有映射或 Claim 的内容不会假装已准备完成。</p><fieldset v-for="u in editingBook?.units" :key="u.id" class="chapter-group"><legend>{{u.name}}</legend><label v-for="ch in u.chapters" :key="ch.id" class="check-label"><input v-model="draft.chapterIds" type="checkbox" :value="ch.id"/>{{ch.name}}<small v-if="!ch.mappings.length">尚无任务映射</small></label></fieldset><p v-if="editor==='scope'&&scopeConflicts.length" class="callout amber">当前选择会移除已有要求依赖的章节：{{scopeConflicts.join('、')}}。请先调整这些要求或移除引用；这里不会静默删除它们。</p></template>
      <div class="dialog-footer button-row"><button type="button" class="btn" @click="editor=null">取消</button><button class="btn primary" type="submit">{{editor==='new'?'创建目标':'保存'}}</button></div>
    </form>
  </WorkbenchDialog>
</div></template>
<style scoped>
.target-workspace{max-width:1500px}.page-header h2{margin-top:8px}.target-header>.btn{flex-shrink:0}.target-header{align-items:center}.target-context{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin-top:12px}.target-context>span{font-size:12px;color:#73867a}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 14px}.section-heading h3{font-size:17px;margin:0}.section-heading p{margin:5px 0 0}.section-heading>.btn{flex-shrink:0}.chapter-links{display:flex;gap:14px 24px;flex-wrap:wrap}.item-name{font-size:14px;font-weight:600}.target-list th:first-child{width:31%}.target-list th:nth-child(2){width:25%}.target-claims th:first-child{width:27%}.target-claims th:nth-child(2){width:16%}.target-claims th:nth-child(3){width:19%}.target-claims th:last-child{width:100px}.claim-search{max-width:420px;margin:14px 0}.remove-claim{display:block;margin:10px auto 0;color:#8c6d59}.claim-back{margin-bottom:18px}.context-filter{font-size:13px;color:#667d6b}.context-filter button{margin-left:16px}.saved-note{font-size:13px;color:#2d6a4f}.chapter-group{padding:10px 14px;border:1px solid #e0e8e2;border-radius:6px;margin:16px 0}.chapter-group legend{font-size:13px;padding:0 6px;color:#46634f}.chapter-group small{color:#8d8e70;font-size:12px;margin-left:8px}.coverage-table{margin-top:14px}.coverage-table th:first-child{width:35%}.coverage-table td>.text-link+small{display:block}.coverage-table td:last-child>.text-link{display:block}.candidate-table th:first-child{width:48%}.history{margin-top:24px}@media(max-width:1050px){.target-claims td,.target-list td{font-size:12px}.target-header{align-items:flex-start}}
</style>
