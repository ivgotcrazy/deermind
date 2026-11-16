<script setup lang="ts">
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
</script>

<template>
  <EntryShell title="管理端" other-label="学生端" other-href="/student/">
    <AuthGate role="admin">
      <p>管理入口已建立。教材和领域管理将在后续增量接入。</p>
    </AuthGate>
  </EntryShell>
</template>
