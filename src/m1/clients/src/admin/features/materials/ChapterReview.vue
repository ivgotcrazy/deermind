<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import RichContent from '../../../shared/content/RichContent.vue';
import type { RichContent as Body } from '../../../shared/content/types';
import type { DomainSession } from '../domain/api';
import { detail, originalUrl } from './api';
import type { MaterialDetail } from './api';
import type { AdoptedCandidate } from './MaterialIntakePanel.vue';

export type ReviewItem = AdoptedCandidate & {
  batch_id: string;
  chapter_ref: { id: string };
  body: { title: string; content: Body; teaching_aids?: Body[] };
};
export type ChapterOption = { id: string; title: string };
const props = defineProps<{
  items: ReviewItem[];
  chapters: ChapterOption[];
  previous?: ReviewItem[];
  material: MaterialDetail;
  session: DomainSession;
  canCorrect: boolean;
}>();
const emit = defineEmits<{ correct: [item: ReviewItem, part: string]; chapter: [id: string] }>();
const chapter = ref('');
watch(chapter, (id) => emit('chapter', id));
watch(
  () => props.chapters,
  (options) => {
    if (!options.some((option) => option.id === chapter.value))
      chapter.value = options[0]?.id ?? '';
  },
  { immediate: true },
);
const current = computed(() => props.items.filter((item) => item.chapter_ref.id === chapter.value));
const fileOrder = computed(
  () => new Map(props.material.sources.map((file) => [file.receipt.storage_ref, file.order])),
);
function pageOrder(item: ReviewItem) {
  return Math.min(
    ...item.body.content.source_refs.map(
      (s) =>
        ('file_id' in s.ref
          ? (fileOrder.value.get(s.ref.file_id) ?? Number.MAX_SAFE_INTEGER)
          : Number.MAX_SAFE_INTEGER) *
          1_000_000 +
        (s.file_page ?? 0),
    ),
  );
}
const roots = computed(() =>
  current.value
    .filter(
      (item) =>
        !item.parent_ref ||
        !current.value.some((parent) => parent.candidate_id === item.parent_ref?.id),
    )
    .sort((a, b) => pageOrder(a) - pageOrder(b)),
);
function family(root: ReviewItem) {
  return [root, ...current.value.filter((item) => item.parent_ref?.id === root.candidate_id)];
}
const kinds: Record<string, string> = {
  kc: '知识成分',
  task_instance: '题目',
  reference: '教材解法',
};
function prior(item: ReviewItem) {
  return props.previous?.find((row) => row.candidate_id === item.candidate_id);
}
const preview = ref<HTMLDialogElement>();
const url = ref('');
const media = ref('');
const caption = ref('');
const previewError = ref('');
let generation = 0;
function release() {
  generation++;
  if (url.value) URL.revokeObjectURL(url.value.split('#', 1)[0] ?? url.value);
  url.value = '';
}
onBeforeUnmount(release);
async function inspect(source: Body['source_refs'][number]) {
  release();
  const request = generation;
  previewError.value = '';
  caption.value = '正在读取原页…';
  preview.value?.showModal();
  try {
    if (!('file_id' in source.ref)) throw new Error('缺少原件引用。');
    const id = source.ref.file_id;
    let page = props.material;
    let file = page.sources.find((s) => s.receipt.storage_ref === id);
    while (!file && page.next_source_cursor && request === generation) {
      page = (await detail(props.session, page.textbook.textbook_id, page.next_source_cursor))
        .import;
      file = page.sources.find((s) => s.receipt.storage_ref === id);
    }
    if (!file) throw new Error('找不到此条内容的原件。');
    const value = await originalUrl(props.session, file);
    if (request !== generation) {
      URL.revokeObjectURL(value);
      return;
    }
    media.value = file.receipt.media_type;
    caption.value = `${file.original_name} · 文件第 ${source.file_page ?? 1} 页`;
    url.value =
      media.value === 'application/pdf' ? value + '#page=' + (source.file_page ?? 1) : value;
  } catch (cause) {
    if (request === generation)
      previewError.value = cause instanceof Error ? cause.message : '无法打开原页。';
  }
}
</script>

<template>
  <label v-if="chapters.length"
    >当前章节
    <select v-model="chapter">
      <option v-for="option in chapters" :key="option.id" :value="option.id">
        {{ option.title }}
      </option>
    </select>
  </label>
  <p v-if="!roots.length">本章暂无内容。</p>
  <section v-for="root in roots" :key="root.candidate_id" class="review-family">
    <article
      v-for="item in family(root)"
      :key="item.candidate_id"
      :class="{ solution: item !== root }"
    >
      <h4>
        <small>{{ kinds[item.kind] }}</small> {{ item.body.title }}
      </h4>
      <template v-if="previous">
        <details
          v-if="prior(item) && JSON.stringify(prior(item)?.body) !== JSON.stringify(item.body)"
        >
          <summary>已修改 · 对照修订前内容</summary>
          <b>{{ prior(item)!.body.title }}</b><RichContent :content="prior(item)!.body.content" />
          <RichContent
            v-for="(aid, i) in prior(item)!.body.teaching_aids"
            :key="i"
            :content="aid"
          />
        </details>
        <small v-else>{{ prior(item) ? '沿用原文' : '新增内容' }}</small>
      </template>
      <RichContent :content="item.body.content" :show-source-pages="false" />
      <details v-if="item.body.teaching_aids?.length">
        <summary>教学辅助</summary>
        <RichContent v-for="(aid, i) in item.body.teaching_aids" :key="i" :content="aid" />
      </details>
      <div class="review-actions">
        <button
          v-for="s in item.body.content.source_refs"
          :key="s.source_id"
          type="button"
          @click="inspect(s)"
        >
          查看原页 · {{ s.printed_page || s.file_page }}
        </button>
        <button v-if="canCorrect" type="button" @click="emit('correct', item, '')">
          引用此项纠错
        </button>
        <template v-for="block in item.body.content.blocks" :key="block.block_id">
          <template v-if="['diagram', 'chart', 'table'].includes(block.type)">
            <button
              v-for="s in item.body.content.source_refs.filter((s) =>
                block.provenance.source_refs.includes(s.source_id),
              )"
              :key="s.source_id"
              type="button"
              @click="inspect(s)"
            >
              图表原页 · {{ s.printed_page || s.file_page }}
            </button>
          </template>
          <button
            v-if="canCorrect && ['diagram', 'chart', 'table'].includes(block.type)"
            type="button"
            @click="emit('correct', item, block.block_id)"
          >
            纠正图表 {{ block.block_id }}
          </button>
        </template>
      </div>
    </article>
  </section>
  <dialog ref="preview" aria-label="来源原页" @close="release">
    <header>
      <strong>{{ caption }}</strong>
      <button type="button" @click="preview?.close()">关闭原页</button>
    </header>
    <p v-if="previewError" role="alert">{{ previewError }}</p>
    <iframe v-else-if="url && media === 'application/pdf'" title="教材原页" :src="url" />
    <img v-else-if="url" :src="url" :alt="caption" />
  </dialog>
</template>

<style scoped>
.review-family {
  margin: 16px 0;
  border-top: 1px solid var(--el-border-color-light);
}
article {
  padding: 12px 0;
  overflow-wrap: anywhere;
}
.solution {
  margin-left: 16px;
  padding-left: 12px;
  border-left: 2px solid var(--el-border-color);
}
h4 {
  margin: 0 0 8px;
}
small {
  color: var(--el-text-color-secondary);
}
.review-actions,
header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
header {
  justify-content: space-between;
  margin-bottom: 10px;
}
dialog {
  width: min(850px, 90vw);
  max-height: 85vh;
  overflow: auto;
}
iframe {
  width: 100%;
  height: 65vh;
  border: 0;
}
img {
  max-width: 100%;
  display: block;
  margin: auto;
}
</style>
