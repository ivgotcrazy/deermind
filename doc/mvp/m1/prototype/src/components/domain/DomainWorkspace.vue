<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { domainData, domainStorageError, kinds, collection, taskIssues, collectKnowledge, knowledgeIssues, saveEntity, clone, id, type Kind, type Domain } from '../../model/domain';
import { loadTaskExample, taskExamples, type TaskExampleKey } from '../../model/domain-complex-examples';
import WorkbenchDialog from '../WorkbenchDialog.vue';
import TaskWorkspace from './TaskWorkspace.vue';
import MethodWorkspace from './MethodWorkspace.vue';
import KnowledgeWorkspace from './KnowledgeWorkspace.vue';
import DomainIntake from './DomainIntake.vue';
import { imports } from '../../model/imports';
import { loadDvtExample } from '../../model/dvt-example';

const props=defineProps<{hash:string}>();
const root=ref<HTMLElement|null>(null);
function showTop(){nextTick(()=>root.value?.closest('.page-container')?.scrollTo({top:0}));}
const params=computed(()=>new URLSearchParams(props.hash.split('?')[1]||''));
const domainId=computed(()=>params.value.get('domain')||'');
const domain=computed(()=>domainData.domains.find(d=>d.id===domainId.value));
const kind=computed<Kind>(()=>params.value.get('kind')==='solution'?'solution':params.value.get('kind')==='kc'?'kc':'task');
const objectId=computed(()=>params.value.get('id')||'');
const tab=computed(()=>params.value.get('tab')||'definition');
const pendingCount=computed(()=>imports.filter(d=>d.book.domainId===domainId.value).reduce((n,d)=>n+(d.flow?.requests.filter(r=>r.status==='pending').reduce((total,r)=>total+r.elements.filter(e=>!r.removed?.includes(e.id)&&!r.result[e.id]).length,0)||0),0));
const object=computed(()=>collection(kind.value).find(o=>o.id===objectId.value&&o.domainId===domainId.value));
const query=ref(''),page=ref(1),notice=ref('');
const editor=ref<Domain|null>(null);
const examples=ref(false);
function openExample(key:TaskExampleKey,latest=false){const domainId=loadTaskExample(key,latest);examples.value=false;go(domainId);}
const rows=computed(()=>collection(kind.value).filter(o=>o.domainId===domainId.value&&(o.name+' '+o.id).toLowerCase().includes(query.value.trim().toLowerCase())));
const domains=computed(()=>domainData.domains.filter(d=>(d.name+' '+d.scope).includes(query.value.trim())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10)));
watch(()=>props.hash,()=>{query.value='';page.value=1;notice.value='';showTop();},{immediate:true});
watch(query,()=>page.value=1);
function go(d='',k:Kind='task',key='',t='definition'){
  const p=new URLSearchParams();if(d)p.set('domain',d);if(d)p.set('kind',k);if(key)p.set('id',key);if(t!=='definition')p.set('tab',t);
  location.hash='/domain'+(p.size?'?'+p:'');
}
function open(k:Kind,key:string,t='definition'){go(domainId.value,k,key,t);}
function domainEditor(){editor.value=domain.value?clone(domain.value):{id:id('DOM'),name:'',scope:'',description:'',version:0};}
function saveDomain(){if(!editor.value?.name.trim())return;const d=saveEntity(domainData.domains,editor.value);editor.value=null;go(d.id);}
function issues(key:string){
  if(kind.value==='task'){const t=domainData.tasks.find(t=>t.id===key)!;return taskIssues(t);}
  if(kind.value==='solution')return collectKnowledge([key],domainId.value).issues;
  return knowledgeIssues(domainData.knowledge.find(k=>k.id===key)!);
}
function count(d:string,k:Kind){return collection(k).filter(x=>x.domainId===d).length;}
function saved(key:string){if(objectId.value==='new')open(kind.value,key);else notice.value='修改已保存到本浏览器。相关实例的检查状态会按当前定义重新核对。';showTop();}
</script>

<template><section ref="root" class="wb-page domain-workspace">
  <p v-if="domainStorageError" class="callout danger" role="alert">{{domainStorageError}}</p>
  <template v-if="!domainId">
    <header class="page-header"><div><h2>领域管理</h2><p class="page-desc">维护可复用的任务、方法、知识及具体题目。</p></div><div class="button-row"><button class="btn" :disabled="!!domainStorageError" @click="examples=true">载入示例领域</button><button class="btn primary" :disabled="!!domainStorageError" @click="domainEditor">新建领域</button></div></header>
    <label class="search-label">搜索领域<input v-model="query" type="search" placeholder="名称或覆盖范围"/></label>
    <section class="panel"><table v-if="domains.length" class="data-table"><thead><tr><th>领域</th><th>覆盖范围</th><th>任务</th><th>方法</th><th>知识</th><th>题目</th></tr></thead><tbody><tr v-for="d in domains" :key="d.id"><td><button class="text-link model-name" @click="go(d.id)">{{d.name}}</button><small>{{d.id}}</small></td><td>{{d.scope||'尚未填写'}}</td><td>{{count(d.id,'task')}}</td><td>{{count(d.id,'solution')}}</td><td>{{count(d.id,'kc')}}</td><td>{{domainData.instances.filter(q=>q.domainId===d.id).length}}</td></tr></tbody></table>
      <div v-else class="empty"><h3>{{query?'没有匹配的领域':'从一个空领域开始'}}</h3><p>新建领域后，可分别添加任务、方法和知识。也可以载入小学、初中、高中数学或 K8s 的完整示例。</p></div>
    </section><p class="muted">示例为人工编写的 mock；新建领域没有预填模型，不改变教材导入草稿。</p>
  </template>
  <template v-else-if="domain">
    <nav class="breadcrumbs" aria-label="当前位置"><button class="text-link" @click="go()">领域管理</button><span>/</span><button class="text-link" @click="go(domain.id)">{{domain.name}}</button><template v-if="objectId"><span>/</span><button class="text-link" @click="go(domain.id,kind)">{{kinds[kind].name}}</button></template></nav>
    <template v-if="!objectId">
      <header class="page-header"><div><h2>{{domain.name}}</h2><p class="page-desc">{{domain.scope||'尚未填写覆盖范围'}}</p><p v-if="domain.description" class="muted">{{domain.description}}</p></div><button class="btn" @click="domainEditor">编辑领域</button></header>
      <nav class="domain-tabs" aria-label="领域对象"><button v-for="(info,k) in kinds" :key="k" :class="{active:kind===k&&tab!=='intake'}" :aria-current="kind===k&&tab!=='intake'?'page':undefined" @click="go(domain.id,k)">{{info.name}} <span>{{count(domain.id,k)}}</span><small>{{info.english}}</small></button><button :class="{active:tab==='intake'}" @click="go(domain.id,'task','','intake')">待入库内容 <span>{{pendingCount}}</span><small>教材来源</small></button></nav>
      <DomainIntake v-if="tab==='intake'" :domain-id="domain.id" :source="params.get('source')||''" :chapter="params.get('chapter')||''"/>
      <template v-else>
      <div class="object-toolbar"><label class="search-label">搜索{{kinds[kind].name}}<input v-model="query" type="search" placeholder="名称或编号"/></label><button class="btn primary" @click="open(kind,'new')">新建{{kinds[kind].name}}</button></div>
      <section class="panel"><table v-if="rows.length" class="data-table"><thead><tr><th>{{kinds[kind].name}}</th><th>说明</th><th>准备情况</th></tr></thead><tbody><tr v-for="row in rows.slice((page-1)*10,page*10)" :key="row.id"><td><button class="text-link model-name" @click="open(kind,row.id)">{{row.name}}</button><small>{{row.id}} · v{{row.version}}</small></td><td>{{'summary' in row?row.summary:row.description||'尚未填写'}}</td><td><span class="badge" :class="{warning:issues(row.id).length}">{{issues(row.id).length?'待补齐':'结构完整'}}</span><small>{{issues(row.id)[0]||'语义质量仍需核对'}}</small></td></tr></tbody></table><p v-else class="empty">{{query?'没有匹配项。':'这里还没有'+kinds[kind].name+'，可以从新建开始。'}}</p>
        <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page===1" @click="page--">上一页</button><span>{{page}} / {{pages}}</span><button class="btn" :disabled="page===pages" @click="page++">下一页</button></div>
      </section>
      </template>
    </template>
    <template v-else-if="objectId==='new'||object">
      <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
      <fieldset :disabled="!!domainStorageError" class="object-fieldset">
        <TaskWorkspace v-if="kind==='task'" :key="objectId" :domain-id="domain.id" :object-id="objectId" :tab="tab" @saved="saved" @open="open" @back="go(domain.id,kind)"/>
        <MethodWorkspace v-else-if="kind==='solution'" :key="objectId" :domain-id="domain.id" :object-id="objectId" @saved="saved" @open="open" @back="go(domain.id,kind)"/>
        <KnowledgeWorkspace v-else :key="objectId" :domain-id="domain.id" :object-id="objectId" @saved="saved" @open="open" @back="go(domain.id,kind)"/>
      </fieldset>
    </template>
    <div v-else class="panel"><h3>未找到这个对象</h3><p>对象不存在或不属于当前领域。</p><button class="btn" @click="go(domain.id,kind)">返回列表</button></div>
  </template>
  <div v-else class="panel"><h2>未找到这个领域</h2><button class="btn" @click="go()">返回领域列表</button></div>
  <WorkbenchDialog v-if="editor" :title="editor.version?'编辑领域':'新建领域'" @close="editor=null"><form @submit.prevent="saveDomain"><label>领域名称<input v-model="editor.name" required placeholder="例如：小学数学"/></label><label>覆盖范围<textarea v-model="editor.scope" rows="3" placeholder="说明涉及哪些知识和任务"/></label><label>领域说明<textarea v-model="editor.description" rows="3"/></label><div class="dialog-footer"><button type="button" class="btn" @click="editor=null">取消</button><button class="btn primary" :disabled="!!domainStorageError">{{editor.version?'保存领域':'创建并进入'}}</button></div></form></WorkbenchDialog>
  <WorkbenchDialog v-if="examples" title="选择示例领域" wide @close="examples=false"><p class="muted">每个示例包含任务定义、方法、知识和具体实例。再次打开保留你的修改；新版方法示例另存一份，不覆盖旧记录。</p><p><button class="btn primary" @click="go(loadDvtExample());examples=false">理解 d=v×t · 新模型示例</button></p><table class="data-table"><thead><tr><th>示例</th><th>查看重点</th><th>操作</th></tr></thead><tbody><tr v-for="sample in taskExamples" :key="sample.key"><td>{{sample.name}}</td><td>{{sample.description}}</td><td><button class="btn" :aria-label="'打开示例 '+sample.key" :disabled="!!domainStorageError" @click="openExample(sample.key)">{{domainData.domains.some(d=>d.exampleKey===sample.key)?'打开':'载入并打开'}}</button><button v-if="sample.key!=='primary'&&domainData.domains.some(d=>d.exampleKey===sample.key&&d.exampleRevision!==2)" class="btn" :aria-label="'新版方法示例 '+sample.key" :disabled="!!domainStorageError" @click="openExample(sample.key,true)">{{domainData.domains.some(d=>d.exampleKey===sample.key&&d.exampleRevision===2)?'打开新版方法示例':'载入新版方法示例'}}</button></td></tr></tbody></table></WorkbenchDialog>
</section></template>
