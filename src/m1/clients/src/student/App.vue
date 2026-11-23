<script setup lang="ts">
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import CourseSelection from './CourseSelection.vue';
</script>

<template>
  <EntryShell
    class="student-shell"
    title="学生端"
    other-label="管理端"
    other-href="/admin/"
    hide-note
  >
    <AuthGate v-slot="{ session, realtime }" role="student">
      <CourseSelection :key="session.session_id" :session="session" :realtime="realtime" />
    </AuthGate>
  </EntryShell>
</template>

<style scoped>
.student-shell {
  max-width: 86rem;
}
.student-shell :deep(main) {
  max-width: none;
  padding-top: 1rem;
}
</style>
