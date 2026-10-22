<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { calculateHomeStatistics, referenceEvents, referenceProblems } from './homeStatistics';
const props=defineProps<{available:boolean;showReference:boolean}>();
const days=ref<7|30>(7);
const detail=ref<''|'days'|'lessons'|'checks'|'wrong'>('');
const ready=computed(()=>props.available&&props.showReference);
const stats=computed(()=>calculateHomeStatistics(referenceEvents,referenceProblems,days.value));
const title=computed(()=>({days:'学习日明细',lessons:'讲解活动明细',checks:'已结束检测明细',wrong:'当前错题明细'})[detail.value||'days']);
watch(()=>[props.available,props.showReference],()=>{detail.value='';});
let detailTrigger:HTMLElement|undefined;
function toggle(value:typeof detail.value,event:MouseEvent){detailTrigger=event.currentTarget as HTMLElement;detail.value=detail.value===value?'':value;}
async function closeDetail(){detail.value='';await nextTick();detailTrigger?.focus({preventScroll:true});detailTrigger?.scrollIntoView({block:'nearest'});}
</script>
<template>
 <section class="home-statistics" aria-label="学习活动统计">
  <div class="statistics-heading"><div><h2>学习足迹</h2><p>看看最近做了什么。</p></div><label>统计时段<select v-model.number="days" aria-label="活动统计时段"><option :value="7">近 7 天</option><option :value="30">近 30 天</option></select></label></div>
  <p class="statistics-source"><template v-if="ready"><span class="reference-badge">统计示例</span> {{ stats.from }} 至 {{ stats.through }} · 仅校内数学</template><template v-else>当前空间尚未接入可靠的活动统计，不用 0 代替未知。</template></p>
  <div class="statistics-layout">
   <div class="period-statistics" aria-label="所选时段的活动">
    <button class="statistic" :disabled="!ready" :aria-expanded="detail==='days'" aria-controls="home-statistic-detail" @click="toggle('days',$event)"><span>学习天数</span><strong>{{ ready?stats.studyDays.length:'—' }}<small v-if="ready">天</small></strong><small>{{ ready?'有实际学习活动的日期':'尚未统计' }}</small></button>
    <button class="statistic" :disabled="!ready" :aria-expanded="detail==='lessons'" aria-controls="home-statistic-detail" @click="toggle('lessons',$event)"><span>开展讲解</span><strong>{{ ready?stats.lessons.length:'—' }}<small v-if="ready">次</small></strong><small>{{ ready?'续学不重复计数':'尚未统计' }}</small></button>
    <button class="statistic" :disabled="!ready" :aria-expanded="detail==='checks'" aria-controls="home-statistic-detail" @click="toggle('checks',$event)"><span>已结束检测</span><strong>{{ ready?stats.checks.length:'—' }}<small v-if="ready">次</small></strong><small>{{ ready?'含部分作答后结束':'尚未统计' }}</small></button>
   </div>
   <button class="statistic wrong-inventory" :disabled="!ready" :aria-expanded="detail==='wrong'" aria-controls="home-statistic-detail" @click="toggle('wrong',$event)"><span>当前错题 <small>累计</small></span><strong>{{ ready?stats.wrongProblems.length:'—' }}<small v-if="ready">题</small></strong><small>{{ ready?'不同题目 · 不随时段切换':'尚未统计' }}</small></button>
  </div>
  <p class="statistics-footnote">活动次数不代表掌握程度；错题数也不是“还不会”的题数。<template v-if="ready">数字可展开核对。本轮对话未混入这些预写示例。</template></p>
  <section v-if="detail&&ready" id="home-statistic-detail" class="statistics-detail" :aria-label="title">
   <div class="section-title"><h3>{{ title }}</h3><button class="text" @click="closeDetail">收起明细</button></div>
   <template v-if="detail==='days'"><p>同一天的讲解、检测或作答合计为 1 天。仅登录、查看首页、写草稿不计入。</p><ul><li v-for="day in stats.studyDays" :key="day"><strong>{{ day }}</strong><span>{{ [...new Set(stats.learning.filter(e=>e.day===day).map(e=>e.title))].join('；') }}</span></li></ul></template>
   <template v-else-if="detail==='lessons'"><p>按第一次实际显示讲解内容的日期计数。同一活动跨天继续，仍只计 1 次。</p><ul><li v-for="item in stats.lessons" :key="item.activity"><strong>{{ item.day }}</strong><span>{{ item.title }}</span></li></ul><p class="muted small">“理解单位‘1’”于 10 月 8 日开始、12 日继续，所以不计入近 7 天的新讲解。另有 {{ stats.undated }} 条日期未知的参考事件未计入时段统计。</p></template>
   <template v-else-if="detail==='checks'"><p>检测已结束且至少提交过一次作答才计入。它不一定完成了所有题，也不意味着独立达标。</p><ul><li v-for="item in stats.checks" :key="item.activity"><strong>{{ item.day }}</strong><span>{{ item.title }} · 已提交 {{ item.submittedAnswers }} 次作答</span></li></ul></template>
   <template v-else><p>同一道题反复答错只计 1 题，订正后仍保留曾经出错的记录。未作答、识别待确认及隐藏资料不计入。</p><ul><li v-for="item in stats.wrongProblems" :key="item.id"><strong>{{ item.title }}</strong><span>{{ [...new Set(item.attempts.map(a=>a.source))].join('、') }} · {{ item.attempts.some(a=>a.outcome==='correct')?'已有一次订正答对，仍保留错误历史':'有确认错误的记录' }}</span></li></ul></template>
   <p class="muted small">以上为本组统计示例的对应资料，与“学习记录”中的规模演示资料分开。</p>
  </section>
 </section>
</template>
