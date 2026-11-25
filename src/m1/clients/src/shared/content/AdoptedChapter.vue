<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';
import { get } from '../api/http';
import RichContent from './RichContent.vue';
import type { RichContent as StructuredContent } from './types';

type Chapter = components['schemas']['ChapterSnapshot'];
type Reference = components['schemas']['Ref'];
type Content = {
  title: string;
  content: StructuredContent;
  teachingAids: StructuredContent[];
  source?: Reference;
};
const props = defineProps<{
  session: Pick<components['schemas']['SessionView'], 'session_id' | 'csrf_token'>;
  space: string;
  chapters: Chapter[];
  allowReference?: boolean;
  reading?: { title: string; selectionKey: string };
}>();
const emit = defineEmits<{ reference: [item: { title: string; source: Reference }] }>();
const selected = ref('');
const contents = ref<Content[]>([]);
const error = ref('');
const loading = ref(false);
const chapterTitle = computed(
  () => props.chapters.find((chapter) => chapter.chapter_id === selected.value)?.title,
);
const pages = computed(() => [
  ...new Set(
    contents.value.flatMap(({ content }) =>
      content.source_refs.map((source) => source.printed_page).filter(Boolean),
    ),
  ),
]);
let navigation = 0;
watch(
  () => props.space,
  () => {
    selected.value = '';
    contents.value = [];
    if (!props.reading) return;
    let previous: string | null = null;
    try {
      previous = localStorage.getItem(props.reading.selectionKey);
    } catch {
      // 浏览器存储不可用时打开首个采用章节。
    }
    const chapter =
      props.chapters.find((item) => item.chapter_id === previous) ?? props.chapters[0];
    if (chapter) void open(chapter);
  },
  { immediate: true },
);

async function open(chapter: Chapter) {
  const request = ++navigation;
  const space_id = props.space;
  const chapter_id = chapter.chapter_id;
  selected.value = chapter_id;
  if (props.reading) {
    try {
      localStorage.setItem(props.reading.selectionKey, chapter_id);
    } catch {
      // 阅读不依赖本地存储。
    }
  }
  error.value = '';
  contents.value = [];
  loading.value = true;
  try {
    const data = await get('/api/m1/learning-spaces/{space_id}/chapters/{chapter_id}', {
      session: props.session,
      params: { space_id, chapter_id },
    });
    if (request !== navigation || space_id !== props.space) return;
    contents.value = data.items.flatMap((item) =>
      typeof item.title === 'string' && item.content && typeof item.content === 'object'
        ? [
            {
              title: item.title,
              content: item.content as StructuredContent,
              teachingAids: Array.isArray(item.teaching_aids)
                ? (item.teaching_aids as StructuredContent[])
                : [],
              source:
                item.source_ref && typeof item.source_ref === 'object'
                  ? (item.source_ref as Reference)
                  : undefined,
            },
          ]
        : [],
    );
  } catch (caught) {
    if (request === navigation && space_id === props.space) error.value = (caught as Error).message;
  } finally {
    if (request === navigation && space_id === props.space) loading.value = false;
  }
}
</script>

<template>
  <section class="adopted-content" :class="{ reading }" aria-label="已采用教材内容">
    <header v-if="reading && chapterTitle" class="chapter-heading">
      <p>{{ reading.title }}</p>
      <h4>{{ chapterTitle }}</h4>
    </header>
    <p v-if="!chapters.length">空间暂未采用教材章节。</p>
    <nav v-if="!reading || chapters.length > 1" aria-label="教材章节">
      <button
        v-for="chapter in chapters"
        :key="chapter.chapter_id"
        type="button"
        :aria-pressed="selected === chapter.chapter_id"
        @click="open(chapter)"
      >
        {{ chapter.title }}
      </button>
    </nav>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="loading" role="status">正在读取章节…</p>
    <p v-else-if="selected && !contents.length">这一章尚无可展示的采用内容。</p>
    <template v-else-if="allowReference && contents.length && !reading">
      <button
        v-for="chapter in chapters.filter((item) => item.chapter_id === selected)"
        :key="chapter.chapter_id"
        type="button"
        @click="
          emit('reference', {
            title: chapter.title,
            source: {
              owner: 'product',
              type: 'chapter',
              id: chapter.chapter_id,
              revision: chapter.revision,
            },
          })
        "
      >
        引用本节
      </button>
    </template>
    <article v-for="(item, index) in contents" :key="index">
      <h4>{{ item.title }}</h4>
      <RichContent :content="item.content" :show-source-pages="!reading" />
      <template v-if="reading">
        <RichContent
          v-for="(aid, aidIndex) in item.teachingAids"
          :key="aidIndex"
          :content="aid"
          :show-source-pages="false"
        />
      </template>
      <button
        v-if="allowReference && item.source"
        type="button"
        @click="emit('reference', { title: item.title, source: item.source })"
      >
        引用此处
      </button>
    </article>
    <footer v-if="reading && pages.length" class="page-number" aria-label="教材印刷页码">
      <span>第 {{ pages.join('、') }} 页</span>
      <span>教材内容</span>
    </footer>
  </section>
</template>

<style scoped>
.reading {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 100%;
  color: var(--foreground);
  font: var(--study-font-body, inherit);
}
.chapter-heading {
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}
.chapter-heading p {
  margin: 0 0 0.5rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta, inherit);
}
.chapter-heading h4 {
  margin: 0;
  font: var(--study-font-title, inherit);
}
.reading nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}
.reading button {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 0.375rem;
  background: var(--background);
  color: var(--primary);
  font: var(--study-font-ui, inherit);
  cursor: pointer;
}
.reading button:hover,
.reading button[aria-pressed='true'] {
  background: var(--accent);
}
.reading article h4 {
  margin: 0 0 0.75rem;
  font: var(--study-font-section, inherit);
}
.reading article > .rich-content + .rich-content {
  margin-top: 1rem;
}
.reading article + article {
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
.reading article button {
  margin-top: 0.625rem;
}
.page-number {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: auto;
  padding-block: 1rem 0.25rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta, inherit);
}
</style>
