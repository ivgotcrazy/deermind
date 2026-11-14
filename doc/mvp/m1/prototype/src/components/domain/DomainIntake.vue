<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { imports, storageError, type ImportDraft } from '../../model/imports';
import { domainStorageError, domainData, collection, type Task, type Method, type Knowledge } from '../../model/domain';
import { elementNames, materialUrl, type IntakeGroup, type ParsedElement } from '../../model/material-flow';
import { rowResult, templateCandidate, saveTemplate, knowledgeCandidate, addKnowledge, parentInstance, templateOptions, suggestedTemplate, associateElement, deletionRows, deletePendingElement } from '../../model/intake-actions';
import ParsedElementView from '../ParsedElementView.vue';
import WorkbenchDialog from '../WorkbenchDialog.vue';
const props=defineProps<{domainId:string;source:string;chapter:string}>();
type Action='content'|'extract'|'associate'|'knowledge'|'delete';
type IntakeRow={draft:ImportDraft;request:IntakeGroup;element:ParsedElement};
const classification=ref('match');
const active=ref(''),action=ref<Action>('content'),rowId=ref(''),error=ref(''),notice=ref('');
const candidate=ref<Task|Method|null>(null),knowledge=ref<Knowledge|null>(null),templateId=ref(''),existingKcId=ref('');
const books=computed(()=>imports.filter(d=>d.book.domainId===props.domainId&&d.flow));
const requests=computed(()=>books.value.flatMap(d=>d.flow!.requests.map(r=>({draft:d,request:r}))));
const groups=computed(()=>requests.value.filter(x=>(!props.source||x.draft.id===props.source)&&(!props.chapter||x.request.chapter===props.chapter)&&x.request.status==='pending'));
const selected=computed(()=>requests.value.find(x=>x.request.id===active.value));
const rows=computed(()=>groups.value.flatMap(g=>g.request.elements.filter(e=>!g.request.removed?.includes(e.id)).map(element=>({...g,element}))));
const current=computed(()=>selected.value?.request.elements.find(e=>e.id===rowId.value));
const sourceBook=computed(()=>books.value.find(d=>d.id===props.source));
const knownKc=computed(()=>domainData.knowledge.filter(k=>k.domainId===props.domainId));
const options=computed(()=>selected.value&&current.value?templateOptions(selected.value.draft,selected.value.request,current.value):[]);
const chosenTemplate=computed(()=>options.value.find(t=>t.id===templateId.value));
const parent=computed(()=>selected.value&&current.value?parentInstance(selected.value.draft,selected.value.request,current.value):undefined);
const addsMethod=computed(()=>current.value?.kind==='solution'&&chosenTemplate.value&&!domainData.tasks.find(t=>t.id===parent.value?.taskId)?.methods.includes(templateId.value));
const removing=computed(()=>selected.value&&current.value?deletionRows(selected.value.draft,selected.value.request,current.value):[]);
function result(r:IntakeRow){return rowResult(r.draft,r.request,r.element);}
function targetName(r:IntakeRow){const e=r.element,value=result(r);return value?collection(e.kind==='knowledge'?'kc':e.kind==='question'?'task':'solution').find(x=>x.id===(e.kind==='knowledge'?value.objectId:value.templateId))?.name||'关联对象已保存':'';}
function extractedName(r:IntakeRow){const e=r.element;return e.kind==='knowledge'?'':collection(e.kind==='question'?'task':'solution').find(t=>t.id===r.request.templates?.[e.id])?.name||'';}
function canAssociate(r:IntakeRow){return r.element.kind!=='solution'||!!parentInstance(r.draft,r.request,r.element);}
function close(){active.value='';rowId.value='';candidate.value=null;knowledge.value=null;error.value='';}
watch(()=>[props.source,props.chapter,props.domainId],()=>{close();notice.value='';});
function open(r:IntakeRow,next:Action){
  const {draft,request,element:e}=r;active.value=request.id;rowId.value=e.id;action.value=next;error.value='';notice.value='';
  if(next==='extract')candidate.value=templateCandidate(draft,request,e);
  if(next==='associate'){templateId.value=suggestedTemplate(draft,request,e);classification.value='match';}
  if(next==='knowledge'){knowledge.value=knowledgeCandidate(draft,e);existingKcId.value=knownKc.value.find(k=>k.name===knowledge.value!.name)?.id||'';}
}
function confirm(){
  if(!selected.value||!current.value||storageError.value||domainStorageError.value)return;
  const {draft,request}=selected.value,e=current.value;let issues:string[]=[];let message='';
  if(action.value==='extract'&&candidate.value){issues=saveTemplate(draft,request,e,candidate.value);message='定义已保存，请继续关联定义。';}
  else if(action.value==='knowledge'&&knowledge.value){issues=addKnowledge(draft,request,e,knowledge.value,existingKcId.value);message='知识成分已添加。';}
  else if(action.value==='associate'){issues=associateElement(draft,request,e,templateId.value,classification.value);message='已关联定义并保存实例。';}
  else if(action.value==='delete'){issues=deletePendingElement(draft,request,e);message='已从本次待入库内容移除。';}
  else return;
  error.value=issues.join('；');if(!issues.length){close();notice.value=message;}
}
const dialogTitle=computed(()=>({content:'查看内容',extract:current.value?.kind==='question'?'提取任务':'提取方法',associate:current.value?.kind==='question'?'关联任务':'关联方法',knowledge:'添加知识成分',delete:'删除待入库内容'}[action.value]));
</script>
<template><div class="domain-intake">
  <header class="row-between"><div><h3>待入库内容</h3><p class="muted">来自教材的知识、题目和解法。逐项添加或关联，处理完成后移出待入库列表。</p></div><a v-if="sourceBook" class="btn" :href="materialUrl(sourceBook,chapter,'links')">返回教材章节 →</a></header>
  <p v-if="!selected&&(storageError||domainStorageError)" class="callout danger" role="alert">{{storageError||domainStorageError}}</p>
  <div v-if="source||chapter" class="button-row"><a class="text-link" :href="'#/domain?domain='+domainId+'&tab=intake'">查看本领域全部来源</a></div>
  <p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <section class="panel"><table v-if="rows.length" class="data-table intake-list"><thead><tr><th>内容</th><th>类型</th><th>教材 · 章节</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="r in rows" :key="r.request.id+r.element.id" :data-request="r.request.id" :data-element="r.element.id">
    <td><button class="text-link content-title" @click="open(r,'content')">{{r.element.title}}</button><small v-if="r.element.kind==='solution'">所属题目：{{r.request.elements.find(q=>q.id===r.element.taskElementId)?.title}}</small></td>
    <td>{{r.element.kind==='knowledge'?'知识成分':elementNames[r.element.kind]}}</td>
    <td><a class="text-link" :href="materialUrl(r.draft,r.request.chapter)">{{r.draft.book.name}}</a><small>{{r.request.chapter}}</small></td>
    <td><span class="badge" :class="{'done':result(r)}">{{result(r)?r.element.kind==='knowledge'?'已添加':'已关联':r.element.kind==='knowledge'?'待添加':'待关联'}}</span><small v-if="result(r)">{{targetName(r)}}</small><small v-else-if="extractedName(r)">已提取：{{extractedName(r)}}</small></td>
    <td><div v-if="!result(r)" class="row-actions"><button v-if="r.element.kind==='knowledge'" class="btn" @click="open(r,'knowledge')">添加知识成分</button><template v-else><button class="btn" @click="open(r,'extract')">{{r.element.kind==='question'?'提取任务':'提取方法'}}</button><button class="btn" :disabled="!canAssociate(r)" @click="open(r,'associate')">{{r.element.kind==='question'?'关联任务':'关联方法'}}</button></template><button class="btn danger delete-action" @click="open(r,'delete')">删除</button></div><small v-if="!result(r)&&!canAssociate(r)">请先关联所属题目</small><span v-if="result(r)" class="muted">已保存</span></td>
  </tr></tbody></table><p v-else class="empty">当前没有待入库内容。</p></section>
  <WorkbenchDialog v-if="selected&&current" class="intake-detail" :title="dialogTitle" wide @close="close">
    <p v-if="error||storageError||domainStorageError" class="callout danger" role="alert">{{error||storageError||domainStorageError}}</p>
    <template v-if="current">

      <p class="source-label">{{current.title}}</p>
      <ParsedElementView v-if="action==='content'" :element="current"/>
      <template v-if="action==='extract'">
        <template v-if="candidate"><p class="muted">以下为 mock 提取结果。保存后仍需关联，不自动添加其他定义或知识。</p><label>定义名称<input v-model="candidate.name"/></label><label>定义说明<textarea v-if="'goal' in candidate" v-model="candidate.goal" rows="4"/><textarea v-else v-model="candidate.description" rows="4"/></label><details><summary>查看定义内容</summary><template v-if="'goal' in candidate"><p>参数：{{candidate.parameters.map(p=>p.symbol+'（'+p.name+'）').join('、')||'见任务定义'}}</p><p>交付要求：{{candidate.requirements.map(r=>r.deliverable).join('；')}}</p></template><template v-else><p>{{candidate.procedure}}</p><p>结束条件：{{candidate.ending?.success}}</p></template></details><p class="muted">定义的方法、知识依赖可在领域管理中继续补齐。</p></template>
        <p v-else class="callout amber">此内容尚无 mock 提取结果。可返回后关联已有定义。</p>
      </template>
      <template v-if="action==='associate'">
        <p v-if="current.kind==='solution'">所属题目：{{selected.request.elements.find(e=>e.id===current!.taskElementId)?.title}}<small>{{parent?.id}}</small></p>
        <label>{{current.kind==='question'?'任务':'方法'}}<select v-model="templateId"><option value="">请选择定义</option><option v-for="o in options" :key="o.id" :value="o.id">{{o.name}}</option></select></label>
        <p v-if="chosenTemplate">{{'goal' in chosenTemplate?chosenTemplate.goal:chosenTemplate.description}}</p><p v-if="!options.length" class="muted">暂无可关联定义。请返回提取定义，或在领域管理中补齐。</p>
        <label>归属核对（mock）<select v-model="classification"><option value="match">责任、条件、所需表现与方法适用性一致</option><option value="mismatch">不符合当前任务或方法</option><option value="unclear">依据不足，待确认</option></select></label><p class="muted">预写结果用于验证保存分支；不以名称相似或共用知识代替真实语义检查。</p><p v-if="addsMethod" class="callout">请确认此解法适用于所属任务。确认后，将同时加入该任务的方法列表。</p>
        <p class="muted">{{current.kind==='question'?'保存题目及其任务归属，不生成解法。':'作为该题的参考解法保存，关联方法并保留教材来源；不创建独立解法实例。'}}</p>
      </template>
      <template v-if="action==='knowledge'&&knowledge">
        <label>添加方式<select v-model="existingKcId"><option value="">新增知识成分</option><option v-for="k in knownKc" :key="k.id" :value="k.id">复用：{{k.name}}</option></select></label>
        <template v-if="!existingKcId"><label>名称<input v-model="knowledge.name"/></label><label>定义<textarea v-model="knowledge.description" rows="4"/></label></template><p v-else>{{knownKc.find(k=>k.id===existingKcId)?.description}}</p>
      </template>
      <template v-if="action==='delete'"><p>从本次待入库内容中删除“{{current.title}}”？教材解析内容和已保存的领域对象都会保留。</p><p v-if="removing.length>1">同时移除它的 {{removing.length-1}} 条待处理解法，避免解法失去所属题目。</p></template>
    </template>
    <footer class="dialog-footer"><button class="btn" @click="close">{{action==='content'?'关闭':'取消'}}</button><button v-if="action!=='content'" class="btn" :class="action==='delete'?'danger':'primary'" :disabled="!!storageError||!!domainStorageError||(action==='extract'&&!candidate)||(action==='associate'&&!templateId)" @click="confirm">{{action==='extract'?'保存定义':action==='associate'?'确认关联':action==='knowledge'?'确认添加':'确认删除'}}</button></footer>
  </WorkbenchDialog>
</div></template>
<style scoped>
.intake-list{table-layout:fixed}.intake-list td{vertical-align:top;overflow-wrap:anywhere}.intake-list th:nth-child(1){width:22%}.intake-list th:nth-child(2){width:9%}.intake-list th:nth-child(3){width:22%}.intake-list th:nth-child(4){width:18%}.row-actions{display:flex;gap:8px;flex-wrap:wrap}.row-actions .btn{padding:6px 9px}.content-title{text-align:left;padding:0;background:none;border:0}.delete-action{color:#a3392e}.source-label{font-weight:600}.done{background:#e7f3ed;color:#286349}summary{cursor:pointer}small{display:block;margin-top:7px}.intake-detail details{margin:16px 0}
</style>
