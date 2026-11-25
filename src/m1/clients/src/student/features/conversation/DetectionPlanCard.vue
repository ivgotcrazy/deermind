<script setup lang="ts">
import type { components } from '../../../../../contracts/generated/http/schema';
import { Button } from '../../components/ui/button';

defineProps<{
  plan: components['schemas']['DetectionPlanPart'];
  canStart: boolean;
  busy: boolean;
}>();

const emit = defineEmits<{ start: [] }>();
</script>

<template>
  <section class="question-card" aria-label="检测题单">
    <h4>检测题单 · {{ plan.question_count }} 题</h4>
    <ul v-if="plan.gaps.length">
      <li v-for="(gap, index) in plan.gaps" :key="index">{{ gap }}</li>
    </ul>
    <Button v-if="canStart" :disabled="busy" type="button" size="sm" @click="emit('start')">
      确认并开始
    </Button>
  </section>
</template>

<style scoped>
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
