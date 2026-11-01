<script setup lang="ts">
import { computed } from 'vue';
import type { FlowState, Lesson } from './learning-flow';
import { fractionAssessment, correctionFor } from './fraction-assessment';
const props=defineProps<{state:FlowState;lesson:Lesson;admin?:boolean}>();
const rows=computed(()=>fractionAssessment(props.state,props.lesson));
const claim=computed(()=>props.lesson.snapshot.claims.find(c=>c.taskId==='fraction'));
const requirements=computed(()=>props.lesson.snapshot.target.claims.find(c=>c.claimId===claim.value?.id)?.requirements.filter(r=>r.chapterIds.includes(props.lesson.chapterId))||[]);
const corrected=computed(()=>props.state.uses.filter(u=>u.activityId===props.lesson.id&&correctionFor(props.state,u)));
</script>
<template><section class="fraction-assessment">
  <h3>{{admin?'证据、能力判断与目标结果':'这次表现说明什么'}}</h3>
  <p class="scope">本次范围：已知原量，增加四分之一后求总量 · 评价样例（mock）</p>
  <p v-if="corrected.length" class="correction" role="status">{{corrected.length}} 条题目使用记录的依据已作废，已从本次有效评价中排除。原作答和原判定仍可追溯；这次变化是纠错，不是能力退步。</p>
  <article v-for="r in rows" :key="r.id" :data-aspect="r.id">
    <div class="row-title"><strong>{{r.name}}</strong><span :class="{weak:r.status==='需加强'}">{{r.status==='需加强'?'本次发现不足':'仍需确认'}}</span></div>
    <p>{{r.belief}}</p>
    <details><summary>查看要求、依据与变化</summary>
      <p><b>评价要求：</b>{{claim?.aspects.find(p=>p.id===r.id)?.criterion}}</p>
      <p><b>本次判断：</b>{{r.reason}}</p>
      <p><b>变化：</b>本演示起点没有个人依据 → {{r.belief}} 未涉及的方面不新增结论。</p>
      <div v-for="u in r.uses" :key="u.id" class="evidence"><p><b>题目：</b>{{u.question.question}}</p><p><b>原作答：</b>{{u.answer}}（{{u.result}}）</p><p><b>实际帮助：</b>{{u.help}}</p><small v-if="admin">{{u.question.id}} · v{{u.question.version}}；使用 {{u.id}}。同一次作答仍是一份来源，不按方面重复计样本。</small></div>
      <p v-if="!r.uses.length">当前没有可引用的有效检测作答。</p>
      <p v-for="req in requirements.filter(q=>q.aspectIds.includes(r.id))" :key="req.id"><b>目标要求：</b>{{req.name}}。{{req.standard}} <b>本例结果：{{r.status}}</b>；这是对所采用要求的核对，不是四维平均掌握率。</p>
    </details>
  </article>
  <p class="scope">预设作答只用于审阅判断逻辑；自由输入不自动获得这些结论。真实语义判断及跨活动 Belief 更新留到工程实现。</p>
</section></template>
<style scoped>
.fraction-assessment{color:#2c3e50;margin:20px 0}h3{font-size:17px}p{line-height:1.8;font-size:14px}.scope,small{font-size:12px;color:#72837a}article{border-top:1px solid #e0e9e3;padding:16px 0}.row-title{display:flex;justify-content:space-between;gap:12px}.row-title span{font-size:12px;background:#f0f2f1;padding:4px 8px;border-radius:4px;white-space:nowrap}.row-title .weak{background:#fff0d9;color:#80550e}summary{cursor:pointer;color:#2d6a4f;font-size:13px}.evidence{border-left:3px solid #c3d8cb;padding-left:12px;margin:12px 0}.correction{padding:12px;background:#fff7e6}
</style>
