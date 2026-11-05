<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import { clone, domainData, domainStorageError } from '../model/domain';
import { imports, storageError } from '../model/imports';
import { materialUrl } from '../model/material-flow';
import { evaluationData, evaluationStorageError, blankTarget, blankRequirement, saveDefinition, bookImport, bookChapters, chapterLinks, claimTask, claimIssues, methodName, mappedChapters, allowedMethods, candidateIssues, requirementIssues, targetIssues, type Claim, type LearningTarget, type Requirement } from '../model/evaluation';
import { loadEvaluationExample } from '../model/evaluation-example';

const props=defineProps<{hash:string}>();
const params=computed(()=>new URLSearchParams(props.hash.split('?')[1]||''));
const key=computed(()=>params.value.get('id')||'');
const current=computed(()=>evaluationData.targets.find(t=>t.id===key.value));
const bookFilter=ref(''),query=ref(''),page=ref(1);
const rows=computed(()=>evaluationData.targets.filter(t=>(!bookFilter.value||t.bookId===bookFilter.value)&&(t.name+' '+(bookImport(t.bookId)?.book.name||'')).includes(query.value.trim())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10)));
const book=computed(()=>current.value?bookImport(current.value.bookId):undefined);
const taskIds=computed(()=>current.value?[...new Set(current.value.chapters.flatMap(ch=>chapterLinks(current.value!.bookId,ch).map(l=>l.taskId)))]:[]);
const problems=computed(()=>current.value?targetIssues(current.value):[]);
const mode=ref<''|'new'|'basic'|'requirement'|'remove'>(''),draft=ref<LearningTarget>(blankTarget()),requirement=ref<Requirement>(blankRequirement()),editing=ref(false),error=ref(''),notice=ref('');
const blocked=computed(()=>!!evaluationStorageError.value||!!domainStorageError.value||!!storageError.value);
const claim=(key:string)=>evaluationData.claims.find(c=>c.id===key);
const selectedClaim=computed(()=>claim(requirement.value.claimId));
const candidates=computed(()=>current.value?evaluationData.claims.filter(c=>c.domainId===book.value?.book.domainId&&taskIds.value.includes(c.taskId)):[]);
const candidateChapters=computed(()=>current.value&&selectedClaim.value?mappedChapters(current.value,selectedClaim.value):[]);
const availableMethods=computed(()=>current.value&&selectedClaim.value?allowedMethods(current.value,selectedClaim.value,requirement.value.chapters):[]);
const omitted=computed(()=>selectedClaim.value?.aspects.filter(a=>a.enabled&&!requirement.value.standards.some(s=>s.aspectId===a.id))||[]);
const taskName=(key:string)=>domainData.tasks.find(t=>t.id===key)?.name||'任务不存在';
watch([bookFilter,query],()=>page.value=1);
watch(()=>props.hash,()=>{mode.value='';notice.value='';document.querySelector('.page-container')?.scrollTo({top:0});});
function open(t:LearningTarget){location.hash='/targets?id='+t.id;}
function edit(next:'new'|'basic'){mode.value=next;draft.value=current.value?clone(current.value):blankTarget();error.value='';}
function fail(message:string){error.value=message;nextTick(()=>document.querySelector('dialog [role=alert]')?.scrollIntoView({block:'center'}));}
function saveTarget(){
  if(blocked.value)return;
  const t=draft.value;
  if(!t.name.trim()||!bookImport(t.bookId)||!t.chapters.length)return fail('请填写目标名称，并选择教材和至少一个章节。');
  if(t.chapters.some(ch=>!bookChapters(t.bookId).includes(ch)))return fail('部分章节已不存在，请重新选择。');
  if(t.requirements.some(r=>r.chapters.some(ch=>!t.chapters.includes(ch))))return fail('已有学习要求仍引用将移除的章节，请先编辑或移除这些要求。');
  const next=saveDefinition(evaluationData.targets,t,mode.value==='new'?'创建目标与课程范围':'修改目标名称与章节范围');if(!next)return;
  const creating=mode.value==='new';mode.value='';if(creating)open(next);else notice.value='目标信息已保存。调整目标不会改变学生的历史表现或 Belief。';
}
function editRequirement(r?:Requirement){requirement.value=r?clone(r):blankRequirement();requirement.value.checked=false;if(r&&claim(r.claimId)?.methodMode==='all')requirement.value.methodMode='all';editing.value=!!r;mode.value='requirement';error.value='';}
function chooseClaim(){
  const c=selectedClaim.value;if(!c||!current.value)return;
  requirement.value={...blankRequirement(),claimId:c.id,claimVersion:c.version,name:claimTask(c)?.name||'',scope:'',methodMode:c.methodMode};
  const mapped=mappedChapters(current.value,c);
  if(mapped.length===1)requirement.value.chapters=[mapped[0]];
  requirement.value.methods=allowedMethods(current.value,c,requirement.value.chapters);
  requirement.value.standards=c.aspects.filter(a=>a.enabled).map(a=>({aspectId:a.id,text:''}));
}
function toggleAspect(key:string,checked:boolean){
  const r=requirement.value;r.checked=false;
  if(checked&&!r.standards.some(s=>s.aspectId===key))r.standards.push({aspectId:key,text:''});
  if(!checked)r.standards=r.standards.filter(s=>s.aspectId!==key);
}
function saveRequirement(){
  if(blocked.value||!current.value||!selectedClaim.value)return;
  const r=clone(requirement.value);r.claimVersion=selectedClaim.value.version;
  const issues=requirementIssues(current.value,r);if(issues.length)return fail(issues.join('；'));
  const next=clone(current.value),index=next.requirements.findIndex(x=>x.id===r.id);
  if(index<0)next.requirements.push(r);else next.requirements[index]=r;
  saveDefinition(evaluationData.targets,next,(index<0?'添加':'修改')+'学习要求：'+r.name);mode.value='';notice.value='学习要求已保存，仅配置目标；尚未进行学生评价。';
}
function remove(){
  if(!current.value||blocked.value)return;
  const next=clone(current.value);next.requirements=next.requirements.filter(r=>r.id!==requirement.value.id);
  saveDefinition(evaluationData.targets,next,'移除学习要求：'+requirement.value.name);mode.value='';notice.value='已移除本目标中的要求，共享 Claim 与教材关联保留。';
}
function example(){if(blocked.value)return;open(loadEvaluationExample());}
function missingClaimUrl(taskId:string){return '#/evaluation?'+new URLSearchParams({domain:book.value?.book.domainId||'',task:taskId});}
function chapterUrl(ch:string){return book.value?materialUrl(book.value,ch,'links'):'#/textbooks';}
function compatible(c:Claim){return current.value?candidateIssues(current.value,c):[];}
</script>

<template><section class="wb-page target-workspace">
  <p v-if="evaluationStorageError||domainStorageError||storageError" role="alert" class="callout danger">{{evaluationStorageError||domainStorageError||storageError}}</p>
  <template v-if="!key">
    <header class="page-header"><div><h2>学习目标管理</h2><p class="page-desc">结合教材章节范围，选用领域 Task Claim，配置课程要求与达标标准。</p></div><div class="button-row"><button class="btn" :disabled="blocked" @click="example">打开四分之一样例</button><button class="btn primary" :disabled="blocked" @click="edit('new')">新建学习目标</button></div></header>
    <div class="edit-pair"><label>筛选教材<select aria-label="筛选教材" v-model="bookFilter"><option value="">全部教材</option><option v-for="d in imports" :key="d.id" :value="d.book.id">{{d.book.name||'未命名教材'}}</option></select></label><label>查找学习目标<input v-model="query" type="search" placeholder="目标或教材名称"/></label></div>
    <section class="panel table-scroll"><table v-if="rows.length" class="data-table"><thead><tr><th>学习目标</th><th>教材与范围</th><th>学习要求</th><th>配置情况</th><th>操作</th></tr></thead><tbody><tr v-for="t in rows.slice((page-1)*10,page*10)" :key="t.id"><td><button class="text-link model-name" @click="open(t)">{{t.name}}</button><small>v{{t.version}} · {{t.updatedAt}}</small></td><td>{{bookImport(t.bookId)?.book.name||'教材不存在'}}<small>{{t.chapters.join('、')}}</small></td><td>{{t.requirements.length}} 项</td><td><span class="badge" :class="{warning:targetIssues(t).length}">{{targetIssues(t).length?'待补充／核对':'要求已配置（mock）'}}</span></td><td><button class="btn" @click="open(t)">查看</button></td></tr></tbody></table><div v-else class="empty"><h3>暂无符合条件的学习目标</h3><p>选择教材与章节，再添加对应的 Claim 和学习要求。</p></div></section>
    <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page<=1" @click="page--">上一页</button>{{page}} / {{pages}}<button class="btn" :disabled="page>=pages" @click="page++">下一页</button></div><p class="muted">样例会新增独立 mock，不覆盖已有内容。这里显示目标配置情况，不是学生的达成结果。</p>
  </template>
  <template v-else-if="current">
    <a class="text-link" href="#/targets">← 返回学习目标列表</a><header class="page-header"><div><h2>{{current.name}}</h2><p class="page-desc">{{book?.book.name||'教材不存在'}} · v{{current.version}}</p></div><button class="btn" :disabled="blocked" @click="edit('basic')">编辑目标与范围</button></header>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <details v-if="problems.length" class="preparation"><summary>{{problems.length}} 项配置待补充或核对</summary><ul><li v-for="s in problems" :key="s">{{s}}</li></ul></details>
    <section class="panel"><h3>教材范围</h3><div class="button-row"><a v-for="ch in current.chapters" :key="ch" :href="chapterUrl(ch)">{{ch}} ↗</a></div><p class="muted">章节提供候选任务与方法；下面的学习要求确定本目标实际评价的范围。未选任务不自动成为达标要求。</p>
      <details :open="!current.requirements.length"><summary>查看章节任务与 Claim 准备情况（{{taskIds.length}} 项任务）</summary><table v-if="taskIds.length" class="data-table"><thead><tr><th>Task</th><th>Claim 准备情况</th><th>操作</th></tr></thead><tbody><tr v-for="id in taskIds" :key="id"><td>{{taskName(id)}}</td><td><template v-if="evaluationData.claims.some(c=>c.taskId===id)"><div v-for="c in evaluationData.claims.filter(c=>c.taskId===id)" :key="c.id">{{c.name}}<small>{{compatible(c).length?compatible(c).join('；'):'可以选用'}}</small></div></template><span v-else>尚未定义 Claim</span></td><td><a :href="missingClaimUrl(id)">前往评估管理 →</a></td></tr></tbody></table><p v-else class="callout">所选章节尚未关联 Task，请先在教材管理添加章节关联。</p></details>
    </section>
    <section class="panel"><div class="row-between"><div><h3>学习要求</h3><p class="muted">每项引用一个 Task Claim，配置当前课程的范围、方法及各方面标准。</p></div><button class="btn primary" :disabled="blocked||!book" @click="editRequirement()">添加学习要求</button></div>
      <p v-if="!current.requirements.length" class="empty">尚未添加要求。教材关联本身不会自动生成学习目标。</p>
      <article v-for="r in current.requirements" :key="r.id" class="requirement-card" :data-requirement="r.id"><div class="row-between"><h3>{{r.name}}</h3><div class="button-row"><button class="btn" :disabled="blocked" :aria-label="'编辑要求 '+r.name" @click="editRequirement(r)">编辑</button><button class="btn" :disabled="blocked" :aria-label="'移除要求 '+r.name" @click="requirement=clone(r);mode='remove'">移除</button></div></div>
        <p><a :href="'#/evaluation?id='+r.claimId">{{claim(r.claimId)?.name||'Claim 不存在'}} ↗</a> <span class="muted">引用 v{{r.claimVersion}} · {{r.chapters.join('、')}}</span></p>
        <p v-if="requirementIssues(current,r).length" class="callout amber">{{requirementIssues(current,r).join('；')}}</p>
        <dl class="field-list"><dt>本目标任务范围</dt><dd>{{r.scope}}</dd><dt>方法条件</dt><dd>{{r.methodMode==='all'?'各方法分别覆盖':r.methods.length===1?'使用指定方法':'任选一种'}}：{{r.methods.map(methodName).join('、')}}<small class="muted">实际评价按所用方法与帮助记录核对，不沿用其他方法的成功结论。</small></dd><dt>帮助条件</dt><dd>{{claim(r.claimId)?.support||'Claim 条件待补充'}}</dd></dl>
        <table class="data-table standards-table"><thead><tr><th>评价方面</th><th>本目标达标标准</th></tr></thead><tbody><tr v-for="s in r.standards" :key="s.aspectId"><td>{{claim(r.claimId)?.aspects.find(a=>a.id===s.aspectId)?.name||'方面已不存在'}}</td><td class="multiline">{{s.text}}</td></tr></tbody></table><p v-if="r.omissionReason" class="muted">未纳入方面的依据：{{r.omissionReason}}</p>
      </article>
    </section>
    <p class="muted">配置保存不等于课程已应用，也不代表任何学生已达标。样例题量和七天间隔仅用于本例试用，不是通用门槛。</p>
    <details class="panel"><summary>修改记录</summary><ul><li v-for="(h,i) in current.history" :key="i">v{{h.version}} · {{h.at}} · {{h.change}}</li></ul></details>
  </template>
  <div v-else class="empty"><h2>当前浏览器中没有这个学习目标</h2><a href="#/targets">返回学习目标列表</a></div>

  <WorkbenchDialog v-if="mode==='new'||mode==='basic'" :title="mode==='new'?'新建学习目标':'编辑目标与范围'" @close="mode=''">
    <p v-if="error" role="alert" class="callout danger">{{error}}</p><label>目标名称<input v-model="draft.name"/></label>
    <label>教材<select aria-label="教材" v-model="draft.bookId" :disabled="mode==='basic'" @change="draft.chapters=[]"><option value="">请选择已整理的教材</option><option v-for="d in imports.filter(d=>d.state==='review')" :key="d.id" :value="d.book.id">{{d.book.name}}</option></select></label>
    <p v-if="!imports.some(d=>d.state==='review')" class="callout">暂无已整理教材。先完成教材解析与章节关联，也可以从列表打开独立样例。</p>
    <fieldset class="object-fieldset"><legend>选择章节</legend><div class="picker-list"><label v-for="ch in bookChapters(draft.bookId)" :key="ch" class="check-line"><input v-model="draft.chapters" type="checkbox" :value="ch"/>{{ch}}</label></div><p v-if="draft.bookId&&!bookChapters(draft.bookId).length" class="muted">这份教材尚无章节。</p></fieldset>
    <footer class="dialog-footer"><button class="btn" @click="mode=''">取消</button><button class="btn primary" :disabled="blocked" @click="saveTarget">{{mode==='new'?'创建学习目标':'保存目标'}}</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="mode==='requirement'&&current" :title="editing?'编辑学习要求':'添加学习要求'" wide @close="mode=''">
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
    <label>选用 Claim<select aria-label="选用 Claim" v-model="requirement.claimId" :disabled="editing" @change="chooseClaim"><option value="">选择本教材范围内的 Claim</option><option v-for="c in candidates" :key="c.id" :value="c.id" :disabled="compatible(c).length>0">{{c.name}}{{compatible(c).length?'（待补充／方法不兼容）':''}}</option></select></label>
    <p v-if="!candidates.some(c=>!compatible(c).length)&&!editing" class="callout">没有可添加的 Claim。请检查章节关联、Claim 定义和方法条件。<a :href="'#/evaluation?domain='+(book?.book.domainId||'')">前往评估管理 →</a></p>
    <template v-if="selectedClaim">
      <p class="muted">{{claimTask(selectedClaim)?.name}} · Claim v{{selectedClaim.version}}；当前范围：{{selectedClaim.scope}}</p>
      <p v-if="!editing&&current.requirements.some(r=>r.claimId===selectedClaim!.id)" class="muted">此 Claim 已被本目标选用。可以另设不同范围或方面的要求；它们仍引用同一个 Claim，不新增个人能力状态。</p>
      <p v-if="claimIssues(selectedClaim).length" class="callout amber">{{claimIssues(selectedClaim).join('；')}}</p>
      <p v-if="editing&&requirement.claimVersion!==selectedClaim.version" class="callout amber">Claim 已从 v{{requirement.claimVersion}} 更新至 v{{selectedClaim.version}}。核对下方要求后保存，将明确采用新版；原来的达成结论不能直接沿用。</p>
      <label>学习要求名称<input v-model="requirement.name" placeholder="用学生能看懂的话表达"/></label>
      <fieldset class="object-fieldset"><legend>对应章节</legend><div class="picker-list"><label v-for="ch in candidateChapters" :key="ch" class="check-line"><input v-model="requirement.chapters" type="checkbox" :value="ch" @change="requirement.checked=false"/>{{ch}}</label></div></fieldset>
      <label>具体任务范围<textarea v-model="requirement.scope" rows="3" placeholder="例如只取增加比例 r=1/4；范围应在 Claim 定义内。"/></label>
      <fieldset class="object-fieldset"><legend>本要求采用的方法</legend><div class="picker-list"><label v-for="m in selectedClaim.methods" :key="m" class="check-line"><input v-model="requirement.methods" type="checkbox" :value="m" :disabled="!availableMethods.includes(m)&&!requirement.methods.includes(m)"/>{{methodName(m)}}<small v-if="!availableMethods.includes(m)" class="muted">所选章节未共同采用</small></label></div><p v-for="m in requirement.methods.filter(key=>!selectedClaim!.methods.includes(key))" :key="m" class="callout amber">{{methodName(m)}} 已不在 Claim 允许方法内。<button class="btn" @click="requirement.methods=requirement.methods.filter(key=>key!==m)">移除失效方法</button></p></fieldset>
      <p v-if="requirement.methods.some(m=>!availableMethods.includes(m))" class="callout amber">原选择的方法与当前章节不兼容。请选择匹配的章节或回教材修正关联；不会自动删掉你的选择。</p>
      <label>要求的方法覆盖<select aria-label="要求的方法覆盖" v-model="requirement.methodMode" :disabled="selectedClaim.methodMode==='all'"><option value="any">任选一种（只选一个时为指定方法）</option><option value="all">各方法都要分别有表现依据</option></select></label><p class="muted">{{selectedClaim.methodMode==='all'?'该 Claim 要求覆盖全部指定方法，目标不能放宽。':'收窄方法或要求多法覆盖时，需要相应方法下的证据，不能直接沿用原来的总体判断。'}}</p>
      <p class="callout">帮助与工具条件沿用 Claim：{{selectedClaim.support}}</p>
      <fieldset class="object-fieldset"><legend>评价方面与达标标准</legend><div v-for="a in selectedClaim.aspects.filter(a=>a.enabled)" :key="a.id" class="entry-editor"><label class="check-line"><input type="checkbox" :checked="requirement.standards.some(s=>s.aspectId===a.id)" @change="toggleAspect(a.id,($event.target as HTMLInputElement).checked)"/>{{a.name}}</label><p class="muted">Claim 判据：{{a.criterion}}</p><label v-if="requirement.standards.some(s=>s.aspectId===a.id)">{{a.name}}达标标准<textarea v-model="requirement.standards.find(s=>s.aspectId===a.id)!.text" rows="3" placeholder="说明需要哪些表现、覆盖和条件；不要只填一个分数。"/></label></div></fieldset>
      <p v-for="s in requirement.standards.filter(s=>!selectedClaim!.aspects.some(a=>a.id===s.aspectId&&a.enabled))" :key="s.aspectId" class="callout amber">原标准对应的方面已不适用：{{selectedClaim.aspects.find(a=>a.id===s.aspectId)?.name||s.aspectId}}。<button class="btn" @click="toggleAspect(s.aspectId,false)">移除失效方面标准</button></p>
      <label v-if="omitted.length">未纳入方面的依据<textarea v-model="requirement.omissionReason" rows="3" :placeholder="'本目标未纳入：'+omitted.map(a=>a.name).join('、')"/></label>
      <label class="check-line"><input v-model="requirement.checked" type="checkbox"/>已核对：范围在 Claim 内，方法条件兼容，标准没有改变 Claim 的含义</label><p class="muted">此项由管理员判断语义；mock 只检查引用和填写完整性。暂无证据、未到延迟时间不是裁剪依据。</p>
    </template>
    <footer class="dialog-footer"><button class="btn" @click="mode=''">取消</button><button class="btn primary" :disabled="blocked||!selectedClaim" @click="saveRequirement">保存学习要求</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="mode==='remove'" title="移除学习要求" @close="mode='' "><p>从当前目标移除“{{requirement.name}}”？共享 Claim、领域定义和教材关联会保留。</p><footer class="dialog-footer"><button class="btn" @click="mode=''">取消</button><button class="btn danger-btn" :disabled="blocked" @click="remove">确认移除</button></footer></WorkbenchDialog>
</section></template>

<style scoped>
.row-between h3{margin:0}.requirement-card{border-top:1px solid #dde7e0;padding:20px 0 4px;margin-top:14px}.requirement-card .row-between{align-items:start}.standards-table{margin-top:20px}.standards-table th:first-child{width:140px}.standards-table td{vertical-align:top}.field-list small{display:block;margin-top:6px}.panel summary{cursor:pointer;color:#31543f}.button-row a{margin-right:16px}.check-line small{margin-left:auto}
</style>
