<script setup lang="ts">
import { ArrowUp, BookOpen, Square, X } from '@lucide/vue';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { Button } from '../../components/ui/button';

const props = defineProps<{
  action: 'send' | 'stop' | 'resend';
  disabled: boolean;
  citation?: string;
}>();
const emit = defineEmits<{ send: []; stop: []; removeCitation: [] }>();
const draft = defineModel<string>({ required: true });

const composer = ref<HTMLFormElement>();
const input = ref<HTMLTextAreaElement>();
const actionLabel = computed(() => {
  if (props.action === 'stop') return '停止本次回复';
  return props.action === 'resend' ? '重试发送' : '发送';
});
const blocked = computed(() => props.disabled || (props.action === 'send' && !draft.value.trim()));
const composing = ref(false);
let observer: ResizeObserver | undefined;

function resizeInput() {
  const field = input.value;
  if (!field) return;
  field.style.height = 'auto';
  field.style.height = `${field.scrollHeight}px`;
}

function activate() {
  if (blocked.value || composing.value) return;
  if (props.action === 'stop') emit('stop');
  else emit('send');
}

function onKeydown(event: KeyboardEvent) {
  // 中文输入法用回车确认候选。键盘发送只针对当前草稿。
  if (
    event.key !== 'Enter' ||
    event.shiftKey ||
    event.isComposing ||
    composing.value ||
    event.keyCode === 229 ||
    props.action !== 'send'
  ) {
    return;
  }
  event.preventDefault();
  if (!event.repeat) activate();
}

watch(draft, resizeInput, { flush: 'post' });
onMounted(() => {
  resizeInput();
  if (!composer.value) return;
  let width = composer.value.clientWidth;
  // 侧栏伸缩也会改变文本折行。只观察宽度，避免调高输入框时反复触发。
  observer = new ResizeObserver(() => {
    const nextWidth = composer.value?.clientWidth;
    if (nextWidth === undefined || nextWidth === width) return;
    width = nextWidth;
    resizeInput();
  });
  observer.observe(composer.value);
});
onUnmounted(() => observer?.disconnect());

defineExpose({ focus: () => input.value?.focus() });
</script>

<template>
  <form ref="composer" aria-label="学习消息" @submit.prevent>
    <slot />
    <div class="input-frame">
      <div v-if="citation" class="citation">
        <BookOpen aria-hidden="true" :size="14" />
        <span :title="citation">{{ citation }}</span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="移除引用"
          title="移除引用"
          @click="emit('removeCitation')"
        >
          <X aria-hidden="true" />
        </Button>
      </div>
      <label for="study-input" class="sr-only">输入消息</label>
      <textarea
        id="study-input"
        ref="input"
        v-model="draft"
        rows="1"
        placeholder="输入你的问题或想法…"
        aria-describedby="study-input-help"
        @compositionstart="composing = true"
        @compositionend="composing = false"
        @keydown="onKeydown"
      />
      <div class="input-toolbar">
        <span id="study-input-help" role="status">
          {{ action === 'stop' ? '正在处理上一条消息。' : 'Shift + Enter 换行' }}
        </span>
        <Button
          type="button"
          size="icon-lg"
          class="rounded-full"
          :variant="action === 'stop' ? 'secondary' : 'default'"
          :aria-label="actionLabel"
          :title="actionLabel"
          :disabled="blocked"
          @click="activate"
        >
          <Square v-if="action === 'stop'" aria-hidden="true" fill="currentColor" />
          <ArrowUp v-else aria-hidden="true" />
        </Button>
      </div>
    </div>
  </form>
</template>

<style scoped>
.input-frame {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
  padding: 0.625rem 0.625rem 0.4375rem;
  border: 1px solid var(--border);
  border-radius: 1rem;
  background: var(--background);
}
.input-frame:focus-within {
  border-color: var(--ring);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ring) 18%, transparent);
}
textarea {
  box-sizing: border-box;
  display: block;
  width: 100%;
  min-width: 0;
  max-height: 5lh;
  overflow-y: auto;
  resize: none;
  padding: 0 0.3125rem;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--foreground);
  font: var(--study-font-body);
}
textarea::placeholder {
  color: var(--muted-foreground);
  opacity: 1;
}
.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-height: 2.5rem;
  padding-inline-start: 0.3125rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta);
}
.citation {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  width: max-content;
  max-width: 100%;
  padding: 0 0.1875rem 0 0.5rem;
  border-radius: 0.375rem;
  background: var(--secondary);
  color: var(--secondary-foreground);
  font: var(--study-font-meta);
}
.citation > svg {
  flex: none;
}
.citation span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
