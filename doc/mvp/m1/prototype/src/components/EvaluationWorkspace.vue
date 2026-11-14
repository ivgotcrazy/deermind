<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import ClaimCriteriaPanel from './ClaimCriteriaPanel.vue';
import { clone, id, domainData, domainStorageError } from '../model/domain';
import { storageError } from '../model/imports';
import { blankClaim, claimTask, claimIssues, evaluationData, evaluationStorageError, saveDefinition, taskUrl, type Claim } from '../model/evaluation';
import { loadEvaluationExample } from '../model/evaluation-example';

const props=defineProps<{hash:string}>();
const params=computed(()=>new URLSearchParams(props.hash.split('?')[1]||''));
const key=computed(()=>params.value.get('id')||'');
const current=computed(()=>evaluationData.claims.find(c=>c.id===key.value));
const domainFilter=ref(params.value.get('domain')||''),taskFilter=ref(params.value.get('task')||''),query=ref(''),page=ref(1);
const domainName=(key:string)=>domainData.domains.find(d=>d.id===key)?.name||'领域不存在';
const tasks=computed(()=>domainData.tasks.filter(t=>!domainFilter.value||t.domainId===domainFilter.value));
const rows=computed(()=>evaluationData.claims.filter(c=>(!domainFilter.value||c.domainId===domainFilter.value)&&(!taskFilter.value||c.taskId===taskFilter.value)&&(c.name+' '+(claimTask(c)?.name||'')+' '+c.id).toLowerCase().includes(query.value.trim().toLowerCase())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10)));
const mode=ref<''|'new'|'basic'>(''),draft=ref<Claim>(blankClaim()),error=ref(''),notice=ref(''),adoptTask=ref(false);
const selectedTask=computed(()=>claimTask(draft.value));
const blocked=computed(()=>!!evaluationStorageError.value||!!domainStorageError.value);
const problems=computed(()=>current.value?claimIssues(current.value):[]);
const references=computed(()=>current.value?evaluationData.targets.filter(t=>t.requirements.some(r=>r.claimId===current.value!.id)):[]);
watch([domainFilter,taskFilter,query],()=>page.value=1);
watch(key,()=>{mode.value='';notice.value='';document.querySelector('.page-container')?.scrollTo({top:0});});
watch(()=>params.value.get('method'),()=>{notice.value='';});
function selectMethod(methodId:string){
  const next=new URLSearchParams(params.value);
  next.set('method',methodId);
  location.hash='/evaluation?'+next;
}
function open(c:Claim){location.hash='/evaluation?'+new URLSearchParams({id:c.id,domain:domainFilter.value,task:taskFilter.value});}
function edit(next:typeof mode.value){draft.value=current.value?clone(current.value):blankClaim(domainFilter.value,taskFilter.value);mode.value=next;error.value='';adoptTask.value=false;}
function chooseTask(){const t=selectedTask.value;draft.value.taskVersion=t?.version||0;if(t&&!draft.value.name)draft.value.name=t.name+'的能力评价';}
function addAspect(){draft.value.aspects.push({id:id('ASPECT'),name:'',enabled:true,reason:'',custom:true});}
function fail(message:string){error.value=message;nextTick(()=>document.querySelector('dialog [role=alert]')?.scrollIntoView({block:'center'}));}
function save(){
  if(blocked.value)return;
  const c=draft.value;
  if(!c.aspects.some(a=>a.enabled))return fail('至少保留一个适用的评价方面。');
  const names=new Set<string>();
  for(const a of c.aspects){
    const name=a.name.trim();
    if(!name)return fail('请填写新增评价方面的名称。');
    if(names.has(name))return fail('评价方面名称不能重复。');
    if((!a.enabled||a.custom)&&!a.reason.trim())return fail('请说明「'+name+'」的裁剪或扩展依据。');
    names.add(name);
    a.name=name;
  }
  if(!c.name.trim()||!selectedTask.value)return fail('请选择领域、任务，并填写 Claim 名称。');
  if(c.taskVersion!==selectedTask.value.version){
    if(!adoptTask.value)return fail('任务已更新，请先核对并确认采用当前任务版本。');
    c.taskVersion=selectedTask.value.version;
    c.rules=c.rules.filter(r=>selectedTask.value!.methods.includes(r.methodId));
    c.executions=c.executions.filter(e=>selectedTask.value!.methods.includes(e.methodId));
  }

  const next=saveDefinition(evaluationData.claims,c,mode.value==='new'?'创建 Claim':'修改 Claim 基本信息');
  if(!next)return;
  const creating=mode.value==='new';mode.value='';if(creating)open(next);else notice.value='已保存。引用此 Claim 的目标需核对新版本；没有修改任何学生判断。';
}
function example(){if(blocked.value||storageError.value)return;const t=loadEvaluationExample();location.hash=t.requirements[0]?'/evaluation?id='+t.requirements[0].claimId:'/evaluation';}
</script>

<template><section class="wb-page evaluation-workspace">
  <p v-if="evaluationStorageError||domainStorageError" role="alert" class="callout danger">{{evaluationStorageError||domainStorageError}}</p>
  <template v-if="!key">
    <header class="page-header"><div><h2>评估管理</h2><p class="page-desc">按领域和任务定义如何评价能力。Claim 可由不同教材的学习目标选用。</p></div><div class="button-row"><button class="btn" :disabled="blocked||!!storageError" @click="example">打开四分之一样例</button><button class="btn primary" :disabled="blocked" @click="edit('new')">新建 Claim</button></div></header>
    <div class="evaluation-filters"><label>领域<select aria-label="领域" v-model="domainFilter" @change="taskFilter='' "><option value="">全部领域</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>Task<select aria-label="Task" v-model="taskFilter"><option value="">全部任务</option><option v-for="t in tasks" :key="t.id" :value="t.id">{{t.name}}</option></select></label><label>查找 Claim<input v-model="query" type="search" placeholder="名称、任务或编号"/></label></div>
    <section class="panel table-scroll"><table v-if="rows.length" class="data-table"><thead><tr><th>Claim</th><th>领域与 Task</th><th>评价方面</th><th>配置情况</th><th>操作</th></tr></thead><tbody><tr v-for="c in rows.slice((page-1)*10,page*10)" :key="c.id"><td><button class="text-link model-name" @click="open(c)">{{c.name}}</button><small>{{c.id}} · v{{c.version}}</small></td><td>{{domainName(c.domainId)}}<small>{{claimTask(c)?.name||'任务不存在'}} · 引用 v{{c.taskVersion}}</small></td><td>{{c.aspects.filter(a=>a.enabled).map(a=>a.name).join('、')}}</td><td><span class="badge" :class="{warning:claimIssues(c).length}">{{claimIssues(c).length?'待补充／核对':'定义已填写'}}</span><small>{{c.updatedAt}}</small></td><td><button class="btn" @click="open(c)">查看</button></td></tr></tbody></table><div v-else class="empty"><h3>暂无符合条件的 Claim</h3><p>选择领域与 Task 后，可以创建判据并配置方法。</p><a href="#/domain">前往领域管理 →</a></div></section>
    <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page<=1" @click="page--">上一页</button>{{page}} / {{pages}}<button class="btn" :disabled="page>=pages" @click="page++">下一页</button></div>
    <p class="muted">样例按钮会新增一组独立的领域、教材和目标 mock；再次打开保留修改，不覆盖已有资料。</p>
  </template>
  <template v-else-if="current">
    <a class="text-link" href="#/evaluation">← 返回 Claim 列表</a>
    <header class="page-header"><div><h2>{{current.name}}</h2><p class="page-desc">{{domainName(current.domainId)}} · {{current.id}} · v{{current.version}}</p></div><button class="btn" :disabled="blocked" @click="edit('basic')">编辑基本信息</button></header>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <details v-if="problems.length" class="preparation"><summary>{{problems.length}} 项定义待补充或核对</summary><ul><li v-for="s in problems" :key="s">{{s}}</li></ul></details>
    <section class="panel"><dl class="field-list"><dt>关联 Task</dt><dd><a v-if="claimTask(current)" :href="taskUrl(claimTask(current)!)">{{claimTask(current)!.name}} ↗</a><span v-else>任务不存在</span> · v{{current.taskVersion}}</dd></dl></section>
    <ClaimCriteriaPanel :key="current.id" :claim="current" :requested-method="params.get('method')||''" @select-method="selectMethod" :blocked="blocked||claimTask(current)?.version!==current.taskVersion" @saved="notice=$event"/>
    <details class="panel"><summary>引用目标与修改记录</summary><p v-if="!references.length">尚未被学习目标选用。</p><p v-for="t in references" :key="t.id"><a :href="'#/targets?id='+t.id">{{t.name}} →</a></p><ul><li v-for="(h,i) in current.history" :key="i">v{{h.version}} · {{h.at}} · {{h.change}}</li></ul></details>
  </template>
  <div v-else class="empty"><h2>当前浏览器中没有这个 Claim</h2><a href="#/evaluation">返回评估管理</a></div>

  <WorkbenchDialog v-if="mode" :title="mode==='new'?'新建 Claim':'编辑 Claim 基本信息'" wide @close="mode=''">
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
      <div v-if="mode==='new'" class="edit-pair"><label>所属领域<select aria-label="所属领域" v-model="draft.domainId" @change="draft.taskId='';draft.taskVersion=0"><option value="">请选择领域</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>关联 Task<select aria-label="关联 Task" v-model="draft.taskId" @change="chooseTask"><option value="">请选择任务</option><option v-for="t in domainData.tasks.filter(t=>t.domainId===draft.domainId)" :key="t.id" :value="t.id">{{t.name}}</option></select></label></div>
      <p v-else class="muted">关联任务：{{selectedTask?.name}}。修改其他任务的评价，请另建 Claim。</p>
      <p v-if="mode==='new'&&draft.domainId&&!domainData.tasks.some(t=>t.domainId===draft.domainId)" class="callout">该领域尚无任务，请先到领域管理创建 Task。</p>
      <label>Claim 名称<input v-model="draft.name"/></label>
      <p v-if="selectedTask?.exclusions" class="muted">Task 边界参考：{{selectedTask.exclusions}}</p>
    <fieldset v-if="mode==='basic'" class="aspect-settings" @input="error=''">
      <legend>评价方面</legend>
      <div v-for="a in draft.aspects" :key="a.id" class="aspect-setting">
        <div class="aspect-row">
          <label class="check-line"><input v-model="a.enabled" type="checkbox" :aria-label="'启用'+(a.name||'新增评价方面')"/>{{a.custom?'启用':a.name}}</label>
          <input v-if="a.custom" v-model="a.name" aria-label="自定义方面名称" placeholder="方面名称"/>
          <button v-if="a.custom&&!current?.aspects.some(old=>old.id===a.id)" class="text-link" @click="draft.aspects=draft.aspects.filter(item=>item.id!==a.id)">撤销新增</button>
        </div>
        <label v-if="!a.enabled||a.custom">裁剪或扩展依据<textarea v-model="a.reason" rows="2" :aria-label="(a.name||'新增评价方面')+'的裁剪或扩展依据'"/></label>
      </div>
      <button class="btn" @click="addAspect">增加评价方面</button>
    </fieldset>
    <label v-if="selectedTask&&draft.taskVersion!==selectedTask.version" class="check-line callout amber"><input v-model="adoptTask" type="checkbox"/>已核对任务 v{{selectedTask.version}} 的范围与方法，采用此版本</label>
    <p class="muted">保存到本浏览器。未填写的定义会列为待补充，不会产生学生 Belief。</p>
    <footer class="dialog-footer"><button class="btn" @click="mode=''">取消</button><button class="btn primary" :disabled="blocked" @click="save">{{mode==='new'?'创建 Claim':'保存修改'}}</button></footer>
  </WorkbenchDialog>
</section></template>

<style scoped>
.aspect-settings{border:0;margin:18px 0;padding:0}.aspect-settings legend{font-weight:600}.aspect-setting{padding:7px 0;border-bottom:1px solid #e4ece6}.aspect-row{display:flex;align-items:center;gap:12px}.aspect-row label{margin:0}.aspect-row input:not([type=checkbox]){max-width:320px;margin:0}.aspect-settings>.btn{margin-top:12px}

.evaluation-filters{display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:18px}.panel summary{cursor:pointer;color:#31543f}.row-between h3{margin:0}@media(max-width:950px){.evaluation-filters{grid-template-columns:1fr 1fr}}
</style>
