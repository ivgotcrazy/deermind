<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import lesson from '../../../mvp_foundation/examples/chapter-lesson.json';
import CheckInputReview from './CheckInputReview.vue';
import { checkInputs, closeInputCheck, resetCheckInputs, checkInputWarning } from '../checkInputState';
import { parentState, currentParentLinked as parentLinked, parentWarning, resetParent } from '../parentState';
import LearningHomeReview from './LearningHomeReview.vue';
import OperationsReview from './OperationsReview.vue';
import { hub, hubWarning, currentContext, selectContext, resetHub } from '../hubState';
import { opsWarning, resetOperations } from '../operationsState';
import ProblemHelpReview from './ProblemHelpReview.vue';
import LearningStatusReview from './LearningStatusReview.vue';
import MaintenanceReview from './MaintenanceReview.vue';
import CourseReview from './CourseReview.vue';
import MaterialSetupReview from './MaterialSetupReview.vue';
import AccountReview from './AccountReview.vue';
import RecordsReview from './RecordsReview.vue';
import CaseTraceReview from './CaseTraceReview.vue';
import { liveRecords, resetRecords, reviewWarning } from '../recordState';
import { clearCapture } from '../captureState';
import { journey, examBusy, demoConfirmed, journeyWarning, resetJourney } from '../journeyState';
import { storageStatus, resetFlows, flows } from '../foundationState';
type View = 'lesson' | 'home' | 'prepare' | 'check' | 'summary';
type Role = 'student' | 'parent' | 'admin';
type Run = { answers: string[]; ended: 'completed' | 'help' | 'manual'; helpQuestion?: number };
type Entry = { kind: string; text: string; at: string };
type Session = { shown: number[]; segment: number; unlocked: number; closed: boolean; checkRunning: boolean; view: View; drafts: Record<string,string>; followups: number[]; practiceOpen: boolean; practiceSubmitted: boolean; practiceText: string; practiceExample: boolean; activeAnswers: string[]; checkDraft: string; runs: Run[]; history: Entry[] };
const key = 'deermind-phase4-lesson-v1';
function initial(): Session { return { shown:[], segment:0, unlocked:0, closed:false, checkRunning:false, view:'lesson', drafts:{}, followups:[], practiceOpen:false, practiceSubmitted:false, practiceText:'', practiceExample:false, activeAnswers:[], checkDraft:'', runs:[], history:[] }; }
const warning=ref('');
function restore(): Session {
  try {
    const raw=localStorage.getItem(key); if(!raw) return initial();
    const s=JSON.parse(raw) as Session;
    if(!Number.isInteger(s.segment) || s.segment<0 || s.segment>2 || !Number.isInteger(s.unlocked) || s.unlocked<s.segment || s.unlocked>2 || !['lesson','home','prepare','check','summary'].includes(s.view) || typeof s.closed!=='boolean' || !s.drafts || !Array.isArray(s.history) || !Array.isArray(s.runs) || !Array.isArray(s.activeAnswers) || s.activeAnswers.length>2 || !Array.isArray(s.followups)) throw Error('Invalid state');
    return {...initial(),...s,shown:Array.isArray(s.shown)?s.shown:(s.history.length?Array.from({length:s.unlocked+1},(_,i)=>i):[])};
  } catch { warning.value='先前演示进度无法读取；已从新的演示开始。'; return initial(); }
}
const session=reactive<Session>(restore());
const allRecords=computed(()=>liveRecords(session));
watch(session,()=>{ try { localStorage.setItem(key,JSON.stringify(session)); } catch { warning.value='当前浏览器无法保存；本页可继续，刷新后进度可能丢失。'; } },{deep:true});
const requestedRole=new URLSearchParams(location.search).get('role');
const role=ref<Role>(requestedRole==='parent'||requestedRole==='admin'?requestedRole:'student');
type Section = 'home'|'operations'|'activity'|'help'|'status'|'records'|'maintenance'|'course'|'materials'|'accounts'|'trace';
const requestedView=new URLSearchParams(location.search).get('view');
const section=ref<Section>(['home','activity','operations','help','status','records','maintenance','course','materials','accounts','trace'].includes(requestedView||'')?requestedView as Section:role.value==='student'?'home':'activity');
const tabs=computed(()=>role.value==='student'?[['home','学习'],['status','学习情况'],['records','题目记录'],['course','教材与检测']]:role.value==='parent'?[['activity','本次活动'],['status','学习情况'],['accounts','账号']]:[['operations','运行与处理'],['activity','章节案例'],['trace','记录追溯'],['maintenance','内容与维护'],['materials','教材准备'],['accounts','账号与关系']]);
if(!tabs.value.some(([id])=>id===section.value)&&!(role.value==='student'&&['activity','help','accounts'].includes(section.value)))section.value=role.value==='student'?'home':'activity';
const busySection=computed(()=>session.checkRunning?'activity':examBusy.value?'course':null);
watch(role,()=>{section.value=role.value==='student'&&busySection.value?busySection.value:role.value==='student'?'home':'activity';announcement.value='';historyOpen.value=false;});
watch(section,()=>{announcement.value='';historyOpen.value=false;});
watch([role,section],()=>{const url=new URL(location.href);url.searchParams.set('role',role.value);url.searchParams.set('view',section.value);history.replaceState(null,'',url);});
function navigate(id:string){if(role.value==='student'&&busySection.value&&id!==busySection.value)return;if(id==='course'&&role.value==='student'&&journey.selectedCourse)selectContext(journey.selectedCourse);if(id==='activity'&&role.value==='student'){selectContext('demo');resume();}section.value=id as Section;}
watch(()=>journey.selectedCourse,id=>{if(id)selectContext(id);});
if(role.value==='student'&&section.value==='activity')selectContext('demo');
const toolsOpen=ref(false);const historyOpen=ref(false);const announcement=ref('');
const segment=computed(()=>lesson.segments[session.segment]!);
const draft=computed({get:()=>session.drafts[segment.value.id]||'',set:(v:string)=>session.drafts[segment.value.id]=v});
const checkInputKey=computed(()=>`lesson-check-${session.runs.length}-${session.activeAnswers.length}`);
const lastRun=computed(()=>session.runs.at(-1));
const submitted=computed(()=>session.runs.reduce((n,r)=>n+r.answers.length,0)+session.activeAnswers.length+(session.practiceSubmitted?1:0));
function record(kind:string,text:string) { session.history.push({kind,text,at:new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}); }
function send() { if(!draft.value.trim() || session.closed) return; record('自由输入',draft.value.trim()); draft.value=''; announcement.value='已保留你的输入。此走查未接入语言模型，尚未理解或执行请求；可用“走查工具”的明确示例查看就地追问效果。'; }
function onEnter(e:KeyboardEvent) { if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();} }
function followup() { if(session.closed||session.view!=='lesson'||section.value!=='activity') return; if(!session.followups.includes(session.segment)){session.followups.push(session.segment);record('示例追问',segment.value.followup_question);record('已展示的示例帮助',segment.value.followup_answer);} announcement.value='预写追问已补充在当前讲解段下方。'; }
function next() { if(session.closed||session.segment>=2) return; session.segment++;session.unlocked=Math.max(session.unlocked,session.segment);announcement.value=''; }
function jump(i:number) { if(i<=session.unlocked){session.segment=i;session.view='lesson';announcement.value='';} }
function pause() { if(session.view==='check') record('检测暂离','保留当前未结束检测和草稿'); else {record('暂离','保留讲解位置和草稿');section.value='home';} session.view='home'; }
function resume() { session.view=checkPending.value?'check':'lesson';announcement.value=''; }
const checkPending=computed(()=>session.checkRunning);
if(role.value==='student'&&busySection.value)section.value=busySection.value;
function startCheck() { session.activeAnswers=[];session.checkDraft='';session.view='check';session.checkRunning=true;record('开始检测','2 题；逐题收件，结束统一反馈；保留此前讲解背景'); }
function finishCheck(ended:Run['ended']) { closeInputCheck(checkInputKey.value);session.runs.push({answers:[...session.activeAnswers],ended,helpQuestion:ended==='help'?session.activeAnswers.length:undefined});session.activeAnswers=[];session.checkDraft='';session.checkRunning=false;record('结束检测',`${ended}；已提交 ${lastRun.value?.answers.length||0}/2 题`);session.view='summary';announcement.value=''; }
function submitCheck() { if(!session.checkDraft.trim()||checkInputs.panels[checkInputKey.value]?.open) return; session.activeAnswers.push(session.checkDraft.trim());record('收到检测作答',`第 ${session.activeAnswers.length} 题：${session.checkDraft.trim()}`);session.checkDraft='';if(session.activeAnswers.length===2)finishCheck('completed');else announcement.value='第 1 题已收到。结束检测后统一反馈。'; }
function helpCheck() { finishCheck('help');record('检测结束后展示的帮助',lesson.check.reference[lastRun.value?.helpQuestion??0]!); }
function practice() { if(!session.practiceText.trim())return;session.practiceSubmitted=true;record('练习提交',session.practiceText);announcement.value=''; }
function endLesson() { session.closed=true;session.view='summary';record('结束讲解','记录已展示内容与提交表现，不自动判断掌握'); }
function reset() { if(!window.confirm('清空本页合成演示进度并重新开始？不影响历史原型。'))return;Object.assign(session,initial());resetFlows();resetJourney();resetRecords();clearCapture();resetHub();resetOperations();resetParent();resetCheckInputs();delete flows.problemDraft.input;session.checkRunning=false;announcement.value='';historyOpen.value=false; }
watch(()=>[role.value,section.value,session.view,session.segment],()=>{if(role.value==='student'&&demoConfirmed.value&&section.value==='activity'&&session.view==='lesson'&&!session.shown.includes(session.segment)){session.shown.push(session.segment);record('展示讲解',segment.value.title);}},{immediate:true});
</script>
<template>
<div class="f-app">
  <div class="f-reviewbar"><span><b>Phase 4 · 交互走查</b>　{{ role === 'admin' ? (section === 'maintenance' ? '内容候选与合成维护 / 未连接模型' : '合成章节 / 未连接模型') : '合成章节 / 未连接模型' }}</span><div class="f-role-switch"><a :href="`structure.html?role=${role}`">新版结构走查 →</a><button v-for="r in (['student','parent','admin'] as const)" :key="r" :aria-pressed="role===r" @click="role=r">{{ {student:'学生',parent:'家长',admin:'管理员'}[r] }}</button><button @click="toolsOpen=!toolsOpen" :aria-expanded="toolsOpen">走查工具</button></div></div>
  <div v-if="toolsOpen" class="f-tools"><span>这里的角色切换和示例按钮仅用于评审。自由输入不作语义判断。</span><button :disabled="role!=='student'||section!=='activity'||session.view!=='lesson'||session.closed" @click="followup">载入当前段追问示例</button><button @click="reset">重置本页演示</button><label v-if="role==='parent'">合成家长身份 <select v-model="parentState.actor" aria-label="当前合成家长"><option v-for="p in journey.accounts.profiles.filter(p=>p.role==='parent')" :key="p.id" :value="p.id">{{ p.name }}</option></select></label><a href="./index.html#/student/home">查看历史原型</a></div>
  <p v-if="warning" class="f-notice" role="status">{{ warning }}</p>
  <header class="f-header"><a class="f-brand" href="./phase4.html">DeerMind<span>让每一次理解，都有来处</span></a><span class="f-context">{{ section==='operations'?'运行状态 · 独立合成任务':section==='trace'?'记录追溯 · 本地合成操作':section==='accounts'?'账号与关系 · 合成档案':section==='materials'?'教材准备 · 合成材料':section==='course'?'教材范围 · 演示空间':role==='student'?currentContext.name:role==='parent'?'家长视角 · 演示孩子':section==='maintenance'?'内容候选与合成维护':'案例走查 · 合成活动 DEMO-LESSON-AREA-001' }}</span><button v-if="role==='student'" :disabled="!!busySection" @click="navigate('accounts')">账号</button></header>
  <nav class="f-main-nav" aria-label="当前角色导航"><button v-for="[id,label] in tabs" :key="id" :aria-current="section===id?'page':undefined" :disabled="role==='student'&&!!busySection&&id!==busySection" @click="navigate(id!)">{{ label }}</button><span v-if="role==='student'&&busySection" class="f-muted">检测尚未结束，可返回继续或结束后求助。</span></nav>
  <p v-if="hubWarning.text||opsWarning.text" role="status" class="f-notice">{{ hubWarning.text||opsWarning.text }}</p>
  <p v-if="parentWarning.text||checkInputWarning.text" role="status" class="f-notice">{{ parentWarning.text||checkInputWarning.text }}</p>
  <p v-if="storageStatus.warning" role="status" class="f-notice">{{ storageStatus.warning }}</p>
  <p v-if="reviewWarning.text" role="status" class="f-notice">{{ reviewWarning.text }}</p>
  <p v-if="journeyWarning.text" role="status" class="f-notice">{{ journeyWarning.text }}</p>
  <main v-if="role==='parent'&&!parentLinked&&section!=='accounts'" class="f-flow-page"><h1>当前没有可查看的学生关联</h1><p>该亲子关联已经解除，旧页面和链接不能继续展示孩子的学习资料。请联系管理员核实；其他家长的关联不受影响。</p><button @click="section='accounts'">查看账号与关系说明</button></main>
  <AccountReview v-else-if="section==='accounts'" :key="role+parentState.actor" :role="role"/>
  <main v-else-if="role==='student'&&!demoConfirmed" class="f-flow-page"><h1>先完成必要的首次说明</h1><p>请先在家长端和学生端分别完成演示确认。此门槛不代表真实服务条件已核实。</p><button @click="section='accounts'">查看账号与首次说明</button></main>
  <LearningHomeReview v-else-if="role==='student'&&section==='home'" :shown="session.shown.length" :closed="session.closed" :segment="segment.title" :records="allRecords" @open="navigate"/>
  <OperationsReview v-else-if="role==='admin'&&section==='operations'" @open="navigate"/>
  <CourseReview v-else-if="role==='student'&&section==='course'" @accounts="section='accounts'"/>
  <MaterialSetupReview v-else-if="role==='admin'&&section==='materials'"/>
  <RecordsReview v-else-if="role==='student'&&section==='records'" :records="allRecords" :initial-space="hub.current"/>
  <CaseTraceReview v-else-if="role==='admin'&&section==='trace'" :records="allRecords" @maintenance="section='maintenance'"/>
  <ProblemHelpReview v-else-if="role==='student'&&section==='help'"/>
  <LearningStatusReview v-else-if="section==='status'&&role!=='admin'" :key="role+parentState.actor" :records="allRecords" :parent="role==='parent'" :space-id="role==='student'?hub.current:undefined" @lesson="navigate('activity')" @help="navigate('help')"/>
  <MaintenanceReview v-else-if="role==='admin'&&section==='maintenance'"/>
  <template v-else-if="role==='student'">
    <main v-if="session.view==='home'" class="f-home"><span class="f-eyebrow">教材 / 合成章节</span><h1>回到刚才的问题</h1><p>三角形面积：{{ lesson.purpose }}</p><article class="f-card"><h2>{{ session.closed?'本次讲解已结束':checkPending?'你有一段尚未结束的检测':'继续上次的讲解' }}</h2><p>{{ segment.title }} · 第 {{ session.segment+1 }} / 3 段</p><p>讲解进度、追问及未发送草稿保留在当前浏览器。</p><button class="f-primary" @click="resume">{{ session.closed?'回看本次讲解':checkPending?'继续未结束的检测':'继续本次讲解' }}</button></article><p class="f-muted">可通过上方导航查看求助与学习情况。教材原材料、多模态及真实模型尚未接入。</p></main>
    <main v-else-if="session.view==='lesson'" class="f-workspace">
      <aside class="f-outline"><button class="f-back" @click="pause">← 返回学习</button><span class="f-eyebrow">本次要弄清楚</span><h2>三角形面积</h2><p>{{ lesson.purpose }}</p><ol><li v-for="(s,i) in lesson.segments" :key="s.id"><button :disabled="i>session.unlocked" :class="{current:i===session.segment}" :aria-current="i===session.segment?'step':undefined" @click="jump(i)"><span>{{ String(i+1).padStart(2,'0') }}</span>{{ s.title }}</button></li></ol><div class="f-side-note">{{ session.closed?'本次已结束，当前为回看。':'按自己的节奏来。每次讲一小段，想清楚再继续。' }}</div></aside>
      <section class="f-content"><div class="f-content-heading"><span class="f-eyebrow">理解一个关键问题 · {{ session.segment+1 }} / 3</span><button v-if="!session.closed" class="f-text-button" @click="endLesson">先到这里</button></div><h1>{{ segment.title }}</h1><p class="f-lead">{{ segment.lead }}</p>
        <figure class="f-figure" v-if="session.segment===0"><svg viewBox="0 0 460 200" role="img" aria-label="两个完全相同的三角形拼成平行四边形，底为6厘米，对应高为4厘米"><polygon points="70,145 310,145 380,35" fill="#b2cbbf"/><polygon points="70,145 380,35 140,35" fill="#e2b77d"/><path d="M70 145L380 35" stroke="#425d52" stroke-width="2" stroke-dasharray="6 5"/><path d="M140 35V145M140 133H152V145" fill="none" stroke="#52665a" stroke-width="1.5"/><text x="184" y="176">底 6 厘米</text><text x="29" y="88">高 4 厘米</text><text x="205" y="83">一半</text><text x="260" y="132">另一半</text></svg><figcaption>两个完全一样的三角形，拼出同底同高的平行四边形。</figcaption></figure>
        <figure class="f-figure" v-else><svg viewBox="0 0 460 200" role="img" aria-label="三角形的底与对应垂直高度"><polygon points="70,145 370,145 180,30" fill="#c5d8cb" stroke="#607e6a" stroke-width="2"/><path d="M180 30V145M180 132H193V145" fill="none" stroke="#52665a" stroke-width="2" stroke-dasharray="5 4"/><text x="200" y="174">选定的底</text><text x="194" y="90">对应的高</text></svg><figcaption>先选底，再找从对面顶点到这条直线的垂直距离。</figcaption></figure>
        <p class="f-explanation">{{ segment.body }}</p><div class="f-equation">{{ segment.formula }}</div>
        <div v-if="session.followups.includes(session.segment)" class="f-followup"><span class="f-eyebrow">这一段的追问 · 预写示例</span><h3>{{ segment.followup_question }}</h3><p>{{ segment.followup_answer }}</p></div>
        <div v-if="session.practiceOpen" class="f-practice"><span class="f-eyebrow">讲解中的练习</span><h2>试着把理由说出来</h2><p>{{ lesson.practice.prompt }}</p><textarea v-model="session.practiceText" :disabled="session.practiceSubmitted||session.closed" aria-label="练习作答" placeholder="写下算式，也可以用自己的话解释。" @input="session.practiceExample=false"/><div class="f-actions" v-if="!session.practiceSubmitted&&!session.closed"><button class="f-primary" :disabled="!session.practiceText.trim()" @click="practice">提交练习</button><button @click="session.practiceText=lesson.practice.example_answer;session.practiceExample=true">载入预写示例作答</button></div><p v-if="session.practiceSubmitted" class="f-result">{{ session.practiceExample?lesson.practice.feedback:'已收到作答；此原型未接入真实判断，不能给出正确或掌握结论。' }}</p></div>
        <div class="f-actions f-next" v-if="!session.closed"><button v-if="session.segment<2" class="f-primary" @click="next">继续下一段 →</button><button v-else class="f-primary" @click="session.view='prepare'">做一次结束检查</button><button v-if="!session.practiceOpen" class="f-secondary" @click="session.practiceOpen=true">试着做一题</button><span class="f-muted">继续或阅读完成，都不代表已经掌握。</span></div>
        <p v-if="session.closed" class="f-notice">这次活动已结束。可以回看内容与记录，不能继续向已结束的活动提交作答。</p>
      </section>
    </main>
    <main v-else-if="session.view==='prepare'" class="f-home"><span class="f-eyebrow">开始前，先看看范围</span><h1>检查这次理解了什么</h1><article class="f-card"><h2>三角形面积的计算与理由</h2><p>2 道合成示例题 · 参考用时约 {{ lesson.check.estimated_minutes }} 分钟</p><ul><li>提交后先确认收到，结束时统一反馈。</li><li>如果中途需要讲解，会先结束这次检测，再提供帮助。</li><li>刚才的讲解背景会保留；这次检查不能单独证明持久掌握。</li></ul><div class="f-actions"><button class="f-primary" @click="startCheck">开始检查</button><button @click="session.view='lesson'">先不检查，返回讲解</button></div></article></main>
    <main v-else-if="session.view==='check'" class="f-home"><div class="f-content-heading"><span class="f-eyebrow">结束检查 · 第 {{ session.activeAnswers.length+1 }} / 2 题</span><button @click="pause">暂时离开</button></div><h1>把你的想法写下来</h1><article class="f-card"><h2>{{ lesson.check.questions[session.activeAnswers.length] }}</h2><textarea v-model="session.checkDraft" :disabled="!!checkInputs.panels[checkInputKey]?.open" aria-label="检测作答" placeholder="提交前不会分析。此原型仅保存作答，不作真实判定。"/><CheckInputReview :key="checkInputKey" :context="checkInputKey" :draft="session.checkDraft" @apply="(text)=>{session.checkDraft=text;record('输入核对','学生确认录入文字，未提交新作答，未认证独立性');}"/><p class="f-muted">求助会结束本次检测；剩余题目记为未检测。</p><div class="f-actions"><button class="f-primary" :disabled="!session.checkDraft.trim()||!!checkInputs.panels[checkInputKey]?.open" @click="submitCheck">提交本题</button><button class="f-secondary" @click="helpCheck">需要讲解，结束检测</button><button @click="finishCheck('manual')">结束并查看记录</button></div></article></main>
    <main v-else class="f-home"><span class="f-eyebrow">本次记录</span><h1>{{ lastRun?.ended==='help'?'检测已结束，现在可以讲解':session.closed?'今天先到这里':'看看这次做了什么' }}</h1><article class="f-card"><h2>三角形面积</h2><p>已展示 {{ session.shown.length }} 段讲解，提交 {{ submitted }} 次作答。</p><template v-if="lastRun"><p>最近检测已提交 {{ lastRun.answers.length }} / 2 题；{{ 2-lastRun.answers.length }} 题未检测。结束原因：{{ {completed:'完成题单',help:'请求讲解',manual:'主动结束'}[lastRun.ended] }}。</p><div v-for="(a,i) in lastRun.answers" :key="i" class="f-answer"><b>第 {{ i+1 }} 题实际提交</b><p>{{ a }}</p><details><summary>查看预写参考（不等于自动评分）</summary><p>{{ lesson.check.reference[i] }}</p></details></div><div v-if="lastRun.ended==='help'" class="f-followup"><h3>检测结束后的帮助示例</h3><p>{{ lesson.check.reference[lastRun?.helpQuestion??0] }}</p></div></template><p class="f-notice">尚未连接真实评价模型。本页只呈现实际演示操作，不给出掌握结论，也不把未检测当成不会。</p><div class="f-actions"><button v-if="!session.closed" class="f-primary" @click="session.view='lesson'">返回讲解</button><button v-if="!session.closed" @click="endLesson">结束本次讲解</button><button v-else @click="section='home'">返回学习</button></div></article></main>
  </template>
  <main v-else-if="role==='parent'" class="f-home"><span class="f-eyebrow">同一活动 · 家长只读视图</span><h1>这次学习发生了什么</h1><article class="f-card"><h2>三角形面积</h2><p>讲解{{ session.closed?'已结束':'进行中或暂离' }} · 已展示 {{ session.shown.length }} 段 · 提交 {{ submitted }} 次作答</p><p>内容涉及“为什么除以 2”和“底、高如何对应”。展示过讲解不代表已掌握。</p><p class="f-notice">没有真实 Evaluation 结果，因此尚无可展示的章节达标项数。本例不能显示为 0 分或全部不会。</p><details><summary>查看相关操作依据</summary><ol><li v-for="(e,i) in session.history" :key="i"><b>{{ e.kind }}</b>：{{ e.text }}</li></ol><p v-if="!session.history.length">尚无新增演示操作。</p></details></article><p class="f-muted">此轮只验证家长如何理解同源结果；私人咨询在学习情况页、首次说明在账号页走查；尚未实现真实权限。没有修改学生资料入口。</p></main>
  <main v-else class="f-admin"><span class="f-eyebrow">工作事项：核对合成章节的讲解与检测衔接</span><h1>查看依据，再判断问题在哪里</h1><div class="f-admin-grid"><article class="f-card"><h2>本次案例</h2><dl><dt>活动</dt><dd>DEMO-LESSON-AREA-001</dd><dt>内容来源</dt><dd>人工编写合成内容，版本 1</dd><dt>实际教材映射</dt><dd>未准备</dd><dt>Observation / Evidence / Belief</dt><dd>未执行，不能用页面操作代替</dd><dt>展示与控制记录</dt><dd>本浏览器中的演示事件</dd></dl></article><article class="f-card"><h2>Interaction 操作时间线</h2><ol class="f-timeline"><li v-for="(e,i) in session.history" :key="i"><span>{{ e.at }} · {{ e.kind }}</span><p>{{ e.text }}</p></li></ol><p v-if="!session.history.length">暂无新增演示事件。事件只在操作发生后记录。</p></article></div><p class="f-muted">管理身份与事项权限在正式系统由服务端检查；此处角色切换只用于走查，不是权限实现。“内容与维护”可走查本地候选、审核、发布与指定采用；不连接正式模型。</p></main>
  <div v-if="announcement" class="f-announcement" role="status">{{ announcement }}</div>
  <section v-if="role==='student'&&demoConfirmed&&section==='activity'&&session.view==='lesson'" class="f-composer" aria-label="与 DeerMind 对话"><div class="f-composer-meta"><span>正在讨论 · {{ segment.title }}</span><button @click="historyOpen=!historyOpen" :aria-expanded="historyOpen">{{ historyOpen?'收起':'对话' }}历史</button></div><form @submit.prevent="send"><textarea v-model="draft" :disabled="session.closed" aria-label="向 DeerMind 提问" placeholder="哪里还没想明白？随时说说你的想法…" rows="2" @keydown="onEnter"/><button type="submit" class="f-send" :disabled="!draft.trim()||session.closed" aria-label="发送">↑</button></form><p>Enter 发送 · Shift + Enter 换行 · 本轮自由输入仅保存，不执行语义判断</p></section>
  <section v-if="historyOpen&&role==='student'&&demoConfirmed&&section==='activity'&&session.view==='lesson'" class="f-history" aria-label="对话历史"><header><h2>本次对话与操作</h2><button @click="historyOpen=false" aria-label="关闭对话历史">关闭</button></header><p v-if="!session.history.length">这里还没有记录。</p><article v-for="(e,i) in session.history" :key="i"><small>{{ e.at }} · {{ e.kind }}</small><p>{{ e.text }}</p></article></section>
</div>
</template>
