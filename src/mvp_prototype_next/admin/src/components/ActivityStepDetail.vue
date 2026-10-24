<script setup lang="ts">
import { ref } from 'vue';
import type { AuditStep,AuditRef } from '../workbench/activity-review-mock';
import { defaultAspectNames } from '../workbench/evaluation-mock';
defineProps<{step:AuditStep}>();const emit=defineEmits<{reference:[value:AuditRef]}>();
const labels={success:'步骤完成',failed:'拒绝／失败',partial:'部分完成',skipped:'跳过',running:'处理中'};
const aspect=(id:string)=>(defaultAspectNames as Record<string,string>)[id]||id;
const refLabels={claim:'Task Claim',task:'Task',solution:'Solution',target:'学习目标',chapter:'教材章节',requirement:'学习要求',evidence:'Evidence',observation:'Observation'};
const copied=ref('');async function copy(value:string){try{await navigator.clipboard.writeText(value);copied.value='已复制';}catch{copied.value='复制失败，可选中文本复制。';}}
</script>
<template><div class="audit-step-detail"><div class="row-between"><h3>{{step.label}}</h3><span class="badge" :class="step.status==='failed'?'red':'green'">{{labels[step.status]}}</span></div><p class="step-owner">{{step.detail.owner}}<small>{{step.spanId}} · +{{(step.startTime/1000).toFixed(2)}}s · {{step.duration}}ms（演示）</small></p>
  <dl v-if="step.detail.fields?.length" class="step-fields"><template v-for="f in step.detail.fields" :key="f.label"><dt>{{f.label}}</dt><dd>{{f.value}}</dd></template></dl>
  <section v-if="step.detail.checks"><h4>逐项校验</h4><div v-for="c in step.detail.checks" :key="c.name" class="audit-check" :class="{rejected:!c.passed}"><strong>{{c.passed?'通过':'拒绝'}} · {{c.name}}</strong><p>{{c.reason}}</p></div></section>
  <section v-if="step.detail.candidate"><h4>观察候选</h4><pre>{{JSON.stringify(step.detail.candidate,null,2)}}</pre></section>
  <section v-if="step.detail.actions"><h4>候选行动</h4><div v-for="a in step.detail.actions" :key="a.name" class="audit-check"><strong>{{a.selected?'已选择':'未选择'}} · {{a.name}}</strong><p>{{a.reason}}</p></div></section>
  <section v-if="step.detail.changes"><h4>本轮前后判断</h4><article v-for="c in step.detail.changes" :key="c.aspect" class="aspect-transition"><strong>{{aspect(c.aspect)}}</strong><p><span class="muted">之前：</span>{{c.before}}</p><p><span class="muted">之后：</span>{{c.after}}</p><small>{{c.reason}}</small></article></section>
  <section v-if="step.detail.results"><h4>目标要求的变化</h4><article v-for="r in step.detail.results" :key="r.id" class="aspect-transition"><button class="text-link" @click="emit('reference',{kind:'requirement',id:r.id})">{{r.id}} · 查看具体要求 →</button><p>{{r.before}} → {{r.after}}</p><small>{{r.reason}}</small></article></section>
  <template v-if="step.detail.prompt"><p v-if="step.detail.tokens" class="muted">输入 {{step.detail.tokens.input}} / 输出 {{step.detail.tokens.output}} tokens（演示值）</p><h4>调用输入 <button class="text-link" @click="copy(step.detail.prompt!)">复制调用输入</button></h4><pre>{{step.detail.prompt}}</pre><h4>模型输出 <button class="text-link" @click="copy(step.detail.response||'')">复制模型输出</button></h4><pre>{{step.detail.response}}</pre><p v-if="copied" role="status">{{copied}}</p></template>
  <section v-if="step.detail.refs?.length"><h4>相关对象与依据</h4><button v-for="r in step.detail.refs" :key="r.kind+r.id" class="text-link reference-link" @click="emit('reference',r)">{{refLabels[r.kind]}} · {{r.id}} →</button></section>
</div></template>
<style scoped>
.audit-step-detail{padding:18px;font-size:13px;line-height:1.7;overflow-wrap:anywhere}.audit-step-detail h3{font-size:16px}.audit-step-detail h4{font-size:13px;margin:18px 0 9px}.step-owner{color:#53735e;margin:12px 0}.step-owner small{display:block;color:#849187;font-size:11px}.step-fields{margin:14px 0}.step-fields dt{font-size:12px;color:#738277;margin:12px 0 3px}.step-fields dd{white-space:pre-wrap}.audit-check,.aspect-transition{background:#f0f6f2;border:1px solid #e3ece5;border-radius:6px;padding:12px;margin:10px 0}.audit-check.rejected{background:#fff0ea;border-color:#efd3c7}.aspect-transition p,.audit-check p{margin:6px 0}.aspect-transition small{color:#617b6a;display:block}.reference-link{display:block;margin:8px 0}.audit-step-detail pre{max-height:300px}.audit-step-detail h4 button{float:right;font-weight:normal}.audit-step-detail .badge{white-space:nowrap}
</style>
