<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { chapterOf } from './data';
import { state, orderedSessions } from './state';
import type { Session } from './state';
import { activityTime, chapterCounts, hasReference, homeReference, topic } from './home';
import SavedRequest from './SavedRequest.vue';
import HomeStatistics from './HomeStatistics.vue';
import ClassroomProgress from './ClassroomProgress.vue';
import { statusCatalog } from './statusCatalog';
import './learning-status.css';
import './student-home.css';
const props=defineProps<{space:string;scope:string}>();
const emit=defineEmits<{navigate:[page:string,query?:Record<string,string>];begin:[chapter:string];resume:[session:Session]}>();
const route=useRoute();
const sessions=computed(()=>orderedSessions(state.sessions.filter(s=>s.learner==='S0001'&&s.space===props.space)));
const latest=computed(()=>sessions.value[0]);
const resumable=computed(()=>sessions.value.filter(s=>s.status!=='ended'&&!s.realSuccessor));
const available=computed(()=>props.space==='school');
const catalog=computed(()=>statusCatalog(state.home.catalogScale));
const reference=computed(()=>hasReference('S0001',props.space));
const focusChapter=computed(()=>latest.value?.chapter||(reference.value?homeReference.chapter:''));
const feedback=computed(():string|undefined=>({fractions:'能找出比较标准；为什么用它作除数，还需要讲清楚。',circle:'能辨认半径和直径；两者为什么是两倍关系，还需要帮助。',ratio:'能分清比的两个对象；怎样理解比值，还需要弄清楚。'} as Record<string,string>)[focusChapter.value]);
const deferred=computed(()=>!!state.home.deferred[`${props.space}:${homeReference.id}`]);
const suggestion=computed(()=>available.value&&reference.value&&!latest.value&&!deferred.value&&state.home.timePreview===0);
const evidenceOpen=ref(false);
function navigate(page:string,query:Record<string,string>={}){emit('navigate',page,query);}
function defer(){state.home.deferred[`${props.space}:${homeReference.id}`]=true;}
function restoreSuggestion(){delete state.home.deferred[`${props.space}:${homeReference.id}`];}
function openRecord(id:string){navigate('record',{id,from:route.fullPath});}
</script>
<template>
 <div class="learning-status student-home">
  <div class="home-heading"><div><h1>首页</h1><p>{{ available?'校内数学 · 北师大版六年级上册':'校外数学 · 教材待准备' }}</p></div><div class="home-time"><span>今日用时</span><strong>{{ state.home.timePreview?`${state.home.timePreview} 分钟`:'尚未统计' }}</strong><small>{{ state.home.timePreview?'时间情境示例 · 跨课程累计':'每日总投入上限 30 分钟' }}</small></div></div>
  <SavedRequest :scope="scope" :available="available" @materials="navigate('materials')"/>
  <div v-if="state.home.timePreview" class="time-reminder" role="note"><strong>{{ state.home.timePreview===30?'今天先到这里，也可以。':'今天还可以安排约 4 分钟。' }}</strong><span>{{ state.home.timePreview===30?'进度和草稿会保留，下一次可以接着学。':'可以收束当前问题，较长的学习留到下次。' }}</span><small>预写时间情境，不是实际计时；不会强制锁屏。</small></div>
  <section v-if="!available" class="status-summary" aria-label="学习情况摘要"><h2>本空间暂无学习情况</h2><p>教材还在准备中，暂不能开始本空间的学习。校内与校外记录分别保存。</p><button class="text" @click="navigate('materials')">查看教材准备情况 →</button></section>
  <div v-else class="home-primary">
  <ClassroomProgress learner="S0001" :space="space" :catalog="catalog" prominent/>
  <aside class="status-next" aria-label="下一步选择">
   <section class="status-next-card" aria-label="当前学习安排">
    <template v-if="state.home.timePreview===30||(state.home.timePreview===26&&(!latest||latest.status==='ended'))">
     <p class="home-kicker">留好下一次的起点</p><h2>{{ state.home.timePreview===30?'收好今天的学习':'先回顾一下今天的内容' }}</h2>
     <p v-if="resumable[0]">“{{ topic(resumable[0].chapter) }}”的进度已经保留。</p><p v-else>可以回看已有记录，下一次再开始新的问题。</p>
     <button @click="navigate('records',{kind:'activities'})">回看学习记录</button><button v-if="resumable[0]" class="text" @click="emit('resume',resumable[0])">查看未结束的活动</button>
    </template>
    <template v-else-if="latest&&latest.status!=='ended'">
     <p class="home-kicker">继续学习</p><h2>{{ latest.real?'分数的应用':topic(latest.chapter) }}</h2>
     <p v-if="latest.real||latest.conversation">对话、学习进度与未提交的输入已保留。</p><p v-else>停在“{{ chapterOf(latest.chapter)?.segments[latest.segment]?.title }}”。</p>
     <p class="muted small">{{ activityTime(latest.updatedAt) }}</p><button class="primary" @click="emit('resume',latest)">继续这次学习 →</button>
    </template>
    <template v-else-if="latest">
     <p class="home-kicker">最近一次学习</p><h2>{{ latest.real?'分数的应用':topic(latest.chapter) }}</h2>
     <p>{{ latest.real?'交流和反馈已经保存，尚未形成正式学习评价。':latest.submitted?'已提交一次作答，目前尚未判定。':'本次学习已保存，尚未形成正式评价。' }}</p>
     <button @click="openRecord(latest.id)">查看本次记录</button><button v-if="latest.real" class="text" @click="navigate('lesson',{id:latest.id})">回看对话</button>
    </template>
    <template v-else-if="suggestion">
     <p class="home-kicker">相关建议 · {{ homeReference.duration }} <span class="reference-badge">预写建议</span></p><h2>{{ homeReference.title }}</h2>
     <div class="home-actions"><button class="primary" @click="emit('begin',homeReference.chapter)">从这里开始讲解 →</button><button class="text" @click="defer">暂不安排</button></div>
     <button class="home-evidence-link" @click="evidenceOpen=!evidenceOpen" :aria-expanded="evidenceOpen">{{ evidenceOpen?'收起建议依据':'为什么建议这个？' }}</button>
     <section v-if="evidenceOpen" class="status-suggestion-evidence" aria-label="建议的参考依据">
      <p>{{ homeReference.question }}</p><dl><dt>参考作答</dt><dd>{{ homeReference.answer }}</dd><dt>帮助条件</dt><dd>{{ homeReference.help }}</dd><dt>判断边界</dt><dd>{{ homeReference.scope }}</dd></dl>
      <button class="text" @click="navigate('status',{chapter:'fractions',from:'home'})">查看本章要求 →</button>
     </section>
    </template>
    <template v-else>
     <p class="home-kicker">下一步，由你选择</p><h2>{{ deferred?'按自己的需要来':'从一个具体疑问开始' }}</h2>
     <p>点开章节请求讲解，或在下方直接输入、带来一道题。</p>
     <p v-if="!reference" class="muted small">{{ state.home.reference==='none'?'还没有足够记录了解你的学习情况。':'已有记录尚未形成学习评价，暂不据此安排针对性学习。' }}</p>
     <button class="text" @click="navigate('materials')">选择教材章节 →</button><button v-if="deferred" class="text" @click="restoreSuggestion">重新查看建议</button>
    </template>
   </section>
   <details v-if="resumable.length&&(latest?.status==='ended'||resumable.length>1)" class="home-other">
    <summary>还有 {{ resumable.filter(s=>s.id!==latest?.id).length }} 项学习可以继续</summary>
    <button v-for="s in resumable.filter(s=>s.id!==latest?.id).slice(0,3)" :key="s.id" class="record-row" @click="emit('resume',s)"><span><strong>{{ topic(s.chapter) }}</strong><small>{{ activityTime(s.updatedAt) }}</small></span><span>继续 →</span></button>
    <button class="text" @click="navigate('records',{kind:'activities'})">查看全部学习活动 →</button>
   </details>
  </aside>
   <section class="home-overview" aria-label="学习情况摘要">
    <div class="section-title"><h2>{{ latest?'在 DeerMind 的学习':reference?'DeerMind 近期关注':'从你的问题开始' }}</h2><span v-if="reference&&!latest" class="reference-badge">预写参考</span></div>
    <article v-if="focusChapter" class="recent-chapter">
     <h3>{{ chapterOf(focusChapter)?.name||'最近学习的章节' }}</h3>
     <p class="home-position">{{ latest?'最近活动：':'关注内容：' }}{{ topic(focusChapter) }}<span v-if="latest"> · {{ latest.status==='ended'?'已结束':'进度已保留' }}</span></p>
     <template v-if="reference&&feedback"><p class="home-feedback-brief">{{ feedback }}</p><p class="muted small">还有 {{ chapterCounts(focusChapter,'S0001',space)[2] }} 项要求待确认。<span class="reference-badge">预写反馈</span></p></template>
     <p v-else class="muted">还不能判断学得怎样。学习活动已保留，尚未形成正式评价。</p>
     <button class="text" @click="navigate('status',{chapter:focusChapter,from:'home'})">查看本章学习情况 →</button>
    </article>
    <template v-else><h3>还不能判断学得怎样</h3><p>当前尚无充分评价依据。可以从想了解的章节开始，也可以在下方提出问题。</p></template>
    <p v-if="sessions.length" class="muted small">本轮 {{ sessions.length }} 项活动尚未形成正式评价，未计入预写反馈和统计。<button class="text" @click="navigate('records',{kind:'activities'})">查看实际活动 →</button></p>
    <button v-if="!focusChapter" class="text" @click="navigate('status')">查看章节学习情况 →</button>
   </section>
  </div>
  <HomeStatistics :available="available" :show-reference="state.home.reference!=='none'"/>
 </div>
</template>
