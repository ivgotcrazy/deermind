<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{
  expand: [];
  send: [text: string];
}>();

const input = ref('');
const isExpanded = ref(false);

function handleSend() {
  const text = input.value.trim();
  if (!text) return;
  emit('send', text);
  input.value = '';
  isExpanded.value = false;
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}

function handleFocus() {
  isExpanded.value = true;
  emit('expand');
}
</script>

<template>
  <div class="bottom-input-bar" :class="{ expanded: isExpanded }">
    <button class="expand-btn" @click="emit('expand')" title="展开聊天">
      💬
    </button>
    <div class="input-wrapper">
      <input
        v-model="input"
        @focus="handleFocus"
        @keydown="handleKeydown"
        placeholder="有问题？直接问 DeerMind..."
        class="bar-input"
      />
      <button class="quick-hint" @click="emit('expand')">⋯</button>
    </div>
    <button class="send-btn" :disabled="!input.trim()" @click="handleSend">
      发送
    </button>
  </div>
</template>

<style scoped>
.bottom-input-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #1a3a2e 0%, #244c40 100%);
  border-top: 1px solid #2d5a4a;
  flex-shrink: 0;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
}

.expand-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  border: none;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}

.expand-btn:hover {
  background: rgba(255,255,255,0.25);
}

.input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.bar-input {
  width: 100%;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 20px;
  padding: 9px 36px 9px 16px;
  font-size: 13px;
  color: #e8f0ec;
  font-family: inherit;
  transition: all 0.2s;
}

.bar-input::placeholder {
  color: rgba(232,240,236,0.5);
}

.bar-input:focus {
  outline: none;
  background: rgba(255,255,255,0.18);
  border-color: rgba(255,255,255,0.35);
}

.quick-hint {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: rgba(232,240,236,0.5);
  font-size: 18px;
  cursor: pointer;
  padding: 2px 6px;
  line-height: 1;
}

.quick-hint:hover {
  color: #e8f0ec;
}

.send-btn {
  background: #40916c;
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #52b788;
}

.send-btn:disabled {
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.4);
  cursor: not-allowed;
}

@media (max-width: 700px) {
  .bottom-input-bar {
    padding: 8px 12px;
    gap: 8px;
  }
  .send-btn {
    padding: 7px 14px;
    font-size: 12px;
  }
}
</style>
