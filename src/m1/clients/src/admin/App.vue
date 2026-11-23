<script setup lang="ts">
import { ref } from 'vue';
import EntryShell from '../shared/ui/EntryShell.vue';
import AuthGate from '../shared/auth/AuthGate.vue';
import DomainWorkspace from './features/domain/DomainWorkspace.vue';
import { clearCreateDraft } from './features/domain/draft';
import TextbookWorkspace from './features/materials/TextbookWorkspace.vue';
import ClaimWorkspace from './features/evaluation/ClaimWorkspace.vue';
import ActivityWorkspace from './features/interaction/ActivityWorkspace.vue';
import TargetWorkspace from './features/learning/TargetWorkspace.vue';
import SpaceWorkspace from './features/learning/SpaceWorkspace.vue';

const selection = ref<'domain' | 'textbooks' | 'evaluation' | 'interaction' | 'targets' | 'spaces'>(
  'domain',
);
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
        <button
          type="button"
          :aria-pressed="selection === 'evaluation'"
          @click="selection = 'evaluation'"
        >
          评估管理
        </button>
        <button
          type="button"
          :aria-pressed="selection === 'interaction'"
          @click="selection = 'interaction'"
        >
          交互活动
        </button>
        <button
          type="button"
          :aria-pressed="selection === 'targets'"
          @click="selection = 'targets'"
        >
          目标管理
        </button>
        <button type="button" :aria-pressed="selection === 'spaces'" @click="selection = 'spaces'">
          学习空间
        </button>
      </nav>
      <DomainWorkspace v-if="selection === 'domain'" :session="session" />
      <TextbookWorkspace v-else-if="selection === 'textbooks'" :session="session" />
      <ClaimWorkspace v-else-if="selection === 'evaluation'" :session="session" />
      <ActivityWorkspace v-else-if="selection === 'interaction'" :session="session" />
      <TargetWorkspace v-else-if="selection === 'targets'" :session="session" />
      <SpaceWorkspace v-else :session="session" />
    </AuthGate>
  </EntryShell>
</template>
