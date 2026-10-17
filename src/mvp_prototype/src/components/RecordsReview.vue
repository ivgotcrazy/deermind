<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { addNote, recordsReview, referenceRecords, type LearningRecord } from '../recordState';
import { contexts } from '../hubState';
import { flows } from '../foundationState';
const detail=ref<HTMLElement|null>(null);
const props=defineProps<{records:LearningRecord[];initialSpace?:string}>();
const dataset=ref('live'),space=ref(props.initialSpace||'demo'),source=ref('all'),wrong=ref(false),selected=ref(''),kind=ref<'transcription'|'retry'>('retry'),text=ref(''),reason=ref(''),notice=ref('');
const all=computed(()=>dataset.value==='live'?props.records.filter(r=>!r.hidden):referenceRecords());
const spaces=computed(()=>dataset.value==='live'?contexts.value:[{id:'reference',name:'预写状态展示空间'}]);
watch([dataset,spaces],()=>{if(!spaces.value.some(s=>s.id===space.value))space.value=dataset.value==='live'?(props.initialSpace||'demo'):'reference';},{immediate:true});
watch([space,source,dataset,wrong],()=>{selected.value='';notice.value='';});
const visible=computed(()=>all.value.filter(r=>r.spaceId===space.value&&(source.value==='all'||r.source===source.value)&&(!wrong.value||r.status==='incorrect')));
const current=computed(()=>visible.value.find(r=>r.id===selected.value));
const status={pending:'尚未判定',unanswered:'未作答',correct:'参考：已判对',incorrect:'参考：确认错误'};
const sources={external:'外部录入',lesson:'讲解练习',test:'检测'};
function choose(r:LearningRecord){selected.value=r.id;text.value='';reason.value='';kind.value='retry';notice.value='';nextTick(()=>detail.value?.scrollIntoView({block:'start'}));}
function save(){if(!current.value||current.value.synthetic||!text.value.trim()||!reason.value.trim())return;addNote(current.value.id,kind.value,text.value,reason.value);text.value='';reason.value='';notice.value=kind.value==='retry'?'已新增订正尝试，原表现保留；尚未判定。':'已记录资料更正，原件和原提交保留；不计为新一次答题，相关判断待复核。';}
function remove(){const r=current.value;if(!r||r.synthetic||r.source!=='external')return;if(!confirm('从学生端删除整份原始资料及关联输入、更正和求助记录？本端不可恢复；内部保留，关联家长可按权限只读。'))return;const target=flows.requests.find(x=>`help-${x.id}`===r.id);if(target)target.hidden=true;selected.value='';}
</script>
<template><main class="f-flow-page">
  <span class="f-eyebrow">题目、来源与每一次真实尝试</span><h1>回看做过什么，找出下一步</h1>
  <div class="f-actions"><label class="f-field">查看材料<select v-model="dataset" aria-label="记录数据来源"><option value="live">本轮实际操作</option><option value="reference">预写评价参考（单独展示）</option></select></label><label class="f-field">课程空间<select v-model="space" aria-label="记录所属空间"><option v-for="s in spaces" :key="s.id" :value="s.id">{{ s.name }}</option></select></label><label class="f-field">题目来源<select v-model="source" aria-label="题目来源筛选"><option value="all">本空间全部来源</option><option value="external">外部录入</option><option value="lesson">讲解练习</option><option value="test">检测</option></select></label></div>
  <label class="f-check-line"><input type="checkbox" v-model="wrong"/> 只看确认错题</label>
  <p class="f-provenance">{{ dataset==='live'?'本轮提交未运行真实评价，所以不会自动进入确认错题。打开旧题不新增作答，也不自动安排复测。':'预写参考只用于核对跨来源错题的表达；与本轮操作、真实掌握状态分开。' }}</p>
  <div class="f-flow-columns"><section class="f-card"><h2>本空间记录</h2><p v-if="!visible.length">当前筛选下没有记录。未作答、识别争议和尚未判定都不算确认错题。</p><button v-for="r in visible" :key="r.id" class="f-record-link" @click="choose(r)" :aria-pressed="current?.id===r.id"><span class="f-tag">{{ sources[r.source] }} · {{ status[r.status] }}</span><strong>{{ r.prompt }}</strong><small>{{ r.version }} · {{ r.id }}</small></button></section>
  <section v-if="current" ref="detail" class="f-card"><h2>{{ current.prompt }}</h2><p class="f-muted">{{ current.provenance }} · {{ current.id }}</p><h3>当时提交的内容</h3><p>{{ current.answer||'未提供作答；不代表做错。' }}</p><p>{{ current.help }}</p><details v-if="current.input"><summary>查看原材料与输入核对</summary><p>{{ current.input.provenance }}</p><p v-for="(raw,i) in current.input.originals" :key="i">原始 {{ i+1 }}：{{ raw }}</p><p>识别／转写：{{ current.input.transcript||'未运行' }}</p><p>核对后的文本：{{ current.input.prompt }}</p><svg v-if="current.input.strokes.length" viewBox="0 0 600 200" class="f-ink" aria-label="记录中的原笔迹"><path v-for="(stroke,i) in current.input.strokes" :key="i" :d="stroke.map((p,j)=>`${j?'L':'M'} ${p[0]} ${p[1]}`).join(' ')" fill="none" stroke="#285a48" stroke-width="3"/></svg></details>
    <section v-if="current.checks?.length"><h3>提交前的输入核对</h3><article v-for="c in current.checks" :key="c.id" class="f-answer"><p>{{ c.original }} → {{ c.corrected }}</p><p>{{ c.reason }}</p><p class="f-muted">保留学生说明；没有由原型认证独立性，也不新增一次作答。</p></article></section>
    <section v-if="recordsReview.notes[current.id]?.length"><h3>后来发生的变化</h3><article v-for="(n,i) in recordsReview.notes[current.id]" :key="i" class="f-answer"><b>{{ n.kind==='retry'?'新的订正尝试 · 尚未判定':'资料更正 · 不计新作答' }}</b><p>{{ n.text }}</p><p class="f-muted">{{ n.reason }} · {{ n.at }}</p></article></section>
    <template v-if="!current.synthetic"><h3>更正记录或重新尝试</h3><label class="f-field">这次要做什么<select v-model="kind" aria-label="更正或订正方式"><option value="retry">我重新作答，留下订正尝试</option><option v-if="current.source==='external'" value="transcription">原材料没变，是录入／识别内容需要更正</option></select></label><label class="f-field">{{ kind==='retry'?'新的作答':'应当记录的原内容' }}<textarea v-model="text" aria-label="新增记录内容"/></label><label class="f-field">说明<textarea v-model="reason" aria-label="新增记录说明" :placeholder="kind==='retry'?'说明这次是否看过提示或讲解。':'说明哪处录入不符；如题面也变更，请明确写出。'"/></label><button class="f-secondary" :disabled="!text.trim()||!reason.trim()" @click="save">保存这次记录</button><p>原始内容不被覆盖。这里没有重新评分或自动安排复测；完整的事实更正与依赖处理留给正式运行链。</p><button v-if="current.source==='external'" class="f-text-button" @click="remove">删除这份外部原资料</button></template>
  </section></div><p v-if="notice" role="status" class="f-notice">{{ notice }}</p>
</main></template>
