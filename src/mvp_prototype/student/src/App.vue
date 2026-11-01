<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue';
import { useLiveWorkspace, type ClassroomReport } from './live';
import ClassroomProgressDialog from './components/ClassroomProgressDialog.vue';
import {createTeachingSession,scenarios,type Scenario} from './teaching-session';
import StudentPages from './components/StudentPages.vue';
import { demoCourse } from './student-pages';
import { flowCourse, teachingCourse } from './course-page-data';
import ConversationPane from './components/ConversationPane.vue';
import { conversationStorageKey, seedConversation, courseWithConversation, currentActivity, requestActivity, sendConversation, finishActivity, type Conversation, type ConversationRequest } from './conversation';
const params=new URLSearchParams(location.search);
const scenario=params.get('teaching') as Scenario;
const teaching=scenario&&Object.prototype.hasOwnProperty.call(scenarios,scenario)?createTeachingSession(scenario,params.get('context')||'textbook'):undefined;
const pageOnlyPreview=params.get('preview')==='pages';
const live = useLiveWorkspace(!teaching && !pageOnlyPreview);
const pagePreview=ref<{text:string;reply:string}|undefined>();
const conversationRef=ref<InstanceType<typeof ConversationPane>|null>(null);
const conversations=reactive<Record<string,Conversation>>({});
const conversationError=ref(''),pendingSpace=ref<LearningSpace|null>(null);
try { Object.assign(conversations,JSON.parse(localStorage.getItem(conversationStorageKey)||'{}')); } catch { conversationError.value='历史记录读取失败，当前使用示例内容；原存储不会被自动覆盖。'; }
watch(conversations,value=>{if(conversationError.value)return;try{localStorage.setItem(conversationStorageKey,JSON.stringify(value));}catch{conversationError.value='本机保存失败，请暂时保留此页，刷新后可能无法恢复本次输入。';}},{deep:true});
if(teaching){live.workspace.page=teaching.state.page as PageId;live.workspace.visible=teaching.state.visible;live.workspace.collapsed=teaching.state.collapsed;}
const progressOpen = ref(false);
const report = computed(() => live.workspace.classroom[live.workspace.space]?.slice(-1)[0]);
function saveProgress(value: ClassroomReport) {
  live.workspace.classroom[live.workspace.space] = [...(live.workspace.classroom[live.workspace.space] || []), value];
  progressOpen.value = false;
}
import { courseFlow } from './course-flow';
import { beginLesson, endLesson, chapterReady, sendLessonMessage } from '../../shared/learning-flow';
import CreateSpaceDialog from './components/CreateSpaceDialog.vue';
import type { LearningState } from './types';
import ChatWorkspace from './components/ChatWorkspace.vue';
import BottomInputBar from './components/BottomInputBar.vue';

const state = reactive<LearningState>({
  currentChapter: 'c4-3',
  chapterTitle: '比例的应用',
  masteryPercent: 65,
  classroomProgress: '六下·第四单元',
  mode: 'idle',
  lecturePhase: undefined,
  lectureTopic: undefined,
});

const modeLabelMap: Record<string, string> = {
  'lecture': '讲解中',
  'problem': '讲题中',
  'error-check': '错题检测中',
  'review': '复习中',
  'qa': '问答中',
  'idle': '学习中',
};
const activityLabel = computed(() => teaching ? teaching.label.value : isCourseFlow.value && activeFlow.value ? activeFlow.value.stage === 'testing' ? '检测中' : activeFlow.value.stage === 'finished' ? '本次已结束' : '学习中' : modeLabelMap[state.mode] || '学习中');

type PageId = 'home' | 'status' | 'textbook' | 'errorbook';
const currentPage = computed<PageId>({get:() => live.workspace.page,set:v => live.workspace.page = v});
const inActivity = computed({get:() => live.workspace.visible,set:v => live.workspace.visible = v});
const chatCollapsed = computed({get:() => live.workspace.collapsed,set:v => live.workspace.collapsed = v});
const chatRef = ref<InstanceType<typeof ChatWorkspace> | null>(null);

// 学习空间
interface LearningSpace {
  id: string;
  subject: string;
  grade: string;
  label: string;
  icon: string;
}
const demoSpaces: LearningSpace[] = [
  { id: 'math-6b', subject: '数学', grade: '六年级下册', label: '数学·六下', icon: '🔢' },
  { id: 'chinese-6b', subject: '语文', grade: '六年级下册', label: '语文·六下', icon: '📖' },
  { id: 'english-6b', subject: '英语', grade: '六年级下册', label: '英语·六下', icon: '🔤' },
  { id: 'math-5b', subject: '数学', grade: '五年级下册', label: '数学·五下', icon: '🔢' },
];
const learningSpaces = computed<LearningSpace[]>(()=>[...demoSpaces,...courseFlow.spaces.map(s=>({id:s.id,subject:'数学',grade:'已选课程',label:s.name,icon:'📖'}))]);
const selectedSpaceId = ref(live.workspace.space);
const currentSpace = computed(()=>learningSpaces.value.find(s=>s.id===selectedSpaceId.value)||demoSpaces[0]!);
if(teaching){state.mode='lecture';state.sessionTitle='分清两层分数各对应谁';}
watch([currentPage,inActivity,chatCollapsed],()=>{if(teaching){teaching.state.page=currentPage.value;teaching.state.visible=inActivity.value;teaching.state.collapsed=chatCollapsed.value;}});
const createSpaceOpen = ref(false),flowError=ref('');
const flowActivityId=ref(courseFlow.lessons.filter(a=>a.spaceId===selectedSpaceId.value).slice(-1)[0]?.id||'');
const isCourseFlow=computed(()=>courseFlow.spaces.some(s=>s.id===currentSpace.value.id));
const activeFlow=computed(()=>courseFlow.lessons.find(a=>a.id===flowActivityId.value));
watch(activeFlow,a=>{if(isCourseFlow.value&&a){state.mode=a.stage==='testing'?'error-check':'lecture';state.sessionTitle=a.snapshot.book.units.flatMap(u=>u.chapters).find(ch=>ch.id===a.chapterId)?.name||'学习';}},{immediate:true});
function createdSpace(id:string){createSpaceOpen.value=false;selectSpace(learningSpaces.value.find(s=>s.id===id)!);currentPage.value='textbook';}
function startCourse(chapterId:string,mode:'lesson'|'test'){
  try{flowActivityId.value=beginLesson(currentSpace.value.id,chapterId,mode);flowError.value='';state.mode=mode==='test'?'error-check':'lecture';state.sessionTitle=activeFlow.value?.snapshot.book.units.flatMap(u=>u.chapters).find(ch=>ch.id===activeFlow.value?.chapterId)?.name||'学习';enterActivity();}catch(e){flowError.value=(e as Error).message;}
}
function resumeCourse(id:string){flowActivityId.value=id;state.mode='lecture';state.sessionTitle=activeFlow.value?.snapshot.book.units.flatMap(u=>u.chapters).find(ch=>ch.id===activeFlow.value?.chapterId)?.name||'学习';enterActivity();}

const isLive = computed(() => !teaching && !pageOnlyPreview && !pagePreview.value && currentSpace.value.id === 'math-6b');
const baseCourse=computed(()=>teaching?teachingCourse(teaching):isCourseFlow.value?flowCourse(courseFlow,currentSpace.value.id):demoCourse(currentSpace.value.id,currentSpace.value.label));
const conversation=computed(()=>conversations[currentSpace.value.id]!);
watch(baseCourse,course=>{if(pageOnlyPreview&&!conversations[course.id])conversations[course.id]=seedConversation(course);},{immediate:true});
const studentCourse=computed(()=>pageOnlyPreview?courseWithConversation(baseCourse.value,conversation.value):baseCourse.value);
function conversationRequest(request:ConversationRequest){enterActivity();requestActivity(conversation.value,request);void nextTick(()=>conversationRef.value?.latest());}
const progressUnits=computed(()=>[...new Set(studentCourse.value.chapters.map(c=>c.unit))].map(name=>({id:name,name,chapters:studentCourse.value.chapters.filter(c=>c.unit===name)})));
function previewPageAction(text:string,reply='我们先把这个问题讲清楚。可以从题目中找出已知条件，再说明你想求的量。你也可以直接追问。'){
  pagePreview.value={text,reply};state.mode='lecture';state.sessionTitle='当前内容';enterActivity();
}
function pageAction(text:string){
  if(pageOnlyPreview){
    const question=studentCourse.value.questions.find(q=>text.includes(q.text));
    const chapter=studentCourse.value.chapters.find(ch=>text.includes(ch.name));
    conversationRequest({kind:'答疑',title:question?'题目答疑':chapter?.name||'学习要求答疑',chapters:question?[question.chapterId]:chapter?[chapter.id]:[],text});return;
  }
  if(teaching){handleStartAction(text);return;}
  if(isCourseFlow.value){
    const chapter=studentCourse.value.chapters.find(c=>text.includes(c.name));
    const question=studentCourse.value.questions.find(q=>text.includes(q.text));
    const a=courseFlow.lessons.filter(a=>a.spaceId===currentSpace.value.id&&a.chapterId===(chapter?.id||question?.chapterId)).slice(-1)[0];
    if(a){pagePreview.value=undefined;sendLessonMessage(a.id,text);resumeCourse(a.id);return;}
  }
  previewPageAction(text);
}
function pageStart(ids:string[],mode:'lesson'|'test'){
  if(pageOnlyPreview){
    const title=studentCourse.value.chapters.filter(ch=>ids.includes(ch.id)).map(ch=>ch.name).join('、');
    if(mode==='test'&&(ids.length!==1||ids[0]!=='c4-3')){conversationRequest({kind:'答疑',title:'准备检测：'+title,chapters:ids,text:'准备检测：'+title});return;}
    conversationRequest({kind:mode==='test'?'检测':'讲解',title:mode==='test'?title+'检测':title,chapters:ids,text:(mode==='test'?'我想检测：':'请讲解：')+title});return;
  }
  pagePreview.value=undefined;
  if(teaching){enterActivity();if(mode==='test')teaching.offer();return;}
  if(isCourseFlow.value&&ids.length===1&&chapterReady(courseFlow.courses.find(c=>c.id===courseFlow.spaces.find(s=>s.id===currentSpace.value.id)?.courseId)!.snapshot,ids[0]!).scripted){startCourse(ids[0]!,mode);return;}
  const names=studentCourse.value.chapters.filter(c=>ids.includes(c.id)).map(c=>c.name).join('、');
  previewPageAction((mode==='test'?'准备检测：':'请讲解：')+names,mode==='test'?'本次选择的范围是：'+names+'。接下来会根据这些章节的学习要求准备题目，并在开始前说明题量和预计用时。':'我们围绕“'+names+'”展开。先明确当前想解决的一个问题，再分段解释；你可以随时追问或结束。');
}
function pageResume(id:string){
  if(pageOnlyPreview){
    const a=conversation.value.activities.find(a=>a.id===id);if(!a)return;
    if(a.status==='已结束'){pageHistory(id);return;}
    conversationRequest({kind:a.kind,title:a.title,chapters:a.chapters,text:'继续上次的'+a.title,resumeId:a.id,reference:conversation.value.messages.find(m=>m.activityId===a.id&&m.role==='assistant')?.id});return;
  }
  pagePreview.value=undefined;
  if(teaching){enterActivity();return;}
  if(isCourseFlow.value){resumeCourse(id.replace(/:test$/,''));return;}
  const a=studentCourse.value.activities.find(a=>a.id===id);
  previewPageAction('回到学习：'+(a?.title||'上次学习'),id==='DEMO-L2'?'上次我们看到图中有原长80米和新增的一段。80 × 1/4 得到20米，只是新增的部分。题目要求现在的总长，需要把原长加回来。你想先看图，还是说说两段分别表示什么？':a?.detail||'回看当时的学习内容。');
}
watch([live.activity, isLive], () => {
  const a = live.activity.value;
  if (isLive.value && a) Object.assign(state, {mode:a.mode,lecturePhase:a.phase || undefined,sessionTitle:a.title});
});
const spaceDropdownOpen = ref(false);

function selectSpace(space: LearningSpace) {
  if(pageOnlyPreview && currentActivity(conversation.value)?.kind==='检测'){pendingSpace.value=space;spaceDropdownOpen.value=false;return;}
  if(activeFlow.value?.stage==='testing'){flowError.value='请先完成或结束当前检测，再切换学习空间。';return;}
  pagePreview.value=undefined;
  selectedSpaceId.value = space.id;
  flowActivityId.value=courseFlow.lessons.filter(a=>a.spaceId===space.id).slice(-1)[0]?.id||'';
  live.workspace.space = space.id;
  progressOpen.value = false;
  spaceDropdownOpen.value = false;
  // 切换学习空间时重置状态
  state.mode = 'idle';
  state.lecturePhase = undefined;
  state.sessionTitle = undefined;
  inActivity.value = false;
  chatCollapsed.value = false;
}
function confirmSpace(){const next=pendingSpace.value;if(!next)return;finishActivity(conversation.value,'切换学习空间，结束检测');pendingSpace.value=null;selectSpace(next);}
function pageHistory(id:string){
  if(!pageOnlyPreview){pageResume(id);return;}
  const m=conversation.value.messages.find(m=>m.activityId===id&&m.role!=='event');
  enterActivity();void nextTick(()=>m?conversationRef.value?.locate(m.id):conversationRef.value?.latest());
}

const navItems = [
  { id: 'home' as PageId, label: '首页', icon: '🏠' },
  { id: 'status' as PageId, label: '学习', icon: '📊' },
  { id: 'textbook' as PageId, label: '教材', icon: '📖' },
  { id: 'errorbook' as PageId, label: '题目', icon: '📝' },
];

function updateState(partial: Partial<LearningState>) {
  if (isLive.value) return;
  Object.assign(state, partial);
}

function enterActivity() {
  inActivity.value = true;
  chatCollapsed.value = false;
}

async function exitActivity() {
  if(pagePreview.value){inActivity.value=false;pagePreview.value=undefined;return;}
  if(teaching){teaching.finish();return;}
  if(isCourseFlow.value && activeFlow.value) endLesson(activeFlow.value.id);
  if (isLive.value && (live.workspace.sessionId || live.workspace.operation)) {
    if (!await live.command('end')) return;
  }
  inActivity.value = false;
  chatCollapsed.value = false;
}

function toggleChatCollapse() {
  chatCollapsed.value = !chatCollapsed.value;
}

async function handleBottomSend(text: string) {
  if(pageOnlyPreview){enterActivity();sendConversation(conversation.value,text,baseCourse.value);return;}
  if(teaching){enterActivity();teaching.submit(text);return;}
  enterActivity();
  await nextTick();
  if (isCourseFlow.value) {
    if(!flowActivityId.value){
      const space=courseFlow.spaces.find(s=>s.id===currentSpace.value.id),course=courseFlow.courses.find(c=>c.id===space?.courseId);
      const chapter=course?.snapshot.book.units.flatMap(u=>u.chapters).find(ch=>chapterReady(course.snapshot,ch.id).explain&&chapterReady(course.snapshot,ch.id).scripted);
      if(!chapter){flowError.value='请先选择已准备好的教材章节。';return;}startCourse(chapter.id,'lesson');await nextTick();
    }
    chatRef.value?.injectMessage(text);return;
  }
  if (isLive.value) { await live.command('message', text); return; }
  // 根据输入内容推断初始模式
  const lower = text.toLowerCase();
  if (lower.includes('讲') || lower.includes('不懂') || lower.includes('没听懂')) {
    state.mode = 'lecture';
    state.sessionTitle = state.chapterTitle;
  } else if (lower.includes('复习')) {
    state.mode = 'review';
    state.sessionTitle = state.chapterTitle;
  } else if (lower.includes('错题') || lower.includes('检测')) {
    state.mode = 'error-check';
    state.sessionTitle = '错题检测';
  } else if (lower.includes('题') || lower.includes('不会')) {
    state.mode = 'problem';
    state.sessionTitle = '题目讲解';
  } else {
    state.mode = 'qa';
  }
  setTimeout(() => chatRef.value?.injectMessage(text), 50);
}

function handleStartAction(text: string) {
  if(teaching){enterActivity();teaching.submit(text);return;}
  enterActivity();
  if (isLive.value) { void live.command('message', text); return; }
  // 根据动作文本推断模式
  if (text.includes('讲') || text.includes('复习')) {
    state.mode = text.includes('复习') ? 'review' : 'lecture';
    state.sessionTitle = state.chapterTitle;
  } else if (text.includes('错题') || text.includes('检测')) {
    state.mode = 'error-check';
    state.sessionTitle = '错题检测';
  } else if (text.includes('题') || text.includes('不会')) {
    state.mode = 'problem';
    state.sessionTitle = '题目讲解';
  } else {
    state.mode = 'qa';
  }
  setTimeout(() => chatRef.value?.injectMessage(text), 50);
}

function switchPage(page: PageId) {
  currentPage.value = page;
}
</script>

<template>
  <div class="app">
    <!-- 顶部导航栏 -->
    <header class="top-nav">
      <div class="nav-left">
        <span class="logo">🦌 DeerMind</span>
        <nav class="nav-items">
          <button v-for="item in navItems" :key="item.id"
            class="nav-item" :class="{active: currentPage === item.id}"
            @click="switchPage(item.id)">
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </button>
        </nav>
      </div>
      <div class="nav-right">
        <span v-if="inActivity && !pageOnlyPreview" class="activity-indicator">
          <span class="ai-dot"></span>
          {{ activityLabel }}
          <button class="ai-close" @click="exitActivity">结束 ×</button>
        </span>
        <!-- 学习空间选择 -->
        <span v-if="teaching" class="teaching-space">数学 · 六上 · 情境演示</span>
        <div v-else class="space-selector" :class="{ open: spaceDropdownOpen }">
          <button class="space-trigger" @click="spaceDropdownOpen = !spaceDropdownOpen">
            <span>{{ currentSpace.icon }}</span>
            <span>{{ currentSpace.label }}</span>
            <span class="dropdown-arrow">▼</span>
          </button>
          <div v-if="spaceDropdownOpen" class="space-dropdown">
            <div class="dropdown-header">选择学习空间</div>
            <button v-for="space in learningSpaces" :key="space.id"
              class="space-option" :class="{ active: space.id === currentSpace.id }"
              @click="selectSpace(space)">
              <span class="space-icon">{{ space.icon }}</span>
              <div class="space-info">
                <div class="space-label">{{ space.label }}</div>
                <div class="space-sub">{{ space.grade }}</div>
              </div>
              <span v-if="space.id === currentSpace.id" class="space-check">✓</span>
            </button>
            <button class="space-option" :disabled="activeFlow?.stage==='testing'" @click="createSpaceOpen=true;spaceDropdownOpen=false">＋ 新建学习空间</button>
          </div>
        </div>
        <span class="user-avatar">学</span>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content" :class="{ 'split-view': inActivity && !chatCollapsed, 'collapsed-view': inActivity && chatCollapsed }">
      <!-- 聊天区（展开时左侧，收起时底部） -->
      <div v-if="inActivity" class="chat-pane" :class="{ collapsed: chatCollapsed }">
        <ConversationPane v-if="pageOnlyPreview" ref="conversationRef" :key="currentSpace.id" :conversation="conversation" :course="studentCourse" :collapsed="chatCollapsed" @toggle-collapse="toggleChatCollapse"/>
        <ChatWorkspace v-else
          ref="chatRef"
          :state="state"
          :teaching="pagePreview ? undefined : teaching"
          :page-preview="pagePreview"
          :key="currentSpace.id"
          :live="isLive ? live : undefined"
          :collapsed="chatCollapsed"
          :mock-activity-id="isCourseFlow && !pagePreview ? flowActivityId : undefined"
          @show-status="currentPage='status'"
          @update-state="updateState"
          @toggle-collapse="toggleChatCollapse"
        />
      </div>

      <!-- 静态页面区 -->
      <div class="static-pane" :class="{ narrowed: inActivity && !chatCollapsed }">
        <p v-if="flowError" role="alert" class="flow-error">{{flowError}}</p>
        <p v-if="pageOnlyPreview && conversationError" role="alert" class="flow-error">{{conversationError}}</p>
        <StudentPages :key="studentCourse.id" :course="studentCourse" :page="currentPage" :report="report"
          @navigate="currentPage=$event" @update-progress="progressOpen=true" @start-action="pageAction"
          @start="pageStart" @resume="pageResume" @history="pageHistory"/>
      </div>
    </main>

    <!-- 底部常驻输入条（非活动时显示） -->
    <transition name="fade">
      <BottomInputBar v-if="!inActivity" :model-value="pageOnlyPreview ? conversation.draft : isLive ? live.workspace.draft : undefined"
        :disabled="isLive && live.busy.value" @update:model-value="pageOnlyPreview ? conversation.draft=$event : live.workspace.draft = $event" @expand="enterActivity" @send="handleBottomSend" />
    </transition>
    <CreateSpaceDialog v-if="createSpaceOpen" @close="createSpaceOpen=false" @created="createdSpace"/>
    <ClassroomProgressDialog v-if="progressOpen" :available="progressUnits.length>0" :units="progressUnits" :report="report"
      @close="progressOpen = false" @save="saveProgress" />
    <div v-if="pendingSpace" class="space-switch-shade"><section role="dialog" aria-modal="true" aria-label="切换学习空间"><h3>结束当前检测，再切换空间？</h3><p>保留已提交的作答，未提交不计错。旧空间的聊天和草稿仍会保留。</p><button @click="confirmSpace">结束检测并切换空间</button><button @click="pendingSpace=null">继续检测</button></section></div>
  </div>
</template>

<style scoped>
.space-switch-shade{position:fixed;inset:0;z-index:80;background:#17392e55;display:grid;place-items:center}.space-switch-shade section{max-width:460px;background:white;padding:24px;border-radius:12px;color:#234b42}.space-switch-shade button{padding:9px;margin:8px 8px 0 0;border:1px solid #b9cec2;border-radius:6px;background:#edf5f0;color:#28664f;cursor:pointer}
.teaching-space{font-size:12px;color:#75857c}
.flow-error{margin:12px 24px;padding:12px;background:#fff4e5;color:#8c5b25;border-radius:6px}
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #f7f9fa;
}

/* 顶部导航 */
.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 52px;
  background: white;
  border-bottom: 1px solid #e1e8ed;
  flex-shrink: 0;
}
.nav-left { display: flex; align-items: center; gap: 24px; }
.logo { font-size: 16px; font-weight: 700; color: #1b4332; }
.nav-items { display: flex; gap: 4px; }
.nav-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px; border: none; background: none;
  font-size: 13px; color: #5a6b7a; cursor: pointer; font-family: inherit;
  border-radius: 6px; transition: all 0.15s;
}
.nav-item:hover { background: #f0f4f7; color: #2c3e50; }
.nav-item.active { background: #e8f5ee; color: #1b4332; font-weight: 600; }
.nav-icon { font-size: 14px; }
.nav-right { display: flex; align-items: center; gap: 12px; }
.activity-indicator {
  display: flex; align-items: center; gap: 8px;
  background: #e8f5ee; color: #1b4332;
  padding: 4px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;
}
.ai-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #2d8a5e; animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.ai-close {
  background: none; border: none; color: #5a7a6a; cursor: pointer;
  font-size: 12px; font-family: inherit; padding: 0 0 0 8px;
  border-left: 1px solid #c8e0d4; margin-left: 4px;
}
.ai-close:hover { color: #1b4332; }

/* 学习空间选择器 */
.space-selector {
  position: relative;
}
.space-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f0f4f7;
  border: 1px solid transparent;
  color: #5a6b7a;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.space-trigger:hover {
  background: #e8f5ee;
  border-color: #40916c;
  color: #1b4332;
}
.space-selector.open .space-trigger {
  background: #e8f5ee;
  border-color: #40916c;
  color: #1b4332;
}
.dropdown-arrow {
  font-size: 8px;
  transition: transform 0.2s;
}
.space-selector.open .dropdown-arrow {
  transform: rotate(180deg);
}
.space-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: white;
  border: 1px solid #e1e8ed;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  min-width: 200px;
  z-index: 100;
  overflow: hidden;
}
.dropdown-header {
  padding: 8px 14px;
  font-size: 11px;
  color: #8a99a8;
  border-bottom: 1px solid #f0f4f7;
  background: #fafbfc;
}
.space-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 14px;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: background 0.15s;
}
.space-option:hover {
  background: #f0f7f4;
}
.space-option.active {
  background: #e8f5ee;
}
.space-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
}
.space-info {
  flex: 1;
}
.space-label {
  font-size: 13px;
  font-weight: 500;
  color: #2c3e50;
}
.space-sub {
  font-size: 11px;
  color: #8a99a8;
  margin-top: 1px;
}
.space-check {
  color: #2d8a5e;
  font-weight: 600;
  font-size: 14px;
}
.user-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #2d6a4f, #40916c);
  color: white; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
}

/* 主内容区 */
.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: row;
}
/* 收起时：上下布局 */
.main-content.collapsed-view {
  flex-direction: column;
}

.static-pane {
  flex: 1;
  overflow: hidden;
  transition: flex 0.3s ease;
  min-width: 0;
}
/* 展开时：静态内容占40% */
.static-pane.narrowed {
  flex: 0 0 40%;
  border-left: 1px solid #e1e8ed;
}
/* 收起时：静态内容占满 */
.main-content.collapsed-view .static-pane {
  flex: 1;
  border-left: none;
  order: 1;
}

/* 聊天区 */
.chat-pane {
  flex: 0 0 60%;
  min-width: 0;
  display: flex;
  background: #f7f9fa;
  transition: flex 0.3s ease;
}
/* 收起时：聊天区变为底部横条 */
.chat-pane.collapsed {
  flex: 0 0 auto;
  border-top: 1px solid #e1e8ed;
  order: 2;
}

/* 底部输入条淡入 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

@media (max-width: 900px) {
  .top-nav { padding:0 12px; height:auto; min-height:52px; flex-wrap:wrap; gap:6px; }
  .nav-left { gap:8px; }
  .nav-item { padding:6px 8px; }
  .logo { font-size:14px; }
  .nav-right { gap:6px; }
  .chat-pane { flex:0 0 55%; }
  .static-pane.narrowed { flex:0 0 45%; }
}
</style>
