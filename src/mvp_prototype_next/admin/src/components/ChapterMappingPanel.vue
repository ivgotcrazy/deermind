<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import { domainMock, collectKnowledge, type DomainKind } from '../workbench/domain-mock';
import { recordBookChange, mockId, type MockTextbook, type MaterialChapter, type ChapterMapping } from '../workbench/textbook-mock';
import { go } from '../workbench/navigation';
import WorkbenchDialog from './WorkbenchDialog.vue';
const props=defineProps<{book:MockTextbook;chapter:MaterialChapter}>();
const emit=defineEmits<{locate:[id:string]}>();
const taskFor=(id:string)=>domainMock.tasks.find(t=>t.id===id&&t.domainId===props.book.domainId);
const methodFor=(id:string)=>domainMock.methods.find(m=>m.id===id&&m.domainId===props.book.domainId);
const allowed=(m:ChapterMapping)=>m.methods.filter(id=>taskFor(m.taskId)?.methods.includes(id)&&methodFor(id));
const knowledge=computed(()=>collectKnowledge(props.chapter.mappings.flatMap(allowed),props.book.domainId));
const invalid=computed(()=>props.chapter.mappings.filter(m=>!taskFor(m.taskId)||allowed(m).length!==m.methods.length));
const dialog=ref(false),editingId=ref(''),draft=ref<ChapterMapping>({id:'',taskId:'',methods:[],sources:[],reason:''}),error=ref(''),errorNode=ref<HTMLElement>(),removeConfirm=ref(false),query=ref(''),notice=ref('');
const choices=computed(()=>domainMock.tasks.filter(t=>t.domainId===props.book.domainId&&(t.name+' '+t.id).toLowerCase().includes(query.value.toLowerCase())));
const selectedTask=computed(()=>taskFor(draft.value.taskId));
const methods=computed(()=>domainMock.methods.filter(m=>m.domainId===props.book.domainId&&selectedTask.value?.methods.includes(m.id)));
const previewKC=computed(()=>collectKnowledge(draft.value.methods,props.book.domainId));
function open(kind:DomainKind,id:string){go('domain',{domain:props.book.domainId,filter:kind,id,returnTo:window.location.hash});}
function sourceLabel(id:string){const s=props.chapter.locations.find(s=>s.id===id);return s?`${s.printedPage?'书页 '+s.printedPage:'文件第 '+s.filePage+' 页'} · ${s.label}`:'来源位置缺失';}
function edit(value?:ChapterMapping){editingId.value=value?.id||'';draft.value=value?JSON.parse(JSON.stringify(value)):{id:mockId('MAP'),taskId:'',methods:[],sources:[],reason:''};error.value='';query.value='';removeConfirm.value=false;dialog.value=true;}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}
function save(){
  if(!selectedTask.value)return fail('请选择当前领域中的任务模板。');
  if(props.chapter.mappings.some(m=>m.id!==editingId.value&&m.taskId===draft.value.taskId))return fail('本章已有这个任务的映射，请在原映射中补充方法和来源。');
  if(!draft.value.methods.length||draft.value.methods.some(id=>!methods.value.some(m=>m.id===id)))return fail('请至少选择一种该任务直接关联的方法，并移除已失效的选择。');
  if(!draft.value.sources.length||draft.value.sources.some(id=>!props.chapter.locations.some(s=>s.id===id)))return fail('请至少选择一个本章的来源位置。');
  if(!draft.value.reason.trim())return fail('请说明这些内容为什么对应此任务及所选方法。');
  const next=JSON.parse(JSON.stringify(draft.value)),index=props.chapter.mappings.findIndex(m=>m.id===editingId.value);
  if(index<0)props.chapter.mappings.push(next);else props.chapter.mappings[index]=next;
  recordBookChange(props.book,(index<0?'新增':'修改')+'章节映射：'+props.chapter.name);dialog.value=false;notice.value='映射已保存，依赖知识已按所选方法重新汇总。';
}
function remove(){props.chapter.mappings=props.chapter.mappings.filter(m=>m.id!==editingId.value);recordBookChange(props.book,'移除章节映射：'+props.chapter.name);dialog.value=false;notice.value='已移除这条章节映射，领域定义未改变。';}
</script>
<template><div class="chapter-mapping">
  <div class="section-heading"><div><h3>任务与采用的方法</h3><p class="muted">明确本章覆盖的任务、采用的方法及教材依据。</p></div><button class="btn primary" @click="edit()">添加任务映射</button></div>
  <p v-if="notice" role="status" class="saved-note">{{notice}}</p><p v-if="invalid.length" class="callout amber">有任务或方法已变化，请编辑相应映射重新核对。知识汇总只包含当前仍适用的方法。</p>
  <section class="table-card"><table class="data-table mapping-table"><thead><tr><th>任务模板</th><th>本章采用的方法</th><th>教材来源</th><th></th></tr></thead><tbody><tr v-for="m in chapter.mappings" :key="m.id"><td><button v-if="taskFor(m.taskId)" class="text-link item-name" @click="open('task',m.taskId)">{{taskFor(m.taskId)!.name}} ↗</button><span v-else>任务不存在</span><details><summary>映射依据</summary><p>{{m.reason}}</p></details></td><td><div v-for="id in m.methods" :key="id" class="linked-line"><button v-if="methodFor(id)" class="text-link" @click="open('solution',id)">{{methodFor(id)!.name}} ↗</button><span v-else>方法不存在</span><small v-if="!allowed(m).includes(id)">已不适用，待核对</small></div></td><td><button v-for="id in m.sources" :key="id" class="text-link source-link" @click="emit('locate',id)">{{sourceLabel(id)}} ↗</button></td><td><button class="btn" :aria-label="'编辑映射 '+m.taskId" @click="edit(m)">编辑</button></td></tr></tbody></table><div v-if="!chapter.mappings.length" class="empty">本章尚无任务映射。先确认章节内容和来源，再选择适用的任务与方法。</div></section>
  <div class="section-heading knowledge-heading"><div><h3>依赖知识 <span class="muted">{{knowledge.rows.length}} 项，已去重</span></h3><p class="muted">由本章所选方法及其子方法递归汇总，不根据相同 KC 自动扩展任务。</p></div></div>
  <p v-if="knowledge.issues.length" class="callout amber">{{knowledge.issues.join(' ')}}</p>
  <section class="table-card"><table class="data-table knowledge-table"><thead><tr><th>Knowledge Component</th><th>知识说明</th><th>来自本章采用的方法</th></tr></thead><tbody><tr v-for="row in knowledge.rows" :key="row.knowledge.id"><td><button class="text-link" @click="open('kc',row.knowledge.id)">{{row.knowledge.name}} ↗</button></td><td>{{row.knowledge.description}}</td><td><div v-for="source in row.sources" :key="source.methodId" class="linked-line"><button class="text-link" @click="open('solution',source.methodId)">{{methodFor(source.methodId)?.name}}</button><small>{{source.direct&&source.indirect?'直接依赖、经子方法':source.direct?'直接依赖':'经子方法汇总'}}</small></div></td></tr></tbody></table><p v-if="!knowledge.rows.length" class="empty">尚无可汇总的方法依赖知识。</p></section>
  <WorkbenchDialog v-if="dialog" :title="editingId?'编辑任务映射':'添加任务映射'" wide @close="dialog=false"><form @submit.prevent="save" novalidate><p v-if="error" ref="errorNode" class="callout danger" role="alert" tabindex="-1">{{error}}</p>
    <p class="muted">当前章节：{{chapter.name}}。选用领域定义，不改写任务或方法。</p>
    <label>查找任务<input v-model="query" type="search" placeholder="任务名称或编号"/></label><label>任务模板<select v-model="draft.taskId" aria-label="任务模板" @change="draft.methods=[]"><option value="">请选择</option><option v-if="selectedTask&&!choices.some(t=>t.id===selectedTask!.id)" :value="selectedTask.id">{{selectedTask.name}}（当前选择）</option><option v-for="t in choices" :key="t.id" :value="t.id">{{t.name}}</option></select></label>
    <fieldset><legend>本章采用的方法</legend><div class="choice-list"><label v-for="m in methods" :key="m.id" class="check-label"><input v-model="draft.methods" type="checkbox" :value="m.id"/><span>{{m.name}}<small>{{m.conditions}}</small></span></label><label v-for="id in draft.methods.filter(id=>!methods.some(m=>m.id===id))" :key="id" class="check-label"><input v-model="draft.methods" type="checkbox" :value="id"/>{{methodFor(id)?.name||id}}（已不适用，请取消选择）</label><p v-if="!methods.length" class="muted">{{selectedTask?'此任务尚未关联方法，请先在领域中补充。':'选择任务后显示它直接关联的方法。'}}</p></div></fieldset>
    <p v-if="draft.methods.length" class="muted">将汇总 {{previewKC.rows.length}} 项依赖知识：{{previewKC.rows.map(r=>r.knowledge.name).join('、')}}。</p>
    <fieldset><legend>教材来源位置</legend><div class="choice-list"><label v-for="s in chapter.locations" :key="s.id" class="check-label"><input v-model="draft.sources" type="checkbox" :value="s.id"/><span>{{sourceLabel(s.id)}}<small>{{book.sources.find(f=>f.id===s.fileId)?.name}} · 文件第 {{s.filePage}} 页</small></span></label><p v-if="!chapter.locations.length" class="muted">本章尚无来源定位，请先在“章节内容”中添加。</p></div></fieldset>
    <label>映射依据<textarea v-model="draft.reason" rows="3" placeholder="哪些题目或讲解体现了该任务，采用这些方法的依据是什么"/></label>
    <p v-if="removeConfirm" class="callout amber">只移除此章节的映射，不删除 Task 或 Solution。<button type="button" class="text-link" @click="remove">确认移除</button></p>
    <div class="dialog-footer editor-footer"><button v-if="editingId" type="button" class="text-link remove-link" @click="removeConfirm=true">移除此映射</button><div class="button-row"><button type="button" class="btn" @click="dialog=false">取消</button><button class="btn primary" type="submit">保存映射</button></div></div>
  </form></WorkbenchDialog>
</div></template>
<style scoped>
.section-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.section-heading h3{margin:0;font-size:16px}.section-heading p{margin:5px 0 0}.section-heading>.btn{flex-shrink:0}.mapping-table th:first-child{width:29%}.mapping-table th:nth-child(2){width:29%}.mapping-table th:last-child{width:72px}.data-table td{line-height:1.8}.data-table details{margin-top:10px;padding-top:6px;border:0}.data-table details p{font-size:12px;color:#63796b}.item-name{font-weight:600}.linked-line+.linked-line{margin-top:12px}.source-link{display:block;margin-bottom:10px}.knowledge-heading{margin-top:28px}.knowledge-table th:first-child{width:25%}.knowledge-table th:nth-child(2){width:34%}.saved-note{font-size:13px;color:#2d6a4f}.choice-list{border:1px solid #dfe8e1;border-radius:6px;padding:8px 14px}.choice-list small{display:block;color:#7b8b80;font-size:12px}.choice-list .check-label{align-items:flex-start;margin:12px 0}.choice-list input{margin-top:5px}legend{font-size:13px;margin:16px 0 8px;color:#405a4c}.editor-footer{display:flex;justify-content:flex-end;align-items:center;gap:16px}.editor-footer .button-row{margin:0}.remove-link{margin-right:auto;color:#9b533d}
</style>
