<script setup lang="ts">
import type { components } from '../../../../../contracts/generated/http/schema';

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
    <button v-if="canStart" :disabled="busy" type="button" @click="emit('start')">
      确认并开始
    </button>
  </section>
</template>

<style scoped>
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
