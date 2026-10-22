<script setup lang="ts">
import { computed } from 'vue';
import { state as stateSource, catalog, resolve, scopeBindings, readDefinitionPackage, act, objectActivity, domain } from '../workbench/store';
const state=stateSource;
const emit=defineEmits<{editDomain:[]}>();
import { kinds, editableKinds, personalKinds, objectKey, type Kind } from '../workbench/model';
import { route as routeSource, go, setQuery, openObject, back } from '../workbench/navigation';
const route=routeSource;
import ModelObjectContent from './ModelObjectContent.vue';
import AccessGate from './AccessGate.vue';
import ObjectDrafts from './ObjectDrafts.vue';
import { newObject, editInOwner, importObject } from '../workbench/ui';
const selectedDomain=computed(()=>route.page==='domain'?domain(route.domain):undefined);
const location=window.location;
const title=computed(()=>route.page==='domain'?selectedDomain.value?.name||'领域管理':route.page==='evaluation'?'评估模型管理':'对象详情');
const typeOptions=computed(()=>route.page==='domain'?['task','solution','kc']:['claim','evidence-rule','inference-rule']);
const activeKind=computed(()=>typeOptions.value.includes(route.filter)?route.filter:typeOptions.value[0]||'task');
const rows=computed(()=>catalog().filter(o=>(route.page!=='domain'||o.domainId===route.domain) && o.kind===activeKind.value && (!route.q||`${o.id} ${o.name} ${o.summary}`.toLowerCase().includes(route.q.toLowerCase()))));
const paged=computed(()=>rows.value.slice((route.p-1)*10,route.p*10));
const obj=computed(()=>resolve(route.id,route.scope?scopeBindings(route.scope):undefined));
const guarded=computed(()=>obj.value && personalKinds.includes(obj.value.kind));
const accessRef=computed(()=>objectActivity(route.id)?.id || (obj.value?objectActivity(objectKey(obj.value))?.id:undefined) || route.id);
async function importPackage(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;try{if(file.size>100000)throw Error('定义包过大，请拆分为单对象。');const object=readDefinitionPackage(JSON.parse(await file.text()));go('evaluation',{filter:object.kind});importObject(object);}catch(e){act(()=>{throw e;});}finally{input.value='';}}
function exportPackage(){if(!obj.value)return;const next={...JSON.parse(JSON.stringify(obj.value)),version:obj.value.version+1,status:'draft'};const url=URL.createObjectURL(new Blob([JSON.stringify({format:'deermind-definition-package-v1',object:next},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=next.id+'-candidate.json';a.click();URL.revokeObjectURL(url);}
</script>
<template><div class="wb-page">
  <header class="page-header"><div><button v-if="route.page!=='object' && route.returnTo.startsWith('#/observed-')" class="text-link" @click="back('objects')">← 返回观测详情</button><button v-if="route.page==='object'" class="text-link" @click="back('objects')">← 返回来源</button><button v-if="route.page==='domain' && !route.returnTo.startsWith('#/observed-')" class="text-link" @click="back('domain')">← 返回领域列表</button><h2>{{title}}</h2><p class="page-desc">{{selectedDomain?selectedDomain.scope:route.page==='object'?'同一身份、准确版本；各入口共享定义和维护流程。':'可查询的模型目录；个人状态与规范定义分开查看。'}}</p><details v-if="selectedDomain" class="domain-description"><summary>领域说明</summary><button class="text-link" @click="emit('editDomain')">编辑领域</button><p>{{selectedDomain.description||'尚未填写补充说明。'}}</p><small class="mono">{{selectedDomain.id}}</small></details></div>
    <button v-if="route.page==='domain' && selectedDomain && ['task','solution','kc'].includes(activeKind)" class="btn primary" @click="act(()=>newObject(activeKind as Kind,route.domain))">新增{{kinds[activeKind as Kind]}}</button>
    <button v-if="obj && route.page==='object' && editableKinds.includes(obj.kind)" class="btn primary" @click="act(()=>editInOwner(route.id))">编辑定义</button>
  </header>
  <div v-if="route.page==='evaluation' || (route.page==='object' && obj && ['claim','evidence-rule','inference-rule'].includes(obj.kind))" class="panel"><div class="row-between"><p>导入定义包，检查格式与引用后直接保存；不改变已有空间采用的版本。</p><button v-if="obj" class="btn" @click="exportPackage">导出下一版本模板</button></div><label>导入模型定义包<input type="file" accept=".json,application/json" @change="importPackage"/></label></div>
  <template v-if="route.page==='object'">
    <div class="tabs"><button v-for="(label,key) in {definition:'定义内容',relations:'关联关系',versions:'版本记录',impact:'使用与影响'}" :key="key" :class="{active:(route.tab||'definition')===key}" @click="setQuery({tab:key})">{{label}}</button></div>
    <section class="panel"><AccessGate v-if="guarded" :subject="accessRef"><ModelObjectContent :reference="route.id" :scope="route.scope" :tab="route.tab||'definition'"/></AccessGate><ModelObjectContent v-else :reference="route.id" :scope="route.scope" :tab="route.tab||'definition'"/></section>
  </template>
  <template v-else>
    <p v-if="route.page==='evaluation'" class="callout">Task Claim 内包含多个评价方面；同一模板、同一组评价条件组织一个多维 Claim。规则通过定义包导入并保存，当前不提供通用在线规则编辑器。</p>
    <div class="toolbar"><label class="search-label">搜索<input :value="route.q" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})" placeholder="名称、编号或定义内容"/></label><label>对象类型<select aria-label="对象类型" :value="activeKind" @change="setQuery({filter:($event.target as HTMLSelectElement).value,p:1})"><option v-for="k in typeOptions" :key="k" :value="k">{{kinds[k as Kind]}}</option></select></label><span class="muted">{{rows.length}} 项 · 精确数量</span></div>
    <section class="table-card"><table class="data-table"><thead><tr><th>对象</th><th>所属模型</th><th>定义或含义</th><th>版本与状态</th><th>操作</th></tr></thead><tbody><tr v-for="o in paged" :key="objectKey(o)"><td><button class="text-link" @click="openObject(objectKey(o))">{{o.name}}</button><small class="mono">{{o.id}}</small></td><td>{{o.space}}<small>{{o.model}}</small></td><td>{{o.summary}}</td><td>v{{o.version}}<small>{{o.status==='published'?'已保存':o.status==='recorded'?'历史记录':'草稿'}}</small></td><td><div class="button-row"><button class="btn" @click="openObject(objectKey(o))">详情</button><button v-if="editableKinds.includes(o.kind)" class="btn" @click="editInOwner(objectKey(o))">编辑</button></div></td></tr></tbody></table><div v-if="!rows.length" class="empty">{{selectedDomain&&!route.q?'本领域还没有已保存的'+kinds[activeKind as Kind]+'。可从右上方新增并直接保存。':'没有符合筛选条件的对象。'}}</div></section>
    <ObjectDrafts v-if="route.page==='domain'||route.page==='evaluation'" :kind="activeKind as Kind" :domain="route.domain||undefined"/>

    <div class="pagination"><button class="btn" :disabled="route.p<=1" @click="setQuery({p:route.p-1})">上一页</button><span>第 {{route.p}} / {{Math.max(1,Math.ceil(rows.length/10))}} 页</span><button class="btn" :disabled="route.p*10>=rows.length" @click="setQuery({p:route.p+1})">下一页</button></div>
    <p v-if="state.objects.length" class="muted">当前为可操作的统一示例目录，未将示例定义接入真实学生对话。</p>
  </template>
</div></template>
