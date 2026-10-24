<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue';
import type { ChatMessage, LearningState } from '../types';
import type { LiveWorkspace } from '../live';
import FlowLesson from './FlowLesson.vue';
import { courseFlow } from '../course-flow';
import ChatMessageComp from './ChatMessage.vue';
import SuggestionChips from './SuggestionChips.vue';
import InputComposer from './InputComposer.vue';
import { generateMockReply, getContextActions, welcomeMessage, fullLectureFlow, fullQAFlow } from '../data';

const props = defineProps<{
  state: LearningState;
  live?: LiveWorkspace;
  collapsed?: boolean;
  mockActivityId?: string;
}>();
const emit = defineEmits<{
  updateState: [partial: Partial<LearningState>];
  toggleCollapse: [];
  showStatus: [];
}>();

const mockLesson = ref<InstanceType<typeof FlowLesson> | null>(null);
const mockTesting = computed(() => courseFlow.lessons.find(a => a.id === props.mockActivityId)?.stage === 'testing');
const demoMessages = ref<ChatMessage[]>([welcomeMessage]);
const demoTyping = ref(false);
const realWelcome: ChatMessage = {...welcomeMessage,blocks:welcomeMessage.blocks.filter((_,i) => i !== 1)};
const messages = computed(() => props.live ? [realWelcome,...props.live.messages.value] : demoMessages.value);
const isTyping = computed(() => props.live ? props.live.busy.value : demoTyping.value);
const liveError = computed(() => props.live && (props.live.view.storageError || props.live.view.error || props.live.view.connectionError || props.live.view.session?.error?.message));
const activeCheck = computed(() => props.live?.view.session?.check || null);
const canRetry = computed(() => props.live && !props.live.view.storageError &&
  (!!props.live.workspace.operation || (!props.live.view.error && (!!props.live.view.connectionError || props.live.view.session?.error?.retryable))));
const scrollContainer = ref<HTMLElement | null>(null);

const contextActions = computed(() => props.live ? props.live.messages.value.filter(m => m.role === 'assistant').slice(-1)[0]?.suggestions || [] : getContextActions(props.state.mode, props.state.lecturePhase));

const modeConfig: Record<string, { icon: string; label: string; className: string }> = {
  'lecture': { icon: '📖', label: '章节讲解', className: 'lecture' },
  'problem': { icon: '✏️', label: '题目讲解', className: 'problem' },
  'error-check': { icon: '📝', label: '错题检测', className: 'error-check' },
  'review': { icon: '🔄', label: '章节复习', className: 'review' },
  'qa': { icon: '💬', label: '自由问答', className: 'qa' },
  'idle': { icon: '🦌', label: 'DeerMind', className: 'idle' },
};

const currentMode = computed(() => {
  const lesson = courseFlow.lessons.find(a => a.id === props.mockActivityId);
  if (lesson) return { icon: lesson.stage === 'testing' ? '📝' : '📖', label: lesson.stage === 'testing' ? '检测中' : lesson.stage === 'finished' ? '学习已结束' : lesson.stage === 'offer' ? '准备检测' : '章节讲解', className: lesson.stage === 'testing' ? 'error-check' : 'lecture' };
  return modeConfig[props.state.mode] || modeConfig['idle'];
});
const displayTitle = computed(() => {
  const title = props.state.sessionTitle || props.state.lectureTopic;
  if (props.state.mode === 'qa' || props.state.mode === 'idle') return currentMode.value.label;
  return title ? `${currentMode.value.label} · ${title}` : currentMode.value.label;
});

async function scrollToBottom() {
  await nextTick();
  if (scrollContainer.value) scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
}
watch(messages, () => scrollToBottom(), { deep: true });

async function handleSend(text: string) {
  if (mockTesting.value || activeCheck.value || isTyping.value) return;
  if (props.mockActivityId) { mockLesson.value?.send(text); return; }
  if (props.live) { await props.live.command('message',text); return; }
  if (demoTyping.value) return;
  demoMessages.value.push({ id: 'u' + Date.now(), role: 'user', blocks: [{ type: 'text', text }], timestamp: Date.now() });
  demoTyping.value = true;
  await scrollToBottom();
  await new Promise(r => setTimeout(r, 600 + Math.random() * 500));
  const result = generateMockReply(text, props.state, messages.value);
  demoMessages.value.push(result.reply);
  demoTyping.value = false;
  if (result.stateUpdate) emit('updateState', result.stateUpdate);
  await scrollToBottom();
}

function handleQuestion(kind: 'start_check' | 'answer' | 'help', id: string) {
  if (!props.live || isTyping.value) return;
  void props.live.command(kind, kind === 'answer' ? props.live.workspace.answers[id] || '' : undefined, id);
}
function saveAnswer(id: string, value: string) {
  if (props.live) props.live.workspace.answers[id] = value;
}

function handleSuggestion(text: string) {
  if (props.live) { void handleSend(text); return; }
  if (text === '（模拟）输入一道题') { handleSend('老师，3/4 + 2/5 等于多少？我不会。'); return; }
  if (text === '（在上方输入答案）') return;
  handleSend(text);
}

function loadLectureDemo() { demoMessages.value = [...fullLectureFlow]; emit('updateState', { mode: 'lecture', lecturePhase: 'summary', lectureTopic: '比较标准量' }); scrollToBottom(); }
function loadQADemo() { demoMessages.value = [...fullQAFlow]; emit('updateState', { mode: 'qa', lecturePhase: undefined }); scrollToBottom(); }
function resetToWelcome() { demoMessages.value = [welcomeMessage]; emit('updateState', { mode: 'idle', lecturePhase: undefined, lectureTopic: undefined }); scrollToBottom(); }
function injectMessage(text: string) { handleSend(text); }

defineExpose({ loadLectureDemo, loadQADemo, resetToWelcome, injectMessage });
</script>

<template>
  <div class="chat-workspace" :class="{ collapsed }">
    <!-- 模式指示栏（收起时隐藏） -->
    <div v-if="!collapsed" class="chat-header">
      <div class="mode-indicator" :class="currentMode.className">
        <span class="mode-icon">{{ currentMode.icon }}</span>
        <span class="mode-text">{{ displayTitle }}</span>
        <div v-if="state.mode === 'lecture' && !mockActivityId" class="mode-steps">
          <span :class="{ active: state.lecturePhase === 'concept' }">概念</span>
          <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'example' }">例题</span>
          <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'practice' }">练习</span>
          <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'summary' }">总结</span>
        </div>
      </div>
    </div>

    <!-- 消息区域（收起时隐藏） -->
    <div v-if="!collapsed" class="messages-container" ref="scrollContainer">
      <div class="messages-inner">
        <FlowLesson v-if="mockActivityId" ref="mockLesson" :activity-id="mockActivityId" @show-status="emit('showStatus')"/>
        <template v-for="msg in (mockActivityId ? [] : messages)" :key="msg.id">
          <ChatMessageComp :message="msg" :live="!!live" :busy="isTyping" :active-check="activeCheck"
            :answer-drafts="live?.workspace.answers" @answer-draft="saveAnswer" @question-action="handleQuestion" />
          <SuggestionChips v-if="msg.role === 'assistant' && msg.suggestions?.length" :suggestions="msg.suggestions"
            :disabled="isTyping || !!activeCheck || mockTesting" @select="handleSuggestion" />
        </template>
        <div v-if="isTyping" class="typing-indicator">
          <div class="avatar">🦌</div>
          <div class="typing-bubble"><span></span><span></span><span></span></div>
        </div>
      </div>
    </div>

    <!-- 输入框（始终显示） -->
    <div class="composer-wrapper">
      <div v-if="live && (liveError || live.view.session?.pending || activeCheck)" class="live-controls">
        <span v-if="liveError" role="alert">{{ liveError }}</span>
        <span v-else-if="activeCheck">检测已开始，请在题目处提交答案，或点击“求助”转入讲解。</span>
        <span v-else>正在生成回复…</span>
        <button v-if="live.view.session?.pending" :disabled="live.view.sending || live.view.loading"
          @click="live.command('cancel')">停止</button>
        <button v-else-if="liveError && canRetry" :disabled="live.view.sending || live.view.loading"
          @click="live.retry()">重试</button>
      </div>
      <InputComposer
        :model-value="live?.workspace.draft"
        @update:model-value="value => { if (live) live.workspace.draft = value; }"
        :context-actions="mockActivityId ? [] : contextActions"
        :disabled="isTyping || !!activeCheck || mockTesting"
        :collapsed="collapsed"
        @send="handleSend"
        @toggle-collapse="emit('toggleCollapse')"
      />
    </div>
  </div>
</template>

<style scoped>
.live-controls { display: flex; align-items: center; gap: 12px; padding: 8px 20px; font-size: 12px; line-height: 1.6; color: #5a6b7a; background: #f7f9fa; }
.live-controls span { flex: 1; }
.live-controls button { border: 1px solid #c8d6e0; border-radius: 6px; background: white; color: #2d6a4f; font: inherit; padding: 4px 12px; cursor: pointer; flex-shrink: 0; }
.live-controls button:disabled { opacity: .5; cursor: default; }
.chat-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f9fa;
  width: 100%;
  min-width: 0;
}

.chat-header {
  flex-shrink: 0;
  border-bottom: 1px solid #e1e8ed;
}
.mode-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  font-size: 12px;
}
.mode-indicator.lecture { background: #e8f5ee; color: #1b4332; }
.mode-indicator.problem { background: #fef3e2; color: #8a5a1a; }
.mode-indicator.error-check { background: #fde8e8; color: #8a2a2a; }
.mode-indicator.review { background: #e8f0fe; color: #1e3a8a; }
.mode-indicator.qa { background: #e8f0f8; color: #1e3a5f; }
.mode-indicator.idle { background: #f0f4f7; color: #5a6b7a; }
.mode-icon { font-size: 14px; }
.mode-text { font-weight: 600; flex-shrink: 0; }
.mode-steps { display: flex; align-items: center; gap: 4px; margin-left: auto; font-size: 11px; }
.mode-steps span { padding: 2px 8px; border-radius: 8px; background: rgba(255,255,255,0.5); color: #7a8a9a; }
.mode-steps span.active { background: #2d6a4f; color: white; font-weight: 600; }
.mode-steps .sep { background: transparent; padding: 0; color: #9aab9a; }

.messages-container {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
  min-height: 0;
}
.messages-inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 20px 16px;
}
.typing-indicator { display: flex; gap: 12px; margin-bottom: 24px; align-items: flex-start; }
.typing-indicator .avatar { width: 36px; height: 36px; border-radius: 50%; background: #2d5a4a; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.typing-bubble { background: #fff; border-radius: 12px; padding: 14px 18px; display: flex; gap: 5px; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.typing-bubble span { width: 7px; height: 7px; background: #a0b0a8; border-radius: 50%; animation: bounce 1.2s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.15s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-5px); opacity: 1; } }

.composer-wrapper {
  width: 100%;
  flex-shrink: 0;
}

@media (max-width: 700px) {
  .messages-inner { padding: 16px 12px; }
  .mode-indicator { padding: 6px 12px; flex-wrap: wrap; gap: 6px; }
  .mode-steps { margin-left: 0; width: 100%; }
}
</style>
