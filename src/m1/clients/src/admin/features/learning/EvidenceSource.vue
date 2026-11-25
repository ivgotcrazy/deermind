<script setup lang="ts">
import { computed } from 'vue';
import RichContentView from '../../../shared/content/RichContent.vue';
import type { RichContent } from '../../../shared/content/types';
import type { components } from '../../../../../contracts/generated/http/schema';

type Schema = components['schemas'];
const props = defineProps<{
  excerpt: Schema['SourceExcerpt'];
  paths: Schema['EventPartRef'][];
  question?: Schema['SourceExcerpt'];
  occurredAt?: string | null;
}>();
const clockTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
function statement(value: unknown) {
  const item = object(value);
  if (
    Array.isArray(item.blocks) &&
    Array.isArray(item.data_tables) &&
    Array.isArray(item.source_refs)
  ) {
    return value as RichContent;
  }
}
const question = computed(() => {
  for (const value of [...(props.question?.content ?? []), ...props.excerpt.content]) {
    const item = statement(object(value).statement) ?? statement(value);
    if (item) return item;
  }
  return undefined;
});
const help = computed(() => {
  for (const entry of props.excerpt.content) {
    const item = object(entry);
    if ('external_help' in item || 'help_event_ids' in item) return item;
  }
  return undefined;
});
const text = computed(() =>
  props.excerpt.content.flatMap((value) => {
    const item = object(value);
    const content =
      typeof value === 'string'
        ? value
        : (item.text ?? object(item.answer).text ?? item.quote ?? item.reason);
    return typeof content === 'string' && content.trim() ? [content] : [];
  }),
);
const isAnswer = computed(() => props.paths.some((ref) => ref.path === '/answer'));

// Some sources describe a round or a teaching action rather than a text excerpt.
function fields(value: unknown, path: string): { label: string; value: string }[] {
  if (value === null || value === undefined) return [{ label: path, value: '未记录' }];
  if (typeof value !== 'object') return [{ label: path, value: String(value) }];
  return Object.entries(value).flatMap(([key, part]) =>
    fields(part, path ? path + ' / ' + key : key),
  );
}
const recordFields = computed(() =>
  props.excerpt.content.flatMap((part, i) =>
    fields(part, props.excerpt.content.length > 1 ? '记录 ' + (i + 1) : ''),
  ),
);
</script>
<template>
  <section class="origin-card" aria-label="来源事实">
    <strong
      ><template v-if="occurredAt"
        ><time :datetime="occurredAt">{{ clockTime.format(new Date(occurredAt)) }}</time>
        · </template
      >{{ isAnswer ? '学生提交作答' : question ? '原始题面' : '来源事实' }}</strong
    >
    <RichContentView v-if="question" :content="question" :show-source-pages="false" />
    <p v-else-if="isAnswer" class="origin-note">这条证据未提供可核对的原始题面。</p>
    <div v-if="text.length" class="origin-text">
      <p v-for="(line, i) in text" :key="i">{{ line }}</p>
    </div>
    <p v-if="help" class="origin-note">
      <template v-if="Array.isArray(help.help_event_ids)">{{
        help.help_event_ids.length ? '本轮有系统帮助记录。' : '本轮没有记录到系统帮助。'
      }}</template>
      {{ help.external_help === 'unknown' ? '场外帮助未知。' : '' }}
    </p>
    <details v-if="!text.length && !question && !help" open>
      <summary>来源记录字段</summary>
      <dl>
        <template v-for="field in recordFields" :key="field.label"
          ><dt>{{ field.label }}</dt>
          <dd>{{ field.value }}</dd></template
        >
      </dl>
    </details>
  </section>
</template>
<style scoped>
.origin-card {
  background: white;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 15px;
  margin-top: 22px;
  line-height: 1.65;
  font-size: 14px;
}
dt {
  font-weight: 600;
  margin-top: 8px;
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.origin-card > strong,
.origin-note {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.origin-card :deep(.rich-content) {
  margin: 12px 0 0;
}
.origin-text {
  margin-top: 32px;
  border-top: 1px solid var(--el-border-color);
  padding-top: 16px;
  font-size: 16px;
  font-weight: 600;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.origin-text p {
  margin: 0;
}
.origin-note {
  margin: 32px 0 12px;
}
</style>
