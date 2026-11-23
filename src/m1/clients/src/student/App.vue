<script setup lang="ts">
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import CourseSelection from './CourseSelection.vue';
</script>

<template>
  <EntryShell title="学生端" other-label="管理端" other-href="/admin/">
    <AuthGate v-slot="{ session }" role="student">
      <CourseSelection :session="session" />
    </AuthGate>
  </EntryShell>
</template>
