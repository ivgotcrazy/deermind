<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { emptyTextbook } from '../model/textbook';
import { prepareRealBook } from '../model/material-fixture';
import LessonMessage from './LessonMessage.vue';
import { chooseCard, cardReply, items, type Turn, type LessonCard, type Check, type Activity } from './quarter';
import './student.css';

// A snapshot of the course offered to this trial learner. Admin drafts are never read as applied courses.
const book = prepareRealBook(emptyTextbook());
const bookName = '北师大版数学六年级上册';
const goal = '能自己算出增加四分之一后的数量，并说明为什么';
const bookId = 'BNU-6A';
const targetId = 'TARGET-M1-QUARTER-SEPARATE';
const chapters = book.units.flatMap(unit => unit.chapters);
const teachingChapter = '分数的应用（一）';
type Layout = 'book' | 'split' | 'chat';
type Space = { bookId: string; targetId: string; chapter: string; page: string; layout: Layout; paperPosition: number; chatPosition: number; draft: string; turns: Turn[]; activities:Activity[]; activeId?:string };
const key = 'deermind-m1-student-trial-space-v1';
const error = ref('');
function restore(): Space | null {
  try {
    const data = JSON.parse(localStorage.getItem(key) || 'null') as (Partial<Space> & {teaching?: boolean}) | null;
    if (data?.bookId === bookId && data.targetId === targetId && Array.isArray(data.turns)) {
      const layout = data.layout ?? (data.teaching ? 'split' : 'book');
      return {bookId, targetId, chapter:data.chapter || teachingChapter, page:data.page || '49',
        layout:['book','split','chat'].includes(layout) ? layout : 'book', paperPosition:data.paperPosition ?? 0,
        chatPosition:data.chatPosition ?? -1, draft:data.draft || '', turns:data.turns,activities:data.activities||[],activeId:data.activeId};
    }
  } catch { error.value = '未能读取这台设备上的学习空间。'; }
  return null;
}
const space = ref<Space | null>(restore());
const bookChoice = ref(''), targetChoice = ref('');
const chapter = computed(() => chapters.find(c => c.name === space.value?.chapter) || chapters[0]);
const pages = computed(() => chapter.value.locations);
const page = computed(() => pages.value.find(p => p.printedPage === space.value?.page) || pages.value[0]);
const canTeach = computed(() => chapter.value.name === teachingChapter);
const transcript = ref<HTMLElement | null>(null);
const paper = ref<HTMLElement | null>(null);
const prompt = ref<HTMLTextAreaElement | null>(null);
const lastTurn = computed(()=>space.value?.turns.at(-1));
const active=computed(()=>space.value?.activities.find(a=>a.id===space.value?.activeId));
const paused=computed(()=>active.value?.status==='暂停');
const openCheck = computed(()=>lastTurn.value?.check?.status==='answering' ? lastTurn.value.check : undefined);
watch(space, value => {
  try { if (value) localStorage.setItem(key, JSON.stringify(value)); }
  catch { error.value = '本机未能保存进度，请保持此页打开。'; }
}, {deep:true, flush:'sync'});
function createSpace() {
  if (bookChoice.value !== bookId || targetChoice.value !== targetId) return;
  space.value = { bookId, targetId, chapter: teachingChapter, page: chapters[0].locations[0].printedPage, layout:'book', paperPosition:0, chatPosition:-1, draft:'', turns:[],activities:[] };
}
function begin(kind:string,title:string,parentId?:string,triggerRound?:string){
  const s=space.value!;if(active.value)active.value.status='暂停';
  const a:Activity={id:'ACT-'+crypto.randomUUID().slice(0,8),kind,title,parentId,triggerRound,status:'进行中',state:kind==='检测'?'准备检测':'回应中'};
  s.activities.push(a);s.activeId=a.id;return a;
}
function returnToParent(){
  const s=space.value!,a=active.value;if(!a)return;
  a.status='已结束';a.state='结束';
  const parent=s.activities.find(p=>p.id===a.parentId);
  if(parent){parent.status='进行中';parent.state=parent.kind==='检测'?'轮后处置':'讲解与互动';s.activeId=parent.id;}
  else s.activeId=undefined;
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
onMounted(() => { restorePositions(); window.addEventListener('pagehide', rememberPositions); });
onBeforeUnmount(() => window.removeEventListener('pagehide', rememberPositions));
function exampleReply(question: string, printed: string) {
  if (/四分之一|增加|1\s*\/\s*4/.test(question))
    return '“增加四分之一”要先看是哪个量的四分之一。我们另举个例子：原有 80 本书，增加的是原来 80 本的四分之一，也就是 20 本。问现在共有多少本，就把这 20 本加回原来的 80 本。你想再看看为什么要加回去，还是试着自己说一遍？';
  if (/为什么|整体|参照|基准/.test(question))
    return '先找“谁的几分之几”里的“谁”。参照的量一变，同一个分数代表的人数也会变。你可以指一下书页里让你拿不准的那句话。';
  if (/讲|不懂|不会|小组|这页/.test(question))
    return printed === '49' ? '看第 49 页的三个兴趣小组。两个分数说的是不同小组之间的关系。先找已知人数的小组，再看哪个小组的人数是它的几分之几。你想先弄清哪两个小组之间的关系？' : '看第 50 页上方的两种算法。第一种先算出中间小组的人数，再用它求航模小组的人数。第二种先合并两层比例。你想先看哪一步？';
  return '我记下了你的问题。这次演示可以一起看书里的小组人数关系，也可以用“增加四分之一”举个例子。';
}
async function append(question:string, card?:LessonCard) {
  const s = space.value;
  if (!s || openCheck.value || paused.value) return;
  if(card==='check'&&s.turns.filter(t=>t.check).length>=items.length)return;
  if(card==='return'){returnToParent();}
  else if(card==='question')begin('答疑','分母为什么不能为零',active.value?.id,lastTurn.value?.roundId);
  else if(card==='free')begin('自由交谈','普通交流',active.value?.id);
  else if(card==='formula'&&active.value?.kind==='检测'){active.value.helped=true;active.value.plan=active.value.used;begin('答疑','解释本轮方法',active.value.id,lastTurn.value?.roundId);}
  else if(card==='check'){
    if(active.value?.kind!=='检测'){const a=begin('检测','增加四分之一检测',active.value?.id);a.plan=2;a.used=0;}
    if(active.value!.helped)active.value!.plan=(active.value!.used||0)+1;
    active.value!.state='检测轮进行';active.value!.used=(active.value!.used||0)+1;
  }
  else if(card==='diagram'&&active.value?.kind==='检测'){active.value.helped=true;active.value.plan=active.value.used;begin('讲解','解释刚才的题目',active.value.id,lastTurn.value?.roundId);}
  else if(!active.value&&card!=='offer')begin(card==='formula'?'答疑':'讲解','增加四分之一');
  const turn:Turn = { question, chapter:chapter.value.name, page:page.value.printedPage,
    reply:card ? cardReply[card] : exampleReply(question,page.value.printedPage), card,activityId:active.value?.id };
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
  if(card==='finish'&&active.value)active.value.status='暂停';
  s.turns.push(turn);
  if (s.layout === 'book') await show('split');
  await nextTick();
  s.chatPosition = -1;
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight;
  if (!turn.check) prompt.value?.focus();
}
function send() {
  const s = space.value, question = s?.draft.trim();
  if (!s || !question || !canTeach.value || openCheck.value) return;
  s.draft = '';
  void append(question,chooseCard(question,lastTurn.value));
}
async function startAction(card:LessonCard, request:string) {
  if (!canTeach.value) return;
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
  await nextTick();
  if (transcript.value) transcript.value.scrollTop=transcript.value.scrollHeight;
}
async function roundHelp(){
  const s=space.value;if(!s||openCheck.value||active.value?.kind!=='检测')return;
  active.value.helped=true;active.value.plan=active.value.used;
  await append('用图再讲一次','diagram');
}
function endAssessment(){const s=space.value;if(!s)return;s.turns.filter(t=>t.activityId===active.value?.id&&t.check?.status==='submitted').forEach(t=>t.feedback=true);returnToParent();}
</script>

<template><main class="student">
  <header class="mast"><strong>DeerMind</strong><span>学生端 · 模拟课程</span></header>
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
    <div class="desk" :class="{split:space.layout==='split'}">
      <section v-if="space.layout!=='book'" class="chat" aria-label="持续对话">
        <header><h2>对话</h2><button v-if="space.layout==='split'" @click="show('book')">收起对话</button><button v-else @click="show('split')">展开教材</button></header>
        <div ref="transcript" class="transcript" role="log">
          <p v-if="!space.turns.length" class="muted">想从哪里开始？可以问问书上哪一步没看懂。</p>
          <article v-for="(turn,i) in space.turns" :key="i"><small>{{turn.chapter}} · 第 {{turn.page}} 页</small><p class="question">{{turn.question}}</p><p v-if="turn.reply">{{turn.reply}}</p><LessonMessage :turn="turn" :latest="canTeach && !paused && i===space.turns.length-1" @action="startAction" @draft="saveDraft" @finish-check="finishCheck"/></article>
          <section v-if="active" class="lesson-visual activity-progress" aria-label="当前学习进度">
            <strong>{{active.title}}</strong><p>{{paused?'已暂停，进度与草稿已保留。':active.kind==='检测'?'检测中的讲解和答疑会保留原检测记录。':active.parentId?'先处理当前问题，结束后回到原来的主线。':'可以继续、提问或暂时休息。'}}</p>
            <div class="lesson-actions">
              <button v-if="paused" @click="active.status='进行中'">继续刚才的学习</button>
              <template v-else>
                <button v-if="active.parentId&&!openCheck&&active.kind!=='检测'" @click="append('回到原来的主线','return')">回到原来的主线</button>
                <template v-if="active.kind==='检测'&&!openCheck">
                  <button v-if="(active.used||0)<(active.plan||0)||active.helped" :disabled="space.turns.filter(t=>t.check).length>=items.length" @click="append('继续检测','check')">{{active.helped?'用新题重新确认':'下一轮'}}</button>
                  <button @click="roundHelp">讲讲刚才这道题</button><button @click="endAssessment">结束本次检测</button>
                </template>
                <button @click="active.status='暂停'">暂停学习</button>
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
        <div class="composer-heading"><label v-if="canTeach" for="student-prompt">问 DeerMind <small>{{chapter.name}} · 第 {{page.printedPage}} 页</small></label><button v-if="space.layout==='book'" type="button" @click="show('split')">展开对话</button></div>
        <p v-if="paused">已保存进度。<button type="button" @click="active!.status='进行中';show('split')">继续刚才的学习</button></p>
        <p v-else-if="openCheck">正在独立作答。<button type="button" @click="show(space.layout==='book'?'split':space.layout); nextTick(()=>transcript?.querySelector('input')?.focus())">回到答题区</button></p>
        <template v-else-if="canTeach">
          <button v-if="!space.turns.length" class="start-example" type="button" @click="startAction('example','讲讲增加四分之一')">讲讲增加四分之一</button>
          <div v-if="!space.turns.length" class="lesson-actions"><button type="button" @click="startAction('offer','我想直接检测')">直接测一测</button><button type="button" @click="startAction('question','分母为什么不能为零？')">问一个问题</button></div>
          <div><textarea id="student-prompt" ref="prompt" v-model="space.draft" rows="2" placeholder="这页有哪里没看懂？" @keydown.enter.exact="!$event.isComposing && ($event.preventDefault(),send())"></textarea><button class="primary" :disabled="!space.draft.trim()">发送</button></div>
        </template>
        <p v-else>本节可阅读原页。当前目标的讲解在「{{teachingChapter}}」。 <button type="button" @click="readChapter(teachingChapter)">回到可讲解章节</button></p>
      </form>
    </div>
  </template>
</main></template>
