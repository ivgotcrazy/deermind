<script setup lang="ts">
import type { Exchange } from '../conversation';
defineProps<{ entry: Exchange; stale: boolean; offline: boolean }>();
defineEmits<{ execute: [entry: Exchange]; cancel: [entry: Exchange] }>();
</script>
<template>
  <div class="intent-answer">{{ entry.response }}</div>
  <div v-if="entry.action" class="intent-action">
    <span v-if="entry.action.status === 'done'" class="tag">已完成上述操作</span>
    <span v-else-if="entry.action.status === 'cancelled'" class="tag neutral">已取消，未执行</span>
    <template v-else>
      <p v-if="stale" class="note">
        当前对象或活动已经变化，这项旧操作不能直接执行。请针对当前对象重新表达意图。
      </p>
      <button class="button primary" :disabled="stale || offline" @click="$emit('execute', entry)">
        {{ entry.action.label }}
      </button>
      <button class="text-button" @click="$emit('cancel', entry)">暂时不做</button>
    </template>
  </div>
</template>
