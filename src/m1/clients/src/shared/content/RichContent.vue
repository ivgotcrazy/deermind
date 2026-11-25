<script setup lang="ts">
import { computed } from 'vue';
import ContentChart from './ContentChart.vue';
import ContentDiagram from './ContentDiagram.vue';
import ContentTable from './ContentTable.vue';
import MathFormula from './MathFormula';
import type { RichContent } from './types';

const { content, showSourcePages = true } = defineProps<{
  content: RichContent;
  showSourcePages?: boolean;
}>();

const blocks = computed(() => {
  const tables = new Map(content.data_tables.map((table) => [table.data_id, table]));
  return content.blocks.map((block) => ({
    block,
    table: 'data_ref' in block.payload ? tables.get(block.payload.data_ref) : undefined,
  }));
});

function sourceLabel(source: RichContent['source_refs'][number]) {
  const pages = [];
  if (source.printed_page) pages.push(`印刷页 ${source.printed_page}`);
  if (source.file_page != null) pages.push(`文件第 ${source.file_page} 页`);
  return pages.join('，');
}

const sourcePages = computed(() => [
  ...new Set(content.source_refs.map(sourceLabel).filter((label) => label)),
]);
</script>

<template>
  <div class="rich-content" :data-role="content.role">
    <div v-for="{ block, table } in blocks" :key="block.block_id" :data-block-id="block.block_id">
      <p v-if="block.type === 'paragraph'" class="paragraph">
        <template v-for="(span, index) in block.payload.spans" :key="index">
          <span v-if="span.type === 'text'">{{ span.text }}</span>
          <MathFormula v-else-if="span.type === 'math'" :expression="span.expression" />
          <span v-else class="response-blank" role="img" :aria-label="span.label"></span>
        </template>
      </p>
      <div
        v-else-if="block.type === 'math_sequence'"
        class="math-sequence"
        :data-purpose="block.payload.purpose"
      >
        <div v-for="(line, index) in block.payload.lines" :key="index" class="math-line">
          <span class="relation">{{ line.relation }}</span>
          <MathFormula :expression="line.expression" />
          <span>{{ line.suffix }}</span>
        </div>
      </div>
      <template v-else-if="block.type === 'table' || block.type === 'chart'">
        <p v-if="!table" class="source">对应数据表缺失。</p>
        <ContentTable
          v-else-if="block.type === 'table'"
          :caption="block.payload.caption"
          :table="table"
        />
        <ContentChart v-else :chart="block.payload" :table="table" />
      </template>
      <ContentDiagram v-else-if="block.type === 'diagram'" :diagram="block.payload" />
      <p v-else class="source">这个内容块暂时无法显示。</p>
      <p v-if="block.provenance.note" class="source">{{ block.provenance.note }}</p>
    </div>
    <p v-if="showSourcePages && sourcePages.length" class="source">
      来源 {{ sourcePages.join('、') }}
    </p>
  </div>
</template>

<style scoped>
.rich-content {
  display: grid;
  gap: 1rem;
  min-width: 0;
}

.rich-content > div {
  min-width: 0;
}

.paragraph {
  max-width: 40em;
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.response-blank {
  display: inline-block;
  min-width: 3em;
  border-bottom: 1px solid currentColor;
}

.math-sequence {
  overflow-x: auto;
  padding: 0.5rem 0.75rem;
  border-left: 2px solid var(--color-line);
}

.math-line {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  min-width: max-content;
}

.math-line + .math-line {
  margin-top: 0.375rem;
}

.relation {
  min-width: 1em;
  color: var(--color-muted);
}

:deep(mn.cancelled) {
  text-decoration: line-through;
}

.source {
  margin: 0.375rem 0 0;
  color: var(--color-muted);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}
</style>
