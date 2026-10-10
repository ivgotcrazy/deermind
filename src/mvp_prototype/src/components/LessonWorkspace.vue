<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { state, current, notify } from '../store';
import { spaces } from '../data';
import { lessons, lessonProgress, lessonState } from '../lessons';
import Icon from './Icon.vue';

const route = useRoute();
const router = useRouter();
const blocked = computed(() => current().test.stage === 'running');
const available = computed(() => state.space === 'school' && current().book === 'open');
const lesson = computed(() => lessons.find((l) => l.id === route.query.lesson) || lessons[0]!);
const progress = computed(() => available.value && !blocked.value ? lessonProgress(state.space, lesson.value.id) : null);
const step = computed(() => lesson.value.steps[progress.value?.index ?? 0]!);
const draft = computed({
  get: () => progress.value?.drafts[progress.value.index] || '',
  set: (value: string) => { if (progress.value) progress.value.drafts[progress.value.index] = value; },
});
const unsent = computed(() => Object.entries(progress.value?.drafts || {}).filter(([, text]) => text.trim()));
const history = ref(false);
const examples = ref(false);
const playing = ref(false);
const input = ref<HTMLTextAreaElement>();
const content = ref<HTMLElement>();
const dock = ref<HTMLElement>();
const expanded = ref(true);
const replies = computed(() => progress.value?.exchanges.filter((e) => e.step === progress.value?.index) || []);
const observer = new ResizeObserver(([entry]) => {
  document.documentElement.style.setProperty('--intent-dock-height', `${entry!.target.getBoundingClientRect().height}px`);
});
watch(dock, (el) => { observer.disconnect(); if (el) observer.observe(el); }, { flush: 'post' });
function stopAudio() { window.speechSynthesis?.cancel(); playing.value = false; }
watch(() => [route.query.lesson, state.space, blocked.value, available.value], () => {
  history.value = false; examples.value = false; expanded.value = true; stopAudio();
});
onBeforeUnmount(() => { stopAudio(); observer.disconnect(); document.documentElement.style.removeProperty('--intent-dock-height'); });
function canRespond() {
  if (!progress.value || progress.value.ended) return false;
  if (state.scenario === 'offline' || state.scenario === 'failure') {
    notify(state.scenario === 'offline' ? '尚未发送，内容与进度已保留。' : '本次演示处理失败，内容与进度已保留，可以重试。');
    return false;
  }
  return true;
}
async function locate() { await nextTick(); content.value?.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
function selectStep(index: number) {
  const p = progress.value;
  if (!p || index > p.revealed) return;
  stopAudio(); p.index = index; expanded.value = true; void locate();
}
function advance() {
  if (!canRespond()) return;
  const p = progress.value!;
  if (p.index >= lesson.value.steps.length - 1) return;
  stopAudio(); p.revealed = Math.max(p.revealed, p.index + 1); p.index++; p.updated = Date.now(); expanded.value = true; void locate();
}
function send(fixture = false) {
  if (!canRespond() || (!fixture && !draft.value.trim())) return;
  const p = progress.value!;
  p.exchanges.push({ step: p.index, question: fixture ? step.value.question : draft.value.trim(),
    answer: fixture ? step.value.answer : '你的追问已保存在这一段。本原型尚未连接语义模型，没有理解或回答这句话；可使用“情景示例”体验就地补充。', fixture });
  if (!fixture) draft.value = '';
  p.updated = Date.now(); expanded.value = true; examples.value = false; history.value = false;
  void nextTick(() => { document.querySelector('.lesson-discussion')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); input.value?.focus({ preventScroll: true }); });
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); send(); }
}
function play() {
  if (!('speechSynthesis' in window)) { notify('当前浏览器无法朗读，请阅读本段。'); return; }
  stopAudio(); const utterance = new SpeechSynthesisUtterance(`${step.value.title}。${step.value.text}。${step.value.takeaway}`);
  utterance.lang = 'zh-CN'; utterance.onend = () => { playing.value = false; }; utterance.onerror = () => { playing.value = false; };
  playing.value = true; window.speechSynthesis.speak(utterance);
}
function end() { if (progress.value) { stopAudio(); progress.value.ended = true; progress.value.updated = Date.now(); history.value = false; } }
function openLesson(id: string) { stopAudio(); void router.push({ path: '/student/lesson', query: { lesson: id } }); }
</script>

<template>
  <section v-if="blocked" class="card lesson-unavailable">
    <h1>先回到正在进行的自测</h1>
    <p>本次自测尚未结束。可以回去继续作答，或在自测中请求讲解；求助会结束本次检测。</p>
    <RouterLink class="button primary" to="/student/test">返回自测</RouterLink>
  </section>
  <section v-else-if="!available" class="card lesson-unavailable">
    <h1>这个空间还没有章节讲解新样例</h1>
    <p>本轮先用校内数学的两个章节走查。课程内容保持分开，不会带入另一空间的学习记录。</p>
    <RouterLink class="button secondary" to="/student/book">返回本空间教材</RouterLink>
  </section>
  <div v-else-if="progress" class="lesson-workspace">
    <header class="lesson-header">
      <div><span class="eyebrow">{{ spaces[state.space].name }} / 章节讲解</span><h1>{{ lesson.chapter }}</h1><p>{{ lesson.purpose }}</p></div>
      <div class="lesson-header-actions"><RouterLink class="text-button" to="/student/book">返回教材</RouterLink><button v-if="!progress.ended" class="text-button" @click="end">结束本次</button></div>
    </header>
    <p class="lesson-demo-note">交互走查 · 预写讲解与示例追问，不形成真实学习判断</p>
    <p v-if="lessonState.storageWarning" class="banner warning">浏览器无法保留记录，刷新后可能丢失本次内容。</p>
    <div class="lesson-layout">
      <aside class="lesson-outline" aria-label="本次讲解内容">
        <span class="eyebrow">这次一起弄懂</span>
        <button v-for="(s, i) in lesson.steps" :key="s.title" :disabled="i > progress.revealed" :aria-current="i === progress.index ? 'step' : undefined" @click="selectStep(i)">
          <span class="lesson-step-number">{{ i + 1 }}</span><span>{{ s.title }}<small>{{ i > progress.revealed ? '还没讲到' : i === progress.index ? '正在查看' : '可以回看' }}</small></span>
        </button>
        <p>这是讲解的位置，不代表掌握程度。</p>
        <div class="lesson-switch"><span class="eyebrow">也可以先学别的</span><button v-for="other in lessons.filter((l) => l.id !== lesson.id)" :key="other.id" class="text-button" @click="openLesson(other.id)">{{ other.chapter }} <Icon name="arrow" :size="14" /></button><small>当前进度会保留，回来可以继续。</small></div>
      </aside>
      <div class="lesson-body">
        <section v-if="progress.ended" class="lesson-summary card" aria-label="本次讲解小结">
          <span class="eyebrow">本次已结束 · 内容仍可回看</span><h2>今天先到这里</h2>
          <p>已展示 {{ progress.revealed + 1 }} 段讲解，收到 {{ progress.exchanges.length }} 条追问。独立运用还未检查。</p>
          <p v-for="[index, text] in unsent" :key="index">第 {{ Number(index) + 1 }} 段尚未发送的草稿已保留：{{ text }}</p>
          <RouterLink class="button secondary" to="/student/book">回到教材</RouterLink>
        </section>
        <article ref="content" class="card lesson-content" aria-label="当前讲解">
          <div class="lesson-content-top"><span class="eyebrow">第 {{ progress.index + 1 }} 段 / 共 {{ lesson.steps.length }} 段示例</span><button class="text-button" @click="playing ? stopAudio() : play()"><Icon :name="playing ? 'pause' : 'volume'" :size="16" />{{ playing ? '停止播放' : '试听本段' }}</button></div>
          <h2>{{ step.title }}</h2><p class="lesson-explanation">{{ step.text }}</p>
          <figure v-if="step.illustration" class="lesson-fraction-figure" aria-label="相同大小的整体，分别取四分之三与四分之二">
            <div v-for="filled in [3, 2]" :key="filled" class="fraction-row"><strong>{{ filled === 3 ? '3/4' : '1/2' }}</strong><div class="fraction-bar"><span v-for="part in 4" :key="part" :class="{ filled: part <= filled }">1/4</span></div><span v-if="filled === 2">= 2/4</span></div>
            <figcaption>每一小份一样大，比较的是 3 份与 2 份。</figcaption>
          </figure>
          <div class="lesson-formula">{{ step.formula }}</div><p class="lesson-takeaway">{{ step.takeaway }}</p>
          <section v-if="replies.length" class="lesson-discussion" aria-label="这一段的追问">
            <button class="lesson-discussion-toggle" :aria-expanded="expanded" @click="expanded = !expanded"><Icon name="chat" :size="17" />这一段的追问 · {{ replies.length }}<span>{{ expanded ? '收起' : '展开' }}</span></button>
            <div v-if="expanded"><article v-for="(reply, i) in replies" :key="i" class="lesson-followup"><h3>{{ reply.question }}</h3><small>{{ reply.fixture ? '固定情景示例' : '已保存 · 尚未由模型回答' }}</small><p>{{ reply.answer }}</p></article></div>
          </section>
          <footer v-if="!progress.ended" class="lesson-next">
            <p>这里可以停一停。想继续，或有哪里不明白，都由你决定。</p>
            <button v-if="progress.index < lesson.steps.length - 1" class="button primary" @click="advance">继续下一段 <Icon name="arrow" :size="17" /></button>
            <button v-else class="button primary" @click="end">结束本次讲解</button>
          </footer>
        </article>
      </div>
    </div>
    <section ref="dock" class="intent-dock student lesson-dock" aria-label="DeerMind 输入区">
      <aside v-if="history" id="lesson-history" class="intent-panel" aria-label="DeerMind 对话历史" @keydown.esc="history = false">
        <header class="intent-heading"><strong>本次追问历史</strong><button class="icon-button" aria-label="收起对话历史" @click="history = false">×</button></header>
        <div class="intent-messages"><p v-if="!progress.exchanges.length">还没有追问。每段讲解可以从左侧内容列表回看。</p><article v-for="(reply, i) in progress.exchanges" :key="i" class="lesson-history-entry"><button class="text-button" @click="selectStep(reply.step); history = false">回到第 {{ reply.step + 1 }} 段</button><strong>{{ reply.question }}</strong><p>{{ reply.answer }}</p></article></div>
      </aside>
      <div v-if="examples && !progress.ended" class="intent-suggestions"><span>固定情景示例 · 点击走查就地补充</span><button @click="send(true)">{{ step.question }} <Icon name="arrow" :size="13" /></button></div>
      <form class="intent-composer" @submit.prevent="send()">
        <div class="conversation-context"><Icon name="leaf" :size="15" /><strong>DeerMind</strong><span>{{ lesson.chapter }} · 第 {{ progress.index + 1 }} 段</span><small>{{ progress.ended ? '已结束，可回看' : '随时追问' }}</small></div>
        <label for="lesson-input" class="sr-only">对 DeerMind 说</label><textarea id="lesson-input" ref="input" v-model="draft" :disabled="progress.ended" rows="2" :placeholder="progress.ended ? '本次已结束，内容与草稿已保留。' : '这一步哪里不明白？直接说说…'" @keydown="keydown" />
        <div class="composer-toolbar"><button type="button" class="composer-tool" :aria-expanded="history" :aria-label="history ? '隐藏对话历史' : '展开对话历史'" @click="history = !history; examples = false"><Icon name="clock" :size="16" />对话历史</button><button v-if="!progress.ended" type="button" class="composer-tool" :aria-expanded="examples" @click="examples = !examples; history = false"><Icon name="plus" :size="16" />情景示例</button><span class="composer-key-hint">Enter 发送 · Shift + Enter 换行</span><button class="round-button" type="submit" :disabled="progress.ended || !draft.trim()" aria-label="发送对话"><Icon name="arrow" :size="18" /></button></div>
      </form>
    </section>
  </div>
</template>
