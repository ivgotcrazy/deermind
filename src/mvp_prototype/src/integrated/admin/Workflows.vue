<script setup lang="ts">
import { computed, ref } from 'vue';
import MaintenanceReview from '../../components/MaintenanceReview.vue';
import CaseTraceReview from '../../components/CaseTraceReview.vue';
import MaterialSetupReview from '../../components/MaterialSetupReview.vue';
import SourceReferenceReview from '../../components/SourceReferenceReview.vue';
import AccountReview from '../../components/AccountReview.vue';
import OperationsReview from '../../components/OperationsReview.vue';
import { state } from '../../structure/state';
import { liveRecords, type LessonRecords } from '../../recordState';
import type { PageType } from './types';
import './legacy-workflows.css';
const props=defineProps<{page:string}>();
const emit=defineEmits<{navigate:[page:PageType]}>();
const issueId=ref(''),note=ref(''),notice=ref('');
function retainedLesson():LessonRecords {
 try {
  const value=JSON.parse(localStorage.getItem('deermind-phase4-lesson-v1')||'null');
  if(value&&Array.isArray(value.runs)&&typeof value.practiceText==='string')return value;
 } catch { /* Do not rewrite unreadable historical storage. */ }
 return {practiceSubmitted:false,practiceText:'',runs:[]};
}
const records=computed(()=>liveRecords(retainedLesson()));
const issue=computed(()=>state.issues.find(i=>i.id===issueId.value));
function saveNote(){
 if(!issue.value||!note.value.trim())return;
 issue.value.note=note.value.trim();issue.value.status='已记录意见';
 notice.value='处理意见已保存，家长可在原记录查看；没有更改作答或学习状态。';
}
</script>
<template><div class="legacy-workflows">
 <MaintenanceReview v-if="page==='maintenance'"/>
 <template v-else-if="page==='review'">
  <section class="f-card"><h2>来自家长端的复核事项</h2><p>与保留的家长端共用本地记录。处理意见不会直接修改学习状态。</p>
   <label class="f-field">选择事项<select v-model="issueId" aria-label="选择家长复核事项" @change="note=issue?.note||''"><option value="">请选择</option><option v-for="row in state.issues" :key="row.id" :value="row.id">{{ row.id }} · {{ row.recordId }} · {{ row.status }}</option></select></label>
   <template v-if="issue"><p>{{ issue.reason }}</p><label class="f-field">处理意见<textarea v-model="note" aria-label="家长复核处理意见"/></label><button :disabled="!note.trim()" @click="saveNote">保存处理意见</button></template><p v-if="notice" role="status">{{ notice }}</p>
  </section>
  <CaseTraceReview :records="records" @maintenance="emit('navigate','maintenance')"/>
 </template>
 <template v-else-if="page==='content'"><MaterialSetupReview/><SourceReferenceReview/></template>
 <AccountReview v-else-if="page==='account'" role="admin"/>
 <template v-else-if="page==='config'"><section class="f-card"><h2>真实模型配置与运行流程</h2><p>真实对话继续读取原本地服务的 .env 配置；本页面不显示或修改 API key。下面保留原运行流程的合成走查，不会修改真实模型服务配置。</p></section><OperationsReview/></template>
</div></template>
