<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { initializeFlow, chapters, elementNames, elementText, elementProblems, reparseCandidate, adoptReparse, submitElements, isImported, elementResult, chapterSuggestions, saveChapterLinks, materialUrl, intakeUrl, type ParsedElement, type ElementKind, type ChapterLink } from '../model/material-flow';
import { domainData, clone, collectKnowledge } from '../model/domain';
import { storageError, type ImportDraft } from '../model/imports';
import { materialPageUrl } from '../model/material-content';
import WorkbenchDialog from './WorkbenchDialog.vue';
import ParsedElementView from './ParsedElementView.vue';

const props=defineProps<{draft:ImportDraft;hash:string}>();
const flow=initializeFlow(props.draft),kind=ref<ElementKind>('question'),selected=ref<string[]>([]),query=ref(''),notice=ref(''),error=ref('');
const chapter=computed(()=>flow.selectedChapter),tab=computed(()=>flow.tab);
const pending=computed(()=>flow.requests.filter(r=>r.chapter===chapter.value&&r.status==='pending').length);
const content=computed(()=>flow.elements.filter(e=>e.chapter===chapter.value));
const rows=computed(()=>content.value.filter(e=>e.kind===kind.value&&(e.title+' '+elementText(e)).includes(query.value.trim())));
const detail=ref<ParsedElement|null>(null),reparsing=ref<ParsedElement[]|null>(null),candidate=ref<ParsedElement[]|null>(null),prompt=ref(''),sourcePage=ref(0),showSource=ref(false);
const links=computed(()=>flow.links[chapter.value]||[]);
const linkDraft=ref<ChapterLink|null>(null),editingTask=ref(''),linkError=ref('');
const suggestions=computed(()=>chapterSuggestions(props.draft,chapter.value));
const availableTasks=computed(()=>domainData.tasks.filter(t=>t.domainId===props.draft.book.domainId&&!links.value.some(l=>l.taskId===t.id)));
const pageNumbers=computed(()=>[...new Set((reparsing.value||[detail.value].filter(Boolean) as ParsedElement[]).flatMap(e=>e.blocks.map(b=>b.page)))].sort((a,b)=>a-b));
const activePage=computed(()=>sourcePage.value||pageNumbers.value[0]||49);
const sourceUrl=computed(()=>materialPageUrl(activePage.value));
function parentName(e:ParsedElement){return flow.elements.find(q=>q.id===e.taskElementId)?.title||'所属题目待解析';}
function state(e:ParsedElement){return isImported(flow,e)?'已入库':flow.requests.some(r=>r.status==='pending'&&!r.removed?.includes(e.id)&&r.elements.some(x=>x.id===e.id))?'待入库':elementProblems(e).length?'需重新解析':elementResult(flow,e.id)?'内容已更新':'可提交';}
function navigate(ch=chapter.value,view=tab.value){location.hash=materialUrl(props.draft,ch,view);}
watch(()=>props.hash,()=>{
  const p=new URLSearchParams(props.hash.split('?')[1]||'');
  const ch=p.get('chapter'),item=p.get('item');
  if(ch&&chapters(flow).includes(ch))flow.selectedChapter=ch;
  if(item){const found=flow.elements.find(e=>e.itemId===item&&e.kind==='question');if(found){flow.selectedChapter=found.chapter;detail.value=found;}}
  flow.tab=p.get('view')==='links'?'links':'content';
  closeLink();
  selected.value=[];notice.value='';error.value='';
},{immediate:true});
function select(key:string,checked:boolean){selected.value=checked?[...selected.value,key]:selected.value.filter(k=>k!==key);}
function inspect(e:ParsedElement){detail.value=e;sourcePage.value=0;showSource.value=false;}
function reparse(elements:ParsedElement[]){reparsing.value=clone(elements);candidate.value=null;prompt.value='';detail.value=null;showSource.value=false;sourcePage.value=0;error.value='';}
function propose(){if(!prompt.value.trim())return;candidate.value=reparsing.value!.flatMap(e=>reparseCandidate(flow,e));}
function adopt(){if(!candidate.value||!reparsing.value)return;adoptReparse(flow,reparsing.value,candidate.value,prompt.value);reparsing.value=null;candidate.value=null;selected.value=[];notice.value='已采用重新解析结果。已入库的领域对象未被覆盖；需要时可重新提交。';}
function submit(){error.value=submitElements(flow,selected.value).join('；');if(!error.value){notice.value='已提交到领域管理。题目和选中的解法按组处理。';selected.value=[];}}
function openLink(link?:ChapterLink){editingTask.value=link?.taskId||'';linkDraft.value=clone(link||{taskId:'',methodIds:[]});linkError.value='';error.value='';notice.value='';}
function closeLink(){linkDraft.value=null;editingTask.value='';linkError.value='';}
function chooseLinkTask(){
  if(!linkDraft.value)return;const key=linkDraft.value.taskId;
  linkDraft.value.methodIds=(suggestions.value.find(s=>s.taskId===key)?.methodIds||[]).filter(id=>task(key)?.methods.includes(id)&&method(id));
  linkError.value='';
}
function selectMethod(link:ChapterLink,key:string,checked:boolean){link.methodIds=checked?[...link.methodIds,key]:link.methodIds.filter(k=>k!==key);}
function saveLink(){
  if(!linkDraft.value||storageError.value)return;
  if(!linkDraft.value.taskId){linkError.value='请选择任务模板。';return;}
  if(!editingTask.value&&links.value.some(l=>l.taskId===linkDraft.value!.taskId)){linkError.value='本章已经关联该任务，请使用编辑修改方法。';return;}
  const next=editingTask.value?links.value.map(l=>l.taskId===editingTask.value?linkDraft.value!:l):[...links.value,linkDraft.value];
  linkError.value=saveChapterLinks(props.draft,chapter.value,next).join('；');
  if(!linkError.value){closeLink();notice.value='本章关联已保存。';}
}
function removeLink(link:ChapterLink){
  if(storageError.value)return;
  error.value=saveChapterLinks(props.draft,chapter.value,links.value.filter(l=>l.taskId!==link.taskId)).join('；');
  if(!error.value)notice.value='已取消本章关联，领域中的任务、方法和知识未删除。';
}
const task=(key:string)=>domainData.tasks.find(t=>t.id===key&&t.domainId===props.draft.book.domainId);
const method=(key:string)=>domainData.methods.find(m=>m.id===key&&m.domainId===props.draft.book.domainId);
</script>

<template><div class="material-contents">
  <div v-if="notice" class="saved-note" role="status">{{notice}}</div><p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <div class="material-layout">
    <aside class="panel chapter-nav"><h3>章节</h3><button v-for="ch in chapters(flow)" :key="ch" :class="{active:chapter===ch}" @click="navigate(ch)">{{ch}}<small>{{flow.elements.filter(e=>e.chapter===ch&&e.kind==='question').length}} 道题 · {{flow.links[ch]?.length||0}} 项任务已关联</small></button></aside>
    <section class="panel chapter-workspace">
      <header class="row-between"><h3>{{chapter||'解析内容'}}</h3><a v-if="pending" class="text-link" :href="intakeUrl(draft,chapter)">领域待入库 {{pending}} 组 →</a></header>
      <nav class="material-tabs" aria-label="教材内容"><button :class="{active:tab==='content'}" @click="navigate(chapter,'content')">解析内容</button><button :class="{active:tab==='links'}" @click="navigate(chapter,'links')">章节关联</button></nav>
      <template v-if="tab==='content'">
        <div class="row-between content-toolbar"><div class="type-switch" aria-label="元素类型"><button v-for="(name,key) in elementNames" :key="key" :class="{active:kind===key}" @click="kind=key;query=''">{{name}} {{content.filter(e=>e.kind===key).length}}</button></div><button class="text-link" @click="reparse(content)">重新解析本章</button></div>
        <label class="search-label">查找{{elementNames[kind]}}<input v-model="query" type="search" placeholder="名称或内容"/></label>
        <table v-if="rows.length" class="data-table element-table"><thead><tr><th class="select-cell">选择</th><th>{{elementNames[kind]}}</th><th v-if="kind==='solution'">所属题目</th><th v-else-if="kind==='question'">教材解法</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="e in rows" :key="e.id" :data-element="e.id"><td><input type="checkbox" :aria-label="'选择 '+e.title" :checked="selected.includes(e.id)" :disabled="isImported(flow,e)||!!elementProblems(e).length" @change="select(e.id,($event.target as HTMLInputElement).checked)"/></td><td><button class="text-link element-title" @click="inspect(e)">{{e.title}}</button><small>第 {{[...new Set(e.blocks.map(b=>b.page))].join('、')}} 页</small></td><td v-if="kind==='solution'">{{parentName(e)}}</td><td v-else-if="kind==='question'">{{flow.elements.filter(s=>s.taskElementId===e.id).length}} 种</td><td><span class="badge" :class="{warning:!!elementProblems(e).length}">{{state(e)}}</span></td><td><button class="text-link" :aria-label="'重新解析 '+e.title" @click="reparse([e])">重新解析</button></td></tr></tbody></table>
        <p v-else class="empty">当前章节没有{{elementNames[kind]}}解析结果。</p>
        <footer class="row-between selection-footer"><span class="muted">已选 {{selected.length}} 项。题目与解法分开选择；只选解法时自动带上所属题目。</span><button class="btn primary" :disabled="!selected.length||!!storageError" @click="submit">提交到领域</button></footer>
      </template>
      <template v-else>
        <p class="muted">选择本章涉及的任务及采用的方法。已有领域定义可以直接关联；教材解析内容只作为依据。</p>
        <div class="row-between chapter-links-toolbar"><a class="text-link" :href="intakeUrl(draft,chapter)">前往领域处理待入库内容 →</a><button class="btn primary" :disabled="!!storageError" @click="openLink()">添加关联</button></div>
        <table v-if="links.length" class="data-table chapter-links"><thead><tr><th>任务模板</th><th>本章采用的方法</th><th>汇总知识</th><th>操作</th></tr></thead><tbody><tr v-for="link in links" :key="link.taskId" :data-task="link.taskId"><td>{{task(link.taskId)?.name||'任务不存在'}}<details><summary>教材依据</summary><p v-for="r in flow.requests.filter(r=>r.chapter===chapter&&r.status==='done'&&Object.values(r.result).some(v=>v.templateId===link.taskId))" :key="r.id">{{r.elements[0].title}}</p><small>仅作为章节关联的来源依据。</small></details></td><td><ul class="method-list"><li v-for="key in link.methodIds" :key="key">{{method(key)?.name||'方法不存在'}}</li></ul></td><td>{{collectKnowledge(link.methodIds,draft.book.domainId).rows.map(r=>r.knowledge.name).join('、')||'暂无关联知识'}}</td><td><div class="link-actions"><button class="btn" :disabled="!!storageError" @click="openLink(link)">编辑</button><button class="btn" :disabled="!!storageError" @click="removeLink(link)">取消关联</button></div></td></tr></tbody></table>
        <p v-else class="empty">尚无章节关联。点击“添加关联”选择任务及本章采用的方法。</p>
      </template>
    </section>
  </div>
  <WorkbenchDialog v-if="linkDraft" :title="editingTask?'编辑章节关联':'添加章节关联'" @close="closeLink">
    <p v-if="linkError||storageError" class="callout danger" role="alert">{{linkError||storageError}}</p>
    <p class="muted">当前章节：{{chapter}}</p>
    <p v-if="editingTask"><strong>任务模板：</strong>{{task(linkDraft.taskId)?.name||'任务不存在'}}</p>
    <label v-else>任务模板<select v-model="linkDraft.taskId" aria-label="任务模板" @change="chooseLinkTask"><option value="">请选择当前领域中的任务</option><option v-for="t in availableTasks" :key="t.id" :value="t.id">{{t.name}}{{suggestions.some(s=>s.taskId===t.id)?'（教材建议）':''}}</option></select></label>
    <p v-if="!editingTask&&!availableTasks.length" class="muted">当前没有可添加的任务。已有任务可在表格中编辑，缺少的任务请先在领域管理中建立。</p>
    <fieldset v-if="linkDraft.taskId" class="link-methods"><legend>本章采用的方法</legend><label v-for="key in task(linkDraft.taskId)?.methods||[]" :key="key" class="check-line"><input type="checkbox" :aria-label="'本章采用 '+method(key)?.name" :checked="linkDraft.methodIds.includes(key)" @change="selectMethod(linkDraft,key,($event.target as HTMLInputElement).checked)"/>{{method(key)?.name||'方法不存在'}}</label><p v-if="!task(linkDraft.taskId)?.methods.length" class="muted">该任务尚未关联方法，请先在领域管理中补齐。</p></fieldset>
    <p v-if="linkDraft.taskId&&!editingTask&&suggestions.some(s=>s.taskId===linkDraft!.taskId)" class="muted">已按教材建议预选方法，可调整；保存后才建立本章关联。</p>
    <footer class="dialog-footer"><button class="btn" @click="closeLink">取消</button><button class="btn primary" :disabled="!!storageError" @click="saveLink">保存</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="detail||reparsing" :title="reparsing?(reparsing.length===1?'重新解析'+elementNames[reparsing[0].kind]:'重新解析本章'):'解析内容'" wide @close="detail=null;reparsing=null;candidate=null">
    <template v-if="reparsing"><label>需要纠正什么<textarea v-model="prompt" rows="3" placeholder="例如：这里是两种解法，请分别提取；原题中的错误算式请保留。"/></label><p class="muted">当前使用固定 mock 结果演示，不执行提示词、不调用 LLM。采用前不会替换原结果。</p></template>
    <button class="text-link" @click="showSource=!showSource">{{showSource?'收起原页':'查看原页'}}</button>
    <div v-if="showSource" class="original-preview"><label>原页<select v-model.number="sourcePage"><option v-for="n in pageNumbers" :key="n" :value="n">第 {{n}} 页</option></select></label><img :src="sourceUrl" :alt="'教材第'+activePage+'页'"/></div>
    <div v-if="candidate" class="reparse-result"><h4>重新解析结果</h4><ParsedElementView v-for="e in candidate" :key="e.id" :element="e"/></div>
    <template v-else><ParsedElementView v-if="detail" :element="detail"/><details v-else open><summary>当前解析结果</summary><ParsedElementView v-for="e in reparsing" :key="e.id" :element="e"/></details></template>
    <footer class="dialog-footer"><button class="btn" @click="detail=null;reparsing=null;candidate=null">取消</button><button v-if="detail" class="btn primary" @click="reparse([detail])">重新解析</button><button v-else-if="!candidate" class="btn primary" :disabled="!prompt.trim()" @click="propose">生成解析结果</button><button v-else class="btn primary" :disabled="!!storageError" @click="adopt">采用结果</button></footer>
  </WorkbenchDialog>
</div></template>
<style scoped>
.material-layout{display:grid;grid-template-columns:205px minmax(0,1fr);gap:20px}.chapter-nav{align-self:start}.chapter-nav>button{display:block;text-align:left;width:100%;padding:12px;border:0;border-radius:6px;background:none;color:#385746;margin:5px 0}.chapter-nav>button.active{background:#e9f3ed;border-left:3px solid #2d6a4f}.chapter-nav small{display:block;font-size:11px;color:#74847b;margin-top:5px}.material-tabs{display:flex;gap:24px;border-bottom:1px solid #dfe8e2;margin:14px 0 20px}.material-tabs button{border:0;border-bottom:3px solid transparent;background:none;padding:10px 0;color:#6b7f73}.material-tabs .active{border-color:#2d6a4f;color:#2d6a4f;font-weight:600}.type-switch{display:flex;gap:5px}.type-switch button{border:0;border-radius:6px;background:none;padding:8px 12px;color:#6b7f73}.type-switch .active{background:#edf5f0;color:#285b42}.select-cell{width:50px}.element-title{font-weight:600}.selection-footer{margin-top:20px;padding-top:14px;border-top:1px solid #e5ece7}.chapter-links-toolbar{gap:16px;margin:16px 0}.link-actions{display:flex;gap:8px;flex-wrap:wrap}.link-actions .btn{white-space:nowrap}.method-list{margin:0;padding-left:18px}.method-list li+li{margin-top:6px}.link-methods{border:0;padding:0;margin:20px 0}.link-methods legend{font-weight:600;margin-bottom:10px}.link-methods label{margin:10px 0}.original-preview img{display:block;max-width:100%;max-height:650px;margin:16px auto}.original-preview label{max-width:180px}.reparse-result{border-top:1px solid #dfe8e2;margin-top:16px}.chapter-links details{font-size:12px;color:#738579}.chapter-links td{vertical-align:top}.chapter-links td:nth-child(2){min-width:190px}.chapter-links td:last-child{min-width:160px}.element-table td{vertical-align:top}.content-toolbar{gap:10px}@media(max-width:1100px){.material-layout{grid-template-columns:160px minmax(0,1fr);gap:12px}.chapter-nav,.chapter-workspace{padding:14px}.type-switch button{padding:6px 8px}}
</style>
