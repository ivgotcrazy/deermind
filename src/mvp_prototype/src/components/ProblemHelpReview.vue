<script setup lang="ts">
import { computed, ref, watch, nextTick, onUnmounted } from 'vue';
import { fixture, flows, type HelpRequest } from '../foundationState';
import InputCaptureReview from './InputCaptureReview.vue';
import { hub, currentContext } from '../hubState';
import type { Capture } from '../captureState';
const props=defineProps<{recordsOnly?:boolean}>();
const activeId=ref<number|null>(null);
const wrongOnly=ref(false);
const message=ref('');
const current=computed(()=>flows.requests.find(r=>r.id===activeId.value&&!r.hidden&&(r.spaceId||'demo')===hub.current));
const visible=computed(()=>flows.requests.filter(r=>!r.hidden&&(r.spaceId||'demo')===hub.current));
let alive=true;onUnmounted(()=>{alive=false;});
watch(()=>[current.value?.id,current.value?.expanded],async()=>{const id=current.value?.id;await nextTick();if(!alive||current.value?.id!==id)return;const r=current.value;if(r?.sample)r.helpShown=r.mode==='hint'&&!r.expanded?'hint':'explain';},{immediate:true});
function useCapture(input:Capture){Object.assign(flows.problemDraft,{prompt:input.prompt,answer:input.answer,sample:false,input});message.value='已放入求助草稿，核对后仍需点击提交。';}
function loadSample(){delete flows.problemDraft.input;Object.assign(flows.problemDraft,{prompt:fixture.problem.prompt,answer:'',sample:true});message.value='已载入合成题；可不填作答，直接选择提示或讲解。';}
function submit(){
  if(!flows.problemDraft.prompt.trim())return;
  const r:HelpRequest={id:Math.max(Date.now(),...flows.requests.map(r=>r.id+1)),spaceId:hub.current,spaceName:currentContext.value.name,prompt:flows.problemDraft.prompt.trim(),answer:flows.problemDraft.answer.trim(),mode:flows.problemDraft.mode,sample:flows.problemDraft.sample,expanded:false,hidden:false,input:flows.problemDraft.input?JSON.parse(JSON.stringify(flows.problemDraft.input)):undefined};
  flows.requests.push(r);activeId.value=r.id;message.value='';
  delete flows.problemDraft.input;Object.assign(flows.problemDraft,{prompt:'',answer:'',mode:'explain',sample:false});
}
function remove(r:HelpRequest){if(window.confirm('从学生端删除这条原始资料及其求助内容？本端不可恢复，内部仍保留记录；关联家长仍可只读查看相关依据。')){r.hidden=true;activeId.value=null;message.value='学生端已删除；不改变已有学习判断。';}}
</script>
<template>
<main class="f-flow-page">
  <span class="f-eyebrow">{{ currentContext.name }} · 合成走查</span>
  <h1>{{ props.recordsOnly?'题目与作答':'把卡住的地方带过来' }}</h1>
  <p class="f-lead">{{ props.recordsOnly?'保留每次请求和帮助背景，没作答的题也有自己的位置。':'不会做、做错了，或者只是有一点拿不准，都可以问。' }}</p>
  <div class="f-flow-columns">
    <section v-if="!props.recordsOnly&&!current" class="f-card">
      <div class="f-content-heading"><h2>这次想弄清什么？</h2><button class="f-secondary" @click="loadSample">载入合成题</button></div>
      <label class="f-field">题目<textarea v-model="flows.problemDraft.prompt" aria-label="求助题目" placeholder="输入题目，或从下方材料入口整理后提交。" @input="flows.problemDraft.sample=false"/></label>
      <label class="f-field">我的尝试 <span class="f-muted">可留空</span><textarea v-model="flows.problemDraft.answer" aria-label="已有作答" placeholder="可以写下自己的做法或卡住的地方。"/></label>
      <InputCaptureReview @use="useCapture"/><p v-if="flows.problemDraft.input" class="f-tag">已附 {{ {images:'两张同题图片示例',pdf:'两页同题 PDF 示例',ink:'原笔迹',voice:'语音转写示例'}[flows.problemDraft.input.kind] }} · 原始内容与发送文本分别保留</p>
      <fieldset class="f-options"><legend>希望怎样帮助？</legend><label><input type="radio" v-model="flows.problemDraft.mode" value="explain"/> 给我讲解</label><label><input type="radio" v-model="flows.problemDraft.mode" value="hint"/> 只给提示</label></fieldset>
      <button class="f-primary" :disabled="!flows.problemDraft.prompt.trim()" @click="submit">提交求助</button>
      <p class="f-muted f-spaced">自由输入只保存，不作语义判断。合成题使用预写帮助；任何作答都不会在这里被自动判对错。</p>
    </section>
    <section v-else-if="current" class="f-card">
      <button class="f-back" @click="activeId=null">← {{ props.recordsOnly?'返回记录':'另提一个问题' }}</button>
      <span class="f-tag">{{ current.answer?'作答尚未判定':'未作答' }}</span><h2>{{ current.prompt }}</h2>
      <p v-if="current.answer"><b>提交时的尝试：</b>{{ current.answer }}</p>
      <p class="f-muted">当时请求：{{ current.mode==='hint'?'只给提示':'讲解' }} · 外部输入 · 未作语义判断</p>
      <div v-if="current.sample" class="f-followup">
        <h3>{{ current.mode==='hint'&&!current.expanded?'先给一个提示':'一步一步看' }} <small>· 预写示例</small></h3>
        <template v-if="current.mode==='hint'&&!current.expanded"><p>{{ fixture.problem.hint }}</p><button class="f-secondary f-spaced" @click="current.expanded=true">现在给我完整讲解</button></template>
        <ol v-else><li v-for="line in fixture.problem.explanation" :key="line">{{ line }}</li></ol>
      </div>
      <p v-else class="f-notice">已保存请求。原型尚未连接模型，未生成提示、讲解或学习判断。</p>
      <details v-if="current.input"><summary>查看输入来源与核对前后</summary><p>{{ current.input.provenance }}</p><p v-for="(raw,i) in current.input.originals" :key="i">原始材料 {{ i+1 }}：{{ raw }}</p><p v-if="current.input.transcript">预写识别／转写：{{ current.input.transcript }}</p><p>核对后的草稿：{{ current.input.prompt }}</p><p>正式发送：{{ current.prompt }}</p><svg v-if="current.input.kind==='ink'" viewBox="0 0 600 200" class="f-ink" aria-label="已提交原笔迹"><path v-for="(stroke,i) in current.input.strokes" :key="i" :d="stroke.map((p,j)=>`${j?'L':'M'} ${p[0]} ${p[1]}`).join(' ')" fill="none" stroke="#285a48" stroke-width="3"/></svg></details>
      <p class="f-muted f-spaced">没有作答不表示做错；得到帮助不表示已经掌握。后续正式评价须保留本次帮助背景。</p>
      <button class="f-text-button" @click="remove(current)">删除这条原始资料</button>
    </section>
    <aside class="f-card">
      <h2>本轮求助记录</h2><label class="f-checkbox"><input type="checkbox" v-model="wrongOnly"/> 只看确认错题</label>
      <p v-if="wrongOnly" class="f-empty">暂无确认错题。这里的未作答与尚未判定记录不会自动归入错题。</p>
      <template v-else><p v-if="!visible.length" class="f-empty">还没有提交的问题。未发送草稿不会出现在这里。</p><button v-for="r in visible" :key="r.id" class="f-record-link" @click="activeId=r.id"><span class="f-tag">{{ r.answer?'尚未判定':'未作答' }}</span><strong>{{ r.prompt }}</strong><small>{{ r.mode==='hint'?'请求提示':'请求讲解' }}{{ r.expanded?' → 后来查看完整讲解':'' }}</small></button></template>
    </aside>
  </div>
  <p v-if="message" class="f-notice" role="status">{{ message }}</p>
</main>
</template>
