<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue';
import type { ChatMessage, LearningState } from '../types';
import ChatMessageComp from './ChatMessage.vue';
import SuggestionChips from './SuggestionChips.vue';
import InputComposer from './InputComposer.vue';
import { generateMockReply, getContextActions, welcomeMessage, fullLectureFlow, fullQAFlow } from '../data';

const props = defineProps<{ state: LearningState }>();
const emit = defineEmits<{ updateState: [partial: Partial<LearningState>] }>();

const messages = ref<ChatMessage[]>([welcomeMessage]);
const isTyping = ref(false);
const scrollContainer = ref<HTMLElement | null>(null);

const contextActions = computed(() => getContextActions(props.state.mode, props.state.lecturePhase));

async function scrollToBottom() {
  await nextTick();
  if (scrollContainer.value) scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
}
watch(messages, () => scrollToBottom(), { deep: true });

async function handleSend(text: string) {
  messages.value.push({ id: 'u' + Date.now(), role: 'user', blocks: [{ type: 'text', text }], timestamp: Date.now() });
  isTyping.value = true;
  await scrollToBottom();
  await new Promise(r => setTimeout(r, 600 + Math.random() * 500));
  const result = generateMockReply(text, props.state, messages.value);
  messages.value.push(result.reply);
  isTyping.value = false;
  if (result.stateUpdate) emit('updateState', result.stateUpdate);
  await scrollToBottom();
}

function handleSuggestion(text: string) {
  if (text === '（模拟）输入一道题') { handleSend('老师，3/4 + 2/5 等于多少？我不会。'); return; }
  if (text === '（在上方输入答案）') return;
  handleSend(text);
}

function loadLectureDemo() { messages.value = [...fullLectureFlow]; emit('updateState', { mode: 'lecture', lecturePhase: 'summary', lectureTopic: '比较标准量' }); scrollToBottom(); }
function loadQADemo() { messages.value = [...fullQAFlow]; emit('updateState', { mode: 'qa', lecturePhase: undefined }); scrollToBottom(); }
function resetToWelcome() { messages.value = [welcomeMessage]; emit('updateState', { mode: 'idle', lecturePhase: undefined, lectureTopic: undefined }); scrollToBottom(); }
function injectMessage(text: string) { handleSend(text); }

defineExpose({ loadLectureDemo, loadQADemo, resetToWelcome, injectMessage });
</script>

<template>
  <div class="chat-workspace">
    <div v-if="state.mode === 'lecture'" class="mode-indicator lecture">
      <span>📖</span><span class="mode-text">章节讲解中</span>
      <div class="mode-steps">
        <span :class="{ active: state.lecturePhase === 'concept' }">概念</span>
        <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'example' }">例题</span>
        <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'practice' }">练习</span>
        <span class="sep">→</span><span :class="{ active: state.lecturePhase === 'summary' }">总结</span>
      </div>
    </div>
    <div v-else-if="state.mode === 'qa'" class="mode-indicator qa">
      <span>❓</span><span class="mode-text">答疑解惑</span>
    </div>

    <div class="messages-container" ref="scrollContainer">
      <div class="messages-inner">
        <template v-for="msg in messages" :key="msg.id">
          <ChatMessageComp :message="msg" />
          <SuggestionChips v-if="msg.role === 'assistant' && msg.suggestions?.length" :suggestions="msg.suggestions" @select="handleSuggestion" />
        </template>
        <div v-if="isTyping" class="typing-indicator">
          <div class="avatar">🦌</div>
          <div class="typing-bubble"><span></span><span></span><span></span></div>
        </div>
      </div>
    </div>

    <InputComposer :context-actions="contextActions" :disabled="isTyping" @send="handleSend" />
  </div>
</template>

<style scoped>
.chat-workspace { display: flex; flex-direction: column; height: 100%; background: #f7f9fa; }
.mode-indicator { display: flex; align-items: center; gap: 10px; padding: 8px 20px; font-size: 12px; flex-shrink: 0; }
.mode-indicator.lecture { background: #e8f5ee; color: #1b4332; border-bottom: 1px solid #c8e6d4; }
.mode-indicator.qa { background: #e8f0f8; color: #1e3a5f; border-bottom: 1px solid #c8d8ee; }
.mode-text { font-weight: 600; }
.mode-steps { display: flex; align-items: center; gap: 4px; margin-left: 12px; font-size: 11px; }
.mode-steps span { padding: 2px 8px; border-radius: 8px; background: rgba(255,255,255,0.5); color: #7a8a9a; }
.mode-steps span.active { background: #2d6a4f; color: white; font-weight: 600; }
.mode-steps .sep { background: transparent; padding: 0; color: #9aab9a; }
.messages-container { flex: 1; overflow-y: auto; scroll-behavior: smooth; }
.messages-inner { max-width: 860px; margin: 0 auto; padding: 24px 20px 16px; }
.typing-indicator { display: flex; gap: 12px; margin-bottom: 24px; align-items: flex-start; }
.typing-indicator .avatar { width: 36px; height: 36px; border-radius: 50%; background: #2d5a4a; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.typing-bubble { background: #fff; border-radius: 12px; padding: 14px 18px; display: flex; gap: 5px; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.typing-bubble span { width: 7px; height: 7px; background: #a0b0a8; border-radius: 50%; animation: bounce 1.2s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.15s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-5px); opacity: 1; } }
@media (max-width: 700px) {
  .messages-inner { padding: 16px 12px; }
  .mode-indicator { padding: 6px 12px; flex-wrap: wrap; gap: 6px; }
  .mode-steps { margin-left: 0; width: 100%; }
}
</style>
