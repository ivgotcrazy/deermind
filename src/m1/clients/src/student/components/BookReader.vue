<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ChevronDown, ChevronRight } from '@lucide/vue';
import { ApiError, get } from '../../shared/api/http';
import {
  outline,
  type Node,
  type BookSession,
  type BookTypes,
  type MapTask,
} from '../../shared/book/editions';
import OriginalPage from '../../shared/book/OriginalPage.vue';
const props = defineProps<{ space: string; session: BookSession }>();
const emit = defineEmits<{ reference: [{ title: string; source: BookTypes['Ref'] }] }>();
const book = ref<BookTypes['StudentBook']>(),
  legacy = ref(false),
  error = ref(''),
  tab = ref('章节');
const filter = ref(''),
  page = ref(''),
  selected = ref(''),
  stack = ref<MapTask[]>([]);
const retry = ref(0),
  dialog = ref<HTMLDialogElement>();
const collapsed = ref(new Set<string>());
const quoteId = ref('');
watch(page, () => (quoteId.value = ''), { flush: 'sync' });
watch(
  () => [props.space, retry.value],
  async (_, __, cleanup) => {
    const c = new AbortController();
    cleanup(() => c.abort());
    book.value = undefined;
    legacy.value = false;
    error.value = '';
    page.value = '';
    selected.value = '';
    collapsed.value.clear();
    quoteId.value = '';
    filter.value = '';
    stack.value = [];
    tab.value = '章节';
    try {
      const data = await get('/api/m1/learning-spaces/{space_id}/book', {
        session: props.session,
        params: { space_id: props.space },
        signal: c.signal,
      });
      if (!c.signal.aborted) {
        book.value = data;
        page.value = data.tree.pages[0]?.page_id ?? '';
      }
    } catch (e) {
      if (!c.signal.aborted) {
        if (e instanceof ApiError && e.status === 404) legacy.value = true;
        else error.value = (e as Error).message;
      }
    }
  },
  { immediate: true },
);
const rows = computed(() => outline(book.value?.tree.nodes ?? []));
// Non-directory nodes can group chapters in the source book. Skip them for display and nesting.
const sections = computed(() => {
  type ChapterRow = (typeof rows.value)[number] & { ancestors: string[]; hasChildren: boolean };
  const chapters: ChapterRow[] = [];
  const parents: ChapterRow[] = [];
  for (const row of rows.value) {
    while (parents.length && parents.at(-1)!.depth >= row.depth) parents.pop();
    if (!['unit', 'chapter', 'section'].includes(row.node.node_kind)) continue;
    const parent = parents.at(-1);
    if (parent) parent.hasChildren = true;
    const chapter = { ...row, ancestors: parents.map((p) => p.node.node_id), hasChildren: false };
    chapters.push(chapter);
    parents.push(chapter);
  }
  return chapters;
});
const directory = computed(() =>
  sections.value.filter((r) => !r.ancestors.some((id) => collapsed.value.has(id))),
);
function toggleBranch(id: string) {
  if (collapsed.value.has(id)) collapsed.value.delete(id);
  else collapsed.value.add(id);
}
const pagePassages = computed(() =>
  rows.value.filter(({ node }) => node.covered_page_ids.includes(page.value) && node.content?.text),
);
const quotedPassage = computed(() =>
  pagePassages.value.find(({ node }) => node.node_id === quoteId.value),
);
const allTasks = computed(() => book.value?.extraction.entries ?? []);
const parents = computed(() => new Map(rows.value.map((r) => [r.node.node_id, r.node.parent_id])));
function inside(chapter: string, ancestor: string) {
  let id: string | null = chapter;
  const lookup = parents.value;
  while (id) {
    if (id === ancestor) return true;
    id = lookup.get(id) ?? null;
  }
  return false;
}
function groupTasks(entries: MapTask[]) {
  const groups = new Map<string, MapTask>();
  for (const row of entries) {
    const key = row.task_ref.object_id + ':' + row.task_ref.version;
    const item = groups.get(key);
    if (!item) {
      groups.set(key, {
        ...row,
        method_refs: [...row.method_refs],
        method_names: [...row.method_names],
        method_knowledge: [...row.method_knowledge],
        knowledge: [...row.knowledge],
        knowledge_names: [...row.knowledge_names],
        source_nodes: [...(row.source_nodes ?? [])],
      });
      continue;
    }
    row.method_refs.forEach((ref, i) => {
      if (item.method_refs.some((m) => m.object_id === ref.object_id && m.version === ref.version))
        return;
      item.method_refs.push(ref);
      item.method_names.push(row.method_names[i]!);
      item.method_knowledge.push(row.method_knowledge[i]!);
    });
    row.knowledge.forEach((ref, i) => {
      if (item.knowledge.some((k) => k.object_id === ref.object_id && k.version === ref.version))
        return;
      item.knowledge.push(ref);
      item.knowledge_names.push(row.knowledge_names[i]!);
    });
    item.source_nodes = [...new Set([...(item.source_nodes ?? []), ...(row.source_nodes ?? [])])];
  }
  return [...groups.values()];
}
const bookTasks = computed(() => groupTasks(allTasks.value));
const tasks = computed(() =>
  filter.value
    ? groupTasks(allTasks.value.filter((t) => inside(t.chapter_id, filter.value)))
    : bookTasks.value,
);
function taskSections(t: MapTask) {
  return sections.value
    .filter((r) =>
      allTasks.value.some((a) => same(a, t.task_ref) && a.chapter_id === r.node.node_id),
    )
    .map((r) => r.title)
    .join('、');
}
function same(t: MapTask, r: BookTypes['TaskRef']) {
  return t.task_ref.object_id === r.object_id && t.task_ref.version === r.version;
}
const current = computed(() => stack.value.at(-1));
function open(t: MapTask) {
  stack.value = [...stack.value, t];
  if (!dialog.value?.open) dialog.value?.showModal();
}
function lookup(r: BookTypes['TaskRef']) {
  return (
    bookTasks.value.find((t) => same(t, r)) ?? book.value?.related_tasks?.find((t) => same(t, r))
  );
}
function locate(n: Node) {
  page.value = n.covered_page_ids[0] ?? '';
  quoteId.value = n.node_id;
  dialog.value?.close();
  tab.value = '原始教材';
}
function locateSource(id: string) {
  const n = book.value?.tree.nodes.find((n) => n.node_id === id);
  if (n) locate(n);
}
function quote(n: Node) {
  if (book.value)
    emit('reference', {
      title: rows.value.find((r) => r.node.node_id === n.node_id)?.title ?? '教材原文',
      source: {
        owner: 'product',
        type: 'material_content_node',
        id: n.node_id,
        revision: book.value.tree.number,
      },
    });
}
</script>
<template>
  <slot v-if="legacy" />
  <p v-else-if="error" role="alert">{{ error }} <button @click="retry++">重试</button></p>
  <p v-else-if="!book">正在读取教材…</p>
  <div v-else class="book-reader">
    <nav aria-label="教材视图">
      <button
        v-for="name in ['章节', '学习地图', '原始教材']"
        :key="name"
        :aria-pressed="tab === name"
        @click="tab = name"
      >
        {{ name }}
      </button>
    </nav>
    <section v-if="tab === '章节'" aria-label="章节目录">
      <p v-if="!directory.length">这本教材暂无章节目录。</p>
      <ul v-else>
        <li
          v-for="r in directory"
          :key="r.node.node_id"
          :style="{ paddingInlineStart: Math.min(5, r.ancestors.length) * 12 + 'px' }"
        >
          <div class="chapter-row">
            <button
              v-if="r.hasChildren"
              type="button"
              class="branch"
              :aria-expanded="!collapsed.has(r.node.node_id)"
              :aria-label="(collapsed.has(r.node.node_id) ? '展开 ' : '收起 ') + r.title"
              @click="toggleBranch(r.node.node_id)"
            >
              <component
                :is="collapsed.has(r.node.node_id) ? ChevronRight : ChevronDown"
                :size="16"
                aria-hidden="true"
              />
            </button>
            <span v-else class="branch-space" aria-hidden="true"></span>
            <button
              class="node"
              :aria-expanded="selected === r.node.node_id"
              @click="selected = selected === r.node.node_id ? '' : r.node.node_id"
            >
              {{ r.title }}
            </button>
          </div>
          <div v-if="selected === r.node.node_id" class="links">
            <button @click="locate(r.node)">查看原页</button>
            <button
              @click="
                filter = selected;
                tab = '学习地图';
              "
            >
              本节学习地图
            </button>
          </div>
        </li>
      </ul>
    </section>
    <section v-else-if="tab === '学习地图'">
      <label
        >章节范围<select v-model="filter">
          <option value="">整本教材</option>
          <option v-for="s in sections" :key="s.node.node_id" :value="s.node.node_id">
            {{ s.title }}
          </option>
        </select></label
      >
      <ul>
        <li v-for="t in tasks" :key="t.task_ref.object_id">
          <button class="node" @click="open(t)">{{ t.name }}</button><small>{{
            taskSections(t)
          }}</small>
        </li>
      </ul>
      <p v-if="!tasks.length">此范围尚无教学任务。</p>
    </section>
    <section v-else>
      <OriginalPage
        v-model="page"
        :pages="book.tree.pages"
        :url="'/api/m1/learning-spaces/' + space + '/book/pages'"
        :session="session"
      />
      <details v-if="pagePassages.length" class="quote-passage">
        <summary>引用本页原文</summary>
        <label
          >选择原文<select v-model="quoteId">
            <option value="">请选择</option>
            <option v-for="r in pagePassages" :key="r.node.node_id" :value="r.node.node_id">
              {{ r.title }}
            </option>
          </select></label
        >
        <button :disabled="!quotedPassage" @click="quotedPassage && quote(quotedPassage.node)">
          引用并提问
        </button>
      </details>
    </section>
    <dialog ref="dialog" @close="stack = []">
      <template v-if="current"
        ><button v-if="stack.length > 1" @click="stack.pop()">返回上一个任务</button>
        <h3>{{ current.name }}</h3>
        <p>{{ taskSections(current) }}</p>
        <h4>方法</h4>
        <p>{{ current.method_names.join('、') || '暂无' }}</p>
        <h4>知识点</h4>
        <p>{{ current.knowledge_names.join('、') || '暂无' }}</p>
        <template v-if="current.prerequisites.length"
          ><h4>前置任务</h4>
          <div v-for="p in current.prerequisites" :key="p.task_ref.object_id">
            <button v-if="lookup(p.task_ref)" @click="open(lookup(p.task_ref)!)">
              {{ lookup(p.task_ref)?.name }}
            </button>
            <p>
              {{ p.reason }}<span v-if="p.applies_to === 'specified'">（仅适用于指定方法）</span>
            </p>
          </div></template
        ><button v-for="s in current.source_nodes" :key="s" @click="locateSource(s)">
          查看教材原页 · {{ rows.find((r) => r.node.node_id === s)?.title }}
        </button>
        <footer><button @click="dialog?.close()">关闭</button></footer></template
      >
    </dialog>
  </div>
</template>
<style scoped>
.book-reader {
  font: inherit;
  color: inherit;
}
.book-reader nav,
.links {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}
.book-reader nav {
  border-bottom: 1px solid var(--border, #ddd);
  margin-bottom: 1rem;
}
.book-reader button,
.book-reader select {
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.book-reader nav button,
.node {
  border: 0;
  background: transparent;
  padding: 0.5rem 0.3rem;
  text-align: left;
}
.book-reader nav button[aria-pressed='true'] {
  border-bottom: 2px solid currentColor;
  font-weight: 600;
}
.book-reader ul {
  list-style: none;
  padding: 0;
}
.book-reader li {
  border-bottom: 1px solid var(--border, #ddd);
  padding: 0.25rem 0;
  overflow-wrap: anywhere;
}
.book-reader small,
.links span {
  display: block;
  width: 100%;
}
.chapter-row {
  display: flex;
  align-items: baseline;
}
.branch,
.branch-space {
  flex: 0 0 1.5rem;
}
.branch {
  align-self: center;
  display: grid;
  place-items: center;
  min-height: 1.75rem;
  background: transparent;
  border: 0;
}
.links {
  padding-inline-start: 1.5rem;
}
.quote-passage select {
  max-width: 100%;
}
.book-reader dialog {
  max-width: min(28rem, 90vw);
  border: 1px solid var(--border, #ddd);
  border-radius: 10px;
  padding: 1.4rem;
}
.book-reader dialog::backdrop {
  background: #17232155;
}
.book-reader footer {
  margin-top: 1rem;
}
</style>
