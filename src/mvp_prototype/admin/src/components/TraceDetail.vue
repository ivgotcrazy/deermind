<script setup lang="ts">
import { computed, ref } from 'vue';
import { route as routeSource, back, setQuery } from '../workbench/navigation';
import { state as stateSource, mode, resolve } from '../workbench/store';
import { reviewTraces, findStep, downloadTrace, traceStatus } from '../workbench/traces';
import AccessGate from './AccessGate.vue';
import WaterfallChart from './WaterfallChart.vue';
import SpanDetail from './SpanDetail.vue';
import SemanticTimeline from './SemanticTimeline.vue';
import ModelObjectContent from './ModelObjectContent.vue';
import ModelLink from './ModelLink.vue';
import RecordNotes from './RecordNotes.vue';
import LiveConversation from './LiveConversation.vue';
const route=routeSource,state=stateSource;
const copyMessage=ref('');
async function copyId(){try{await navigator.clipboard.writeText(route.id);copyMessage.value='已复制 ID';}catch{copyMessage.value='复制失败，可选中编号复制';}}
const activity=computed(()=>state.activities.find(a=>a.id===route.id));
const trace=computed(()=>reviewTraces[route.id]);
const missingObjects=computed(()=>activity.value?.objects.filter(key=>!resolve(key))||[]);
const chosen=computed(()=>trace.value?(findStep(trace.value.spans,route.span)||trace.value.spans.find(s=>s.status==='failed')||trace.value.spans[0]||null):null);
const select=(span:string)=>setQuery({span});
function exportRecord(){downloadTrace(`${route.id}-example.json`,{source:'authored-example',processNotice:'处理脚本为人工编写，不是采集日志；时间、模型参数和 token 为示例值。',activity:activity.value,process:trace.value||null,objects:activity.value?.objects.map(ref=>({ref,record:resolve(ref)||null})),notes:state.annotations.filter(n=>n.subject===route.id&&n.mode==='demo'),invalidated:Object.fromEntries(Object.entries(state.invalidated).filter(([ref])=>activity.value?.objects.includes(ref)))});}
</script>
<template><div class="wb-page trace-detail"><header class="page-header"><div><button class="text-link" @click="back('trace-list')">← 返回来源</button><h2>交互审查 · 详情</h2></div></header>
  <AccessGate v-if="mode==='real'&&route.id.startsWith('NEXT-')" :subject="route.id"><p class="callout">真实记录：当前仅保存会话、逐轮调用指标与异常信息，尚无逐阶段 Trace／Span 日志；下方不补造处理瀑布图。</p><LiveConversation :id="route.id"/></AccessGate>
  <AccessGate v-else-if="mode==='demo'&&activity" :subject="activity.id"><header class="detail-topbar"><div><h3>{{activity.name}}</h3><p>{{activity.id}} · {{state.spaces.find(s=>s.id===activity!.ls)?.studentName||'学生未记录'}} · {{activity.ls}} · {{activity.at}}</p></div><span class="trace-status">{{traceStatus[trace?.status||'unknown']}}</span><button class="btn" @click="copyId">复制 ID</button><button class="btn" @click="exportRecord">导出本次示例 JSON</button></header>
    <p v-if="copyMessage" role="status">{{copyMessage}}</p><p class="source-notice">人工编写示例 · 处理步骤、耗时、模型参数及 tokens 均为演示值，不是运行日志。{{trace?.note||'本活动没有对应的处理脚本。'}}</p>
    <section v-if="missingObjects.length" class="panel"><h3>结果记录缺失</h3><p class="callout amber">活动明确引用了以下版本，但当前无法解析。不能将缺失判定为合法未产生；可查看部分保持可追溯。</p><p v-for="key in missingObjects" :key="key" class="mono">{{key}}</p></section>
    <div class="tabs"><button v-for="(label,key) in {facts:'交互过程',evaluation:'评价依据',versions:'关联定义与版本',handling:'处理记录'}" :key="key" :class="{active:(route.tab||'facts')===key}" @click="setQuery({tab:key})">{{label}}</button></div>
    <template v-if="!route.tab||route.tab==='facts'">
      <div class="io-section input-section"><strong>学习者输入</strong><p v-for="f in activity.facts.filter(f=>f.actor==='学生')" :key="f.id"><small>{{f.at}} · {{f.kind}}</small> {{f.text}}</p></div>
      <div v-if="trace?.spans.length" class="trace-main"><section class="waterfall-section"><h4 class="section-title">处理链路（瀑布图） · 示例</h4><WaterfallChart :spans="trace.spans" :total-duration="trace.duration" :selected-span-id="chosen?.spanId||null" @select="select"/></section><section class="detail-section"><h4 class="section-title">步骤详情</h4><SpanDetail :key="chosen?.spanId" :span="chosen" :scope="activity.id"/></section></div>
      <p v-else class="callout">尚无处理步骤记录。{{activity.note}} 不根据结果对象反推已执行的过程。</p>
      <SemanticTimeline v-if="trace?.events.length" :events="trace.events" @select-span="select"/>
      <div class="io-section output-section"><strong>已记录系统内容</strong><p v-for="f in activity.facts.filter(f=>f.actor==='DeerMind')" :key="f.id"><small>{{f.at}} · {{f.kind}}</small> {{f.text}}</p><p v-if="!activity.facts.some(f=>f.actor==='DeerMind')">尚无系统输出记录。</p></div>
      <details class="panel"><summary>完整事实与实际帮助记录</summary><p class="muted">{{activity.note}}</p><article v-for="f in activity.facts" :key="f.id" class="fact" :id="f.id"><header><span>{{f.at}} · {{f.actor}}</span><strong>{{f.kind}}</strong></header><p>{{f.text}}</p><ModelLink v-if="f.object" :to="f.object" :scope="activity.id"/></article></details>
    </template>
    <section v-if="route.tab==='evaluation'" class="panel"><h3>证据、能力判断与目标评价</h3><template v-if="activity.objects.some(k=>resolve(k)?.space==='Evaluation')"><div v-for="key in activity.objects.filter(k=>resolve(k)?.space==='Evaluation')" :key="key" class="evaluation-record"><ModelObjectContent :reference="key" :scope="activity.id"/><RecordNotes v-if="resolve(key)?.kind==='evidence'" :subject="activity.id" :evidence="key"/></div></template><p v-else class="empty">{{missingObjects.length?'部分结果引用缺失，无法确认本次是否形成 Evidence／Belief。':'本次未登记 Evidence／Belief 记录。原因参见活动说明；不能仅凭空列表判断未产生或丢失。'}}</p></section>
    <section v-if="route.tab==='versions'" class="table-card"><h3>活动发生时采用的版本</h3><table class="data-table"><thead><tr><th>定义</th><th>准确版本</th></tr></thead><tbody><tr v-for="(version,id) in activity.versions" :key="id"><td><ModelLink :to="`${id}@${version}`" :scope="activity.id"/></td><td>v{{version}}</td></tr></tbody></table></section>
    <RecordNotes v-if="route.tab==='handling'" :subject="activity.id"/>
  </AccessGate><div v-else class="empty">该记录不属于当前数据来源或不存在。请切换相应数据来源后从列表进入。</div>
</div></template>
<style scoped>
.trace-detail{max-width:none}.trace-detail>.page-header{margin-bottom:12px}.detail-topbar{display:flex;align-items:center;gap:16px;background:white;padding:14px 16px;border:1px solid #e1e8ed;border-radius:8px}.detail-topbar>div{flex:1;min-width:0}.detail-topbar h3{font-size:16px;margin:0}.detail-topbar p{font-size:12px;color:#5a6b7a;margin:8px 0 0;overflow-wrap:anywhere}.trace-status{font-size:12px;color:#735c22;white-space:nowrap}.source-notice{color:#6a7785;font-size:12px;line-height:1.6;margin:12px 0}.trace-main{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);background:white;border:1px solid #e1e8ed;min-height:440px}.waterfall-section,.detail-section{min-width:0}.waterfall-section{border-right:1px solid #e1e8ed}.detail-section{background:#fafbfc}.section-title{margin:0;padding:12px 16px;background:#f0f4f7;color:#5a6b7a;font-size:12px}.detail-section :deep(.span-detail){max-height:560px;overflow-y:auto}.waterfall-section :deep(.waterfall-body){max-height:560px}.waterfall-section :deep(.row-name),.waterfall-section :deep(.col-name){width:160px}.io-section{padding:12px 16px;font-size:13px;line-height:1.65}.io-section p{margin:8px 0}.io-section small{color:#5a6b7a;margin-right:8px}.input-section{background:#edf6f1}.output-section{background:#eef2f6;margin-bottom:16px}.io-section strong{font-size:12px;color:#5a7a6a}@media(max-width:1200px){.trace-main{grid-template-columns:minmax(0,1fr)}.waterfall-section{border-right:0}.detail-topbar{flex-wrap:wrap}.waterfall-section :deep(.waterfall-body){max-height:290px}.detail-section :deep(.span-detail){max-height:430px}}
</style>
