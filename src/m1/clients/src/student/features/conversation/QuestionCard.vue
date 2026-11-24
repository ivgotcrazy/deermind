<script setup lang="ts">
import type { components } from '../../../../../contracts/generated/http/schema';
import RichContent from '../../../shared/content/RichContent.vue';

defineProps<{
  question: components['schemas']['QuestionPart'];
  canAnswer: boolean;
  busy: boolean;
}>();

const answer = defineModel<string>('answer');
const emit = defineEmits<{ submit: [] }>();
</script>

<template>
  <section class="question-card" :aria-label="question.title">
    <h4>{{ question.title }}</h4>
    <RichContent :content="question.statement" />
    <details v-if="question.worked_solution">
      <summary>查看解法</summary>
      <RichContent :content="question.worked_solution" />
    </details>
    <form v-if="canAnswer" @submit.prevent="emit('submit')">
      <label :for="`answer-${question.task_use_ref.id}`">你的作答</label>
      <textarea
        :id="`answer-${question.task_use_ref.id}`"
        v-model="answer"
        rows="3"
        maxlength="4096"
      />
      <button type="submit" :disabled="busy || !answer?.trim()">提交作答</button>
    </form>
  </section>
</template>

<style scoped>
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
