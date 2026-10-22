<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { state, catalog, domain, createDomain, updateDomain } from '../workbench/store';
import { route, go, setQuery } from '../workbench/navigation';
import ModelCatalog from './ModelCatalog.vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import PagingBar from './PagingBar.vue';

const showCreate = ref(false);const editingId=ref(''),baseVersion=ref(0);
const name = ref(''), scope = ref(''), description = ref(''), error = ref('');
watch([name,scope,description], () => { error.value=''; });
const selected = computed(() => domain(route.domain));
const location = window.location;
const rows = computed(() => {
  const query = route.q.trim().toLocaleLowerCase();
  const counts = new Map<string, {task:number; solution:number; kc:number}>();
  for (const o of catalog()) {
    if (!o.domainId || o.status !== 'published' || !['task','solution','kc'].includes(o.kind)) continue;
    const count = counts.get(o.domainId) || {task:0, solution:0, kc:0};
    count[o.kind as 'task'|'solution'|'kc']++;
    counts.set(o.domainId, count);
  }
  return state.domains.filter(d => !query || `${d.name} ${d.id} ${d.scope} ${d.description}`.toLocaleLowerCase().includes(query))
    .map(d => ({...d, count:counts.get(d.id) || {task:0,solution:0,kc:0}}));
});
watch(() => [rows.value.length, route.domain, route.p], () => {
  if (!route.domain && route.p > Math.max(1, Math.ceil(rows.value.length / 10))) setQuery({p:Math.max(1, Math.ceil(rows.value.length / 10))});
});
function openEdit(){if(!selected.value)return;editingId.value=selected.value.id;baseVersion.value=selected.value.version||1;name.value=selected.value.name;scope.value=selected.value.scope;description.value=selected.value.description;error.value='';showCreate.value=true;}
function openCreate() { editingId.value='';name.value=''; scope.value=''; description.value=''; error.value=''; showCreate.value=true; }
function create() {
  error.value='';
  try {
    if(editingId.value){updateDomain(editingId.value,name.value,scope.value,description.value,baseVersion.value);showCreate.value=false;return;}
    const id=createDomain(name.value,scope.value,description.value);
    showCreate.value=false;
    go('domain',{domain:id,returnTo:window.location.hash});
  } catch(e) { error.value=e instanceof Error?e.message:String(e); }
}
</script>

<template>
  <ModelCatalog v-if="route.domain && selected" @edit-domain="openEdit"/>
  <div v-else-if="route.domain" class="wb-page">
    <h2>领域不存在</h2><p class="callout">当前浏览器中没有这个领域，请返回领域列表选择。不会自动切换到其他领域。</p>
    <button class="btn" @click="go('domain')">返回领域列表</button>
  </div>
  <div v-else class="wb-page">
    <header class="page-header">
      <div><h2>领域管理</h2><p class="page-desc">先选择领域，再管理其中的任务模板、方法模板与知识成分。</p></div>
      <button class="btn primary" @click="openCreate">新建领域</button>
    </header>
    <div class="toolbar"><label class="search-label">搜索领域<input :value="route.q" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})" placeholder="名称、覆盖范围或编号" type="search"/></label><span class="muted">共 {{rows.length}} 个领域</span></div>
    <section class="table-card">
      <table class="data-table"><thead><tr><th>领域</th><th>覆盖范围</th><th>Task<br/>任务模板</th><th>Solution<br/>方法模板</th><th>KC<br/>知识成分</th><th>操作</th></tr></thead>
        <tbody><tr v-for="d in rows.slice((route.p-1)*10,route.p*10)" :key="d.id">
          <td><button class="text-link" @click="go('domain',{domain:d.id,returnTo:location.hash})">{{d.name}}</button></td>
          <td>{{d.scope}}</td><td>{{d.count.task}}</td><td>{{d.count.solution}}</td><td>{{d.count.kc}}</td>
          <td><button class="btn" :aria-label="`进入领域：${d.name}`" @click="go('domain',{domain:d.id,returnTo:location.hash})">进入领域</button></td>
        </tr></tbody>
      </table>
      <div v-if="!rows.length" class="empty">{{route.q?'没有匹配的领域，可调整搜索条件。':'还没有领域。新建领域后，可以逐步建立 Task、Solution 和 KC。'}}</div>
    </section>
    <PagingBar :total="rows.length"/>
    <p class="muted">数量按已保存的对象身份统计，各版本不重复计数；本地草稿不计入。</p>
  </div>
    <WorkbenchDialog v-if="showCreate" :title="editingId?'编辑领域':'新建领域'" @close="showCreate=false">
      <form @submit.prevent="create">
        <p class="lead">定义这个领域处理什么，不需要绑定教材或学生的学习空间。</p>
        <label>领域名称<input v-model="name" required maxlength="80" autocomplete="off" placeholder="例如：数学、厨艺"/></label>
        <label>覆盖范围<textarea v-model="scope" required maxlength="1000" placeholder="说明纳入的知识与任务范围，以及必要的边界"/></label>
        <label>说明（选填）<textarea v-model="description" maxlength="2000" placeholder="补充用途或需要管理员了解的背景"/></label>
        <p v-if="error" class="callout danger" role="alert">{{error}}</p>
        <div class="dialog-footer button-row"><button class="btn primary" type="submit">{{editingId?'保存':'创建并进入'}}</button><button class="btn" type="button" @click="showCreate=false">取消</button></div>
      </form>
    </WorkbenchDialog>
</template>
