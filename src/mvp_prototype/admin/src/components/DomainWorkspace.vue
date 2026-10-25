<script setup lang="ts">
import { computed, ref } from 'vue';
import { route, go, link, setQuery } from '../workbench/navigation';
import { domainMock, domainKinds, collectKnowledge, type DomainKind } from '../workbench/domain-mock';
import TaskWorkspace from './TaskWorkspace.vue';
import DomainModelDetail from './DomainModelDetail.vue';
import WorkbenchDialog from './WorkbenchDialog.vue';

const selected=computed(()=>domainMock.domains.find(d=>d.id===route.domain));
const kind=computed<DomainKind>(()=>route.filter==='solution'?'solution':route.filter==='kc'?'kc':'task');
const kindInfo=computed(()=>domainKinds[kind.value]);
const editing=computed(()=>route.id==='new'||route.tab==='edit');
const collections=computed(()=>({task:domainMock.tasks.filter(t=>t.domainId===route.domain),solution:domainMock.methods.filter(m=>m.domainId===route.domain),kc:domainMock.knowledge.filter(k=>k.domainId===route.domain)}));
const allRows=computed(()=>collections.value[kind.value]);
const rows=computed(()=>allRows.value.filter(o=>(o.name+' '+o.id+' '+('summary' in o?o.summary:o.description)).includes(route.q.trim())));
const current=computed(()=>allRows.value.find(o=>o.id===route.id));
const location=window.location;
const showDomain=ref(false),domainEditing=ref(false),domainName=ref(''),domainScope=ref('');
const domains=computed(()=>domainMock.domains.filter(d=>(d.name+' '+d.scope).includes(route.q.trim())));
function showDomainEditor(edit=false){domainEditing.value=edit;domainName.value=edit?selected.value?.name||'':'';domainScope.value=edit?selected.value?.scope||'':'';showDomain.value=true;}
function saveDomain(){
  const name=domainName.value.trim();if(!name)return;
  if(domainEditing.value&&selected.value){selected.value.name=name;selected.value.scope=domainScope.value;}
  else {const id='DOM-'+Date.now();domainMock.domains.push({id,name,scope:domainScope.value,description:''});go('domain',{domain:id,filter:'task'});}
  showDomain.value=false;
}
function switchKind(value:DomainKind){go('domain',{domain:route.domain,filter:value});}
function openObject(value:DomainKind,id:string){go('domain',{domain:route.domain,filter:value,id,returnTo:location.hash});}
function newObject(){go('domain',{domain:route.domain,filter:kind.value,id:'new',tab:'edit',returnTo:location.hash});}
function list(){go('domain',{domain:route.domain,filter:kind.value});}
function back(){if(route.returnTo.startsWith('#/students')||route.returnTo.startsWith('#/objects')||route.returnTo.startsWith('#/activity?')||route.returnTo.startsWith('#/domain?')||route.returnTo.startsWith('#/evaluation?')||route.returnTo.startsWith('#/textbooks?')||route.returnTo.startsWith('#/targets?')||route.returnTo.startsWith('#/learning-spaces?'))location.hash=route.returnTo;else list();}
function saved(id:string){go('domain',{domain:route.domain,filter:kind.value,id,returnTo:route.returnTo||link('domain',{domain:route.domain,filter:kind.value,q:route.q})});}
function cancel(){if(route.id==='new')back();else setQuery({tab:''});}
function taskCount(methodId:string){return domainMock.tasks.filter(t=>t.domainId===route.domain&&t.methods.includes(methodId)).length;}
function knowledgeRefs(id:string){return domainMock.methods.filter(m=>m.domainId===route.domain&&m.kc.includes(id)).length+domainMock.knowledge.filter(k=>k.domainId===route.domain&&k.prerequisites.includes(id)).length;}
function count(domainId:string,value:DomainKind){return (value==='task'?domainMock.tasks:value==='solution'?domainMock.methods:domainMock.knowledge).filter(o=>o.domainId===domainId).length;}
function tabKey(event:KeyboardEvent,index:number){const values=['task','solution','kc'] as const;const next=event.key==='ArrowRight'?(index+1)%3:event.key==='ArrowLeft'?(index+2)%3:-1;if(next<0)return;event.preventDefault();switchKind(values[next]!);document.getElementById('domain-tab-'+values[next])?.focus();}
</script>

<template><div class="wb-page domain-workspace">
  <button v-if="route.returnTo.startsWith('#/observed-')" class="text-link" @click="location.hash=route.returnTo">← 返回观测详情</button>
  <template v-if="!route.domain">
    <header class="page-header"><div><h2>领域管理</h2><p class="page-desc">选择领域，管理其中的任务、方法与知识。</p></div><button class="btn primary" @click="showDomainEditor()">新建领域</button></header>
    <div class="toolbar"><label class="search-label">搜索领域<input :value="route.q" placeholder="名称或覆盖范围" @input="setQuery({q:($event.target as HTMLInputElement).value})"/></label></div>
    <section class="table-card"><table class="data-table"><thead><tr><th>领域</th><th>覆盖范围</th><th>任务模板</th><th>方法模板</th><th>知识成分</th><th></th></tr></thead><tbody><tr v-for="d in domains" :key="d.id"><td><button class="text-link object-name" @click="go('domain',{domain:d.id,filter:'task'})">{{d.name}}</button></td><td>{{d.scope||'尚未填写'}}</td><td>{{count(d.id,'task')}}</td><td>{{count(d.id,'solution')}}</td><td>{{count(d.id,'kc')}}</td><td><button class="btn" @click="go('domain',{domain:d.id,filter:'task'})">进入领域 →</button></td></tr></tbody></table><p v-if="!domains.length" class="empty">没有匹配的领域。</p></section>
  </template>
  <template v-else-if="selected">
    <header class="page-header domain-header"><div><button class="text-link" @click="go('domain')">← 所有领域</button><h2>{{selected.name}}</h2><p class="page-desc">{{selected.scope}}</p></div><button class="btn" @click="showDomainEditor(true)">编辑领域</button></header>
    <div class="domain-tabs" role="tablist" aria-label="领域对象分区"><button v-for="(value,index) in (['task','solution','kc'] as const)" :id="'domain-tab-'+value" :key="value" role="tab" :aria-label="domainKinds[value].name+' '+domainKinds[value].english" :aria-selected="kind===value" :aria-controls="'domain-panel-'+value" :tabindex="kind===value?0:-1" :class="{active:kind===value}" @click="switchKind(value)" @keydown="tabKey($event,index)"><span class="tab-title">{{domainKinds[value].name}} <b>{{collections[value].length}}</b></span><small>{{domainKinds[value].english}}</small></button></div>
    <div :id="'domain-panel-'+kind" role="tabpanel" :aria-labelledby="'domain-tab-'+kind">
      <template v-if="!route.id">
        <div class="collection-tools"><label><span class="sr-only">搜索{{kindInfo.name}}</span><input :aria-label="'搜索'+kindInfo.name" :value="route.q" type="search" :placeholder="'搜索'+kindInfo.name+'的名称或内容'" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})"/></label><span class="muted">{{rows.length}} 项</span><button class="btn primary" @click="newObject">新建{{kindInfo.name}}</button></div>
        <section class="table-card domain-list"><table class="data-table"><thead><tr><th>{{kindInfo.name}}</th><th>{{kind==='task'?'任务目标':'定义说明'}}</th><th>{{kind==='task'?'关联方法':kind==='solution'?'适用任务':'先修知识'}}</th><th>{{kind==='kc'?'被引用':'知识汇总'}}</th><th></th></tr></thead><tbody><tr v-for="o in rows.slice((route.p-1)*10,route.p*10)" :key="o.id">
          <td><button class="text-link object-name" @click="openObject(kind,o.id)">{{o.name}}</button><small class="mono">{{o.id}}</small></td><td>{{'goal' in o?o.goal:'description' in o?o.description:''}}</td><td>{{'methods' in o?o.methods.length:kind==='solution'?taskCount(o.id):'prerequisites' in o?o.prerequisites.length:0}}</td><td>{{kind==='kc'?knowledgeRefs(o.id):collectKnowledge('methods' in o?o.methods:[o.id],route.domain).rows.length}}</td><td><button class="text-link" :aria-label="'查看'+o.name" @click="openObject(kind,o.id)">查看 →</button></td>
        </tr></tbody></table><div v-if="!rows.length" class="empty"><p>{{route.q?'没有找到匹配项，可调整搜索内容。':'还没有'+kindInfo.name+'，从新建开始。'}}</p></div></section>
        <div v-if="rows.length>10" class="pagination"><button class="btn" :disabled="route.p<=1" @click="setQuery({p:route.p-1})">上一页</button><span>{{route.p}} / {{Math.ceil(rows.length/10)}}</span><button class="btn" :disabled="route.p*10>=rows.length" @click="setQuery({p:route.p+1})">下一页</button></div>
      </template>
      <template v-else-if="current||route.id==='new'">
        <div class="object-return"><button class="text-link" @click="back">← {{route.returnTo.startsWith('#/students')?'返回学生状态':route.returnTo.startsWith('#/objects')?'返回空间观测':route.returnTo.startsWith('#/activity?')?'返回交互审查':route.returnTo.startsWith('#/evaluation?')?'返回 Claim':route.returnTo.startsWith('#/textbooks?')?'返回教材章节':route.returnTo.startsWith('#/targets?')?'返回学习目标':route.returnTo.startsWith('#/learning-spaces?')?'返回学习空间':route.returnTo.includes('id=')?'返回来源对象':'返回'+kindInfo.name+'列表'}}</button></div>
        <TaskWorkspace v-if="kind==='task'" :key="route.domain+':'+route.id" :task-id="route.id" :domain-id="route.domain" :editing="editing" @save="saved" @cancel="cancel" @open="openObject"/>
        <DomainModelDetail v-else :key="route.domain+':'+kind+':'+route.id" :kind="kind" :object-id="route.id" :domain-id="route.domain" :editing="editing" @edit="setQuery({tab:'edit'})" @save="saved" @cancel="cancel" @open="openObject"/>
      </template>
      <section v-else class="panel"><h3>当前对象不存在</h3><p>Mock 数据在刷新后恢复初始内容，请从列表重新选择。</p><button class="btn" @click="list">返回{{kindInfo.name}}列表</button></section>
    </div>
  </template>
  <section v-else class="panel"><h2>领域不存在</h2><p>请返回领域列表选择。</p><button class="btn" @click="go('domain')">返回领域列表</button></section>
  <WorkbenchDialog v-if="showDomain" :title="domainEditing?'编辑领域':'新建领域'" @close="showDomain=false"><form @submit.prevent="saveDomain"><label>领域名称<input v-model="domainName" required placeholder="例如：数学、厨艺"/></label><label>覆盖范围<textarea v-model="domainScope" placeholder="这个领域包含哪些知识和任务"/></label><div class="dialog-footer button-row"><button type="button" class="btn" @click="showDomain=false">取消</button><button class="btn primary" type="submit">{{domainEditing?'保存':'创建并进入'}}</button></div></form></WorkbenchDialog>
</div></template>

<style scoped>
.domain-workspace{max-width:1440px}.domain-header{align-items:center;margin-bottom:24px}.domain-header h2{font-size:28px;margin-top:10px}.domain-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-bottom:1px solid #d9e4dd;margin-bottom:22px;gap:8px}.domain-tabs button{background:transparent;border:0;border-bottom:3px solid transparent;text-align:left;padding:14px 18px 16px;color:#728579;display:flex;flex-direction:column;gap:4px}.domain-tabs button.active{color:#225d3f;border-bottom-color:#2d6a4f;background:linear-gradient(0deg,#edf5ef,transparent);border-radius:8px 8px 0 0}.tab-title{font-size:16px;font-weight:600}.tab-title b{font-size:12px;margin-left:8px;font-weight:500;background:#e8efea;border-radius:12px;padding:1px 8px}.domain-tabs small{font-size:12px;letter-spacing:.2px}.collection-tools{display:flex;align-items:center;gap:16px;margin:20px 0}.collection-tools label{margin:0;flex:1;max-width:440px}.collection-tools input{margin:0}.collection-tools>.btn{margin-left:auto}.object-name{font-size:14px;font-weight:600;line-height:1.7}.domain-list td{vertical-align:top;padding-top:20px;padding-bottom:20px}.domain-list th:first-child{width:30%}.domain-list th:nth-child(2){width:38%}.object-return{margin:0 0 16px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}@media(max-width:1000px){.domain-tabs button{padding:12px 8px}.tab-title{font-size:14px}.domain-tabs small{font-size:11px}.collection-tools{flex-wrap:wrap}.collection-tools label{min-width:180px}.domain-list th:first-child{width:28%}.domain-list th:nth-child(2){width:32%}}
</style>
