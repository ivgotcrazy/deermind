<script setup lang="ts">
import { computed } from 'vue';

const { text } = defineProps<{ text: string }>();

type Passage =
  | { type: 'text'; lines: string[] }
  | { type: 'equations'; rows: { label: string; expression: string }[] };

// 只有单独成行、带标签的算式才排成卡片，保留模型提交的内容。
const passages = computed(() => {
  const result: Passage[] = [];
  for (const line of text.split('\n')) {
    const row =
      line.length <= 180
        ? line.match(
            /^([^：:\n]{1,16})[：:]\s*([\d(（][\d\s.,+−\-×*÷/()（）¼½¾％%]*[＝=][\d\s.,+−\-×*÷/()（）¼½¾％%]+[\p{L} ]*)$/u,
          )
        : null;
    const last = result.at(-1);
    if (row) {
      const item = { label: row[1] ?? '', expression: row[2] ?? '' };
      if (last?.type === 'equations') last.rows.push(item);
      else result.push({ type: 'equations', rows: [item] });
    } else if (last?.type === 'text') {
      last.lines.push(line);
    } else {
      result.push({ type: 'text', lines: [line] });
    }
  }
  return result;
});
</script>

<template>
  <template v-for="(passage, index) in passages" :key="index">
    <p
      v-if="passage.type === 'text' && passage.lines.some((line) => line.trim())"
      class="tutor-paragraph"
    >
      {{ passage.lines.join('\n').trim() }}
    </p>
    <dl v-else-if="passage.type === 'equations'" class="equations">
      <div v-for="(row, offset) in passage.rows" :key="offset" class="equation">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.expression }}</dd>
      </div>
    </dl>
  </template>
</template>

<style scoped>
.tutor-paragraph {
  margin: 0;
  white-space: pre-wrap;
}
.equations {
  margin: 2rem 0 0.625rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--muted);
}
.equation {
  display: grid;
  grid-template-columns: minmax(3.5rem, 5.375rem) minmax(0, 1fr);
  align-items: baseline;
  gap: 0.5rem;
  padding-block: 1.125rem;
}
.equation + .equation {
  border-top: 1px solid var(--border);
}
.equation dt {
  color: var(--muted-foreground);
  font: var(--study-font-ui);
}
.equation dd {
  margin: 0;
  font: var(--study-font-section);
  white-space: pre-wrap;
}
</style>
