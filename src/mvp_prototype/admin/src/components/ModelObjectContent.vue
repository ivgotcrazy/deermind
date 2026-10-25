<script setup lang="ts">
import { computed } from 'vue';
import { state as stateSource, resolve, scopeBindings, dependents, objectActivity, domain } from '../workbench/store';
const state=stateSource;
import { kinds, aspectNames as aspectNamesSource, objectKey } from '../workbench/model';
const aspectNames=aspectNamesSource;
import { go } from '../workbench/navigation';
import ModelLink from './ModelLink.vue';
const props=defineProps<{reference:string;scope?:string;tab?:string;observing?:boolean}>();
const location=window.location;
const obj=computed(()=>resolve(props.reference,props.scope?scopeBindings(props.scope):undefined));
const bindings=computed(()=>props.scope?scopeBindings(props.scope):undefined);
const versions=computed(()=>state.objects.filter(x=>x.id===obj.value?.id).sort((a,b)=>b.version-a.version));
const activity=computed(()=>obj.value?objectActivity(objectKey(obj.value)):undefined);
function pinned(ref:string){if(ref.includes('@'))return ref;const version=(bindings.value||obj.value?.referenceVersions)?.[ref];return version?`${ref}@${version}`:ref;}
</script>
<template>
  <div v-if="!obj" class="empty"><h3>没有可解析的对象版本</h3><p>{{reference}} · {{scope||'当前目录'}}</p><p>可能是引用缺失、未采用或版本不匹配；此状态不代表“没有问题”。</p></div>
  <template v-else>
    <div class="object-heading"><span class="badge">{{kinds[obj.kind]}}</span><span class="mono">{{objectKey(obj)}}</span><span class="muted">{{obj.space}} / {{obj.model}}</span></div>
    <h3>{{obj.name}}</h3><p class="lead">{{obj.summary}}</p>
    <p v-if="obj.domainId" class="muted">所属领域：<span v-if="observing">{{domain(obj.domainId)?.name||obj.domainId}}</span><button v-else class="text-link" @click="go('domain',{domain:obj.domainId,filter:obj.kind})">{{domain(obj.domainId)?.name||obj.domainId}}</button></p>
    <p v-if="state.invalidated[objectKey(obj)]" class="callout danger">已退出当前使用：{{state.invalidated[objectKey(obj)]}}</p>
    <p class="muted">{{scope ? `采用上下文：${scope}；关联沿该上下文的准确版本查阅。` : '定义上下文：关联使用本版本保存时记录的引用基线；个人记录保留历史版本。'}}</p>
    <p v-if="bindings && bindings[obj.id]!==undefined && bindings[obj.id]!==obj.version" class="callout amber">此上下文采用 v{{bindings[obj.id]}}；正在查看的 v{{obj.version}} 并未因此被采用。</p>
    <template v-if="!tab || tab==='definition'">
      <dl class="field-list"><template v-for="(value,label) in obj.fields" :key="label"><dt>{{label}}</dt><dd>{{value}}</dd></template></dl>
      <table v-if="obj.aspects" class="data-table"><thead><tr><th>评价方面</th><th>判断条件</th><th>需要什么证据</th></tr></thead><tbody><tr v-for="a in obj.aspects" :key="a.key"><td>{{a.label}}<small v-if="!a.applicable">不适用：{{a.reason}}</small></td><td>{{a.criterion}}</td><td>{{a.evidence}}</td></tr></tbody></table>
      <p v-if="obj.requiredAspects" class="callout">本目标要求：{{obj.requiredAspects.map(k=>aspectNames[k]||k).join('、')}}。这是目标选择，不修改共享 Claim。</p>
      <table v-if="obj.states" class="data-table"><thead><tr><th>方面</th><th>判断</th><th>不确定性与条件</th><th>证据</th></tr></thead><tbody><tr v-for="s in obj.states" :key="s.key"><td>{{aspectNames[s.key]||s.key}}</td><td>{{state.invalidated[objectKey(obj)]?'待重新推断':s.judgment}}</td><td>{{s.uncertainty}}<small>{{s.note}}</small></td><td><ModelLink v-for="ref in s.evidence" :key="ref" :to="ref" :scope="scope"/><span v-if="!s.evidence.length" class="muted">未形成相应证据</span></td></tr></tbody></table>
    </template>
    <template v-if="!tab || tab==='relations'">
      <h4>关联关系</h4><div class="relation-list"><div v-for="(r,i) in obj.relations" :key="i"><span>{{r.label}}</span><ModelLink :to="pinned(r.ref)" :scope="scope"/></div><p v-if="!obj.relations.length" class="muted">当前定义没有登记关联。</p></div>
      <p v-if="obj.kind==='kc'" class="callout">KC 用于定义依赖、解释表现及支持教学；不维护学习者的 KC 掌握率。</p>
      <p v-if="obj.kind==='solution'" class="callout">方法的子任务仍是 TaskTemplate；可继续查看子任务的可用方法。这里是规范分解，不代表学生实际执行的步骤。</p>
      <button v-if="activity" class="btn" @click="go('activity',{id:activity.id,scope:activity.id,returnTo:location.hash})">定位原始活动：{{activity.id}}</button>
    </template>
    <template v-if="tab==='versions'">
      <div v-for="v in versions" :key="v.version" class="list-row"><ModelLink :to="objectKey(v)" :scope="scope"/><span>{{v.at}} · {{v.status==='published'?'已保存':v.status==='recorded'?'历史记录':'草稿'}}</span></div>
      <div v-for="c in state.changes.filter(c=>c.ref.split('@')[0]===obj?.id)" :key="c.ref" class="list-row"><span>{{c.note}} · {{c.ref}}</span><small>{{c.at}}</small></div><p class="callout">保存版本不会自动改变已有学习空间。历史事实和旧版本保留。</p>
    </template>
    <template v-if="tab==='impact'">
      <h4>目录引用</h4><div v-for="o in dependents(obj.id)" :key="o.id" class="list-row"><ModelLink :to="objectKey(o)"/><span>{{kinds[o.kind]}}</span></div>
      <h4>空间采用</h4><div v-for="s in state.spaces.filter(s=>s.adopted[obj!.id]!==undefined)" :key="s.id" class="list-row"><button class="text-link" @click="go(observing?'observed-space':'learning-spaces',{id:s.id,returnTo:location.hash})">{{s.studentName}} · {{s.name}}</button><span>v{{s.adopted[obj.id]}}</span></div>
      <p class="muted">以上是示例目录的已知引用；不等于真实服务已完成全量影响分析。</p>
    </template>
    <details><summary>来源与原始结构</summary><p class="muted">{{obj.source}}</p><pre>{{JSON.stringify({...obj,contextVersions:bindings},null,2)}}</pre></details>
  </template>
</template>
