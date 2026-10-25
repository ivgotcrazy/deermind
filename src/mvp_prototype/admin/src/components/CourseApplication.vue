<script setup lang="ts">
import { computed, ref } from 'vue';
import { flow, applyTargets } from '../workbench/learning-flow';
import { chapterReady } from '../../../shared/learning-flow';
const props=defineProps<{bookId:string;targetId?:string}>();
const notice=ref(''),error=ref('');
const courses=computed(()=>flow.courses.filter(c=>c.snapshot.book.id===props.bookId&&(!props.targetId||c.snapshot.target.id===props.targetId)));
const spaces=computed(()=>flow.spaces.filter(s=>courses.value.some(c=>c.id===s.courseId)));
function apply(){try{const n=applyTargets(props.bookId,props.targetId);notice.value=`已应用 ${n} 个教材与目标组合；学生可以选用，已有引用空间同步采用。`;error.value='';}catch(e){error.value=(e as Error).message;}}
</script>
<template><section class="panel course-application"><div class="section-heading"><div><h3>学生选用与更新</h3><p class="muted">所有试用学生均可选用已应用内容；不需要分配名单或学生确认版本。</p></div><button class="btn primary" @click="apply">应用更新</button></div>
<p v-if="notice" role="status" class="saved-note">{{notice}}</p><p v-if="error" role="alert" class="callout amber">{{error}}</p>
<p v-if="!courses.length" class="muted">尚未应用。准备好教材与目标后，在这里应用一次即可供学生选择。</p>
<p v-else class="muted">最近应用 {{courses.map(c=>c.appliedAt).sort().slice(-1)[0]}} · {{spaces.length}} 个本轮创建的空间引用 · 原活动保留当时版本</p>
<details v-if="courses.length"><summary>查看已应用内容可开展的行为</summary><div v-for="course in courses" :key="course.id"><h4>{{course.snapshot.target.name}}</h4><table class="data-table"><thead><tr><th>章节</th><th>讲解</th><th>检测与评价依据</th></tr></thead><tbody><tr v-for="ch in course.snapshot.book.units.flatMap(u=>u.chapters)" :key="ch.id"><td>{{ch.name}}</td><td>{{chapterReady(course.snapshot,ch.id).explain?'可开展':'待准备'}}</td><td>{{chapterReady(course.snapshot,ch.id).test?'已具备':'待补齐'}}<small v-if="chapterReady(course.snapshot,ch.id).scripted">已提供本轮 mock 走查</small></td></tr></tbody></table></div></details>
<p class="muted">本轮使用同一浏览器内的 mock 记录；应用不表示正式模型或教学质量已经通过验证。</p></section></template>
