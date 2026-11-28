<script setup lang="ts">
defineProps<{ items: { key: string; name: string }[] }>();
defineEmits<{ select: [key: string] }>();
</script>

<template>
  <ul class="knowledge-list" aria-label="知识列表">
    <li v-for="item in items" :key="item.key">
      <button type="button" aria-haspopup="dialog" @click="$emit('select', item.key)">
        <span>{{ item.name }}</span>
        <span aria-hidden="true">›</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.knowledge-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.knowledge-list li {
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.knowledge-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 44px;
  padding: 8px;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  font: inherit;
  text-align: left;
  overflow-wrap: anywhere;
  cursor: pointer;
}
.knowledge-list button:hover,
.knowledge-list button:focus-visible {
  background: var(--el-fill-color-light);
}
.knowledge-list button:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}
</style>
