<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{
  contextActions: string[];
  disabled?: boolean;
  collapsed?: boolean;
  modelValue?: string;
}>();
const emit = defineEmits<{
  send: [text: string];
  'update:modelValue': [value: string];
  toggleCollapse: [];
}>();

const localInput = ref('');
const input = computed({get:() => props.modelValue ?? localInput.value, set:v => {
  if (props.modelValue === undefined) localInput.value = v; else emit('update:modelValue',v);
}});
const canSend = computed(() => input.value.trim().length > 0 && !props.disabled);

function handleSend() {
  const text = input.value.trim();
  if (!text || props.disabled) return;
  emit('send', text);
  if (props.modelValue === undefined) input.value = '';
}
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); handleSend(); }
}
</script>

<template>
  <div class="input-composer">
    <!-- 收起/展开按钮：右上角 -->
    <button class="collapse-btn" @click="emit('toggleCollapse')" :title="collapsed ? '展开聊天' : '收起聊天'">
      {{ collapsed ? '▲ 展开' : '▼ 收起' }}
    </button>

    <div v-if="contextActions.length > 0" class="context-actions">
      <span class="context-label">快捷：</span>
      <button v-for="(a, i) in contextActions" :key="i" class="context-btn" :disabled="disabled" @click="emit('send', a)">{{ a }}</button>
    </div>
    <div class="input-row">
      <textarea v-model="input" @keydown="handleKeydown"
        placeholder="直接说你想做什么，比如：今天学的没听懂，再讲一遍..."
        rows="1" class="input-area"></textarea>
      <button class="send-btn" :disabled="!canSend" @click="handleSend">发送</button>
    </div>
  </div>
</template>

<style scoped>
.input-composer {
  background: #fff;
  border-top: 1px solid #e1e8ed;
  padding: 12px 20px 10px;
  flex-shrink: 0;
  position: relative;
  width: 100%;
  box-sizing: border-box;
}
.collapse-btn {
  position: absolute;
  top: 8px;
  right: 16px;
  background: none;
  border: none;
  color: #8a99a8;
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  padding: 2px 6px;
  border-radius: 4px;
}
.collapse-btn:hover { background: #f0f4f7; color: #2c3e50; }
.context-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding-right: 60px;
}
.context-label { font-size: 11px; color: #8a99a8; }
.context-btn { background: #f0f4f7; border: 1px solid #d4dde4; color: #4a6070; padding: 3px 10px; border-radius: 12px; font-size: 11px; cursor: pointer; transition: all 0.15s; font-family: inherit; }
.context-btn:hover { background: #e0f0e8; border-color: #40916c; color: #1b4332; }
.input-row { display: flex; gap: 10px; align-items: flex-end; width: 100%; box-sizing: border-box; }
.input-area { flex: 1; border: 1px solid #d0d7de; border-radius: 10px; padding: 10px 14px; font-size: 14px; resize: none; max-height: 120px; min-height: 40px; line-height: 1.5; font-family: inherit; transition: border-color 0.15s, box-shadow 0.15s; box-sizing: border-box; }
.input-area:focus { outline: none; border-color: #40916c; box-shadow: 0 0 0 3px rgba(64,145,108,0.12); }
.send-btn { background: #2d6a4f; color: white; border: none; padding: 10px 22px; border-radius: 10px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.15s; height: 40px; flex-shrink: 0; font-family: inherit; }
.send-btn:hover:not(:disabled) { background: #245440; }
.send-btn:disabled { background: #c8d4cc; cursor: not-allowed; }
@media (max-width: 700px) {
  .input-composer { padding: 10px 12px 8px; }
  .send-btn { padding: 8px 16px; font-size: 13px; }
}
</style>
