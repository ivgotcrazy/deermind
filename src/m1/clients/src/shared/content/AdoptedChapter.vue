<script setup lang="ts">
import { ref, watch } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';
import { get } from '../api/http';
import RichContent from './RichContent.vue';
import type { RichContent as StructuredContent } from './types';

type Chapter = components['schemas']['ChapterSnapshot'];
type Content = { title: string; content: StructuredContent };
const props = defineProps<{
  session: Pick<components['schemas']['SessionView'], 'session_id' | 'csrf_token'>;
  space: string;
  chapters: Chapter[];
}>();
const selected = ref('');
const contents = ref<Content[]>([]);
const error = ref('');
const loading = ref(false);
watch(
  () => props.space,
  () => {
    selected.value = '';
    contents.value = [];
  },
);

async function open(chapter: Chapter) {
  const space_id = props.space;
  const chapter_id = chapter.chapter_id;
  selected.value = chapter_id;
  error.value = '';
  contents.value = [];
  loading.value = true;
  try {
    const data = await get('/api/m1/learning-spaces/{space_id}/chapters/{chapter_id}', {
      session: props.session,
      params: { space_id, chapter_id },
    });
    if (chapter_id !== selected.value || space_id !== props.space) return;
    contents.value = data.items.flatMap((item) =>
      typeof item.title === 'string' && item.content && typeof item.content === 'object'
        ? [{ title: item.title, content: item.content as StructuredContent }]
        : [],
    );
  } catch (caught) {
    if (chapter_id === selected.value && space_id === props.space)
      error.value = (caught as Error).message;
  } finally {
    if (chapter_id === selected.value && space_id === props.space) loading.value = false;
  }
}
</script>

<template>
  <section aria-label="已采用教材内容">
    <p v-if="!chapters.length">空间暂未采用教材章节。</p>
    <nav aria-label="教材章节">
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
    <article v-for="(item, index) in contents" :key="index">
      <h4>{{ item.title }}</h4>
      <RichContent :content="item.content" />
    </article>
  </section>
</template>
