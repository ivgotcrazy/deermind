<script setup lang="ts">
import { computed, ref } from 'vue';
import { ops, configReady, configFingerprint, saveConfig, checkConfig, reconcile, retry, operationsFixture } from '../operationsState';
import { journey } from '../journeyState';
import { recordsReview } from '../recordState';
const emit=defineEmits<{open:[view:string]}>();
const selected=ref(ops.tasks[0]!.id),connection=ref('available'),queryResult=ref<'found'|'absent'|'unknown'>('unknown'),retryResult=ref<'completed'|'failed'|'unresolved'>('completed');
const task=computed(()=>ops.tasks.find(t=>t.id===selected.value)!);
const labels:Record<string,string>={unknown:'结果未知，需核对',failed:'明确失败，未提交',unresolved:'语义未决',processing:'处理中',completed:'结果已确认'};
</script>
<template><main class="f-flow-page">
 <span class="f-eyebrow">运行与处理 · 独立合成任务</span><h1>先确认发生了什么，再决定如何处理</h1><p class="f-provenance">{{ operationsFixture.provenance }}。操作只改变此走查的状态；不会请求网络、重放讲解或修改学习判断。</p>
 <div class="f-flow-columns"><section class="f-card"><h2>服务配置与可用性</h2><label class="f-field">服务别名<input v-model="ops.alias" aria-label="服务别名"/></label><label class="f-field">模型标记<input v-model="ops.model" aria-label="模型标记"/></label><p>这里只保存演示标签，请勿填写密钥；实际服务及数据条件仍待核验。</p><button :disabled="!ops.alias.trim()||!ops.model.trim()" @click="saveConfig">保存演示配置</button><p role="status">{{ configReady?'配置已核对：预写可用':ops.saved!==configFingerprint?'当前配置尚未保存':ops.checked===ops.saved&&ops.saved?'预写检查不可用':'配置已保存，尚未检查' }}</p><label class="f-field">预写连接结果<select v-model="connection" aria-label="预写连接结果"><option value="available">可用</option><option value="unavailable">不可用</option></select></label><button :disabled="!ops.saved||ops.saved!==configFingerprint" @click="checkConfig(connection==='available')">载入预写连接检查结果</button></section>
 <section class="f-card"><h2>本浏览器已有事项</h2><p>教材任务：{{ journey.material.taskId||'尚未发起' }} · {{ {empty:'尚未发起',processing:'处理中',review:'待核对',published:'已发布'}[journey.material.stage] }}</p><p>人工复核事项 {{ recordsReview.issues.length }} 项；不会自动诊断或关闭。</p><div class="f-actions"><button @click="emit('open','materials')">查看教材任务</button><button @click="emit('open','trace')">进入记录追溯</button></div><h3>用量样例的读法</h3><p>下方四条预写原始任务已知费用合计 ¥0.03，另有 2 条未知；未知不能记成零。重试结果没有用量数据，不纳入上述合计。</p><p>当前原型未采集真实调用、持续时间或人工投入，不提供产品运行成本结论。</p></section></div>
 <section class="f-card"><h2>任务状态与原始用量示例</h2><div class="f-table-scroll"><table><thead><tr><th>任务</th><th>处理状态</th><th>原始耗时（ms）</th><th>输入 tokens</th><th>费用（元）</th><th>详情</th></tr></thead><tbody><tr v-for="t in ops.tasks" :key="t.id"><td>{{ t.label }}<small class="f-task-id">{{ t.id }}</small></td><td>{{ labels[t.state] }}</td><td>{{ operationsFixture.tasks.find(x=>x.id===t.id)?.latency_ms??'未知' }}</td><td>{{ operationsFixture.tasks.find(x=>x.id===t.id)?.input_tokens??'未知' }}</td><td>{{ operationsFixture.tasks.find(x=>x.id===t.id)?.cost_cny??'未知' }}</td><td><button @click="selected=t.id;queryResult='unknown';retryResult='completed'">查看 {{ t.id }}</button></td></tr></tbody></table></div></section>
 <section class="f-card" aria-label="任务处理详情"><h2>{{ task.label }}</h2><p>{{ task.id }} · {{ labels[task.state] }} · 尝试 {{ task.attempts }} 次</p>
  <template v-if="['unknown','processing'].includes(task.state)"><p>先查询原提交。结果未知时不能直接重试，也不要求孩子重新作答。</p><label class="f-field">预写原提交查询<select v-model="queryResult" aria-label="预写原提交查询"><option value="unknown">仍未知</option><option value="found">原结果已存在</option><option value="absent">确认原请求未提交</option></select></label><button @click="reconcile(task,queryResult)">核对原任务结果</button></template>
  <template v-if="task.state==='failed'"><label class="f-field">预写重试结果<select v-model="retryResult" aria-label="预写重试结果"><option value="completed">处理完成</option><option value="failed">再次传输失败</option><option value="unresolved">处理完成但语义未决</option></select></label><button :disabled="!task.reconciled||!configReady" @click="retry(task,retryResult)">重试原任务</button><p v-if="!configReady">重试前需要保存并核对当前服务配置。</p></template>
  <p v-if="task.state==='unresolved'">网络已经返回；缺少足够依据，不能给出语义结论。不能靠传输重试把它标成通过；需核对输入、规则和模型输出，再决定补充条件或人工维护。</p>
  <p v-if="task.state==='completed'">已恢复原任务结果状态。没有重复新增作答，也没有重新展示教学内容；真实提交核对机制在工程阶段实现。</p>
  <ol><li v-for="(entry,i) in task.audit" :key="i">{{ entry }}</li></ol>
 </section>
</main></template>
