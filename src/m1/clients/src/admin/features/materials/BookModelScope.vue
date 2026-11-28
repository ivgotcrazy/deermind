<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ElSelect, ElOption } from 'element-plus';
import { get } from '../../../shared/api/http';
import { bookPath, type BookTypes, type BookSession } from '../../../shared/book/editions';
import type { DomainRow } from '../domain/api';
const props = defineProps<{ session: BookSession; domain?: string }>();
const emit = defineEmits<{
  change: [BookTypes['TextbookListItem'] | undefined, BookTypes['EditionInfo'] | undefined];
}>();
const domains = ref<DomainRow[]>([]),
  books = ref<BookTypes['TextbookListItem'][]>([]),
  editions = ref<BookTypes['EditionInfo'][]>([]),
  selectedDomain = ref(props.domain ?? ''),
  book = ref(''),
  edition = ref(''),
  error = ref('');
const current = computed(() => books.value.find((b) => b.textbook_id === book.value));
const controller = new AbortController();
onMounted(async () => {
  if (!props.domain)
    try {
      domains.value = (
        await get('/api/m1/domains', { session: props.session, signal: controller.signal })
      ).items;
    } catch (e) {
      if (!controller.signal.aborted) error.value = (e as Error).message;
    }
});
onBeforeUnmount(() => controller.abort());
watch(
  () => props.domain,
  (v) => {
    selectedDomain.value = v ?? '';
  },
);
watch(
  selectedDomain,
  async (id, _, cleanup) => {
    book.value = '';
    books.value = [];
    editions.value = [];
    error.value = '';
    emit('change', undefined, undefined);
    if (!id) return;
    const ctl = new AbortController();
    cleanup(() => ctl.abort());
    try {
      const found: BookTypes['TextbookListItem'][] = [];
      let cursor: string | undefined;
      do {
        const page = await get('/api/m1/textbooks', {
          session: props.session,
          signal: ctl.signal,
          query: { domain_id: id, cursor },
        });
        found.push(...page.items);
        cursor = page.next_cursor ?? undefined;
      } while (cursor);
      if (!ctl.signal.aborted) {
        books.value = found;
        if (found.length === 1) book.value = found[0]!.textbook_id;
      }
    } catch (e) {
      if (!ctl.signal.aborted) error.value = (e as Error).message;
    }
  },
  { immediate: true },
);
watch(book, async (id, _, cleanup) => {
  edition.value = '';
  editions.value = [];
  emit('change', current.value, undefined);
  if (!id) return;
  const ctl = new AbortController();
  cleanup(() => ctl.abort());
  try {
    const all = await get(bookPath, {
      session: props.session,
      signal: ctl.signal,
      params: { book: id },
    });
    if (!ctl.signal.aborted) {
      editions.value = all.filter((e) => e.kind === 'extraction' && e.status === 'published');
      edition.value = editions.value[0]?.edition_id ?? '';
    }
  } catch (e) {
    if (!ctl.signal.aborted) error.value = (e as Error).message;
  }
});
watch(edition, (id) =>
  emit(
    'change',
    current.value,
    editions.value.find((e) => e.edition_id === id),
  ),
);
</script>
<template>
  <div class="scope">
    <label v-if="!domain"
      >领域<ElSelect v-model="selectedDomain" filterable placeholder="选择领域"
        ><ElOption
          v-for="d in domains"
          :key="d.object_ref.object_id"
          :label="d.name"
          :value="d.object_ref.object_id" /></ElSelect
    ></label>
    <label
      >教材<ElSelect v-model="book" filterable :disabled="!selectedDomain" placeholder="选择教材"
        ><ElOption
          v-for="b in books"
          :key="b.textbook_id"
          :label="b.metadata.title"
          :value="b.textbook_id" /></ElSelect
    ></label>
    <label
      >已发布教学提炼<ElSelect
        v-model="edition"
        :disabled="!book"
        placeholder="选择提炼版本"
        no-data-text="这本教材还没有已发布提炼"
        ><ElOption
          v-for="e in editions"
          :key="e.edition_id"
          :label="'教学提炼 v' + e.number"
          :value="e.edition_id" /></ElSelect
    ></label>
  </div>
  <p v-if="error" role="alert">{{ error }}</p>
</template>
<style scoped>
.scope {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: 16px 0;
}
.scope label {
  display: grid;
  gap: 6px;
  min-width: 170px;
  flex: 1;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
