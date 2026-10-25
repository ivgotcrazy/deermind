<script setup lang="ts">
import { computed, ref } from 'vue';
import type { ReviewStep } from '../workbench/traces';
import { resolve, state } from '../workbench/store';
import { aspectNames } from '../workbench/model';
import ModelLink from './ModelLink.vue';
const props=defineProps<{span:ReviewStep|null;scope:string}>();
const statusLabel:Record<string,string>={success:'步骤完成',failed:'拒绝／失败',partial:'待复核',skipped:'跳过',running:'处理中'};
const beliefs=computed(()=>props.span?.detail.refs?.map(ref=>resolve(ref)).filter(o=>o?.kind==='belief')||[]);
const copied=ref('');
async function copy(text:string){try{await navigator.clipboard.writeText(text);copied.value='已复制';}catch{copied.value='复制失败，可选中文本复制';}}
</script>
<template><div v-if="span" class="span-detail"><header class="row-between"><h3>{{span.label}}</h3><span class="step-status" :class="span.status">{{statusLabel[span.status]}}</span></header>
  <dl class="step-meta"><dt>归属</dt><dd>{{span.detail.owner}}</dd><dt>步骤 ID</dt><dd class="mono">{{span.spanId}}</dd><dt>类型</dt><dd class="mono">{{span.type}}</dd><dt>示例时间</dt><dd>+{{(span.startTime/1000).toFixed(2)}}s · {{span.duration}}ms</dd></dl>
  <section v-if="span.detail.model"><h4>模型调用</h4><p>{{span.detail.model}} · temperature {{span.detail.temperature}}</p><p>输入 tokens {{span.detail.tokens?.input}} · 输出 tokens {{span.detail.tokens?.output}}（示例值）</p></section>
  <section v-for="(label,key) in {input:'步骤输入',output:'步骤输出',reason:'依据与边界',authority:'提交权限',standing:'提交状态'}" :key="key" v-show="span.detail[key]"><h4>{{label}}</h4><p class="source-text">{{span.detail[key]}}</p></section>
  <section v-if="span.detail.checks"><h4>逐项校验</h4><article v-for="check in span.detail.checks" :key="check.name" class="check" :class="{rejected:!check.passed}"><strong>{{check.passed?'通过':'拒绝'}} · {{check.name}}</strong><p>{{check.reason}}</p></article></section>
  <section v-if="span.detail.candidate"><h4>Candidate 完整内容</h4><pre>{{JSON.stringify(span.detail.candidate,null,2)}}</pre></section>
  <section v-if="span.detail.candidates"><h4>候选行动与选择依据</h4><article v-for="candidate in span.detail.candidates" :key="candidate.name" class="check"><strong>{{candidate.selected?'已选择':'未选择'}} · {{candidate.name}}</strong><p>{{candidate.reason}}</p></article></section>
  <section v-for="(label,key) in {prompt:'调用输入',response:'模型原始输出'}" :key="key" v-show="span.detail[key]"><div class="row-between"><h4>{{label}}</h4><button class="text-link" @click="copy(span.detail[key]!)">复制{{label}}</button></div><pre>{{span.detail[key]}}</pre></section><p v-if="copied" role="status">{{copied}}</p>
  <section v-for="belief in beliefs" :key="belief!.id"><h4>同一 Task Claim 的方面变化</h4><p v-if="state.invalidated[`${belief!.id}@${belief!.version}`]" class="callout amber">已停止当前使用，以下保留历史判断，待重新推断。</p><div class="aspect-change" v-for="aspect in belief!.states" :key="aspect.key"><strong>{{aspectNames[aspect.key]||aspect.key}}</strong><p>{{span.detail.before?.[aspect.key]||'未记录先前判断'}} → {{aspect.judgment}}</p><small>{{aspect.uncertainty}}；{{aspect.note}}</small><ModelLink v-for="e in aspect.evidence" :key="e" :to="e" :scope="scope" label="查看对应依据"/></div></section>
  <section v-if="span.detail.refs?.length"><h4>关联对象与准确版本</h4><div v-for="ref in span.detail.refs" :key="ref" class="reference"><ModelLink :to="ref" :scope="scope"/><small class="mono">{{ref}}</small></div></section>
</div><p v-else class="empty">选择左侧步骤查看输入、输出与处理依据。</p></template>
<style scoped>
.span-detail{padding:16px;min-width:0;font-size:13px}.span-detail h3{font-size:14px;margin:0}.span-detail h4{font-size:12px;color:#5a6b7a;margin:16px 0 8px}.span-detail p{line-height:1.65;overflow-wrap:anywhere}.step-meta{display:grid;grid-template-columns:76px minmax(0,1fr);gap:8px;margin:16px 0;font-size:12px}.step-meta dt{color:#718092}.step-meta dd{margin:0;overflow-wrap:anywhere}.step-status{font-size:11px;white-space:nowrap;background:#e8f5ee;padding:4px 8px;border-radius:8px}.step-status.failed{background:#fdf0ed;color:#b85c3c}.step-status.partial{background:#fff4d8;color:#8a650d}.check,.aspect-change{padding:10px;background:#f0f5f2;border-radius:6px;margin-bottom:8px}.check p,.aspect-change p{margin:5px 0}.check.rejected{background:#fdf0ed;color:#963e29}.aspect-change small{display:block;color:#5a6b7a;line-height:1.6}.reference{display:flex;flex-direction:column;gap:4px;padding:6px 0}.span-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf1f5;padding:12px;border-radius:6px;font-size:12px}.reference small{color:#718092}
</style>
