<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Lesson, FlowState } from './learning-flow';
import { chainAssessment, type ChainAspect } from './fraction-chain';
const props=defineProps<{lesson:Lesson;state:FlowState;admin?:boolean}>();
const emit=defineEmits<{help:[]}>();
const assessment=computed(()=>chainAssessment(props.state,props.lesson));
const claim=computed(()=>props.lesson.snapshot.claims.find(c=>c.taskId==='fraction-chain'));
const requirements=computed(()=>props.lesson.snapshot.target.claims.find(c=>c.claimId===claim.value?.id)?.requirements.filter(r=>r.chapterIds.includes(props.lesson.chapterId))||[]);
const answers=computed(()=>props.state.uses.filter(u=>u.activityId===props.lesson.id&&u.purpose==='检测'));
const selected=ref('');
function requirement(row:ChainAspect){return requirements.value.find(r=>r.aspectIds.includes(row.id));}
</script>
<template><section class="chain-assessment">
  <h3>{{admin?'能力判断与目标达成':'这次学习说明什么'}}</h3>
  <p class="scope">{{admin?'Task Claim：'+claim?.name:'本次范围：连续两层部分关系'}} · 评价样例（mock）</p>
  <p>能说明文字中的参照量，与换成图后仍能解决，是两项不同要求。不把这次结果折算成整章掌握率。</p>
  <p v-if="!assessment.matched" class="notice">当前没有完整匹配的预设评价。自由作答、未完成或求助结束均保留记录，不套用样例结论。</p>
  <div class="counts" aria-label="本次学习要求统计"><span v-for="status in ['已达标','需加强','待确认']" :key="status">{{status}} {{assessment.rows.filter(r=>r.status===status).length}} 项</span></div>
  <article v-for="row in assessment.rows" :key="row.id" class="assessment-row" :data-aspect="row.id">
    <div class="row-title"><strong>{{requirement(row)?.name||row.name}}</strong><span :class="['state',row.status==='已达标'?'met':row.status==='需加强'?'strengthen':'pending']">{{row.status}}</span></div>
    <p>{{row.belief}}</p>
    <button class="link" :aria-expanded="selected===row.id" @click="selected=selected===row.id?'':row.id">{{selected===row.id?'收起依据':'查看标准与依据'}}</button>
    <div v-if="selected===row.id" class="basis">
      <p><strong>达标标准：</strong>{{requirement(row)?.standard||'尚未配置本项要求。'}}</p>
      <p><strong>{{admin?'Belief 示例及限制':'为什么这样判断'}}：</strong>{{row.reason}}</p>
      <div v-for="index in row.evidence" :key="index" class="evidence"><p><strong>检测第 {{index+1}} 题：</strong>{{answers[index]?.question.question}}</p><p><strong>原作答：</strong>{{answers[index]?.answer}}</p><p><strong>帮助背景：</strong>{{answers[index]?.help}}</p><p v-if="admin">题目 {{answers[index]?.question.id}} · v{{answers[index]?.question.version}}；本次使用 {{answers[index]?.id}}。这是一条预写的 Evidence 解释，不是真实推断。</p></div>
      <p v-if="!row.evidence.length">{{row.id==='retention'?'尚无延迟后的作答记录。':'本次没有足以支持这项要求的表现依据。'}}</p>
      <p><strong>下一步：</strong>{{row.next}}</p>
    </div>
  </article>
  <button v-if="!admin&&assessment.matched&&lesson.reviewCase==='mixed'" class="action" @click="emit('help')">讲讲图中的参照量</button>
  <p v-if="admin" class="scope">目标：{{lesson.snapshot.target.name}} · v{{lesson.snapshot.target.revision}}；采用方法：{{claim?.methodMode==='any'?'任选一种':'按定义覆盖'}}。达标是对本目标要求的结果，不是对整个 Task 的永久认证。</p>
</section></template>
<style scoped>
.chain-assessment{margin:20px 0;color:#2c3e50}h3{font-size:17px;margin:0 0 10px}p{line-height:1.8;font-size:14px}.scope{font-size:12px;color:#72837a}.counts{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0;font-size:14px}.assessment-row{border-top:1px solid #e0e9e3;padding:16px 0}.row-title{display:flex;align-items:start;justify-content:space-between;gap:12px}.state{font-size:12px;border-radius:4px;padding:4px 8px;white-space:nowrap}.met{background:#e9f4ed;color:#28644c}.strengthen{background:#fff0d9;color:#80550e}.pending{background:#f0f2f1;color:#64766b}.link{border:0;padding:0;background:none;color:#2d6a4f;cursor:pointer;font:inherit;font-size:13px}.basis{margin-top:12px;background:#f7faf8;padding:12px 16px}.evidence{border-left:3px solid #c3d8cb;padding-left:12px}.notice{background:#fff7e6;padding:10px}.action{border:1px solid #2d6a4f;border-radius:6px;background:white;color:#2d6a4f;padding:9px 15px;cursor:pointer}
</style>
