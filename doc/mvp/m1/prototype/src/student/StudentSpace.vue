<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { emptyTextbook } from '../model/textbook';
import { prepareRealBook } from '../model/material-fixture';
import LessonMessage from './LessonMessage.vue';
import ActivityDirectory from './ActivityDirectory.vue';
import { activityForestFixture } from './activity-forest-fixture';
import { chooseCard, cardReply, items, type Turn, type LessonCard, type Check, type Activity } from './quarter';
import './student.css';

// A snapshot of the course offered to this trial learner. Admin drafts are never read as applied courses.
const book = prepareRealBook(emptyTextbook());
const bookName = '北师大版数学六年级上册';
const goal = '能自己算出增加四分之一后的数量，并说明为什么';
const bookId = 'BNU-6A';
const targetId = 'TARGET-M1-QUARTER-SEPARATE';
const chapters = book.units.flatMap(unit => unit.chapters);
const initialChapter = '分数的应用（一）';
type Layout = 'book' | 'split' | 'chat';
type ActivityNotice = { at:number; text:string; detail?:string; resumeId?:string; startId?:string };
type Space = { bookId: string; targetId: string; chapter: string; page: string; layout: Layout; paperPosition: number; chatPosition: number; draft: string; turns: Turn[]; activities:Activity[]; activeId?:string; notices:ActivityNotice[]; directoryOpen:boolean; expandedActivities:string[]; reviewingId?:string };
const demoMode = new URLSearchParams(window.location.search).get('mode') !== 'records';
const key = demoMode ? 'deermind-m1-student-activity-forest-demo-v1' : 'deermind-m1-student-trial-space-v1';
const error = ref('');
const narrowQuery=window.matchMedia('(max-width:1100px)');
const narrow=ref(narrowQuery.matches);
function restore(): Space | null {
  try {
    const data = JSON.parse(localStorage.getItem(key) || 'null') as (Partial<Space> & {teaching?: boolean}) | null;
    if (data?.bookId === bookId && data.targetId === targetId && Array.isArray(data.turns)) {
      const layout = data.layout ?? (data.teaching ? 'split' : 'book');
      return {bookId, targetId, chapter:data.chapter || initialChapter, page:data.page || '49',
        layout:['book','split','chat'].includes(layout) ? layout : 'book', paperPosition:data.paperPosition ?? 0,
        chatPosition:data.chatPosition ?? -1, draft:data.draft || '', turns:data.turns,activities:data.activities||[],activeId:data.activeId,notices:data.notices||[],
        directoryOpen:narrow.value&&!demoMode?false:data.directoryOpen??true,expandedActivities:data.expandedActivities||[],reviewingId:data.reviewingId};
    }
  } catch { error.value = '未能读取这台设备上的学习空间。'; }
  return null;
}
const space = ref<Space | null>(restore() ?? (demoMode ? {
  bookId,targetId,chapter:initialChapter,page:'49',layout:'split',paperPosition:0,chatPosition:-1,draft:'',
  directoryOpen:true,...activityForestFixture(),
} : null));
const bookChoice = ref(''), targetChoice = ref('');
const chapter = computed(() => chapters.find(c => c.name === space.value?.chapter) || chapters[0]);
const pages = computed(() => chapter.value.locations);
const page = computed(() => pages.value.find(p => p.printedPage === space.value?.page) || pages.value[0]);
const transcript = ref<HTMLElement | null>(null);
const paper = ref<HTMLElement | null>(null);
const prompt = ref<HTMLTextAreaElement | null>(null);
const lastTurn = computed(()=>space.value?.turns.at(-1));
const active=computed(()=>space.value?.activities.find(a=>a.id===space.value?.activeId));
const paused=computed(()=>active.value?.status==='暂停');
const openCheck = computed(()=>lastTurn.value?.check?.status==='answering' ? lastTurn.value.check : undefined);
const expandedPath = ref(false);
const activityPath = computed(()=>{
  const path:Activity[]=[];let item=active.value;
  while(item&&!path.some(a=>a.id===item!.id)){
    path.unshift(item);item=space.value?.activities.find(a=>a.id===item!.parentId);
  }
  return path;
});
const visiblePath = computed(()=>activityPath.value.length>3&&!expandedPath.value
  ? [activityPath.value[0],null,active.value!] : activityPath.value);
const activeRound = computed(()=>space.value?.turns.filter(t=>t.activityId===active.value?.id&&t.check).at(-1));
const reviewing=computed(()=>space.value?.activities.find(a=>a.id===space.value?.reviewingId));
const following=ref(space.value?.chatPosition===-1||!space.value);
const highlighted=ref('');
const locateError=ref('');
let highlightTimer:ReturnType<typeof setTimeout>|undefined;
watch(()=>space.value?.activeId,()=>{
  const s=space.value;if(!s)return;
  for(const a of activityPath.value.slice(0,-1))if(!s.expandedActivities.includes(a.id))s.expandedActivities.push(a.id);
},{immediate:true});
watch(()=>space.value?.activeId,()=>expandedPath.value=false);
function noticesAt(at:number){return space.value!.notices.filter(n=>n.at===at);}
function canResume(id?:string){return !!id&&space.value?.activities.some(a=>a.id===id&&a.status==='暂停')&&!activityPath.value.some(a=>a.id===id);}
async function scrollToLatest(force=false){
  const follow=force||(!reviewing.value&&following.value);
  await nextTick();if(!follow||(!force&&reviewing.value))return;
  following.value=true;
  if(space.value)space.value.chatPosition=-1;
  if(transcript.value)transcript.value.scrollTop=transcript.value.scrollHeight;
}
function notice(text:string,detail?:string,resumeId?:string,startId?:string){
  space.value!.notices.push({at:space.value!.turns.length,text,detail,resumeId,startId});
  void scrollToLatest();
}
function trackChatPosition(){
  const c=transcript.value,s=space.value;if(!c||!s)return;
  following.value=c.scrollHeight-c.clientHeight-c.scrollTop<4;
  s.chatPosition=following.value?-1:c.scrollTop;
}
function toggleBranch(id:string){
  const s=space.value!;s.expandedActivities=s.expandedActivities.includes(id)?s.expandedActivities.filter(x=>x!==id):[...s.expandedActivities,id];
}
async function toggleDirectory(open:boolean){
  const s=space.value;if(!s)return;
  rememberPositions();s.directoryOpen=open;await nextTick();restorePositions();
  if(narrow.value){
    if(open)document.querySelector<HTMLButtonElement>('.activity-directory header button')?.focus();
    else document.querySelector<HTMLButtonElement>('.directory-open')?.focus();
  }
}
async function locateActivity(id:string){
  const s=space.value;if(!s)return;
  s.reviewingId=id;locateError.value='';
  if(s.layout==='book')await show('split');
  if(narrow.value)s.directoryOpen=false;
  await nextTick();
  const c=transcript.value;
  const target=Array.from(c?.querySelectorAll<HTMLElement>('[data-activity-start]')||[]).find(el=>el.dataset.activityStart===id)
    ||Array.from(c?.querySelectorAll<HTMLElement>('article[data-activity-id]')||[]).find(el=>el.dataset.activityId===id);
  if(!c||!target){locateError.value='这段旧活动没有可定位的聊天内容。';return;}
  c.scrollTop+=target.getBoundingClientRect().top-c.getBoundingClientRect().top-10;
  trackChatPosition();highlighted.value=id;clearTimeout(highlightTimer);
  highlightTimer=setTimeout(()=>highlighted.value='',1800);
  target.focus({preventScroll:true});
}
async function returnToCurrent(){
  if(!space.value)return;
  space.value.reviewingId=undefined;locateError.value='';highlighted.value='';following.value=true;
  if(space.value.layout==='book')await show('split');
  await scrollToLatest(true);
}
function resizeDirectory(){
  narrow.value=narrowQuery.matches;
  if(narrow.value&&space.value)space.value.directoryOpen=false;
}
watch(space, value => {
  try { if (value) localStorage.setItem(key, JSON.stringify(value)); }
  catch { error.value = '本机未能保存进度，请保持此页打开。'; }
}, {deep:true, flush:'sync', immediate:true});
function createSpace() {
  if (bookChoice.value !== bookId || targetChoice.value !== targetId) return;
  space.value = { bookId, targetId, chapter: initialChapter, page: chapters[0].locations[0].printedPage, layout:'book', paperPosition:0, chatPosition:-1, draft:'', turns:[],activities:[],notices:[],directoryOpen:!narrow.value,expandedActivities:[] };
}
function begin(kind:string,title:string,parentId?:string,triggerRound?:string){
  const s=space.value!,previous=active.value;
  if(title==='解释刚才的题目'&&lastTurn.value?.check){const item=items[lastTurn.value.check.item];title=`${item.base}${item.unit}增加四分之一的解法`;}
  if(previous){
    previous.status='暂停';
    if(!parentId)notice(`已保留${previous.kind}进度 · ${previous.title}`,'可以稍后继续。',previous.id);
  }
  const a:Activity={id:'ACT-'+crypto.randomUUID().slice(0,8),kind,title,startedAt:new Date().toISOString(),parentId,triggerRound,status:'进行中',state:kind==='检测'?'准备检测':'回应中',...(kind==='检测'?{plan:2,used:0}:{})};
  s.activities.push(a);s.activeId=a.id;
  notice(`${parentId&&kind==='答疑'?'先解答':'开始'+kind} · ${title}`,parentId?`${previous?.kind}进度已保留，处理完后回到主线。`:undefined,undefined,a.id);
  return a;
}
function returnToParent(){
  const s=space.value!,a=active.value;if(!a||openCheck.value)return;
  a.status='已结束';a.state='结束';
  const parent=s.activities.find(p=>p.id===a.parentId);
  if(parent){
    parent.status='进行中';s.activeId=parent.id;
    notice(`${a.kind}结束，${parent.kind==='检测'?'回到检测，查看本轮结果':'继续刚才的'+parent.kind}`,parent.title);
  }
  else{
    s.activeId=undefined;
    notice(`本次${a.kind}已结束`,a.kind==='讲解'?`已讲解：${a.title}。讲解结束不代表已经掌握，可以继续提问或用新题检测。`:a.kind==='检测'?'本次作答已保留；检测结束不等于目标已达成。':a.title);
  }
}
function pauseActivity(){
  if(!active.value||paused.value)return;
  active.value.status='暂停';notice(`已暂停${active.value.kind} · ${active.value.title}`,'进度与草稿已保留。');
}
function resumeActivity(id=active.value?.id){
  const s=space.value!,a=s.activities.find(a=>a.id===id);
  if(!a||a.status!=='暂停'||(openCheck.value&&active.value?.id!==id))return;
  s.reviewingId=undefined;locateError.value='';following.value=true;
  const previous=active.value;
  if(previous&&previous.id!==id){previous.status='暂停';notice(`已保留${previous.kind}进度 · ${previous.title}`,'可以稍后继续。',previous.id);}
  a.status='进行中';s.activeId=a.id;
  notice(`继续上次的${a.kind} · ${a.title}`,a.kind==='检测'?'从保留的检测进度继续，不重新开启已结束的检测轮。':'从保留的位置继续。');
  if(s.layout==='book')void show('split');
}
function readChapter(name: string) {
  if (!space.value) return;
  space.value.chapter = name;
  readPage(chapter.value.locations[0].printedPage);
}
function readPage(printed: string) {
  if (!space.value) return;
  space.value.paperPosition = 0;
  space.value.page = printed;
}
function rememberPositions() {
  const s = space.value, p = paper.value, c = transcript.value;
  if (!s) return;
  if (p && p.scrollHeight > p.clientHeight) s.paperPosition = p.scrollTop / (p.scrollHeight - p.clientHeight);
  if (c) s.chatPosition = c.scrollHeight - c.clientHeight - c.scrollTop < 2 ? -1 : c.scrollTop;
}
function restorePaper() {
  const p = paper.value;
  if (p && space.value) p.scrollTop = space.value.paperPosition * (p.scrollHeight - p.clientHeight);
}
function restorePositions() {
  restorePaper();
  const c = transcript.value;
  if (c && space.value) c.scrollTop = space.value.chatPosition === -1 ? c.scrollHeight : space.value.chatPosition;
}
async function show(layout: Layout) {
  if (!space.value) return;
  rememberPositions();
  space.value.layout = layout;
  await nextTick();
  restorePositions();
}
onMounted(() => { restorePositions(); window.addEventListener('pagehide', rememberPositions);narrowQuery.addEventListener('change',resizeDirectory); });
onBeforeUnmount(() => {window.removeEventListener('pagehide', rememberPositions);narrowQuery.removeEventListener('change',resizeDirectory);clearTimeout(highlightTimer);});
function refersToPage(question:string){
  return /这(?:一)?页|当前(?:的)?(?:书页|教材页)|(?:书上|教材上)(?:的)?(?:这里|这一|这道)|(?:书上|教材上)(?:这一)?页/.test(question);
}
function exampleReply(question: string, reference?:Turn['bookReference']) {
  if(refersToPage(question)){
    if(!reference)return '你指教材的哪一页？可以告诉我页码和问题，或者展开教材后说“讲讲这一页”。';
    if(reference.page==='49')return '看第 49 页的三个兴趣小组。两个分数说的是不同小组之间的关系。先找已知人数的小组，再看哪个小组的人数是它的几分之几。你想先弄清哪两个小组之间的关系？';
    if(reference.page==='50')return '看第 50 页上方的两种算法。第一种先算出中间小组的人数，再用它求航模小组的人数。第二种先合并两层比例。你想先看哪一步？';
    return `已引用「${reference.chapter}」第 ${reference.page} 页。当前 mock 尚未预写这一页的具体回答，你可以继续描述想了解的问题。`;
  }
  if (/四分之一|增加|1\s*\/\s*4/.test(question))
    return '“增加四分之一”要先看是哪个量的四分之一。我们另举个例子：原有 80 本书，增加的是原来 80 本的四分之一，也就是 20 本。问现在共有多少本，就把这 20 本加回原来的 80 本。你想再看看为什么要加回去，还是试着自己说一遍？';
  if (/整体|参照|基准|中间量/.test(question))
    return '先找“谁的几分之几”里的“谁”。参照的量一变，同一个分数代表的数量也会变。你可以再说说哪一步拿不准。';
  return '已收到你的问题。当前 mock 尚未预写这个问题的具体回答，你可以继续提问或说明想了解的内容。';
}
async function append(question:string, card?:LessonCard) {
  const s = space.value;
  if (!s || openCheck.value || paused.value) return;
  if(card==='check'&&s.turns.filter(t=>t.check).length>=items.length)return;
  const reference=refersToPage(question)&&s.layout!=='chat'?{chapter:chapter.value.name,page:page.value.printedPage}:undefined;
  if(refersToPage(question))card=undefined;
  const switchTopic=/换个话题|换个内容|改学/.test(question)||!!active.value&&!card&&/^(?:请)?(?:讲讲|讲解|介绍)/.test(question);
  if(active.value?.kind==='自由交谈'&&['example','question','offer'].includes(card||'')){
    returnToParent();
  }
  if(switchTopic&&card!=='return'&&card!=='finish'){
    begin(card==='free'?'自由交谈':card==='question'?'答疑':'讲解',card==='free'?'普通交流':card==='question'?'分母为什么不能为零':card?'增加四分之一':question);
  }
  if(card==='return'){returnToParent();}
  else if(card==='question'&&!switchTopic)begin('答疑','分母为什么不能为零',active.value?.id,lastTurn.value?.roundId);
  else if(card==='free'&&!switchTopic&&active.value?.kind!=='自由交谈')begin('自由交谈','普通交流',active.value?.id);
  else if(card==='formula'&&active.value?.kind==='检测'){active.value.helped=true;active.value.plan=active.value.used;begin('答疑','解释本轮方法',active.value.id,lastTurn.value?.roundId);}
  else if(card==='check'){
    if(active.value?.kind!=='检测'){const a=begin('检测','增加四分之一检测',active.value?.id);a.plan=2;a.used=0;}
    if(active.value!.helped)active.value!.plan=(active.value!.used||0)+1;
    active.value!.state='检测轮进行';active.value!.used=(active.value!.used||0)+1;
  }
  else if(card==='diagram'&&active.value?.kind==='检测'){active.value.helped=true;active.value.plan=active.value.used;begin('讲解','解释刚才的题目',active.value.id,lastTurn.value?.roundId);}
  else if(!active.value){
    const kind=card==='offer'?'检测':card==='formula'||/为什么/.test(question)?'答疑':card||/讲|不懂|不会/.test(question)?'讲解':'自由交谈';
    begin(kind,card?'增加四分之一':question);
  }
  const turn:Turn = { question, ...(reference?{bookReference:reference}:{}),
    reply:card ? cardReply[card] : exampleReply(question,reference), card,activityId:active.value?.id };
  if(card==='return')turn.reply=active.value?.kind==='检测'?'回到本次检测。可以查看本轮结果；如果继续检测，将使用新题。':active.value?`继续${active.value.title}。`:'这段交流已结束，可以继续提问。';
  if(card==='question')turn.reply='分母表示把整体平均分成多少份。分成零份不能确定每一份，因此分母不能为零。'+(active.value?.parentId?'这个疑问处理完后，我们再回到原来的主线。':'你想继续讨论哪一步？');
  const used = s.turns.filter(t=>t.check).length;
  if (card==='diagram' || card==='formula') {
    turn.exampleItem=lastTurn.value?.check?.item ?? lastTurn.value?.exampleItem;
    if (turn.exampleItem!==undefined) {
      const {base,unit}=items[turn.exampleItem];
      turn.reply=card==='diagram' ? `回到刚才那道题。把原来的 ${base} ${unit}平均分成四份，新增的是其中一份。` : `两个加数都以原来的 ${base} ${unit}为基准，把共同的数提到括号外，就能写成乘法。`;
    }
  }
  if (card==='offer' && used>=items.length) {
    turn.card=undefined;
    turn.reply='这次演示的新题都已经见过了。可以接着讨论之前的题。';
  }
  if (card==='check') {
    if (used>=items.length) return;
    turn.check = {item:used,status:'answering',answer:'',reason:''};
    turn.roundId='ROUND-'+crypto.randomUUID().slice(0,8);
  }
  s.turns.push(turn);
  if(card==='finish'){
    if(/结束讲解/.test(question)){turn.reply='本次讲解先结束，你仍然可以继续提问。';returnToParent();}
    else pauseActivity();
  }
  if (s.layout === 'book') await show('split');
  await nextTick();
  await scrollToLatest();
  if (!turn.check) prompt.value?.focus();
}
function send() {
  const s = space.value, question = s?.draft.trim();
  if (!s || !question || openCheck.value || paused.value) return;
  s.reviewingId=undefined;locateError.value='';following.value=true;
  s.draft = '';
  void append(question,chooseCard(question,lastTurn.value));
}
async function startAction(card:LessonCard, request:string) {
  if(space.value){space.value.reviewingId=undefined;locateError.value='';following.value=true;}
  await append(request,card);
}
function saveDraft(field:'answer'|'reason',value:string) {
  if (openCheck.value) openCheck.value[field]=value;
}
async function finishCheck(status:Exclude<Check['status'],'answering'>) {
  const c = openCheck.value;
  if (!c || (status==='submitted' && !c.answer.trim())) return;
  c.status = status;
  const a=active.value;
  if(a){a.state='轮后处置';if(status==='help'){a.helped=true;a.plan=a.used;}
    if(status==='submitted'&&(a.used||0)>=(a.plan||1)){lastTurn.value!.feedback=true;}}
  notice(`第${a?.used||1}题检测轮已结束`,status==='help'?'草稿已保留。接下来可以讲解或答疑，旧轮不再提交。':status==='submitted'?'作答已提交，可以查看结果或继续本次检测。':'未提交内容作为草稿保留，不算答错。');
  await nextTick();
  await scrollToLatest();
}
async function roundHelp(){
  const s=space.value;if(!s||openCheck.value||active.value?.kind!=='检测')return;
  active.value.helped=true;active.value.plan=active.value.used;
  await append('用图再讲一次','diagram');
}
function endAssessment(){const s=space.value;if(!s)return;s.turns.filter(t=>t.activityId===active.value?.id&&t.check?.status==='submitted').forEach(t=>t.feedback=true);returnToParent();}
</script>

<template><main class="student">
  <header class="mast"><strong>DeerMind</strong><span>{{demoMode?'活动森林示例 · Mock':'学生端 · 模拟课程'}} · <a :href="demoMode?'?mode=records':'?preview=activities'">{{demoMode?'查看原有记录':'查看活动示例'}}</a></span></header>
  <p v-if="error" role="alert">{{error}}</p>
  <form v-if="!space" class="setup" @submit.prevent="createSpace">
    <h1>创建学习空间</h1><p>选一本教材和这次想学会的目标。</p>
    <label>教材<select aria-label="教材" v-model="bookChoice" @change="targetChoice=''"><option disabled value="">选择教材</option><option :value="bookId">{{bookName}}</option></select></label>
    <label>学习目标<select aria-label="学习目标" v-model="targetChoice" :disabled="!bookChoice"><option disabled value="">选择学习目标</option><option :value="targetId">{{goal}}</option></select></label>
    <p v-if="targetChoice">可从「分数的应用（一）」开始学习。</p>
    <button class="primary" :disabled="!targetChoice">创建并进入教材</button>
  </form>
  <template v-else>
    <header class="course"><div><strong>{{bookName}}</strong><small>学习目标 · {{goal}}</small></div>
    </header>
    <div class="desk" :class="{split:space.layout==='split','with-directory':space.directoryOpen&&!narrow}">
      <button v-if="space.directoryOpen&&narrow" class="directory-backdrop" aria-label="关闭活动目录" @click="toggleDirectory(false)"></button>
      <ActivityDirectory v-if="space.directoryOpen" :class="{'directory-overlay':narrow}" :activities="space.activities" :active-id="space.activeId" :reviewing-id="space.reviewingId" :expanded="space.expandedActivities" @close="toggleDirectory(false)" @toggle="toggleBranch" @locate="locateActivity"/>
      <section v-if="space.layout!=='book'" class="chat" aria-label="持续对话">
        <header class="chat-heading">
          <button v-if="!space.directoryOpen" class="directory-open" aria-label="展开活动目录" @click="toggleDirectory(true)">活动</button>
          <div class="activity-heading" aria-label="当前活动">
            <div v-if="active" class="activity-path" :class="{'path-expanded':expandedPath}" aria-label="活动路径">
              <template v-for="(item,i) in visiblePath" :key="item?.id||'more'">
                <span v-if="i" class="path-separator" aria-hidden="true">›</span>
                <button v-if="!item" class="path-more" aria-label="展开完整活动路径" @click="expandedPath=true">…</button>
                <strong v-else-if="item.id===active.id" aria-current="step">{{item.kind}}</strong>
                <span v-else class="path-parent" :title="item.kind+'：'+item.title">{{item.kind}}：{{item.title}}</span>
              </template>
              <button v-if="expandedPath&&activityPath.length>3" class="path-more" @click="expandedPath=false">收起路径</button>
            </div>
            <h2 v-else>对话</h2>
            <div v-if="active" class="activity-subtitle"><span>{{active.title}}</span><small v-if="paused" class="activity-state">已暂停</small><small v-else-if="active.kind==='检测'" class="activity-state">{{activeRound?'第'+active.used+'题 · '+(openCheck?'独立作答中':'本轮已结束'):'准备检测'}}</small></div>
          </div>
          <button v-if="space.layout==='split'" @click="show('book')">收起对话</button><button v-else @click="show('split')">展开教材</button>
        </header>
        <div v-if="reviewing||!following" class="review-banner" role="status"><div><strong>{{reviewing?'正在回看：'+reviewing.title:'正在回看对话'}}</strong><small>{{locateError||(active?'输入仍继续当前活动，不会切换到历史活动。':'继续输入将开始新的活动，不会重新打开历史活动。')}}</small></div><button @click="returnToCurrent">{{active?'回到当前活动':'回到最新消息'}}</button></div>
        <div ref="transcript" class="transcript" role="log" @scroll="trackChatPosition">
          <p v-if="!space.turns.length" class="muted">想从哪里开始？可以直接提问，也可以让我讲解一个内容。</p>
          <template v-for="(turn,i) in [...space.turns,undefined]" :key="i">
            <div v-for="(entry,n) in noticesAt(i)" :key="n" class="activity-notice" :class="{'activity-highlight':entry.startId&&highlighted===entry.startId}" :data-activity-start="entry.startId" :tabindex="entry.startId?-1:undefined">
              <strong>{{entry.text}}</strong><small v-if="entry.detail">{{entry.detail}}</small>
              <button v-if="canResume(entry.resumeId)" :disabled="!!openCheck" @click="resumeActivity(entry.resumeId)">继续这段活动</button>
            </div>
            <article v-if="turn" :data-activity-id="turn.activityId" tabindex="-1" :class="{'activity-highlight':highlighted===turn.activityId&&!space.notices.some(n=>n.startId===turn.activityId)&&space.turns.findIndex(t=>t.activityId===turn.activityId)===i}"><small v-if="turn.bookReference" class="book-reference">引用教材 · {{turn.bookReference.chapter}} · 第 {{turn.bookReference.page}} 页</small><p class="question">{{turn.question}}</p><p v-if="turn.reply">{{turn.reply}}</p><LessonMessage :turn="turn" :latest="!!active && turn.activityId===active.id && !paused && i===space.turns.length-1" @action="startAction" @draft="saveDraft" @finish-check="finishCheck"/></article>
          </template>
          <div v-if="!active&&space.activities.filter(a=>!a.parentId&&a.status==='已结束').at(-1)?.kind==='讲解'" class="lesson-actions"><button @click="startAction('offer','我想测一下')">测一测</button><button @click="prompt?.focus()">继续提问</button></div>
          <section v-if="active" class="activity-progress" aria-label="当前学习进度">
            <div class="lesson-actions">
              <button v-if="paused" @click="resumeActivity()">继续刚才的学习</button>
              <template v-else>
                <button v-if="active.parentId&&!openCheck&&active.kind!=='检测'" @click="append('回到原来的主线','return')">回到原来的主线</button>
                <template v-if="active.kind==='检测'&&!openCheck">
                  <button v-if="(active.used||0)<(active.plan||0)||active.helped" :disabled="space.turns.filter(t=>t.check).length>=items.length" @click="append('继续检测','check')">{{active.helped?'用新题重新确认':'下一轮'}}</button>
                  <button @click="roundHelp">讲讲刚才这道题</button><button @click="endAssessment">结束本次检测</button>
                </template>
                <button @click="pauseActivity">暂停学习</button>
                <button v-if="!openCheck&&active.kind!=='检测'&&!active.parentId" @click="returnToParent">结束当前活动</button>
              </template>
            </div>
          </section>
        </div>
      </section>
      <section v-if="space.layout!=='chat'" class="reader" aria-label="教材阅读">
        <header><div><small>教材</small><h2>{{chapter.name}}</h2></div><label>章节<select aria-label="章节" :value="chapter.name" @change="readChapter(($event.target as HTMLSelectElement).value)"><optgroup v-for="unit in book.units" :key="unit.id" :label="unit.name"><option v-for="c in unit.chapters" :key="c.id">{{c.name}}</option></optgroup></select></label><button v-if="space.layout==='split'" @click="show('chat')">收起教材</button></header>
        <div ref="paper" class="paper" :key="page.id"><img :src="page.image" @load="restorePaper" :alt="chapter.name+'，教材第 '+page.printedPage+' 页'"></div>
        <footer><button :disabled="pages.indexOf(page)===0" @click="readPage(pages[pages.indexOf(page)-1].printedPage)">上一页</button><span>第 {{page.printedPage}} 页</span><button :disabled="pages.indexOf(page)===pages.length-1" @click="readPage(pages[pages.indexOf(page)+1].printedPage)">下一页</button></footer>
      </section>
      <form class="composer" @submit.prevent="send">
        <div class="composer-heading"><label for="student-prompt">问 DeerMind</label><button v-if="space.layout==='book'&&!space.directoryOpen" class="directory-open" type="button" aria-label="展开活动目录" @click="toggleDirectory(true)">活动</button><button v-if="space.layout==='book'" type="button" @click="show('split')">展开对话</button></div>
        <p v-if="paused">已保存进度。<button type="button" @click="resumeActivity()">继续刚才的学习</button></p>
        <p v-else-if="openCheck">正在独立作答。<button type="button" @click="show(space.layout==='book'?'split':space.layout); nextTick(()=>transcript?.querySelector('input')?.focus())">回到答题区</button></p>
        <template v-else>
          <button v-if="!space.turns.length" class="start-example" type="button" @click="startAction('example','讲讲增加四分之一')">讲讲增加四分之一</button>
          <div v-if="!space.turns.length" class="lesson-actions"><button type="button" @click="startAction('offer','我想直接检测')">直接测一测</button><button type="button" @click="startAction('question','分母为什么不能为零？')">问一个问题</button></div>
          <div><textarea id="student-prompt" ref="prompt" v-model="space.draft" rows="2" placeholder="想学什么，或有什么问题？" @keydown.enter.exact="!$event.isComposing && ($event.preventDefault(),send())"></textarea><button class="primary" :disabled="!space.draft.trim()">发送</button></div>
        </template>
      </form>
    </div>
  </template>
</main></template>
