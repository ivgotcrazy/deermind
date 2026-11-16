<script setup lang="ts">
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
</script>

<template>
  <EntryShell title="学生端" other-label="管理端" other-href="/admin/">
    <AuthGate role="student">
      <p>学习入口已建立。聊天与教材将在后续增量接入。</p>
    </AuthGate>
  </EntryShell>
</template>
