<script setup lang="ts">
import { ref } from 'vue';
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import DomainWorkspace from './features/domain/DomainWorkspace.vue';
import { clearCreateDraft } from './features/domain/draft';
import TextbookWorkspace from './features/materials/TextbookWorkspace.vue';

const selection = ref<'domain' | 'textbooks'>('domain');
</script>

<template>
  <EntryShell title="管理端" other-label="学生端" other-href="/student/" hide-note>
    <AuthGate v-slot="{ session }" role="admin" @sign-out="clearCreateDraft">
      <nav aria-label="管理功能">
        <button type="button" :aria-pressed="selection === 'domain'" @click="selection = 'domain'">
          领域管理
        </button>
        <button
          type="button"
          :aria-pressed="selection === 'textbooks'"
          @click="selection = 'textbooks'"
        >
          教材管理
        </button>
      </nav>
      <DomainWorkspace v-if="selection === 'domain'" :session="session" />
      <TextbookWorkspace v-else :session="session" />
    </AuthGate>
  </EntryShell>
</template>
