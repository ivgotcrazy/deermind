<script setup lang="ts">
import { computed } from 'vue';
import { state, resolve, scopeBindings } from '../workbench/store';
import { objectKey, personalKinds } from '../workbench/model';
import { route, go, back } from '../workbench/navigation';
import { relatedActivities, recordSpaces } from '../workbench/observation';
import { ownerLocation } from '../workbench/ui';
import ModelObjectContent from './ModelObjectContent.vue';
import ModelLink from './ModelLink.vue';
import AccessGate from './AccessGate.vue';

const object=computed(()=>resolve(route.id,scopeBindings(route.scope)));
const context=computed(()=>state.spaces.find(s=>s.id===route.id));
const issue=computed(()=>state.issues.find(i=>i.id===route.id&&i.dataMode==='demo'));
const sources=computed(()=>object.value?relatedActivities(state,object.value):[]);
const personal=computed(()=>object.value&&personalKinds.includes(object.value.kind));
const access=computed(()=>personal.value?(sources.value.find(a=>a.id===route.scope)?.id||objectKey(object.value!)):'');
const tabs={definition:'记录内容',relations:'关联与来源',versions:'版本记录',impact:'引用与采用'};
const currentTab=computed(()=>Object.keys(tabs).includes(route.tab)?route.tab:'definition');
const location=window.location;
function manage(){if(!object.value)return;const target=ownerLocation(object.value);go(target.page,{...(['textbooks','targets'].includes(target.page)?{}:target.values),returnTo:location.hash});}
function activity(id:string){go('activity',{id,scope:id,returnTo:location.hash});}
</script>

<template><div class="wb-page observation-detail"><header class="page-header"><div><button class="text-link" @click="back('objects')">← 返回观测来源</button><h2>{{route.page==='observed-space'?'学习空间观测':route.page==='observed-issue'?'历史演化记录':'对象记录追溯'}}</h2><p class="page-desc">只读查看记录、准确版本与来源。修改定义请前往所属管理页面。</p></div><button v-if="route.page==='observed-object' && object && !personal" class="btn" @click="manage">前往{{object.space==='Domain'?'领域管理':object.space==='Evaluation'?'评估模型管理':object.kind==='target'?'目标管理':'教材管理'}} →</button></header>
  <template v-if="route.page==='observed-object'"><div class="tabs"><button v-for="(label,key) in tabs" :key="key" :class="{active:currentTab===key}" @click="go(route.page,{...route,tab:key},true)">{{label}}</button></div>
    <AccessGate v-if="access" :subject="access"><section class="panel"><ModelObjectContent :reference="route.id" :scope="route.scope" :tab="currentTab" observing/></section><section class="panel"><h3>来源活动</h3><p class="muted">以下活动明确引用了 {{route.id}}，保留各自发生时的定义版本。</p><div v-for="a in sources" :key="a.id" class="list-row"><button class="text-link" @click="activity(a.id)">{{a.name}} · {{a.id}}</button><span>{{a.ls}} · {{a.at}}</span></div><p v-if="!sources.length" class="callout amber">未找到关联活动，不能据此声称来源完整。登记的学习空间：{{object?recordSpaces(state,object).join('、')||'未登记':'未知'}}。</p></section></AccessGate>
    <section v-else class="panel"><ModelObjectContent :reference="route.id" :scope="route.scope" :tab="currentTab" observing/></section>
  </template>
  <template v-else-if="route.page==='observed-space'"><AccessGate v-if="context" :subject="context.id"><section class="panel"><h3>{{context.studentName}} · {{context.name}}</h3><p class="mono">{{context.id}}</p><dl class="field-list"><dt>教材</dt><dd><ModelLink :to="`${context.material}@${context.adopted[context.material]}`" :scope="context.id"/></dd><dt>学习目标</dt><dd><ModelLink :to="`${context.target}@${context.adopted[context.target]}`" :scope="context.id"/></dd><dt>章节范围</dt><dd><ModelLink v-for="id in context.chapters" :key="id" :to="`${id}@${context.adopted[id]}`" :scope="context.id"/></dd></dl><p class="muted">这些是课程范围和采用关系；个人 Claim Belief 在 Evaluation Space 中查看。</p></section>
    <section class="panel"><h3>准确采用版本</h3><div v-for="(v,id) in context.adopted" :key="id" class="list-row"><ModelLink :to="`${id}@${v}`" :scope="context.id"/><span class="mono">{{id}}@{{v}}</span></div></section>
    <section class="panel"><h3>采用历史</h3><div v-for="(h,i) in context.history" :key="i" class="list-row"><span>{{h.at}} · {{h.reason}}</span><details><summary>前后版本</summary><pre>{{JSON.stringify({before:h.before,after:h.after},null,2)}}</pre></details></div><p v-if="!context.history.length" class="muted">尚无采用变更记录。</p><h3>相关活动</h3><div v-for="a in state.activities.filter(a=>a.ls===context!.id)" :key="a.id" class="list-row"><button class="text-link" @click="activity(a.id)">{{a.name}} · {{a.id}}</button><span>{{a.at}}</span></div></section></AccessGate><p v-else class="empty">学习空间不存在，未切换到其他学生。</p></template>
  <template v-else-if="route.page==='observed-issue'"><AccessGate v-if="issue" :subject="issue.origin||issue.id"><section class="panel"><h3>{{issue.title}}</h3><p>{{issue.finding}}</p><p>{{issue.conclusion||'原记录未形成结论'}}</p><button v-if="state.activities.some(a=>a.id===issue!.origin)" class="text-link" @click="activity(issue.origin)">追溯原始活动 {{issue.origin}}</button><div v-for="(entry,i) in issue.log" :key="i" class="list-row"><span>{{entry.text}}</span><span>{{entry.at}}</span></div><details><summary>原始历史记录（只读）</summary><pre>{{JSON.stringify(issue,null,2)}}</pre></details></section></AccessGate><p v-else class="empty">当前示例来源中不存在此历史事项。</p></template>
</div></template>
