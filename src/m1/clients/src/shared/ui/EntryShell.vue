<script setup lang="ts">
defineProps<{
  title: string;
  otherLabel: string;
  otherHref: string;
  hideNote?: boolean;
}>();
</script>

<template>
  <div class="entry-shell">
    <header class="entry-header">
      <span class="brand">DeerMind</span>
      <a :href="otherHref">{{ otherLabel }}</a>
    </header>
    <main>
      <h1>{{ title }}</h1>
      <slot />
      <p v-if="!hideNote" class="entry-note">当前开放账号登录，学习功能按后续增量接入。</p>
    </main>
  </div>
</template>
