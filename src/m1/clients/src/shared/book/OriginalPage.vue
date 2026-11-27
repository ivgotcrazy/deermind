<script setup lang="ts">
import { ref, watch } from 'vue';
import type { BookSession, BookTypes } from './editions';
const props = defineProps<{ pages: BookTypes['BookPage'][]; url: string; session: BookSession }>();
const pageId = defineModel<string>({ required: true });
const image = ref(''),
  error = ref('');
watch(
  () => [pageId.value, props.url, props.session.session_id],
  async (_, __, cleanup) => {
    const controller = new AbortController();
    let objectUrl = '';
    cleanup(() => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    });
    image.value = '';
    error.value = '';
    if (!pageId.value) return;
    try {
      const response = await fetch(props.url + '/' + encodeURIComponent(pageId.value), {
        credentials: 'same-origin',
        headers: { 'X-Expected-Session': props.session.session_id },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('原页暂不可用。');
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      image.value = objectUrl;
    } catch (e) {
      if (!controller.signal.aborted) error.value = String(e);
    }
  },
  { immediate: true },
);
function move(by: number) {
  const next = props.pages[props.pages.findIndex((p) => p.page_id === pageId.value) + by];
  if (next) pageId.value = next.page_id;
}
</script>
<template>
  <section class="original-view">
    <div class="paging">
      <button
        type="button"
        aria-label="上一页"
        :disabled="!pages.length || pages[0]?.page_id === pageId"
        @click="move(-1)"
      >
        ‹
      </button>
      <select v-model="pageId" aria-label="教材原页">
        <option v-for="(p, i) in pages" :key="p.page_id" :value="p.page_id">
          {{ p.printed ? '书页 ' + p.printed : '原页 ' + (i + 1) }} · {{ p.name }}
        </option>
      </select>
      <button
        type="button"
        aria-label="下一页"
        :disabled="!pages.length || pages.at(-1)?.page_id === pageId"
        @click="move(1)"
      >
        ›
      </button>
    </div>
    <a v-if="image" :href="image" target="_blank" rel="noopener" title="打开原图"
      ><img :src="image" alt="所选教材原页"
    /></a>
    <p v-else role="status">{{ error || (pages.length ? '正在读取原页…' : '尚无原页') }}</p>
  </section>
</template>
<style scoped>
.paging {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.8rem;
}
.paging select {
  flex: 1;
  min-width: 0;
  max-width: 100%;
}
.paging button {
  padding: 0.25rem 0.6rem;
}
.original-view img {
  display: block;
  width: 100%;
  height: auto;
}
.original-view {
  min-width: 0;
}
</style>
