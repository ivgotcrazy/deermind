<script setup lang="ts">
import { items, type Turn, type LessonCard } from './quarter';
import { computed } from 'vue';
const props = defineProps<{turn:Turn; latest:boolean}>();
const visual = computed(()=>props.turn.exampleItem===undefined ? {base:80,unit:'本'} : items[props.turn.exampleItem]);
const emit = defineEmits<{action:[card:LessonCard, request:string]; finishCheck:[status:'submitted'|'help'|'stopped']; draft:[field:'answer'|'reason',value:string]}>();
function edit(field:'answer'|'reason', event:Event) {
  emit('draft',field,(event.target as HTMLInputElement).value);
}
function resultMatches() {
  const c=props.turn.check!;
  const item=items[c.item];
  return [String(item.total),item.total+item.unit].includes(c.answer.trim().replace(/\s+/g,''));
}
</script>
<template>
  <div v-if="turn.card==='example' || turn.card==='diagram' || turn.card==='formula'" class="lesson-visual">
    <template v-if="turn.card==='example'">
      <strong>图书角原有 80 本书</strong>
      <p>新增的是原来的 <b>¼</b>，也就是 <b>20 本</b>。</p>
      <div class="equation">80 + 20 = <b>100 本</b></div>
    </template>
    <template v-if="turn.card==='diagram'">
      <figure><figcaption>每格 {{visual.base/4}} {{visual.unit}}</figcaption><div class="fraction-strip" aria-label="原来四格，新增一格"><span v-for="n in 4" :key="n">{{visual.base/4}}</span><b>+{{visual.base/4}}</b></div><small>原来 4 份，再添 1 份，一共 5 份。</small></figure>
    </template>
    <template v-if="turn.card==='formula'">
      <div class="equation">{{visual.base}} × <b>1</b> + {{visual.base}} × <b>¼</b><br>= {{visual.base}} × <b>(1 + ¼)</b></div><p>这里的 <b>1</b> 指原有的全部，<b>¼</b> 指增加的那部分。</p>
    </template>
  </div>
  <div v-if="latest && ['example','diagram','formula'].includes(turn.card || '')" class="lesson-actions">
    <button v-if="turn.card!=='diagram'" @click="emit('action','diagram','没懂，画给我看')">没懂，画给我看</button>
    <button v-if="turn.card!=='formula'" @click="emit('action','formula','为什么能写成乘法？')">为什么能写成乘法？</button>
    <button @click="emit('action','offer','我想测一下')">我想测一下</button>
    <button @click="emit('action','finish','先到这里')">先到这里</button>
  </div>
  <div v-if="turn.card==='offer' && latest" class="lesson-actions"><button class="primary" @click="emit('action','check','开始检测')">开始检测</button><button @click="emit('action','finish','今天先到这里')">先到这里</button></div>
  <section v-if="turn.check" class="test-card">
    <header><strong>自己试一题</strong><small>{{turn.check.status==='answering'?'作答中':'本次检测已结束'}}</small></header>
    <p>{{items[turn.check.item].text}}</p>
    <template v-if="turn.check.status==='answering'">
      <label>我的答案（{{items[turn.check.item].unit}}）<input :value="turn.check.answer" @input="edit('answer',$event)"></label>
      <label>我是怎么想的？<textarea rows="2" placeholder="四分之一指哪个量？" :value="turn.check.reason" @input="edit('reason',$event)"></textarea></label>
      <div class="lesson-actions"><button class="primary" :disabled="!turn.check.answer.trim()" @click="emit('finishCheck','submitted')">提交作答</button><button @click="emit('finishCheck','help')">结束检测并求助</button><button @click="emit('finishCheck','stopped')">先到这里</button></div>
    </template>
    <template v-else>
      <p><b>{{turn.check.status==='submitted'?'我的作答':'未提交的草稿'}}</b><br>{{turn.check.answer || '未填写'}}<template v-if="turn.check.reason"><br>{{turn.check.reason}}</template></p>
      <div v-if="turn.check.status==='submitted'" class="response-note"><strong>本题反馈</strong><p>{{resultMatches()?'结果正确。':'可以对照参考算式再看看。'}} {{items[turn.check.item].steps}}</p><p>{{turn.check.reason?'你写下了理由。可对照：四分之一指原来的数量，新增部分要加回原量。':'这次只看到了结果。你愿意说说四分之一指哪个量吗？'}}</p></div>
      <div v-if="turn.check.status==='help'" class="response-note"><strong>提示</strong><p>先找原来的量，把它平均分成四份。新增的是其中一份，题目问的是增加以后的总量。</p></div>
      <div v-if="latest && turn.check.status!=='stopped'" class="lesson-actions"><button @click="emit('action','diagram','用图再讲一次')">用图再讲一次</button><button @click="emit('action','finish','先到这里')">先到这里</button></div>
    </template>
  </section>
</template>
