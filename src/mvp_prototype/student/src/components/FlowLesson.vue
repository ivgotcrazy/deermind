<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { courseFlow as flow } from '../course-flow';
import { practice, offerTest, startTest, submitAnswer, endLesson, sendLessonMessage, lessonUses, lessonFeedback, changeFlow, type QuestionUse } from '../../../shared/learning-flow';
import ChatMessageComp from './ChatMessage.vue';
import ChainDiagram from '../../../shared/ChainDiagram.vue';
import ChainAssessment from '../../../shared/ChainAssessment.vue';
import FractionAssessment from '../../../shared/FractionAssessment.vue';
import { fractionCases, fractionSample, fractionFollowups, correctionFor, type FractionCase } from '../../../shared/fraction-assessment';
import { isChainLesson, chainCases, chainFollowups, chainAnswer, type ChainCase } from '../../../shared/fraction-chain';
const props=defineProps<{activityId:string}>();
const emit=defineEmits<{status:[];showStatus:[]}>();
const lesson=computed(()=>flow.lessons.find(a=>a.id===props.activityId));
const uses=computed(()=>lesson.value?lessonUses(flow,lesson.value):[]);
const active=computed(()=>lesson.value?.stage==='practice'?uses.value.find(u=>u.id===lesson.value?.practiceId):lesson.value?.stage==='testing'?uses.value.filter(u=>u.purpose==='检测').slice(-1)[0]:undefined);
const answer=ref(''),outcome=ref<QuestionUse['result']>('正确'),error=ref(''),preparing=ref(false),bottom=ref<HTMLElement>();
const feedback=computed(()=>lesson.value?lessonFeedback(flow,lesson.value):null);
const chain=computed(()=>!!lesson.value&&isChainLesson(lesson.value));
const preparation=ref('success'),prepareFailed=ref(false);
const reviewCase=computed({get:()=>lesson.value?.reviewCase||'mixed',set:(value:ChainCase)=>changeFlow(s=>{const a=s.lessons.find(a=>a.id===props.activityId)!;if(a.stage==='offer')a.reviewCase=value;})});
const fractionCase=computed({get:()=>lesson.value?.fractionCase||'mixed',set:(value:FractionCase)=>changeFlow(s=>{const a=s.lessons.find(a=>a.id===props.activityId)!;if(a.stage==='offer'||a.stage==='explaining')a.fractionCase=value;})});
watch(()=>active.value?.id,()=>{answer.value=lesson.value?.draft||'';outcome.value='正确';},{immediate:true});
watch(answer,value=>{if(lesson.value&&lesson.value.draft!==value)changeFlow(s=>{s.lessons.find(a=>a.id===props.activityId)!.draft=value;});});
watch(()=>[lesson.value?.stage,lesson.value?.messages.length,active.value?.id],async()=>{await nextTick();bottom.value?.scrollIntoView({block:'nearest'});});
function run(fn:()=>void){try{error.value='';fn();}catch(e){error.value=(e as Error).message;}}
async function begin(){preparing.value=true;await new Promise(r=>setTimeout(r,350));prepareFailed.value=preparation.value==='failed';if(!prepareFailed.value)run(()=>startTest(props.activityId));preparing.value=false;}
function retry(){preparation.value='success';begin();}
function fillSample(){if(!lesson.value||!active.value)return;const sample=!chain.value?fractionSample(active.value.question,fractionCase.value,active.value.purpose):lesson.value.stage==='practice'?{answer:'24 × 3/4 = 18 人，我用社团总人数来算。',result:'错误' as const}:chainAnswer(lesson.value);if(sample){answer.value=sample.answer;outcome.value=sample.result;}}
function submit(){run(()=>submitAnswer(props.activityId,answer.value,outcome.value));}
function send(text:string){run(()=>sendLessonMessage(props.activityId,text));}
function finish(){run(()=>endLesson(props.activityId));}
function submitText(text:string){answer.value=text;if(active.value)submit();else{send(text);answer.value='';}}
function setDraft(text:string){answer.value=text;}
defineExpose({send,finish,submitText,setDraft,answer});
</script>
<template><div v-if="lesson" class="flow-lesson">
  <p class="mock-note">Mock 流程走查 · 题目与作答会保存，语义判定采用演示结果</p>
  <template v-for="m in lesson.messages.slice(0,lesson.stage==='finished'?lesson.feedbackMessageCount:undefined).filter(m=>!m.useId||m.useId!==active?.id)" :key="m.id">
    <ChatMessageComp :message="{id:m.id,role:m.actor==='学生'?'user':'assistant',timestamp:0,blocks:[{type:'text',text:m.text}]}"/>
    <svg v-if="uses.find(u=>u.id===m.useId)?.question.figure==='length'" viewBox="0 0 400 100" role="img" :aria-label="`原长 ${uses.find(u=>u.id===m.useId)?.question.quantity} 米，增加原长的四分之一`"><rect x="20" y="25" width="280" height="30" fill="#bed8ca"/><rect x="300" y="25" width="70" height="30" fill="#efce8c"/><text x="80" y="80">原长 {{uses.find(u=>u.id===m.useId)?.question.quantity}} 米</text><text x="305" y="18">增加 1/4</text></svg>
    <ChainDiagram v-if="uses.find(u=>u.id===m.useId)?.question.figure==='nested'"/>
  </template>
  <section v-if="active" class="question-card">
    <div class="question-title"><span>{{active.purpose==='检测'?`检测 · 第 ${lesson.current+1}/${lesson.testIds.length} 题`:'随堂练习'}}</span><small>答案提交后保留</small></div>
    <p class="prompt">{{active.question.question}}</p>
    <ChainDiagram v-if="active.question.figure==='nested'"/>
    <svg v-if="active.question.figure==='length'" viewBox="0 0 400 100" role="img" :aria-label="`原长 ${active.question.quantity} 米，增加原长的四分之一`"><rect x="20" y="25" width="280" height="30" fill="#bed8ca"/><rect x="300" y="25" width="70" height="30" fill="#efce8c"/><text x="80" y="80">原长 {{active.question.quantity}} 米</text><text x="305" y="18">增加 1/4</text></svg>
    <label v-if="chain">答案和思路<textarea v-model="answer" rows="3" placeholder="写下答案，也可以说明你的想法"/></label>
    <p v-else class="note">在底部输入答案和理由，再提交。右侧教材和上文保持原位置。</p>
    <details class="mock-control"><summary>{{chain?'Mock 作答判定':'演示工具'}}</summary><p>{{chain?'此处选择用于体验反馈的结果，不根据输入文字判断能力。':'填入预设作答后，在底部提交；其他输入保留为待确认，不按关键词评分。'}}</p><button @click="fillSample">填入本场景示例作答</button><label v-if="chain">本次模拟结果<select aria-label="本次模拟结果" v-model="outcome"><option>正确</option><option>错误</option><option>待确认</option></select></label><p v-else>本场景：{{fractionCases[fractionCase]}}</p></details>
    <div class="actions"><button v-if="chain" class="primary" :disabled="!answer.trim()" @click="submit">提交答案</button><button @click="run(()=>endLesson(lesson!.id,true))">{{lesson.stage==='testing'?'结束并求助':'求助'}}</button><button v-if="lesson.stage==='testing'" @click="finish">结束检测</button></div>
    <p v-if="lesson.stage==='testing'" class="note">逐题提交只确认收到，结束后一起查看结果。</p>
  </section>
  <p v-if="lesson.stage==='testing'&&lesson.current>0" role="status" class="note">前 {{lesson.current}} 题已提交。</p>
  <div v-if="chain&&lesson.stage==='explaining'" class="actions"><button v-for="q in chainFollowups.slice(0,2)" :key="q.label" @click="send(q.label)">{{q.label}}</button></div>
  <div v-if="!chain&&lesson.stage==='explaining'" class="actions"><button v-for="q in fractionFollowups" :key="q.label" @click="send(q.label)">{{q.label}}</button></div>
  <div v-if="lesson.stage==='explaining'" class="actions"><button class="primary" @click="run(()=>practice(lesson!.id))">做一道练习</button><button @click="run(()=>offerTest(lesson!.id))">准备检测</button><button @click="finish">结束本次学习</button></div>
  <section v-if="lesson.stage==='offer'" class="question-card"><h3>准备一次短检测</h3><p>{{chain?'检查两层参照量：一道文字题，一道区域图题。可用逐层求量或先合并比例的方法。':'检查“增加四分之一后的数量”：一道文字题，一道长度示意图。'}}</p><p>共 2 题，约 3–5 分钟。题目会在开始后展示。</p><p class="note">保留刚才的讲解背景，不直接认定为独立掌握。</p><details class="mock-control"><summary>Mock 场景选择</summary><p>只切换演示内容，不是正式学生操作；自由输入不会自动套用这些评价。</p><label v-if="chain">表现样例<select aria-label="表现样例" v-model="reviewCase"><option v-for="(label,key) in chainCases" :key="key" :value="key">{{label}}</option></select></label><label v-else>表现样例<select aria-label="表现样例" v-model="fractionCase"><option v-for="(label,key) in fractionCases" :key="key" :value="key">{{label}}</option></select></label><label>题目准备样例<select v-model="preparation"><option value="success">检查通过</option><option value="failed">检查未通过</option></select></label></details><div v-if="prepareFailed" class="prepare-failure" role="alert"><p>题目检查未通过，检测还没有开始。你的学习记录已保留，可以重新准备，也可以暂不检测。</p><button :disabled="preparing" @click="retry">重新准备</button></div><div class="actions"><button v-if="!prepareFailed" class="primary" :disabled="preparing" @click="begin">{{preparing?'正在准备题目…':'开始检测'}}</button><button :disabled="preparing" @click="finish">暂不开始</button></div></section>
  <section v-if="lesson.stage==='finished'&&feedback" class="question-card result-card"><h3>{{lesson.endReason==='求助后结束'?'本次已结束，转入讲解':'本次学习反馈'}}</h3><p v-if="feedback.total" class="result-count">{{feedback.summary}}</p><p v-else>已保留本次讲解与练习记录。本次没有完成检测，不显示检测得分。</p><p>{{chain?'这次关注两层参照量。题目结果、各项要求是否达到，以及以后还能否完成，分别说明。':'这次只涉及增加四分之一。当前没有足够依据将整类任务或整章标为已掌握。'}}</p>
    <details><summary>查看逐题记录与解释</summary><article v-for="u in uses" :key="u.id" class="past-question"><strong>{{u.purpose}} · {{u.question.question}}</strong><p>作答：{{u.answer||'未提交'}}{{u.result?' · '+u.result+'（mock）':''}}</p><p>{{u.help}}</p><p v-if="correctionFor(flow,u)" class="note">本题依据已作废：{{correctionFor(flow,u)?.reason}}；原判定保留，已排除其当前评价影响。</p><p>{{u.question.explanation}}</p></article><p v-if="feedback.total>uses.filter(u=>u.purpose==='检测').length">剩余题目未展示、未检测。</p></details>
    <ChainAssessment v-if="chain" :lesson="lesson" :state="flow" @help="send('为什么月季不是整块苗圃的一半？')"/>
    <FractionAssessment v-else :lesson="lesson" :state="flow"/>
    <div class="actions"><button class="primary" @click="emit('showStatus')">查看学习情况</button><button @click="run(()=>send('我想继续理解刚才的问题。'))">继续追问</button></div>
  </section>
  <template v-if="lesson.stage==='finished'&&lesson.feedbackMessageCount!==undefined"><ChatMessageComp v-for="m in lesson.messages.slice(lesson.feedbackMessageCount)" :key="m.id" :message="{id:m.id,role:m.actor==='学生'?'user':'assistant',timestamp:0,blocks:[{type:'text',text:m.text}]}"/></template>
  <p v-if="error" role="alert" class="error">{{error}}</p><div ref="bottom"/>
</div><p v-else>请从教材章节开始学习。</p></template>
<style scoped>
.mock-note{font-size:12px;color:#788980;margin:4px 0 20px}.question-card{border:1px solid #dbe6df;border-radius:10px;background:#fff;padding:20px;margin:18px 0 18px 42px}.question-title{display:flex;justify-content:space-between;color:#2d6a4f;font-weight:600}.question-title small{font-weight:400;color:#819087}.prompt,p{line-height:1.8}.prompt{font-size:16px;margin:16px 0}.question-card label{display:block;font-size:14px}textarea{display:block;width:100%;box-sizing:border-box;padding:12px;margin-top:8px;border:1px solid #cedbd2;border-radius:6px;resize:vertical;font:inherit}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}button{font:inherit;padding:9px 15px;border:1px solid #cfdcd4;border-radius:6px;background:#fff;color:#2d5843;cursor:pointer}.primary{background:#2d6a4f;color:white}button:disabled{opacity:.45;cursor:default}.note,.mock-control{font-size:12px;color:#75847b}.mock-control{margin-top:10px}.mock-control p{margin:6px 0}select{margin-left:12px;padding:5px}.past-question{border-top:1px solid #e3ebe6;padding:14px 0}.past-question p{font-size:13px}details{margin:16px 0}summary{cursor:pointer;font-size:14px}h3{font-size:17px;margin:0 0 12px}.result-count{font-weight:600;color:#2d6a4f}svg{display:block;width:100%;max-width:400px;margin:12px auto}.error{color:#9c3d29}@media(max-width:800px){.question-card{margin-left:0;padding:14px}}
</style>
