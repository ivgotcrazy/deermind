<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import { clone, id, domainData, domainStorageError } from '../model/domain';
import { storageError } from '../model/imports';
import { blankClaim, claimTask, claimIssues, claimReferenceIssues, evaluationData, evaluationStorageError, saveDefinition, methodName, taskUrl, type Claim, type Aspect } from '../model/evaluation';
import { loadEvaluationExample } from '../model/evaluation-example';

const props=defineProps<{hash:string}>();
const params=computed(()=>new URLSearchParams(props.hash.split('?')[1]||''));
const key=computed(()=>params.value.get('id')||'');
const current=computed(()=>evaluationData.claims.find(c=>c.id===key.value));
const domainFilter=ref(params.value.get('domain')||''),taskFilter=ref(params.value.get('task')||''),query=ref(''),page=ref(1);
const domainName=(key:string)=>domainData.domains.find(d=>d.id===key)?.name||'领域不存在';
const methodUrl=(domain:string,key:string)=>'#/domain?'+new URLSearchParams({domain,kind:'solution',id:key});
const tasks=computed(()=>domainData.tasks.filter(t=>!domainFilter.value||t.domainId===domainFilter.value));
const rows=computed(()=>evaluationData.claims.filter(c=>(!domainFilter.value||c.domainId===domainFilter.value)&&(!taskFilter.value||c.taskId===taskFilter.value)&&(c.name+' '+(claimTask(c)?.name||'')+' '+c.id).toLowerCase().includes(query.value.trim().toLowerCase())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10)));
const mode=ref<''|'new'|'basic'|'methods'|'aspect'>(''),draft=ref<Claim>(blankClaim()),aspect=ref<Aspect|null>(null),error=ref(''),notice=ref(''),adoptTask=ref(false);
const selectedTask=computed(()=>claimTask(draft.value));
const blocked=computed(()=>!!evaluationStorageError.value||!!domainStorageError.value);
const problems=computed(()=>current.value?claimIssues(current.value):[]);
const references=computed(()=>current.value?evaluationData.targets.filter(t=>t.requirements.some(r=>r.claimId===current.value!.id)):[]);
watch([domainFilter,taskFilter,query],()=>page.value=1);
watch(()=>props.hash,()=>{mode.value='';notice.value='';document.querySelector('.page-container')?.scrollTo({top:0});});
function open(c:Claim){location.hash='/evaluation?'+new URLSearchParams({id:c.id,domain:domainFilter.value,task:taskFilter.value});}
function edit(next:typeof mode.value){draft.value=current.value?clone(current.value):blankClaim(domainFilter.value,taskFilter.value);mode.value=next;error.value='';adoptTask.value=false;}
function chooseTask(){const t=selectedTask.value;draft.value.taskVersion=t?.version||0;draft.value.methods=[];if(t&&!draft.value.name)draft.value.name=t.name+'的能力评价';}
function editAspect(a?:Aspect){edit('aspect');aspect.value=a?clone(a):{id:id('ASPECT'),name:'',enabled:true,criterion:'',insufficient:'',counter:'',reason:'',custom:true};}
function fail(message:string){error.value=message;nextTick(()=>document.querySelector('dialog [role=alert]')?.scrollIntoView({block:'center'}));}
function save(){
  if(blocked.value)return;
  const c=draft.value;
  if(mode.value==='aspect'){
    const a=aspect.value!;
    if(!a.name.trim())return fail('请填写评价方面名称。');
    if((!a.enabled||a.custom)&&!a.reason.trim())return fail('请说明裁剪或扩展的依据。');
    if(c.aspects.some(x=>x.id!==a.id&&x.name.trim()===a.name.trim()))return fail('评价方面名称不能重复。');
    const index=c.aspects.findIndex(x=>x.id===a.id);if(index<0)c.aspects.push(clone(a));else c.aspects[index]=clone(a);
    if(!c.aspects.some(x=>x.enabled))return fail('至少保留一个适用的评价方面。');
  }
  if(!c.name.trim()||!selectedTask.value)return fail('请选择领域、任务，并填写 Claim 名称。');
  if(c.taskVersion!==selectedTask.value.version){
    if(!adoptTask.value)return fail('任务已更新，请先核对并确认采用当前任务版本。');
    c.taskVersion=selectedTask.value.version;
  }
  if(mode.value==='methods'){
    const issues=claimReferenceIssues(c);if(issues.length)return fail(issues.join('；'));
  }
  const next=saveDefinition(evaluationData.claims,c,mode.value==='new'?'创建 Claim':mode.value==='aspect'?'修改评价方面：'+aspect.value!.name:mode.value==='methods'?'修改方法与帮助条件':'修改范围与基本信息');
  if(!next)return;
  const creating=mode.value==='new';mode.value='';if(creating)open(next);else notice.value='已保存。引用此 Claim 的目标需核对新版本；没有修改任何学生判断。';
}
function example(){if(blocked.value||storageError.value)return;const t=loadEvaluationExample();location.hash='/evaluation?id='+t.requirements[0].claimId;}
</script>

<template><section class="wb-page evaluation-workspace">
  <p v-if="evaluationStorageError||domainStorageError" role="alert" class="callout danger">{{evaluationStorageError||domainStorageError}}</p>
  <template v-if="!key">
    <header class="page-header"><div><h2>评估管理</h2><p class="page-desc">按领域和任务定义如何评价能力。Claim 可由不同教材的学习目标选用。</p></div><div class="button-row"><button class="btn" :disabled="blocked||!!storageError" @click="example">打开四分之一样例</button><button class="btn primary" :disabled="blocked" @click="edit('new')">新建 Claim</button></div></header>
    <div class="evaluation-filters"><label>领域<select aria-label="领域" v-model="domainFilter" @change="taskFilter='' "><option value="">全部领域</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>Task<select aria-label="Task" v-model="taskFilter"><option value="">全部任务</option><option v-for="t in tasks" :key="t.id" :value="t.id">{{t.name}}</option></select></label><label>查找 Claim<input v-model="query" type="search" placeholder="名称、任务或编号"/></label></div>
    <section class="panel table-scroll"><table v-if="rows.length" class="data-table"><thead><tr><th>Claim</th><th>领域与 Task</th><th>评价方面</th><th>配置情况</th><th>操作</th></tr></thead><tbody><tr v-for="c in rows.slice((page-1)*10,page*10)" :key="c.id"><td><button class="text-link model-name" @click="open(c)">{{c.name}}</button><small>{{c.id}} · v{{c.version}}</small></td><td>{{domainName(c.domainId)}}<small>{{claimTask(c)?.name||'任务不存在'}} · 引用 v{{c.taskVersion}}</small></td><td>{{c.aspects.filter(a=>a.enabled).map(a=>a.name).join('、')}}</td><td><span class="badge" :class="{warning:claimIssues(c).length}">{{claimIssues(c).length?'待补充／核对':'定义已填写'}}</span><small>{{c.updatedAt}}</small></td><td><button class="btn" @click="open(c)">查看</button></td></tr></tbody></table><div v-else class="empty"><h3>暂无符合条件的 Claim</h3><p>先选择领域中的 Task，再定义评价范围、方法条件和评价方面。无需先导入教材。</p><a href="#/domain">前往领域管理 →</a></div></section>
    <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page<=1" @click="page--">上一页</button>{{page}} / {{pages}}<button class="btn" :disabled="page>=pages" @click="page++">下一页</button></div>
    <p class="muted">样例按钮会新增一组独立的领域、教材和目标 mock；再次打开保留修改，不覆盖已有资料。</p>
  </template>
  <template v-else-if="current">
    <a class="text-link" href="#/evaluation">← 返回 Claim 列表</a>
    <header class="page-header"><div><h2>{{current.name}}</h2><p class="page-desc">{{domainName(current.domainId)}} · {{current.id}} · v{{current.version}}</p></div><button class="btn" :disabled="blocked" @click="edit('basic')">编辑基本信息</button></header>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <details v-if="problems.length" class="preparation"><summary>{{problems.length}} 项定义待补充或核对</summary><ul><li v-for="s in problems" :key="s">{{s}}</li></ul></details>
    <section class="panel"><h3>任务与评价范围</h3><dl class="field-list"><dt>关联 Task</dt><dd><a v-if="claimTask(current)" :href="taskUrl(claimTask(current)!)">{{claimTask(current)!.name}} ↗</a><span v-else>任务不存在</span> · 引用任务 v{{current.taskVersion}}</dd><dt>评价范围</dt><dd>{{current.scope||'待填写'}}</dd></dl></section>
    <section class="panel"><div class="row-between"><h3>方法与帮助条件</h3><button class="btn" :disabled="blocked" @click="edit('methods')">编辑条件</button></div><dl class="field-list"><dt>方法要求</dt><dd>{{current.methodMode==='all'?'分别覆盖每一种方法':current.methods.length===1?'使用指定方法':'任选一种允许的方法'}}<ul><li v-for="m in current.methods" :key="m"><a :href="methodUrl(current.domainId,m)">{{methodName(m)}} ↗</a></li></ul><span v-if="!current.methods.length">尚未选择方法</span></dd><dt>帮助与工具</dt><dd>{{current.support||'待填写'}}</dd></dl></section>
    <section class="panel table-scroll"><div class="row-between"><h3>评价方面</h3><button class="btn" :disabled="blocked" @click="editAspect()">增加评价方面</button></div><p class="muted">这些是同一 Claim 的内部方面。未检测保持未知，不能因为暂时没有证据就裁剪。</p><table class="data-table aspect-table"><thead><tr><th>方面</th><th>支持这一能力的表现</th><th>证据不足与反证</th><th>操作</th></tr></thead><tbody><tr v-for="a in current.aspects" :key="a.id"><td><strong>{{a.name}}</strong><small>{{a.enabled?'适用':'不适用'}}{{a.custom?' · 扩展':''}}</small><small v-if="a.reason">依据：{{a.reason}}</small></td><td class="multiline">{{a.enabled?(a.criterion||'待填写'):'不纳入本 Claim 评价'}}</td><td><template v-if="a.enabled"><p><span class="muted">证据不足：</span>{{a.insufficient||'待填写'}}</p><p><span class="muted">反证：</span>{{a.counter||'待填写'}}</p></template><span v-else>—</span></td><td><button class="btn" :disabled="blocked" :aria-label="'编辑'+a.name" @click="editAspect(a)">编辑</button></td></tr></tbody></table></section>
    <details class="panel"><summary>共同评价规则</summary><ul><li>同一次作答可支持多个方面，但不重复算成多次独立表现。</li><li>只根据实际发生的帮助、所用方法和任务条件解释表现；受助成功不等于独立掌握。</li><li>证据不足保留未知；相互矛盾的证据一起保留，不由最近一次正确自动覆盖。</li><li>经过时间不自动判为遗忘；没有后测不能确认延迟保持。不平均四个方面生成总掌握率。</li></ul><p class="muted">此处维护评价定义；具体证据聚合与校准在工程阶段实现。</p></details>
    <details class="panel"><summary>引用目标与修改记录</summary><p v-if="!references.length">尚未被学习目标选用。</p><p v-for="t in references" :key="t.id"><a :href="'#/targets?id='+t.id">{{t.name}} →</a></p><ul><li v-for="(h,i) in current.history" :key="i">v{{h.version}} · {{h.at}} · {{h.change}}</li></ul></details>
  </template>
  <div v-else class="empty"><h2>当前浏览器中没有这个 Claim</h2><a href="#/evaluation">返回评估管理</a></div>

  <WorkbenchDialog v-if="mode" :title="mode==='new'?'新建 Claim':mode==='basic'?'编辑基本信息':mode==='methods'?'编辑方法与帮助条件':'编辑评价方面'" wide @close="mode=''">
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
    <template v-if="mode==='new'||mode==='basic'">
      <div v-if="mode==='new'" class="edit-pair"><label>所属领域<select aria-label="所属领域" v-model="draft.domainId" @change="draft.taskId='';draft.taskVersion=0"><option value="">请选择领域</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>关联 Task<select aria-label="关联 Task" v-model="draft.taskId" @change="chooseTask"><option value="">请选择任务</option><option v-for="t in domainData.tasks.filter(t=>t.domainId===draft.domainId)" :key="t.id" :value="t.id">{{t.name}}</option></select></label></div>
      <p v-else class="muted">关联任务：{{selectedTask?.name}}。修改其他任务的评价，请另建 Claim。</p>
      <p v-if="mode==='new'&&draft.domainId&&!domainData.tasks.some(t=>t.domainId===draft.domainId)" class="callout">该领域尚无任务，请先到领域管理创建 TaskTemplate。</p>
      <label>Claim 名称<input v-model="draft.name"/></label><label>评价范围<textarea v-model="draft.scope" rows="4" placeholder="在此 Task 内评价哪些参数、情境和表征；不包含什么。"/></label>
      <p v-if="selectedTask" class="muted">Task 边界参考：{{selectedTask.exclusions}}</p>
    </template>
    <template v-else-if="mode==='methods'">
      <p>只选当前 Task 直接关联的方法。</p><div class="picker-list"><label v-for="m in selectedTask?.methods||[]" :key="m" class="check-line"><input v-model="draft.methods" type="checkbox" :value="m"/>{{methodName(m)}}</label></div><p v-if="!selectedTask?.methods.length" class="callout">任务尚未关联方法，请先在领域管理补齐。</p>
      <label>方法要求<select aria-label="方法要求" v-model="draft.methodMode"><option value="any">任选一种（只选一个时为指定方法）</option><option value="all">每一种都要分别覆盖</option></select></label><label>帮助与工具条件<textarea v-model="draft.support" rows="4" placeholder="什么帮助会影响独立判断，允许使用哪些工具，如何解释受助表现。"/></label>
    </template>
    <template v-else-if="aspect">
      <label>方面名称<input v-model="aspect.name" :readonly="!aspect.custom"/></label><label class="check-line"><input v-model="aspect.enabled" type="checkbox"/>适用于本 Claim</label>
      <template v-if="aspect.enabled"><label>支持这一能力的表现<textarea v-model="aspect.criterion" rows="3"/></label><label>证据不足的情况<textarea v-model="aspect.insufficient" rows="3"/></label><label>反证或矛盾表现<textarea v-model="aspect.counter" rows="3"/></label></template>
      <label v-if="!aspect.enabled||aspect.custom">裁剪或扩展依据<textarea v-model="aspect.reason" rows="3"/></label>
    </template>
    <label v-if="selectedTask&&draft.taskVersion!==selectedTask.version" class="check-line callout amber"><input v-model="adoptTask" type="checkbox"/>已核对任务 v{{selectedTask.version}} 的范围与方法，采用此版本</label>
    <p class="muted">保存到本浏览器。未填写的定义会列为待补充，不会产生学生 Belief。</p>
    <footer class="dialog-footer"><button class="btn" @click="mode=''">取消</button><button class="btn primary" :disabled="blocked" @click="save">{{mode==='new'?'创建 Claim':'保存修改'}}</button></footer>
  </WorkbenchDialog>
</section></template>

<style scoped>
.evaluation-filters{display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:18px}.aspect-table{min-width:760px}.aspect-table td{vertical-align:top}.aspect-table th:first-child{width:16%}.aspect-table th:nth-child(2){width:33%}.aspect-table p{margin:0 0 8px}.panel summary{cursor:pointer;color:#31543f}.row-between h3{margin:0}@media(max-width:950px){.evaluation-filters{grid-template-columns:1fr 1fr}}
</style>
