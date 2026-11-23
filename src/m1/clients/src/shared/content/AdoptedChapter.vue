<script setup lang="ts">
import { ref, watch } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';
import { get } from '../api/http';
import RichContent from './RichContent.vue';
import type { RichContent as StructuredContent } from './types';

type Chapter = components['schemas']['ChapterSnapshot'];
type Reference = components['schemas']['Ref'];
type Content = { title: string; content: StructuredContent; source?: Reference };
const props = defineProps<{
  session: Pick<components['schemas']['SessionView'], 'session_id' | 'csrf_token'>;
  space: string;
  chapters: Chapter[];
  allowReference?: boolean;
}>();
const emit = defineEmits<{ reference: [item: { title: string; source: Reference }] }>();
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
        ? [
            {
              title: item.title,
              content: item.content as StructuredContent,
              source:
                item.source_ref && typeof item.source_ref === 'object'
                  ? (item.source_ref as Reference)
                  : undefined,
            },
          ]
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
    <template v-else-if="allowReference && contents.length">
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
      <RichContent :content="item.content" />
      <button
        v-if="allowReference && item.source"
        type="button"
        @click="emit('reference', { title: item.title, source: item.source })"
      >
        引用此处
      </button>
    </article>
  </section>
</template>
