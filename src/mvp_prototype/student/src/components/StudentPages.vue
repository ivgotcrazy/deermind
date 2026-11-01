<script setup lang="ts">
import { ref } from 'vue';
import type { StudentCourse, PageId } from '../student-pages';
import type { ClassroomReport } from '../live';
import HomePage from './HomePage.vue';
import LearningStatusPage from './LearningStatusPage.vue';
import TextbookPage from './TextbookPage.vue';
import ErrorBookPage from './ErrorBookPage.vue';
import '../student-pages.css';
const props=defineProps<{course:StudentCourse;page:PageId;report?:ClassroomReport}>();
const emit=defineEmits<{navigate:[page:PageId];updateProgress:[];startAction:[text:string];start:[chapters:string[],mode:'lesson'|'test'];resume:[id:string];history:[id:string]}>();
const status=ref<InstanceType<typeof LearningStatusPage>|null>(null),records=ref<InstanceType<typeof ErrorBookPage>|null>(null);
const focusQuestion=ref(''),openActivity=ref('');
function showStatus(id:string){status.value?.openChapter(id);emit('navigate','status');}
function showQuestion(id:string){focusQuestion.value=id;records.value?.open(id);openActivity.value='';emit('navigate','errorbook');}
function filterQuestions(filter:string){focusQuestion.value='';records.value?.filter(filter);emit('navigate','errorbook');}
</script>
<template><div class="student-pages">
  <HomePage v-show="page==='home'" :course="course" :classroom-label="report?.unknown?'暂不确定':report?.chapters.map(id=>course.chapters.find(c=>c.id===id)?.name).filter(Boolean).join('、')" :confirmed-at="report?.confirmedAt" @update-progress="emit('updateProgress')" @resume="emit('resume',$event)" @history="emit('history',$event)" @start-action="emit('startAction',$event)" @show-status="showStatus" @show-textbook="emit('navigate','textbook')" @open-questions="filterQuestions" @open-activity="openActivity=$event"/>
  <LearningStatusPage ref="status" v-show="page==='status'" :course="course" :classroom-ids="report?.chapters||[]" @update-progress="emit('updateProgress')" @start-action="emit('startAction',$event)" @open-question="showQuestion"/>
  <TextbookPage v-show="page==='textbook'" :course="course" :classroom-ids="report?.chapters||[]" @start-action="emit('startAction',$event)" @start="(ids,mode)=>emit('start',ids,mode)"/>
  <ErrorBookPage ref="records" v-show="page==='errorbook'" :course="course" :focus-question="focusQuestion" @start-action="emit('startAction',$event)" @open-activity="openActivity=$event" @back-to-status="emit('navigate','status')"/>
  <div v-if="openActivity" class="student-page" style="height:0;padding:0"><div class="modal-shade" @click.self="openActivity=''"><section role="dialog" aria-modal="true" aria-label="学习活动记录" class="modal"><header class="row"><h3>{{props.course.activities.find(a=>a.id===openActivity)?.title}}</h3><button @click="openActivity=''">关闭</button></header><p>{{course.activities.find(a=>a.id===openActivity)?.detail}}</p><article v-for="q in course.questions.filter(q=>q.attempts.some(a=>a.activityId===openActivity))" :key="q.id" class="list-row"><button class="link" @click="showQuestion(q.id)">{{q.text}}</button><p v-for="a in q.attempts.filter(a=>a.activityId===openActivity)" :key="a.id" class="muted">{{a.answer}} · {{a.result}} · {{a.help}}</p></article><button class="primary" @click="emit('history',openActivity);openActivity=''">回到原对话</button></section></div></div>
</div></template>
