<script setup lang="ts">
import AuthGate from '../shared/auth/AuthGate.vue';
import CourseSelection from './CourseSelection.vue';
import StudentSignIn from './StudentSignIn.vue';
</script>

<template>
  <main class="student-app">
    <AuthGate role="student">
      <template #entry="entry">
        <StudentSignIn v-bind="entry" />
      </template>
      <template
        #workspace="{
          session,
          realtime,
          busy,
          error,
          signOut,
          realtimeState,
          storageUnavailable,
          reconnect,
        }"
      >
        <CourseSelection
          :key="session.session_id"
          :session="session"
          :realtime="realtime"
          :sign-out="signOut"
          :signing-out="busy"
          :auth-error="error"
          :realtime-state="realtimeState"
          :storage-unavailable="storageUnavailable"
          :reconnect="reconnect"
        />
      </template>
    </AuthGate>
  </main>
</template>

<style scoped>
.student-app {
  max-width: none;
  padding: 0;
}
.student-app > :deep(.auth-card) {
  width: min(calc(100% - 2rem), 40rem);
  margin: 2rem auto;
}
</style>
