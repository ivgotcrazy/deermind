<script setup lang="ts">
defineProps<{
  title: string;
  otherLabel: string;
  otherHref: string;
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
      <p class="entry-note">当前仅开放启动页。</p>
    </main>
  </div>
</template>
