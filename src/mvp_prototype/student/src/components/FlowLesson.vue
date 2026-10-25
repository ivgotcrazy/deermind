<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { courseFlow as flow } from '../course-flow';
import { practice, offerTest, startTest, submitAnswer, endLesson, sendLessonMessage, lessonUses, lessonFeedback, changeFlow, type QuestionUse } from '../../../shared/learning-flow';
import ChatMessageComp from './ChatMessage.vue';
const props=defineProps<{activityId:string}>();
const emit=defineEmits<{status:[];showStatus:[]}>();
const lesson=computed(()=>flow.lessons.find(a=>a.id===props.activityId));
const uses=computed(()=>lesson.value?lessonUses(flow,lesson.value):[]);
const active=computed(()=>lesson.value?.stage==='practice'?uses.value.find(u=>u.id===lesson.value?.practiceId):lesson.value?.stage==='testing'?uses.value.filter(u=>u.purpose==='检测').slice(-1)[0]:undefined);
const answer=ref(''),outcome=ref<QuestionUse['result']>('正确'),error=ref(''),preparing=ref(false),bottom=ref<HTMLElement>();
const feedback=computed(()=>lesson.value?lessonFeedback(flow,lesson.value):null);
watch(()=>active.value?.id,()=>{answer.value=lesson.value?.draft||'';outcome.value='正确';},{immediate:true});
watch(answer,value=>{if(lesson.value&&lesson.value.draft!==value)changeFlow(s=>{s.lessons.find(a=>a.id===props.activityId)!.draft=value;});});
watch(()=>[lesson.value?.stage,lesson.value?.messages.length,active.value?.id],async()=>{await nextTick();bottom.value?.scrollIntoView({block:'nearest'});});
function run(fn:()=>void){try{error.value='';fn();}catch(e){error.value=(e as Error).message;}}
async function begin(){preparing.value=true;await new Promise(r=>setTimeout(r,350));run(()=>startTest(props.activityId));preparing.value=false;}
function submit(){run(()=>submitAnswer(props.activityId,answer.value,outcome.value));}
function send(text:string){run(()=>sendLessonMessage(props.activityId,text));}
function finish(){run(()=>endLesson(props.activityId));}
defineExpose({send,finish});
</script>
<template><div v-if="lesson" class="flow-lesson">
  <p class="mock-note">Mock 流程走查 · 题目与作答会保存，语义判定采用演示结果</p>
  <template v-for="m in lesson.messages.filter(m=>!m.useId||m.useId!==active?.id)" :key="m.id">
    <ChatMessageComp :message="{id:m.id,role:m.actor==='学生'?'user':'assistant',timestamp:0,blocks:[{type:'text',text:m.text}]}"/>
    <svg v-if="uses.find(u=>u.id===m.useId)?.question.figure==='length'" viewBox="0 0 400 100" role="img" :aria-label="`原长 ${uses.find(u=>u.id===m.useId)?.question.quantity} 米，增加原长的四分之一`"><rect x="20" y="25" width="280" height="30" fill="#bed8ca"/><rect x="300" y="25" width="70" height="30" fill="#efce8c"/><text x="80" y="80">原长 {{uses.find(u=>u.id===m.useId)?.question.quantity}} 米</text><text x="305" y="18">增加 1/4</text></svg>
  </template>
  <section v-if="active" class="question-card">
    <div class="question-title"><span>{{active.purpose==='检测'?`检测 · 第 ${lesson.current+1}/${lesson.testIds.length} 题`:'随堂练习'}}</span><small>答案提交后保留</small></div>
    <p class="prompt">{{active.question.question}}</p>
    <svg v-if="active.question.figure==='length'" viewBox="0 0 400 100" role="img" :aria-label="`原长 ${active.question.quantity} 米，增加原长的四分之一`"><rect x="20" y="25" width="280" height="30" fill="#bed8ca"/><rect x="300" y="25" width="70" height="30" fill="#efce8c"/><text x="80" y="80">原长 {{active.question.quantity}} 米</text><text x="305" y="18">增加 1/4</text></svg>
    <label>答案和思路<textarea v-model="answer" rows="3" placeholder="写下答案，也可以说明你的想法"/></label>
    <details class="mock-control"><summary>Mock 作答判定</summary><p>此处选择用于体验反馈的结果，不根据输入文字判断能力。</p><label>本次模拟结果<select aria-label="本次模拟结果" v-model="outcome"><option>正确</option><option>错误</option><option>待确认</option></select></label></details>
    <div class="actions"><button class="primary" :disabled="!answer.trim()" @click="submit">提交答案</button><button @click="run(()=>endLesson(lesson!.id,true))">{{lesson.stage==='testing'?'结束并求助':'求助'}}</button><button v-if="lesson.stage==='testing'" @click="finish">结束检测</button></div>
    <p v-if="lesson.stage==='testing'" class="note">逐题提交只确认收到，结束后一起查看结果。</p>
  </section>
  <p v-if="lesson.stage==='testing'&&lesson.current>0" role="status" class="note">前 {{lesson.current}} 题已提交。</p>
  <div v-if="lesson.stage==='explaining'" class="actions"><button class="primary" @click="run(()=>practice(lesson!.id))">做一道练习</button><button @click="run(()=>offerTest(lesson!.id))">准备检测</button><button @click="finish">结束本次学习</button></div>
  <section v-if="lesson.stage==='offer'" class="question-card"><h3>准备一次短检测</h3><p>检查“增加四分之一后的数量”：一道文字题，一道长度示意图。</p><p>共 2 题，约 3–5 分钟。题目会在开始后展示。</p><p class="note">保留刚才的讲解背景，不直接认定为独立掌握。</p><div class="actions"><button class="primary" :disabled="preparing" @click="begin">{{preparing?'正在准备题目…':'开始检测'}}</button><button :disabled="preparing" @click="finish">暂不开始</button></div></section>
  <section v-if="lesson.stage==='finished'&&feedback" class="question-card result-card"><h3>{{lesson.endReason==='求助后结束'?'本次已结束，转入讲解':'本次学习反馈'}}</h3><p v-if="feedback.total" class="result-count">{{feedback.summary}}</p><p v-else>已保留本次讲解与练习记录。本次没有完成检测，不显示检测得分。</p><p>这次只涉及增加四分之一。当前没有足够依据将整类任务或整章标为已掌握。</p>
    <details><summary>查看逐题记录与解释</summary><article v-for="u in uses" :key="u.id" class="past-question"><strong>{{u.purpose}} · {{u.question.question}}</strong><p>作答：{{u.answer||'未提交'}}{{u.result?' · '+u.result+'（mock）':''}}</p><p>{{u.help}}</p><p>{{u.question.explanation}}</p></article><p v-if="feedback.total>uses.filter(u=>u.purpose==='检测').length">剩余题目未展示、未检测。</p></details>
    <details><summary>这次表现说明什么</summary><p v-for="a in feedback.aspects" :key="a[0]"><strong>{{a[0]}}：</strong>{{a[1]}}</p></details>
    <div class="actions"><button class="primary" @click="emit('showStatus')">查看学习情况</button><button @click="run(()=>send('我想继续理解刚才的问题。'))">继续追问</button></div>
  </section>
  <p v-if="error" role="alert" class="error">{{error}}</p><div ref="bottom"/>
</div><p v-else>请从教材章节开始学习。</p></template>
<style scoped>
.mock-note{font-size:12px;color:#788980;margin:4px 0 20px}.question-card{border:1px solid #dbe6df;border-radius:10px;background:#fff;padding:20px;margin:18px 0 18px 42px}.question-title{display:flex;justify-content:space-between;color:#2d6a4f;font-weight:600}.question-title small{font-weight:400;color:#819087}.prompt,p{line-height:1.8}.prompt{font-size:16px;margin:16px 0}.question-card label{display:block;font-size:14px}textarea{display:block;width:100%;box-sizing:border-box;padding:12px;margin-top:8px;border:1px solid #cedbd2;border-radius:6px;resize:vertical;font:inherit}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}button{font:inherit;padding:9px 15px;border:1px solid #cfdcd4;border-radius:6px;background:#fff;color:#2d5843;cursor:pointer}.primary{background:#2d6a4f;color:white}button:disabled{opacity:.45;cursor:default}.note,.mock-control{font-size:12px;color:#75847b}.mock-control{margin-top:10px}.mock-control p{margin:6px 0}select{margin-left:12px;padding:5px}.past-question{border-top:1px solid #e3ebe6;padding:14px 0}.past-question p{font-size:13px}details{margin:16px 0}summary{cursor:pointer;font-size:14px}h3{font-size:17px;margin:0 0 12px}.result-count{font-weight:600;color:#2d6a4f}svg{display:block;width:100%;max-width:400px;margin:12px auto}.error{color:#9c3d29}@media(max-width:800px){.question-card{margin-left:0;padding:14px}}
</style>
