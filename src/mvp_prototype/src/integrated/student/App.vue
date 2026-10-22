<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatWorkspace from './components/ChatWorkspace.vue';
import BottomInputBar from './components/BottomInputBar.vue';
import HomePage from './components/HomePage.vue';
import LearningStatusPage from './components/LearningStatusPage.vue';
import TextbookPage from './components/TextbookPage.vue';
import ErrorBookPage from './components/ErrorBookPage.vue';
import { state, storageWarning, type Session } from '../../structure/state';
import { liveRequest, type LiveSession } from '../../structure/live';
import { useConversation } from './useConversation';
import { navigation, canonicalPage, contextPage, rememberContext, inputScope, useView, viewContext, type PageId } from './workspace';

const route = useRoute(), router = useRouter();
const currentPage = computed(() => canonicalPage(String(route.params.page || 'home')));
const current = computed(() => state.sessions.find(s => s.id === (route.query.chat || route.query.id) && s.real && s.learner === 'S0001' && s.space === state.studentSpace));
const conversation = useConversation(current);
const { data, checking, busy, uncertain, ready } = conversation;
const preferences = useView('shell', { collapsed: false });
const opening = ref(false), chatOpened = ref(false), notice = ref(''), spaceDropdownOpen = ref(false), historyOpen = ref(false);
const inActivity = computed(() => !!current.value || chatOpened.value);
const chatCollapsed = computed(() => preferences.collapsed && !checking.value);
const baseDraft = computed({ get: () => state.drafts[inputScope(state.studentSpace)] || '', set: (v:string) => state.drafts[inputScope(state.studentSpace)] = v });
const composerDraft = computed({ get: () => current.value ? conversation.draft.value : baseDraft.value, set: (v:string) => { if(current.value) conversation.draft.value = v; else baseDraft.value = v; } });
const sessions = computed(() => state.sessions.filter(s => s.learner === 'S0001' && s.space === state.studentSpace).sort((a,b) => (b.updatedAt||0)-(a.updatedAt||0)));
const pendingCheck = computed(() => state.sessions.find(s => s.learner === 'S0001' && s.status === 'check'));
const learningSpaces = [{ id:'school', label:'校内数学 · 六上', icon:'🔢' }, { id:'external', label:'校外数学', icon:'📖' }];
const currentSpace = computed(() => learningSpaces.find(s => s.id === state.studentSpace) || learningSpaces[0]!);

function switchPage(page:PageId) {
  notice.value = '';
  if (opening.value) return;
  if (checking.value || pendingCheck.value) { notice.value = '先提交或结束当前检查，再查看其他页面。'; return; }
  if (current.value) rememberContext(current.value.id, page);
  void router.push({ path:`/${page}`, query: current.value ? {chat:current.value.id} : {} });
}
function selectSpace(space:string) {
  if (pendingCheck.value || opening.value || busy.value || uncertain.value) { notice.value = '请先处理当前检查或回复，再切换学习空间。'; return; }
  state.studentSpace = space; spaceDropdownOpen.value = false; chatOpened.value = false; historyOpen.value = false;
  notice.value = ''; preferences.collapsed = false;
  void router.push('/home');
}
function openChat() { chatOpened.value = true; preferences.collapsed = false; }
function resume(session:Session) {
  if (opening.value || pendingCheck.value && pendingCheck.value.id !== session.id || busy.value || uncertain.value) { notice.value = '请先处理当前活动，再打开另一段对话。'; return; }
  if (!session.real) { notice.value = '这是一段保留的预写活动，可在历史列表中打开旧版记录。'; return; }
  rememberContext(session.id, currentPage.value); preferences.collapsed = false; historyOpen.value = false;
  void router.push({path:`/${currentPage.value}`, query:{chat:session.id}});
}
async function begin(text:string, chapter='fractions') {
  if (opening.value || busy.value || uncertain.value || pendingCheck.value) { notice.value = '请先处理当前活动，再开始新话题。'; return; }
  if (state.studentSpace !== 'school' || chapter !== 'fractions') { notice.value = '这个范围尚未接通真实教学。当前可以体验校内“分数的应用”，输入已保留。'; return; }
  opening.value = true; notice.value = '';
  const scope = inputScope(state.studentSpace), space = state.studentSpace;
  try {
    const remote = await liveRequest<LiveSession>('sessions', {});
    const session:Session = { id:remote.id, real:true, learner:'S0001', space, chapter, segment:0, status:'learning', answer:'', submitted:false, endedReason:'', date:new Date().toISOString().slice(0,10), updatedAt:Date.now() };
    state.sessions.unshift(session); rememberContext(session.id, currentPage.value);
    if(text.trim()) {
      state.drafts[`real:${session.id}`] = text;
      state.drafts[`real-request:${session.id}`] = JSON.stringify({requestId:crypto.randomUUID(), kind:'message', text, context:viewContext(currentPage.value)});
      if(state.drafts[scope] === text) state.drafts[scope] = '';
    }
    chatOpened.value = false; preferences.collapsed = false;
    await router.push({path:`/${currentPage.value}`, query:{chat:session.id}});
  } catch(e) { notice.value = (e as Error).message; }
  finally { opening.value = false; }
}
async function send(text:string) {
  if (!text.trim()) return;
  if (!current.value) { await begin(text); return; }
  await conversation.act(checking.value ? 'answer' : 'message', text, data.value?.check || undefined, viewContext(currentPage.value));
}
async function startAction(text:string, chapter='fractions') {
  if (state.studentSpace !== 'school' || chapter !== 'fractions') { notice.value = '该章节尚未接通真实教学，当前仅开放分数的应用。'; return; }
  openChat();
  if (current.value && data.value?.phase !== 'ended') await send(text);
  else await begin(text, chapter);
}
async function exitActivity() {
  if (current.value && (!ready.value || busy.value || uncertain.value)) return;
  if (current.value && data.value?.phase !== 'ended') await conversation.act('end');
  if (current.value && data.value?.phase !== 'ended') return;
  chatOpened.value = false; preferences.collapsed = false;
  await router.push({path:`/${currentPage.value}`});
}
watch(() => route.fullPath, () => {
  // Older bookmarked activity URLs keep the original session, never a new conversation.
  if (route.params.page === 'lesson') {
    const id = String(route.query.id || '');
    const saved = state.sessions.find(s => s.id === id && s.learner === 'S0001');
    if(saved?.real) { state.studentSpace = saved.space; void router.replace({path:`/${contextPage(id)}`, query:{chat:id}}); }
    else { notice.value = '没有找到可恢复的真实对话；原有预写活动仍保存在历史记录中。'; void router.replace('/home'); }
  } else if (route.query.chat && !current.value) notice.value = '当前空间没有这段对话，未加载其他空间的记录。';
  if (pendingCheck.value && (route.query.chat !== pendingCheck.value.id || currentPage.value !== contextPage(pendingCheck.value.id))) {
    state.studentSpace = pendingCheck.value.space;
    void router.replace({path:`/${contextPage(pendingCheck.value.id)}`,query:{chat:pendingCheck.value.id}});
  }
}, {immediate:true});
</script>

<template>
 <div class="app">
  <header class="top-nav">
   <div class="nav-left"><span class="logo">🦌 DeerMind</span><nav class="nav-items" aria-label="主导航">
    <button v-for="item in navigation" :key="item.id" class="nav-item" :class="{active:currentPage===item.id}" @click="switchPage(item.id)"><span class="nav-icon" aria-hidden="true">{{ item.icon }}</span><span class="nav-label">{{ item.label }}</span></button>
   </nav></div>
   <div class="nav-right">
    <span v-if="inActivity" class="activity-indicator"><span class="ai-dot"/>{{ checking?'检查中':'学习中' }}<button class="ai-close" :disabled="opening || !!current && (!ready || busy || !!uncertain)" @click="exitActivity">结束 ×</button></span>
    <div class="space-selector" :class="{open:spaceDropdownOpen}"><button class="space-trigger" aria-label="当前学习空间" @click="spaceDropdownOpen=!spaceDropdownOpen">{{ currentSpace.icon }} {{ currentSpace.label }} <span class="dropdown-arrow">▼</span></button>
     <div v-if="spaceDropdownOpen" class="space-dropdown"><div class="dropdown-header">选择学习空间</div><button v-for="space in learningSpaces" :key="space.id" class="space-option" :class="{active:space.id===state.studentSpace}" @click="selectSpace(space.id)">{{ space.icon }} {{ space.label }}</button></div>
    </div><button class="user-avatar" aria-label="对话历史" title="对话历史" @click="historyOpen=!historyOpen">学</button>
   </div>
  </header>
  <div class="prototype-note"><span>真实对话试用 · 学习评价尚未接入</span><details><summary>原型工具</summary><div><a href="structure.html?role=parent">家长端</a><a href="structure.html?role=admin">管理员端</a><a href="legacy-structure.html?role=student">旧版对照</a><label>目录规模<select v-model.number="state.home.catalogScale" aria-label="目录规模"><option :value="3">3 章</option><option :value="30">30 章示例</option><option :value="300">300 章示例</option></select></label></div></details></div>
  <p v-if="notice || storageWarning" class="notice" role="alert">{{ notice || storageWarning }}</p>
  <main class="main-content" :class="{'split-view':inActivity&&!chatCollapsed,'collapsed-view':inActivity&&chatCollapsed}">
   <div v-if="inActivity" class="chat-pane" :class="{collapsed:chatCollapsed}">
    <ChatWorkspace :conversation="conversation" :collapsed="chatCollapsed" :opening="opening" :has-session="!!current" v-model="composerDraft" @send="send" @toggle-collapse="preferences.collapsed=!preferences.collapsed" @history="historyOpen=true"/>
   </div>
   <div class="static-pane" :class="{narrowed:inActivity&&!chatCollapsed}" :aria-label="`页面上下文：${navigation.find(n=>n.id===currentPage)?.label}`">
    <div v-if="checking" class="check-context"><span>✎</span><h2>先自己试一试</h2><p>检查期间暂时收起参考内容。提交或求助后，这个页面会恢复原来的位置。</p></div>
    <div v-show="!checking" class="page-host" :key="state.studentSpace">
     <HomePage v-show="currentPage==='home'" :space="state.studentSpace" @continue-learning="s=>s?resume(s):openChat()" @start-action="startAction" @navigate="switchPage" @history="historyOpen=true"/>
     <LearningStatusPage v-show="currentPage==='status'" :space="state.studentSpace" @start-action="startAction" @resume="resume"/>
     <TextbookPage v-show="currentPage==='textbook'" :space="state.studentSpace" @start-action="startAction"/>
     <ErrorBookPage v-show="currentPage==='errorbook'" :space="state.studentSpace" @start-action="startAction"/>
    </div>
   </div>
  </main>
  <BottomInputBar v-if="!inActivity" v-model="baseDraft" :scope="inputScope(state.studentSpace)" :disabled="opening" @expand="openChat" @send="send" @history="historyOpen=true"/>
  <Teleport to="body"><div v-if="historyOpen" class="history-overlay" @click.self="historyOpen=false"><section class="history-dialog" role="dialog" aria-label="对话历史" aria-modal="true"><header><h2>对话历史</h2><button aria-label="关闭对话历史" @click="historyOpen=false">×</button></header><div class="history-list"><article v-for="s in sessions" :key="s.id"><span>{{ s.date }} · {{ s.real?'真实交流':'预写活动' }}</span><button v-if="s.real" @click="resume(s)">继续这次交流</button><a v-else :href="`legacy-structure.html?role=student&preview=scripted#/lesson?id=${s.id}`">打开原记录</a></article><p v-if="!sessions.length">这个空间还没有对话。</p></div><button :disabled="busy || !!uncertain || !!pendingCheck" @click="historyOpen=false; begin('')">开始新对话</button></section></div></Teleport>
 </div>
</template>

<style scoped>
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
  .chat-pane { flex: 0 0 100%; position: absolute; z-index: 5; }
  .static-pane.narrowed { flex: 1; }
}

.main-content,.static-pane,.chat-pane { min-height:0; }
.page-host { height:100%; }
.prototype-note{display:flex;justify-content:space-between;align-items:center;padding:4px 24px;font-size:11px;color:#7b8d83;border-bottom:1px solid #edf2ef;flex-shrink:0}
.prototype-note details{position:relative}.prototype-note details>div{position:absolute;right:0;top:22px;background:white;padding:15px;z-index:20;border:1px solid #d4e4dc;border-radius:8px;display:grid;gap:12px;min-width:160px}
.prototype-note summary{cursor:pointer}.notice{padding:8px 24px;font-size:12px;background:#fff5df;color:#815b1f;flex-shrink:0}
.check-context{padding:40px 24px;text-align:center;color:#64786b;line-height:1.8}.check-context span{font-size:32px}
.chat-pane{flex:1 1 60%}.static-pane.narrowed{flex:0 0 40%}
.user-avatar{border:0;cursor:pointer}
@media(max-width:1000px){.top-nav{padding:0 12px}.nav-left{gap:10px}.nav-item{padding:6px 9px}.nav-right{gap:6px}.logo{font-size:14px}.space-trigger{padding:5px 7px}.activity-indicator{padding:4px 6px}.nav-icon{display:none}}
@media(min-width:701px) and (max-width:900px){.chat-pane{position:static;flex:1 1 58%;z-index:auto}.static-pane.narrowed{flex:0 0 42%}.chat-pane.collapsed{flex:0 0 auto}}
@media(max-width:700px){.top-nav{height:auto;min-height:88px;flex-wrap:wrap;padding:8px 12px;gap:6px}.nav-left{width:100%;justify-content:space-between}.nav-right{width:100%;justify-content:flex-end}.main-content.split-view{flex-direction:column}.chat-pane{position:static;flex:1;min-height:0;z-index:auto}.static-pane.narrowed{flex:0 0 30%;border-left:0;border-top:1px solid #e1e8ed;min-height:100px}.chat-pane.collapsed{flex:0 0 auto}.prototype-note{padding:4px 12px;font-size:10px}.activity-indicator{margin-right:auto}.logo{font-size:13px}.nav-item{padding:5px 6px;font-size:12px}.main-content.collapsed-view .static-pane{min-height:0}}

</style>
