<script setup lang="ts">
import { computed } from 'vue';
const props = defineProps<{ body: string }>();
const lines = computed(() =>
  props.body
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean),
);
</script>

<template>
  <article class="prompt-text">
    <template v-for="(line, index) in lines" :key="index">
      <h3 v-if="/^#{1,6}\s/.test(line)">{{ line.replace(/^#{1,6}\s+/, '') }}</h3>
      <p v-else>{{ line }}</p>
    </template>
  </article>
</template>

<style scoped>
.prompt-text {
  max-width: 72ch;
  color: var(--el-text-color-regular);
  line-height: 1.85;
  overflow-wrap: anywhere;
}
.prompt-text h3 {
  margin: 20px 0 5px;
  font-size: 16px;
  color: var(--el-text-color-primary);
}
.prompt-text p {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.prompt-text > :first-child {
  margin-top: 0;
}
</style>
