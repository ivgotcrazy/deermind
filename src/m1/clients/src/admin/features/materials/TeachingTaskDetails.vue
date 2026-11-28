<script setup lang="ts">
import type { BookTypes } from '../../../shared/book/editions';
defineProps<{ task: BookTypes['TeachingTask'] }>();
</script>
<template>
  <article class="model-reading">
    <p>{{ task.description }}</p>
    <dl>
      <dt>预期产出</dt>
      <dd>{{ task.expected_output }}</dd>
      <dt>完成条件</dt>
      <dd>{{ task.completion_conditions }}</dd>
      <dt>先导任务</dt>
      <dd>{{ task.prerequisites.join('、') || '无' }}</dd>
    </dl>
    <h3>解法</h3>
    <section v-for="method in task.methods" :key="method.name">
      <h4>{{ method.name }}</h4>
      <p>{{ method.steps }}</p>
      <p>{{ method.rationale }}</p>
      <p v-if="method.knowledge.length">涉及知识点 · {{ method.knowledge.join('、') }}</p>
      <p>适用条件 · {{ method.applicability }}</p>
    </section>
    <h3>直接检验的知识点</h3>
    <section v-for="kc in task.direct_knowledge" :key="kc.name">
      <h4>{{ kc.name }}</h4>
      <p>{{ kc.meaning }}</p>
      <p>直接检验 · {{ kc.test_method }} · {{ kc.observable_behavior }}</p>
      <p v-if="kc.applicability">适用条件 · {{ kc.applicability }}</p>
      <p v-if="kc.insufficient_example">证据不足 · {{ kc.insufficient_example }}</p>
    </section>
  </article>
</template>
<style scoped>
.model-reading {
  line-height: 1.65;
}
.model-reading dt {
  color: var(--el-text-color-secondary);
}
.model-reading dd {
  margin: 0 0 12px;
}
.model-reading section {
  padding: 0 0 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
</style>
