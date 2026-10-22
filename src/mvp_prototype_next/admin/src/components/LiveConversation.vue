<script setup lang="ts">
import { ref, watch } from 'vue';
import { request, type LiveDetail } from '../workbench/live';

import { go } from '../workbench/navigation';
import RecordNotes from './RecordNotes.vue';
const props=defineProps<{id:string}>();const data=ref<LiveDetail>();const error=ref('');const loading=ref(false);let generation=0;
const dialog=ref(false),reason=ref('');
async function load(){const n=++generation;loading.value=true;error.value='';data.value=undefined;try{const value=await request<LiveDetail>('/api/live/admin/sessions/'+encodeURIComponent(props.id));if(n===generation)data.value=value;}catch(e){if(n===generation)error.value=e instanceof Error?e.message:'读取失败';}finally{if(n===generation)loading.value=false;}}
watch(()=>props.id,load,{immediate:true});

</script>
<template><section class="panel"><div class="row-between"><h3>真实会话 · {{id}}</h3><div class="button-row"><button class="btn" :disabled="loading" @click="load">刷新记录</button></div></div><p v-if="loading" role="status">正在读取会话…</p><p v-if="error" class="callout danger">{{error}}。已有输入与文件未修改。</p><template v-if="data"><p>{{data.scope.label}} · {{data.model}} · 最后更新 {{data.updatedAt}}</p><p class="callout">此记录尚未绑定正式学生身份、教材模型及 Evaluation。模型回复已保存不等于已确认学生看到；当前没有逐条展示回执，不能伪造实际帮助、Evidence 或 Belief。</p><p v-if="data.pending" class="callout amber">文件记录仍在处理或尚未收束；查阅不会替学生恢复、重试或停止。开始时间 {{data.pending.startedAt}}</p><p v-if="data.error" class="callout danger">{{data.error.message}}</p>
  <div class="conversation-audit"><article v-for="turn in data.turns" :key="turn.id" class="audit-turn" :class="turn.role"><header><strong>{{turn.role==='user'?'学习者输入':'模型生成内容'}}</strong><span>{{turn.at}}</span><code>{{turn.action}}</code></header><p v-if="turn.role==='user'" class="source-text">{{turn.displayText||turn.text}}</p><template v-else><div v-for="(block,index) in turn.blocks" :key="index" class="audit-block"><strong v-if="block.title">{{block.title}}</strong><p v-if="block.text" class="source-text">{{block.text}}</p><p v-if="block.prompt" class="source-text">{{block.prompt}}</p><ol v-if="block.steps"><li v-for="(step,i) in block.steps" :key="i">{{step}}</li></ol><p v-if="block.answer">已保存作答：{{block.answer}}</p><p v-if="block.state" class="muted">题目状态：{{block.state}}</p><details><summary>结构化内容</summary><pre>{{JSON.stringify(block,null,2)}}</pre></details></div></template><p v-if="turn.metrics" class="muted">本轮记录耗时 {{(turn.metrics.ms/1000).toFixed(2)}} 秒 · {{turn.metrics.calls.length}} 次模型调用（含格式重试）</p></article></div><p v-if="!data.turns.length" class="empty">会话已创建，尚无输入。不是数据丢失。</p><details><summary>运行元信息与原始输入</summary><pre>{{JSON.stringify(data,null,2)}}</pre></details></template></section><RecordNotes v-if="data" :subject="id"/></template>
