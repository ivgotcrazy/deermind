<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import { editor } from '../workbench/ui';
import { clone, catalog, domain, saveDefinition, saveDraft, relationKinds, relationLabels, latest } from '../workbench/store';
import { kinds, aspectNames, objectKey } from '../workbench/model';
import {route,setQuery} from '../workbench/navigation';
import WorkbenchDialog from './WorkbenchDialog.vue';
const session=editor.value!;
const value=ref(clone(session.object));const error=ref('');const query=ref('');
const errorNode=ref<HTMLElement>();
const labels=relationLabels[value.value.kind]||[];const label=ref(labels[0]||'');const reference=ref('');
const choices=computed(()=>catalog().filter(o=>relationKinds[label.value]?.includes(o.kind)&&(!query.value||`${o.id} ${o.name}`.toLowerCase().includes(query.value.toLowerCase()))));
const mismatch=computed(()=>(latest(value.value.id)?.version||0)!==session.baseVersion);
function add(){if(!reference.value)return;if(!value.value.relations.some(r=>r.label===label.value&&r.ref===reference.value))value.value.relations.push({label:label.value,ref:reference.value});reference.value='';}
async function save(){error.value='';try{const saved=saveDefinition(value.value,session.baseVersion,session.draftId,session.package);if(route.page==='object'&&route.id.split('@')[0]===value.value.id)setQuery({id:saved});editor.value=null;}catch(e){error.value=e instanceof Error?e.message:String(e);await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}}
function draft(){error.value='';try{saveDraft(value.value,session.baseVersion,session.draftId);editor.value=null;}catch(e){error.value=e instanceof Error?e.message:String(e);}}
</script>
<template><WorkbenchDialog :title="`${session.baseVersion?'修改':'新增'}${kinds[value.kind]}`" wide @close="editor=null">
  <form @submit.prevent="save">
    <p class="muted">{{value.domainId?'所属领域：'+(domain(value.domainId)?.name||value.domainId):kinds[value.kind]}} · {{value.id}} · {{session.baseVersion?'基于 v'+session.baseVersion:'新对象'}}</p>
    <p v-if="mismatch" class="callout danger">此草稿的基线已变化，不能覆盖当前版本。可保留草稿并对照当前定义重新编辑。</p>
    <p v-if="session.package" class="callout">以下为导入定义包的内容。保存后形成新版本；需要改正文时，请调整定义包再导入。</p>
    <fieldset :disabled="!!session.package"><label>名称<input v-model="value.name" required maxlength="160"/></label><label>定义说明<textarea v-model="value.summary" required/></label>
      <label v-for="(_,key) in value.fields" :key="key">{{key}}<textarea v-model="value.fields[key]" required/></label>
      <div v-if="value.requiredAspects"><h4>目标要求的评价方面</h4><label class="check-label" v-for="(name,key) in aspectNames" :key="key"><input type="checkbox" :value="key" v-model="value.requiredAspects"/>{{name}}</label></div>
    </fieldset>
    <h4>关联对象</h4><p v-if="!value.relations.length" class="muted">尚未关联对象。任务模板可以先保存，再补充方法和知识关系。</p>
    <div v-for="(r,i) in value.relations" :key="i" class="list-row"><span>{{r.label}}</span><span>{{catalog().find(o=>o.id===r.ref.split('@')[0])?.name||r.ref}} <small class="mono">{{r.ref}}</small></span><button v-if="!session.package" class="btn" type="button" @click="value.relations.splice(i,1)">移除</button></div>
    <div v-if="!session.package && labels.length" class="toolbar"><label>关系类型<select aria-label="关系类型" v-model="label" @change="reference='' "><option v-for="l in labels" :key="l">{{l}}</option></select></label><label>查找关联对象<input v-model="query" placeholder="名称或编号"/></label><label>关联对象<select aria-label="关联对象" v-model="reference"><option value="">请选择</option><option v-for="o in choices" :key="o.id" :value="['采用 Claim','精确绑定任务版本'].includes(label)?objectKey(o):o.id">{{o.name}} · {{o.id}}{{o.domainId?' · '+domain(o.domainId)?.name:''}}</option></select></label><button class="btn" type="button" :disabled="!reference" @click="add">添加关联</button></div>
    <table v-if="value.aspects" class="data-table"><thead><tr><th>评价方面</th><th>条件</th><th>证据要求</th></tr></thead><tbody><tr v-for="a in value.aspects" :key="a.key"><td>{{a.label}}<small v-if="!a.applicable">不适用：{{a.reason}}</small></td><td>{{a.criterion}}</td><td>{{a.evidence}}</td></tr></tbody></table>
    <p v-if="error" ref="errorNode" tabindex="-1" class="callout danger" role="alert" style="white-space:pre-wrap;scroll-margin-bottom:140px">{{error}}</p>
    <div class="dialog-footer"><p class="muted">保存自动记录版本。已有学习空间和历史记录保留原采用版本。</p><div class="button-row"><button class="btn primary" :disabled="mismatch" type="submit">保存</button><button class="btn" type="button" @click="draft">保存草稿</button><button class="btn" type="button" @click="editor=null">取消</button></div></div>
  </form>
</WorkbenchDialog></template>
