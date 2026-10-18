<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import type { LearningState } from './types';
import ChatWorkspace from './components/ChatWorkspace.vue';
import BottomInputBar from './components/BottomInputBar.vue';
import HomePage from './components/HomePage.vue';
import LearningStatusPage from './components/LearningStatusPage.vue';
import TextbookPage from './components/TextbookPage.vue';
import ErrorBookPage from './components/ErrorBookPage.vue';

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
const activityLabel = computed(() => modeLabelMap[state.mode] || '学习中');

type PageId = 'home' | 'status' | 'textbook' | 'errorbook';
const currentPage = ref<PageId>('home');
const inActivity = ref(false);
const chatCollapsed = ref(false);
const chatRef = ref<InstanceType<typeof ChatWorkspace> | null>(null);

// 学习空间
interface LearningSpace {
  id: string;
  subject: string;
  grade: string;
  label: string;
  icon: string;
}
const learningSpaces: LearningSpace[] = [
  { id: 'math-6b', subject: '数学', grade: '六年级下册', label: '数学·六下', icon: '🔢' },
  { id: 'chinese-6b', subject: '语文', grade: '六年级下册', label: '语文·六下', icon: '📖' },
  { id: 'english-6b', subject: '英语', grade: '六年级下册', label: '英语·六下', icon: '🔤' },
  { id: 'math-5b', subject: '数学', grade: '五年级下册', label: '数学·五下', icon: '🔢' },
];
const currentSpace = ref<LearningSpace>(learningSpaces[0]);
const spaceDropdownOpen = ref(false);

function selectSpace(space: LearningSpace) {
  currentSpace.value = space;
  spaceDropdownOpen.value = false;
  // 切换学习空间时重置状态
  state.mode = 'idle';
  state.lecturePhase = undefined;
  state.sessionTitle = undefined;
  inActivity.value = false;
  chatCollapsed.value = false;
}

const navItems = [
  { id: 'home' as PageId, label: '首页', icon: '🏠' },
  { id: 'status' as PageId, label: '学习情况', icon: '📊' },
  { id: 'textbook' as PageId, label: '教材', icon: '📖' },
  { id: 'errorbook' as PageId, label: '错题本', icon: '📝' },
];

function updateState(partial: Partial<LearningState>) {
  Object.assign(state, partial);
}

function enterActivity() {
  inActivity.value = true;
  chatCollapsed.value = false;
}

function exitActivity() {
  inActivity.value = false;
  chatCollapsed.value = false;
}

function toggleChatCollapse() {
  chatCollapsed.value = !chatCollapsed.value;
}

function handleBottomSend(text: string) {
  enterActivity();
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

function handleContinueLearning() {
  enterActivity();
  state.mode = 'lecture';
  state.lecturePhase = 'concept';
  state.sessionTitle = state.chapterTitle;
  setTimeout(() => chatRef.value?.injectMessage('继续学习比例的应用'), 50);
}

function handleStartAction(text: string) {
  enterActivity();
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
        <span v-if="inActivity" class="activity-indicator">
          <span class="ai-dot"></span>
          {{ activityLabel }}
          <button class="ai-close" @click="exitActivity">结束 ×</button>
        </span>
        <!-- 学习空间选择 -->
        <div class="space-selector" :class="{ open: spaceDropdownOpen }">
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
          </div>
        </div>
        <span class="user-avatar">学</span>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content" :class="{ 'split-view': inActivity && !chatCollapsed, 'collapsed-view': inActivity && chatCollapsed }">
      <!-- 聊天区（展开时左侧，收起时底部） -->
      <div v-if="inActivity" class="chat-pane" :class="{ collapsed: chatCollapsed }">
        <ChatWorkspace
          ref="chatRef"
          :state="state"
          :collapsed="chatCollapsed"
          @update-state="updateState"
          @toggle-collapse="toggleChatCollapse"
        />
      </div>

      <!-- 静态页面区 -->
      <div class="static-pane" :class="{ narrowed: inActivity && !chatCollapsed }">
        <HomePage v-if="currentPage === 'home'"
          @continue-learning="handleContinueLearning"
          @start-action="handleStartAction" />
        <LearningStatusPage v-else-if="currentPage === 'status'" />
        <TextbookPage v-else-if="currentPage === 'textbook'" @start-action="handleStartAction" />
        <ErrorBookPage v-else-if="currentPage === 'errorbook'" @start-action="handleStartAction" />
      </div>
    </main>

    <!-- 底部常驻输入条（非活动时显示） -->
    <transition name="fade">
      <BottomInputBar v-if="!inActivity" @expand="enterActivity" @send="handleBottomSend" />
    </transition>
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
</style>
