<script setup lang="ts">
import { computed, ref } from 'vue';
import { hub, contexts, currentContext, selectContext } from '../hubState';
import { journey } from '../journeyState';
import type { LearningRecord } from '../recordState';
const props=defineProps<{shown:number;closed:boolean;segment:string;records:LearningRecord[]}>();
const emit=defineEmits<{open:[view:string]}>();
const historyOpen=ref(false),notice=ref('');
const draft=computed({get:()=>hub.drafts[hub.current]||'',set:(s:string)=>hub.drafts[hub.current]=s});
const messages=computed(()=>hub.messages[hub.current]||[]);
const records=computed(()=>props.records.filter(r=>!r.hidden&&r.spaceId===hub.current));
const course=computed(()=>journey.courses.find(c=>c.id===hub.current));
const exam=computed(()=>journey.exam.courseId===hub.current&&journey.exam.status!=='idle'?journey.exam:undefined);
function change(e:Event){selectContext((e.target as HTMLSelectElement).value);historyOpen.value=false;notice.value='';}
function send(){if(!draft.value.trim())return;(hub.messages[hub.current]??=[]).push(draft.value.trim());draft.value='';notice.value='已保留在当前空间。原型未连接模型，尚未理解或执行请求；下方历史可按需查看。';}
function enter(e:KeyboardEvent){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}}
</script>
<template><div class="f-flow-layout">
<main class="f-flow-page f-learning-home">
 <div class="f-content-heading"><div><span class="f-eyebrow">从你想弄清楚的地方开始</span><h1>今天，想学什么？</h1></div><label class="f-field">当前学习空间<select :value="hub.current" aria-label="当前学习空间" @change="change"><option v-for="c in contexts" :key="c.id" :value="c.id">{{ c.name }}</option></select></label></div>
 <details class="f-provenance"><summary>合成内容 · 尚未连接模型</summary><p>实际教材与模型尚未接入。新建空间不会继承演示学习判断。</p></details>
 <section class="f-card f-home-focus" v-if="hub.current==='demo'"><span class="f-eyebrow">{{ shown?'上次的学习':'一段可体验的讲解' }}</span><h2>三角形面积，为什么要除以 2？</h2><p>{{ shown?`停留在「${segment}」，已展示 ${shown} 段。`:'从拼合图形开始，每次弄清一个关键问题。' }}{{ closed?'本次已结束，可以回看。':'你决定继续、追问或暂时离开。' }}</p><button class="f-primary" @click="emit('open','activity')">{{ closed?'回看本次讲解':shown?'继续本次讲解':'开始章节讲解' }}</button></section>
 <section v-else class="f-card f-home-focus"><span class="f-eyebrow">{{ currentContext.name }} · 教材与目标 v{{ course?.version }}</span><h2>{{ exam?'查看这次检测安排与记录':'按教材范围准备学习' }}</h2><p>已选择 {{ course?.units.length }} 节。此空间可体验范围检测与问题求助；章节讲解内容尚未准备。</p><button class="f-primary" @click="emit('open','course')">{{ exam?'回到本空间检测':'选择范围，准备检测' }}</button></section>
 <div class="f-home-cards">
  <section class="f-card"><span class="f-eyebrow">有具体的问题</span><h2>不会做，也可以来问</h2><p>带上题目、自己的尝试，或用笔写下卡住的地方。</p><button @click="emit('open','help')">问题求助</button></section>
  <section class="f-card"><span class="f-eyebrow">看看依据</span><h2>学习情况与记录</h2><p>本空间已有 {{ records.length }} 条可见题目记录。{{ hub.current==='demo'?'章节状态页另有明确标注的预写参考。':'尚无正式学习评价，不显示达标项数。' }}</p><div class="f-actions"><button @click="emit('open','status')">查看学习情况</button><button @click="emit('open','records')">回看题目记录</button></div></section>
 </div>
 <button class="f-text-button" @click="emit('open','course')">选择教材、创建空间或准备检测 →</button>
</main>
<section class="f-inline-composer" aria-label="学习首页对话"><div class="f-content-heading"><label for="home-input">正在 {{ currentContext.name }} · 随时说说你的想法</label><button @click="historyOpen=!historyOpen" :aria-expanded="historyOpen">{{ historyOpen?'收起历史':'对话历史' }}</button></div><form @submit.prevent="send"><textarea id="home-input" v-model="draft" rows="2" placeholder="想学什么，或哪里不太明白…" @keydown="enter"/><button type="submit" class="f-primary" :disabled="!draft.trim()">发送</button></form><p v-if="notice" role="status">{{ notice }}</p><div v-if="historyOpen" class="f-home-history" aria-label="首页对话历史"><p v-if="!messages.length">当前空间还没有对话记录。</p><p v-for="(message,i) in messages" :key="i">{{ message }}</p></div></section>
</div></template>
