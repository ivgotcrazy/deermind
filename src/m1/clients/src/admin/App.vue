<script setup lang="ts">
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import DomainWorkspace from './features/domain/DomainWorkspace.vue';
import { clearCreateDraft } from './features/domain/draft';
</script>

<template>
  <EntryShell title="管理端" other-label="学生端" other-href="/student/" hide-note>
    <AuthGate v-slot="{ session }" role="admin" @sign-out="clearCreateDraft">
      <DomainWorkspace :session="session" />
    </AuthGate>
  </EntryShell>
</template>
