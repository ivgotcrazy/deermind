<script setup lang="ts">
import { ref } from 'vue';
import type { TeachingSession } from '../teaching-session';
defineProps<{session:TeachingSession;page:string}>();
const emit=defineEmits<{resume:[]}>();
const expanded=ref(true),query=ref('');
</script>
<template><div class="course-page">
  <header><h2>{{({home:'首页',status:'学习情况',textbook:'教材',errorbook:'错题本'} as Record<string,string>)[page]}}</h2><p>北师大版六年级上册数学 · 分数的应用</p></header>
  <template v-if="page==='textbook'"><p>本次学习目标：分清连续两层分数各对应谁，并解释自己的计算。</p><label>查找章节 <input v-model="query" type="search" placeholder="输入章节名称"/></label><section v-if="'分数的应用'.includes(query)"><button class="toggle" @click="expanded=!expanded">分数的应用 <span>{{expanded?'−':'＋'}}</span></button><div v-if="expanded"><h3>连续求一个量的几分之几</h3><p>教材第49—50页。可以逐步求出中间量，也可以合并比例；两种方法都需要说明每个分数对应的整体。</p><button @click="emit('resume')">继续本次学习</button></div></section></template>
  <template v-else-if="page==='status'"><p>按本次课程目标查看判断及依据。</p><section><button class="toggle" @click="expanded=!expanded">分数的应用 <span>{{expanded?'−':'＋'}}</span></button><template v-if="expanded"><article v-for="r in session.summary.value" :key="r.name"><b>{{r.name}} · {{r.target}}</b><p>{{r.judgment}}</p></article><p class="note">仅为当前情境预设的局部状态，不是整章掌握率。</p></template></section></template>
  <template v-else-if="page==='home'"><section><h3>继续学习</h3><p>分清两层分数各对应谁</p><button @click="emit('resume')">继续本次学习</button></section></template>
  <template v-else><section><h3>本次活动中的题目</h3><article v-for="(a,i) in session.state.attempts.filter(a=>a.result==='参照量错误')" :key="i"><p>{{a.answer}}</p><small>来源：本次检测 · {{a.help}}</small><button @click="emit('resume')">回到原对话</button></article><p v-if="!session.state.attempts.some(a=>a.result==='参照量错误')">本情境暂无已确认的检测错题。未提交和未决记录不计错。</p></section></template>
  <p class="note">固定情境的课程内容；不读取其他学习空间的个人记录。</p>
</div></template>
<style scoped>
.course-page{padding:28px 32px;max-width:1100px;margin:auto;color:#2c3e50}header{margin-bottom:24px}h2{font-size:24px;margin:0 0 8px}header p,.note,small{color:#75857c;font-size:13px}h3{font-size:16px;margin:18px 0 8px}p{line-height:1.8}section{padding:20px;border:1px solid #dce5df;border-radius:10px;background:white;margin:20px 0}button,input{font:inherit;border:1px solid #d5dfd8;border-radius:6px;padding:8px 14px;background:white;color:#2d6a4f}button{cursor:pointer}.toggle{display:flex;justify-content:space-between;width:100%;border:0;text-align:left;padding:0}label{font-size:14px}input{margin-left:8px;max-width:100%;box-sizing:border-box}article{border-top:1px solid #e4ece6;padding:16px 0}@media(max-width:800px){.course-page{padding:20px 16px}}
</style>
