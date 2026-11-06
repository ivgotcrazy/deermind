<script setup lang="ts">
import { computed, ref } from 'vue';
import { copyTeaching, teachingMock } from '../model/teaching-mock';

type Phase = 'question' | 'explanation' | 'testing' | 'test-ended' | 'hint' | 'finished';
type Event = { who: string; text: string };
const initialQuestion = '原来有 80 本书，增加四分之一。我知道多了 20 本，为什么也能乘 1.25？';
const phase = ref<Phase>('question');
const model = ref(snapshot());
const events = ref<Event[]>([{ who: '学生', text: initialQuestion }]);
const answer = ref('');
function snapshot() {
  const stage = teachingMock.blueprint.stages.find(s => s.id === 'teach');
  const recommendations = teachingMock.strategies.filter(s => s.enabled && stage?.strategies.includes(s.id));
  return {
    version: teachingMock.revision,
    blueprint: copyTeaching(teachingMock.blueprint),
    recommendations: recommendations.map(s => s.name),
  };
}
function connected(from: string, to: string) {
  return model.value.blueprint.transitions.some(edge => edge.from === from && edge.to === to);
}
const canExplain = computed(() => connected('start','focus') && connected('focus','entry') && connected('entry','teach'));
const reason = computed(() => {
  switch (phase.value) {
    case 'question': return canExplain.value ? '已知增加量，疑问是两种算法为何相等。本例没有命中推荐策略，可以在讲解阶段回应。' : '当前蓝图缺少从开始进入讲解的路径。';
    case 'explanation': return connected('teach','check') ? '本例已准备一题未展示过解法的新题。学生同意后，可从讲解直接进入检测。' : '当前蓝图没有从讲解直接进入检测的连接。';
    case 'testing': return '独立检测进行中。可以提交或求助，提示与参考解法尚不可展示。';
    case 'test-ended': return connected('check','teach') ? '检测已结束。现在可以返回讲解并展示提示。' : '检测已结束。当前蓝图没有返回讲解的连接，暂停提示。';
    case 'hint': return '提示属于检测后的帮助。后续作答不能记作刚才的独立表现。';
    case 'finished': return '已收束。走查记录只描述这次模拟活动。';
  }
});
function log(who: string, text: string) { events.value.push({ who, text }); }
function explain() {
  if (phase.value !== 'question' || !canExplain.value) return;
  log('DeerMind','你想到的加法是 80＋80×1/4。把同一个 80 提出来，就得到 80×(1＋1/4)。这里的 1 表示原来的整份 80 本，加上的 1/4 是这份原量的四分之一。');
  phase.value = 'explanation';
}
function startTest() {
  if (phase.value !== 'explanation' || !connected('teach','check')) return;
  log('学生','我想自己试一道新题。');
  log('独立检测','图书角原有 120 本书，又增加原来数量的四分之一。现在有多少本？请说明四分之一指哪个量。');
  phase.value = 'testing';
}
function endTest(help: boolean) {
  if (phase.value !== 'testing' || (!help && !answer.value.trim())) return;
  if (help) {
    log('学生','我想要一个提示。');
    if (answer.value.trim()) log('未提交草稿',answer.value);
    log('系统','本次独立检测因求助结束，本题未提交。');
    phase.value = 'test-ended';
  } else {
    log('学生提交',answer.value);
    log('系统','本次独立检测已提交并结束。参考结果是 150 本，解释要指出四分之一以原来的 120 本为基准。');
    phase.value = 'finished';
  }
}
function showHint() {
  if (phase.value !== 'test-ended' || !connected('check','teach')) return;
  log('检测后提示','先找出作为整体的 120 本。四分之一表示新添了原来的几份？求现在的数量时，还需要加上哪一部分？');
  phase.value = 'hint';
}
function finish() {
  if (phase.value === 'testing') {
    if (answer.value.trim()) log('未提交草稿', answer.value);
    log('系统','学生结束学习，本次检测结束，本题未提交。');
  } else log('系统','学生结束本次学习。');
  phase.value = 'finished';
}
function restart() {
  model.value = snapshot();
  events.value = [{ who: '学生', text: initialQuestion }];
  phase.value = 'question';
  answer.value = '';
}
</script>

<template>
  <section class="panel">
    <div class="row-between"><div><h3>一个量增加四分之一</h3><p class="muted">模拟对话 · 本次采用教学蓝图 v{{model.version}}</p></div><button class="btn" @click="restart">重新走查</button></div>
    <ol class="quarter-events" aria-label="走查记录" aria-live="polite">
      <li v-for="(event,index) in events" :key="index"><strong>{{event.who}}</strong><p>{{event.text}}</p></li>
    </ol>
    <details v-if="phase==='question'||phase==='explanation'"><summary>本阶段推荐的策略（{{model.recommendations.length}}）</summary>
      <p>{{model.recommendations.join('、') || '当前没有启用的推荐策略。'}}</p>
    </details>
    <p class="callout" role="status">{{reason}}</p>
    <label v-if="phase==='testing'">独立作答<textarea v-model="answer" rows="2"/></label>
    <div class="button-row">
      <button v-if="phase==='question'" class="btn primary" :disabled="!canExplain" @click="explain">继续讲解</button>
      <button v-if="phase==='explanation'" class="btn primary" :disabled="!connected('teach','check')" @click="startTest">同意并开始独立检测</button>
      <template v-if="phase==='testing'"><button class="btn primary" :disabled="!answer.trim()" @click="endTest(false)">提交作答</button><button class="btn" @click="endTest(true)">请求提示</button></template>
      <button v-if="phase==='test-ended'" class="btn primary" :disabled="!connected('check','teach')" @click="showHint">展示检测后提示</button>
      <button v-if="phase!=='finished'" class="btn" @click="finish">结束本次学习</button>
    </div>
  </section>
</template>

<style scoped>
.quarter-events{list-style:none;padding:0;margin:20px 0}
.quarter-events li{border-left:3px solid #c7dbce;padding:6px 14px;margin:12px 0}
.quarter-events p{margin:3px 0}
</style>
