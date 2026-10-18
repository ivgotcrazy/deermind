<script setup lang="ts">
import { ref, reactive } from 'vue';
import type { LearningState } from './types';
import StatusBar from './components/StatusBar.vue';
import ChatWorkspace from './components/ChatWorkspace.vue';
import SidePanel from './components/SidePanel.vue';
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

const chatCollapsed = ref(false);
const chatRef = ref<InstanceType<typeof ChatWorkspace> | null>(null);

function updateState(partial: Partial<LearningState>) {
  Object.assign(state, partial);
}

function toggleChat() {
  chatCollapsed.value = !chatCollapsed.value;
}

function expandChat() {
  chatCollapsed.value = false;
}

function handleUpdateProgress() {
  const newProgress = prompt('更新学校课堂进度', state.classroomProgress);
  if (newProgress) state.classroomProgress = newProgress;
}

function handleSelectChapter(chapterId: string, chapterName: string) {
  state.chapterTitle = chapterName;
  state.currentChapter = chapterId;
  chatRef.value?.injectMessage(`给我讲一下${chapterName}`);
  expandChat();
}

function handleSelectTopic(topicName: string) {
  chatRef.value?.injectMessage(`我想复习一下${topicName}`);
  expandChat();
}

function handleRetryQuestion(questionId: number) {
  chatRef.value?.injectMessage('我想重做一道错题');
  expandChat();
}

function handleBottomSend(text: string) {
  chatRef.value?.injectMessage(text);
  expandChat();
}
</script>

<template>
  <div class="app">
    <StatusBar
      :state="state"
      :chat-collapsed="chatCollapsed"
      @toggle-chat="toggleChat"
      @update-progress="handleUpdateProgress"
    />

    <main class="main-area">
      <!-- 聊天区（可收起） -->
      <transition name="chat-slide">
        <div v-if="!chatCollapsed" class="chat-area">
          <ChatWorkspace ref="chatRef" :state="state" @update-state="updateState" />
        </div>
      </transition>

      <!-- 静态内容区（始终存在，聊天收起时占满） -->
      <div class="static-area" :class="{ fullscreen: chatCollapsed }">
        <SidePanel
          @select-chapter="handleSelectChapter"
          @select-topic="handleSelectTopic"
          @retry-question="handleRetryQuestion"
        />
      </div>
    </main>

    <!-- 聊天收起时的底部输入条 -->
    <transition name="fade">
      <BottomInputBar
        v-if="chatCollapsed"
        @expand="expandChat"
        @send="handleBottomSend"
      />
    </transition>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.chat-area {
  flex: 1;
  min-width: 0;
  display: flex;
  border-right: 1px solid #e1e8ed;
}

.static-area {
  flex-shrink: 0;
  display: flex;
  transition: flex 0.3s ease;
}

.static-area.fullscreen {
  flex: 1;
}

.static-area.fullscreen :deep(.side-panel) {
  width: 100%;
  min-width: unset;
  border-left: none;
}

/* 聊天区收起动画 */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  flex: 0;
  opacity: 0;
  min-width: 0;
}

/* 底部输入条淡入 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

@media (max-width: 900px) {
  .chat-area {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 10;
    background: #f7f9fa;
  }
  .static-area {
    width: 100%;
  }
}
</style>
