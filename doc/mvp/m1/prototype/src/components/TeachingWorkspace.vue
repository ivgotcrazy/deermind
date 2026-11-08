<script setup lang="ts">
import { computed } from 'vue';
import ActivityEditor from './ActivityEditor.vue';
import ActivityTrace from './ActivityTrace.vue';
import { activityNames, type ActivityKind } from '../model/activity-mock';
const props=defineProps<{hash:string}>();
const requested=computed(()=>new URLSearchParams(props.hash.split('?')[1]).get('kind')||'explanation');
const kind=computed<ActivityKind>(()=>requested.value in activityNames?requested.value as ActivityKind:'explanation');
function select(value:string){location.hash='/interaction?kind='+value;}
</script>
<template><div class="wb-page">
  <header class="page-header"><div><div class="muted">Interaction Space · Mock</div><h2>交互活动管理</h2><p class="page-desc">选择活动，查看和调整蓝图节点、活动规则与推荐策略。</p></div><a class="btn" href="/student/" target="_blank">打开学生端 ↗</a></header>
  <nav class="button-row panel" aria-label="活动类型"><button v-for="(name,id) in activityNames" :key="id" class="btn" :class="{primary:kind===id&&requested!=='trace'}" @click="select(id)">{{name}}</button><button class="btn" :class="{primary:requested==='trace'}" @click="select('trace')">运行记录</button></nav>
  <ActivityTrace v-if="requested==='trace'"/>
  <ActivityEditor v-else :key="kind" :kind="kind" :hash="hash"/>
</div></template>
