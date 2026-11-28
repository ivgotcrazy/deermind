<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue';
import { get } from '../../../shared/api/http';
import OriginalPage from '../../../shared/book/OriginalPage.vue';
import type { BookSession, BookTypes } from '../../../shared/book/editions';

const props = defineProps<{ book: string; session: BookSession }>();
const pages = ref<BookTypes['BookPage'][]>([]),
  page = ref(''),
  error = ref('');
const stop = new AbortController();
onMounted(async () => {
  try {
    pages.value = await get('/api/m1/textbooks/{book}/editions/pages', {
      session: props.session,
      params: { book: props.book },
      signal: stop.signal,
    });
    page.value = pages.value[0]?.page_id ?? '';
  } catch (e) {
    if (!stop.signal.aborted) error.value = (e as Error).message;
  }
});
onBeforeUnmount(() => stop.abort());
</script>
<template>
  <p v-if="error" role="alert">{{ error }}</p>
  <OriginalPage
    v-else
    v-model="page"
    :pages="pages"
    :session="session"
    :url="'/api/m1/textbooks/' + book + '/editions/pages'"
  />
</template>
