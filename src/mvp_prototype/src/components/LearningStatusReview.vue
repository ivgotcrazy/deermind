<script setup lang="ts">
import { computed, ref } from 'vue';
import ParentConsultationReview from './ParentConsultationReview.vue';
import { parentState } from '../parentState';
import { recordsReview, type LearningRecord } from '../recordState';
import { journey } from '../journeyState';
import { fixture } from '../foundationState';
const props=defineProps<{parent?:boolean;spaceId?:string;records?:LearningRecord[]}>();
const emit=defineEmits<{lesson:[];help:[]}>();
const courseLocal=ref('school');
const course=computed({get:()=>props.parent?(parentState.spaces[parentState.actor]||'school'):courseLocal.value,set:(v:string)=>{if(props.parent)parentState.spaces[parentState.actor]=v;else courseLocal.value=v;}});
const selectedCourse=computed(()=>journey.courses.find(c=>c.id===(props.parent?course.value:props.spaceId)));
const visibleSpace=computed(()=>selectedCourse.value?.id||(course.value==='school'?'demo':'external'));
const actualRecords=computed(()=>(props.records||[]).filter(r=>r.spaceId===visibleSpace.value));
const spaceName=computed(()=>selectedCourse.value?.name||(course.value==='school'?'章节／求助演示空间':'校外内容待准备'));const range=ref('7');const condition=ref('ready');const expanded=ref(false);
const selected=ref('');const contextInput=ref('');const histories=ref<string[]>([]);const showHistory=ref(false);const notice=ref('');
const names:Record<string,string>={met:'已达标',strengthen:'需加强',unknown:'待确认'};
const detail=computed(()=>fixture.requirements.find(r=>r.id===selected.value));
const counts=computed(()=>fixture.requirements.reduce((acc,r)=>{acc[r.status]=(acc[r.status]||0)+1;return acc;},{} as Record<string,number>));
const start=computed(()=>range.value==='all'?'':new Date(Date.parse(fixture.as_of+'T00:00:00Z')-(Number(range.value)-1)*86400000).toISOString().slice(0,10));
const attempts=computed(()=>fixture.attempts.filter(a=>range.value==='all'||(a.date!==null&&a.date>=start.value&&a.date<=fixture.as_of)));
const included=computed(()=>attempts.value.filter(a=>a.ended&&a.help==='independent'&&['correct','incorrect'].includes(a.judgment)));
const correct=computed(()=>included.value.filter(a=>a.judgment==='correct').length);
function reason(a:typeof fixture.attempts[number]){if(!a.ended)return '未结束，暂不计入';if(a.help==='assisted')return '受助作答，另列';if(a.help==='unknown')return '帮助条件不明';if(a.judgment==='pending')return '判断未决';return a.judgment==='correct'?'独立 · 正确':'独立 · 错误';}
function send(){if(!contextInput.value.trim())return;histories.value.push(contextInput.value.trim());contextInput.value='';notice.value='输入已暂存在本页；尚未连接模型，没有生成解释或执行行动。';}
function courseChange(){selected.value='';expanded.value=false;contextInput.value='';histories.value=[];notice.value='';}
</script>
<template>
<div class="f-flow-layout">
<main class="f-flow-page">
  <div class="f-content-heading f-status-heading"><div><span class="f-eyebrow">{{ props.parent?'家长查看 · 同源结果':'按教材章节查看' }}</span><h1>学习情况</h1></div><label v-if="props.parent||!selectedCourse" class="f-field">查看空间<select v-model="course" aria-label="查看课程空间" @change="courseChange"><option value="school">校内 · 合成课程</option><option value="external">校外 · 内容待准备</option><template v-if="props.parent"><option v-for="c in journey.courses" :key="c.id" :value="c.id">{{ c.name }} · {{ c.id.slice(0,6) }}</option></template></select></label></div>
  <details v-if="!selectedCourse" class="f-provenance"><summary>合成数据 · 非真实学习结果</summary><p>固定截至 {{ fixture.as_of }}，时区 {{ fixture.timezone }}。状态与作答均为预写样例，独立于刚才的原型操作；不是孩子的真实评价，也不是北师大版的正式章节。</p></details>
  <section v-if="selectedCourse" class="f-card"><h2>当前空间还没有正式评价</h2><p>{{ selectedCourse.name }} · 教材与目标 v{{ selectedCourse.version }}。本轮输入与作答尚未运行评价，不借用合成状态样例填充。</p><p>没有结论不等于没有掌握，也不显示为零分。</p></section>
  <section v-else-if="course==='external'" class="f-card"><h2>校外内容还没有准备好</h2><p>实际内部教材待提供，尚无章节、目标和学习判断。不会借用校内结果填充，也不显示为全部不会。</p></section>
  <template v-else>
    <details class="f-demo-controls"><summary>走查异常状态</summary><label>读取状态 <select v-model="condition" aria-label="评价读取状态"><option value="ready">有效示例结果</option><option value="failed">服务读取失败</option><option value="stale">旧判断失效，等待重处理</option></select></label></details>
    <section v-if="condition!=='ready'" class="f-card" role="status"><h2>{{ condition==='failed'?'学习情况暂时无法读取':'相关判断正在更新' }}</h2><p>这是系统处理状态，不能写成孩子未达标或待确认。旧项数暂不展示。</p><button class="f-secondary" @click="condition='ready'">恢复有效示例</button></section>
    <section v-else class="f-card f-chapter-summary">
      <div class="f-content-heading"><div><span class="f-eyebrow">合成教材 · 示例章</span><h2>{{ fixture.chapter }}</h2></div><button class="f-secondary" @click="expanded=!expanded" :aria-expanded="expanded">{{ expanded?'收起具体要求':'展开具体要求' }}</button></div>
      <div class="f-status-numbers" aria-label="当前学习要求项数"><div v-for="(label,key) in names" :key="key"><strong>{{ counts[key]||0 }}<small> 项</small></strong><span>{{ label }}</span></div></div>
      <p class="f-muted">共 {{ fixture.requirements.length }} 项要求 · 当前有效结果更新至 {{ fixture.as_of }}。项数不表示掌握百分比。</p>
      <div v-if="expanded" class="f-requirements"><button v-for="r in fixture.requirements" :key="r.id" class="f-requirement" @click="selected=selected===r.id?'':r.id" :aria-expanded="selected===r.id"><span>{{ r.label }}</span><b :class="'f-state-'+r.status">{{ names[r.status] }} →</b></button></div>
      <article v-if="expanded&&detail" class="f-evidence"><h3>{{ detail.label }}</h3><p>{{ detail.reason }}</p><details v-for="a in fixture.attempts.filter(a=>detail?.records.includes(a.id))" :key="a.id"><summary>{{ a.date||'原作答日期未知' }} · {{ a.source }} · {{ reason(a) }}</summary><p>{{ a.prompt }}</p><p><b>作答：</b>{{ a.answer }}</p><p class="f-muted">{{ a.context }}</p></details><div v-if="!props.parent" class="f-actions"><button class="f-secondary" @click="emit('lesson')">进入相关章节讲解</button><button @click="emit('help')">带一个问题来求助</button></div><p v-else class="f-muted">家长可以查看依据、咨询支持方式，不修改学生资料或代替孩子发起学习。</p></article>
    </section>
    <section class="f-card">
      <div class="f-content-heading"><div><h2>近期作答</h2><p class="f-muted">日期只筛选这组记录，不改变上方当前学习状态。</p></div><label class="f-field">时间范围<select v-model="range" aria-label="作答统计时间范围"><option value="7">近 7 天</option><option value="30">近 30 天</option><option value="all">全部</option></select></label></div>
      <p>{{ range==='all'?'全部记录，未知日期单独标注':start+' 至 '+fixture.as_of+'（包含当天）' }}</p>
      <p class="f-stat-result" data-testid="answer-stat">{{ included.length?`已判定独立作答 ${included.length} 次，正确 ${correct} 次 · ${Math.round(correct/included.length*100)}%`:'暂无可统计的独立作答' }}</p>
      <p class="f-muted">{{ attempts.length-included.length }} 次另列；这不是整章掌握率。日期未知的外部作答仅在“全部”中出现。</p>
      <details><summary>核对计入与排除的记录</summary><div v-for="a in attempts" :key="a.id" class="f-record-row"><b>{{ a.id }} · {{ a.date||'原作答日期未知' }}</b><span>{{ a.source }} · {{ reason(a) }}</span><p>{{ a.context }}</p></div></details>
    </section>

  </template>
  <section v-if="props.parent" class="f-card"><h2>这个空间的实际学习记录</h2><p class="f-muted">来自本浏览器实际操作，尚未运行正式评价；与上方预写样例分开。家长只读，学生已删除的资料按现行规则仍可查看相关依据。</p><p v-if="!actualRecords.length">当前空间还没有可查看的实际记录。</p><details v-for="r in actualRecords" :key="r.id" class="f-parent-record"><summary>{{ r.hidden?'查看本轮求助原资料':r.prompt }}</summary><p v-if="r.hidden">{{ r.prompt }}</p><p>{{ {external:'外部录入',lesson:'讲解练习',test:'检测'}[r.source] }} · {{ r.hidden?'学生端已删除 · 家长只读':'家长只读' }} · {{ r.status==='unanswered'?'未作答':'尚未判定' }}</p><p><b>原提交：</b>{{ r.answer||'未提供作答' }}</p><p>{{ r.help }}</p><p class="f-muted">{{ r.version }} · {{ r.provenance }}</p><div v-for="n in recordsReview.notes[r.id]||[]" :key="n.at"><b>{{ n.kind==='retry'?'后来的订正尝试':'资料更正说明' }}</b><p>{{ n.text }}</p><p>{{ n.reason }}</p></div><div v-for="c in r.checks||[]" :key="c.id"><b>提交前的输入核对</b><p>{{ c.original }} → {{ c.corrected }}</p><p>{{ c.reason }}；保留学生声明，未自动认证独立性。</p></div></details></section>
</main>
  <ParentConsultationReview v-if="props.parent" :key="parentState.actor+visibleSpace" :space="visibleSpace" :name="spaceName"/>
  <section v-else class="f-inline-composer" aria-label="询问学习情况"><div class="f-content-heading"><label for="status-question">{{ props.parent?'咨询孩子的学习情况':'对学习情况有疑问，直接说说' }}</label><button @click="showHistory=!showHistory">{{ showHistory?'收起历史':'对话历史' }}</button></div><form @submit.prevent="send"><textarea id="status-question" v-model="contextInput" rows="2" placeholder="说说你的疑问…"/><button class="f-primary" :disabled="!contextInput.trim()" type="submit">发送</button></form><p v-if="notice" role="status">{{ notice }}</p><ul v-if="showHistory"><li v-for="(h,i) in histories" :key="i">{{ h }}</li></ul><p class="f-muted">原型输入仅暂存，离开后不保留。</p></section>
</div>
</template>
