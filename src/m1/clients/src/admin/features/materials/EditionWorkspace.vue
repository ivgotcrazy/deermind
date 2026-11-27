<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElButton, ElDialog, ElMessageBox, ElTag } from 'element-plus';
import { get, post, postAccepted } from '../../../shared/api/http';
import OriginalPage from '../../../shared/book/OriginalPage.vue';
import {
  bookPath,
  editionPath,
  nodeText,
  outline,
  sectionOf,
  type BookSession,
  type BookTypes,
  type Edition,
  type MapTask,
} from '../../../shared/book/editions';
const { session, book, importId } = defineProps<{
  session: BookSession;
  book: string;
  importId: string;
}>();
type Info = BookTypes['EditionInfo'];
const versions = ref<Info[]>([]),
  tree = ref<Edition>(),
  extraction = ref<Edition>(),
  pages = ref<BookTypes['BookPage'][]>([]);
const catalog = ref<MapTask[]>([]),
  page = ref(''),
  node = ref(''),
  error = ref(''),
  feedback = ref(''),
  busy = ref(false);
const correction = ref(''),
  editTasks = ref(false),
  selected = ref<Record<string, string[]>>({}),
  usage = ref<string[]>([]);
const stop = new AbortController();
const options = { session, signal: stop.signal };
const trees = computed(() => versions.value.filter((v) => v.kind === 'tree'));
const extracts = computed(() =>
  versions.value.filter((v) => v.kind === 'extraction' && v.tree_id === tree.value?.edition_id),
);
const rows = computed(() => outline(tree.value?.nodes ?? []));
const chapter = computed(() => sectionOf(tree.value?.nodes ?? [], node.value));
const chapterTitle = computed(
  () => rows.value.find((r) => r.node.node_id === chapter.value)?.title || '请选择章或节',
);
const associated = computed(
  () => extraction.value?.entries.filter((t) => t.chapter_id === chapter.value) ?? [],
);
const title = (v: Info) => 'v' + v.number + ' · ' + (v.status === 'published' ? '已发布' : '草稿');
const diffs = computed(() => {
  if (!tree.value?.pending) return [];
  const before = new Map(tree.value.nodes.map((n) => [n.node_id, n])),
    after = new Map(tree.value.pending.map((n) => [n.node_id, n]));
  return [...new Set([...before.keys(), ...after.keys()])].flatMap((id) => {
    const a = before.get(id),
      b = after.get(id);
    if (JSON.stringify(a) === JSON.stringify(b)) return [];
    const describe = (n: NonNullable<typeof a>) =>
      [
        n.node_kind,
        nodeText(n),
        '顺序 ' + n.sibling_order,
        '父节点 ' +
          (rows.value.find((r) => r.node.node_id === n.parent_id)?.title ?? n.parent_id ?? '全书'),
      ].join(' · ');
    return [(a ? describe(a) : '新增') + ' → ' + (b ? describe(b) : '移除')];
  });
});
function chooseNode(id: string) {
  node.value = id;
  const n = tree.value?.nodes.find((n) => n.node_id === id);
  if (n && !n.covered_page_ids.includes(page.value)) page.value = n.covered_page_ids[0] ?? '';
}
async function pickExtraction(id?: string) {
  extraction.value = undefined;
  usage.value = [];
  if (!id) return;
  extraction.value = await get(editionPath, { ...options, params: { book, edition: id } });
  usage.value = (
    await get('/api/m1/textbooks/{book}/editions/{edition}/usage', {
      ...options,
      params: { book, edition: id },
    })
  ).map((r) => r.title + ' v' + r.target_ref.revision);
}
const savedNotes = new Map<string, string>();
async function switchTree(select: HTMLSelectElement) {
  const next = select.value;
  const current = tree.value?.edition_id;
  if (current && correction.value.trim()) {
    select.value = current;
    try {
      await ElMessageBox.confirm('切换版本前是否保留这段未发送的纠错说明？', '切换内容树版本', {
        confirmButtonText: '保留后切换',
        cancelButtonText: '放弃后切换',
        distinguishCancelAndClose: true,
        showClose: true,
      });
      savedNotes.set(current, correction.value);
    } catch (reason) {
      if (reason !== 'cancel') return;
      savedNotes.delete(current);
    }
  }
  await pickTree(next);
  correction.value = savedNotes.get(next) ?? '';
}
async function pickTree(id?: string, prefer?: string) {
  tree.value = undefined;
  node.value = '';
  extraction.value = undefined;
  usage.value = [];
  if (!id) return;
  tree.value = await get(editionPath, { ...options, params: { book, edition: id } });
  if (!tree.value.pages.some((p) => p.page_id === page.value))
    page.value = tree.value.pages[0]?.page_id ?? '';
  chooseNode(
    rows.value.find((r) => r.node.node_kind === 'section' || r.node.node_kind === 'chapter')?.node
      .node_id ?? '',
  );
  await pickExtraction(
    extracts.value.find((v) => v.edition_id === prefer)?.edition_id ??
      extracts.value[0]?.edition_id,
  );
  sessionStorage.setItem('book-tree-' + book, id);
}
async function reload(preferTree?: string, preferExtraction?: string) {
  versions.value = await get(bookPath, { ...options, params: { book } });
  const requested = new URLSearchParams(window.location.search);
  const key =
    preferTree ??
    tree.value?.edition_id ??
    requested.get('tree') ??
    sessionStorage.getItem('book-tree-' + book);
  const next =
    trees.value.find((v) => v.edition_id === key) ??
    trees.value.find((v) => v.status === 'draft') ??
    trees.value[0];
  const last = node.value;
  await pickTree(
    next?.edition_id,
    preferExtraction ?? extraction.value?.edition_id ?? requested.get('extraction') ?? undefined,
  );
  if (tree.value?.nodes.some((n) => n.node_id === last)) chooseNode(last);
}
async function act(fn: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await fn();
  } catch (e) {
    if (!stop.signal.aborted) error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
onMounted(
  () =>
    void act(async () => {
      pages.value = await get('/api/m1/textbooks/{book}/editions/pages', {
        ...options,
        params: { book },
      });
      page.value = pages.value[0]?.page_id ?? '';
      await reload();
    }),
);
onBeforeUnmount(() => stop.abort());
async function submit(
  value: Edition,
  action: BookTypes['EditionCommand']['action'],
  tasks?: BookTypes['ChapterTask'][],
) {
  if (action === 'publish') {
    const base = value.base_edition_id
      ? await get(editionPath, { ...options, params: { book, edition: value.base_edition_id } })
      : undefined;
    const items = (ed?: Edition) =>
      new Map(
        ed?.kind === 'tree'
          ? ed.nodes.map((n) => [n.node_id, JSON.stringify(n)] as const)
          : (ed?.entries ?? []).map(
              (t) => [t.chapter_id + ':' + t.task_ref.object_id, JSON.stringify(t)] as const,
            ),
      );
    const old = items(base),
      next = items(value);
    const added = [...next.keys()].filter((id) => !old.has(id)).length;
    const removed = [...old.keys()].filter((id) => !next.has(id)).length;
    const changed = [...next.keys()].filter(
      (id) => old.has(id) && old.get(id) !== next.get(id),
    ).length;
    const basis = value.kind === 'extraction' ? '，基于内容树 v' + tree.value?.number : '';
    if (
      !window.confirm(
        '发布整本' +
          (value.kind === 'tree' ? '内容树' : '教学提炼') +
          ' v' +
          value.number +
          basis +
          '？\n新增 ' +
          added +
          ' 项，修改 ' +
          changed +
          ' 项，移除 ' +
          removed +
          ' 项。发布后只读。',
      )
    )
      return;
  }
  if (action === 'discard' && !window.confirm('丢弃整份草稿 v' + value.number + '？')) return;
  const result = await post(
    editionPath,
    {
      request_id: crypto.randomUUID(),
      action,
      revision: value.revision,
      chapter_id: chapter.value || null,
      tasks: tasks ?? [],
    },
    { ...options, params: { book, edition: value.edition_id } },
  );
  editTasks.value = false;
  await reload(
    value.kind === 'tree' ? result.edition_id : tree.value?.edition_id,
    value.kind === 'extraction' ? result.edition_id : undefined,
  );
  feedback.value = action === 'publish' ? '已发布。' : '已保存。';
}
async function generate(action: 'tree' | 'correct' | 'extract') {
  const request = crypto.randomUUID(),
    source = tree.value;
  const job = await postAccepted(
    '/api/m1/material-imports/{import_id}/messages',
    {
      request_id: request,
      message:
        action === 'correct'
          ? correction.value
          : action === 'tree'
            ? '生成整本教材内容树。'
            : '根据已发布的内容树重新提炼整本教材。',
      edition_job: {
        action,
        edition_id: action === 'tree' ? null : source?.edition_id,
        revision: action === 'tree' ? null : source?.revision,
        node_id: action === 'correct' ? node.value : null,
      },
    },
    { ...options, params: { import_id: importId } },
  );
  feedback.value = '教材助手正在处理，可离开后再回来查看。';
  for (let tries = 0; tries < 600 && !stop.signal.aborted; tries++) {
    await new Promise((r) => setTimeout(r, 2000));
    if (stop.signal.aborted) return;
    const receipt = await get('/api/m1/requests/receipt', {
      ...options,
      query: {
        request_id: request,
        action: 'product.converse_material_assistant',
        resource_kind: 'material_import',
        resource_id: importId,
      },
    });
    if (receipt.receipt_state === 'rejected' || receipt.business_state === 'failed')
      throw new Error('生成失败，请查看教材助手记录后重试。');
    if (receipt.receipt_state === 'completed') {
      if (receipt.business_state === 'needs_input')
        throw new Error('教材助手需要补充说明，请在下方对话记录查看原因。');
      await reload(
        action === 'tree' ? job.request_ref : source?.edition_id,
        action === 'extract' ? job.request_ref : undefined,
      );
      feedback.value = '处理已结束。';
      correction.value = '';
      return;
    }
  }
  feedback.value = '请刷新查看最新处理结果。';
}
async function editing() {
  catalog.value = await get('/api/m1/textbooks/{book}/editions/catalog', {
    ...options,
    params: { book },
  });
  selected.value = Object.fromEntries(
    associated.value.map((t) => [t.task_ref.object_id, t.method_refs.map((m) => m.object_id)]),
  );
  for (const t of catalog.value) selected.value[t.task_ref.object_id] ??= [];
  editTasks.value = true;
}
function taskSelection() {
  return catalog.value.flatMap((t) => {
    const methods = t.method_refs.filter((m) =>
      selected.value[t.task_ref.object_id]?.includes(m.object_id),
    );
    return methods.length
      ? [
          {
            chapter_id: chapter.value,
            task_ref: t.task_ref,
            method_refs: methods,
            source_nodes:
              associated.value.find((a) => a.task_ref.object_id === t.task_ref.object_id)
                ?.source_nodes ?? [],
          },
        ]
      : [];
  });
}
</script>
<template>
  <section aria-label="教材版本工作区" class="editions">
    <p v-if="error" class="problem" role="alert">{{ error }}</p>
    <p v-if="feedback" role="status">{{ feedback }}</p>
    <div class="book-columns">
      <section>
        <h3>教材原页</h3>
        <OriginalPage
          v-model="page"
          :pages="tree?.pages ?? pages"
          :session="session"
          :url="'/api/m1/textbooks/' + book + '/editions/pages'"
        />
      </section>
      <section>
        <header>
          <h3>内容树</h3>
          <select
            v-if="trees.length"
            aria-label="内容树版本"
            :value="tree?.edition_id"
            :disabled="busy"
            @change="act(() => switchTree($event.target as HTMLSelectElement))"
          >
            <option v-for="v in trees" :key="v.edition_id" :value="v.edition_id">
              {{ title(v) }}
            </option>
          </select>
        </header>
        <ElButton v-if="!tree" :disabled="busy" type="primary" @click="act(() => generate('tree'))"
          >从原页生成内容树</ElButton
        >
        <template v-if="tree"
          ><div class="node-list">
            <button
              v-for="row in rows"
              :key="row.node.node_id"
              type="button"
              :class="{
                chosen: row.node.node_id === node,
                near: row.node.covered_page_ids.includes(page),
              }"
              :style="{ paddingLeft: 8 + row.depth * 12 + 'px' }"
              :aria-pressed="row.node.node_id === node"
              @click="chooseNode(row.node.node_id)"
            >
              {{ row.title }}
            </button>
          </div>
          <template v-if="tree.status === 'draft'"
            ><label
              >引用所选节点纠错<textarea
                v-model.trim="correction"
                placeholder="说明需要添加、移动或修改的内容"
                rows="2"
              /></label
            ><ElButton
              :disabled="busy || !correction || !node"
              @click="act(() => generate('correct'))"
              >提交给教材助手</ElButton
            >
            <div v-if="tree.pending">
              <h4>修正前后</h4>
              <p v-for="d in diffs" :key="d">{{ d }}</p>
              <ElButton :disabled="busy" @click="act(() => submit(tree!, 'apply_correction'))"
                >接受修正</ElButton
              ><ElButton :disabled="busy" @click="act(() => submit(tree!, 'reject_correction'))"
                >放弃修正</ElButton
              >
            </div>
            <div class="actions">
              <ElButton
                :disabled="busy || !!tree.pending"
                type="primary"
                @click="act(() => submit(tree!, 'publish'))"
                >发布整本内容树</ElButton
              ><ElButton :disabled="busy" @click="act(() => submit(tree!, 'discard'))"
                >丢弃草稿</ElButton
              >
            </div></template
          >
          <ElButton v-else :disabled="busy" @click="act(() => submit(tree!, 'copy'))"
            >基于此版建树草稿</ElButton
          ></template
        >
      </section>
      <section>
        <header>
          <h3>教学提炼</h3>
          <select
            v-if="extracts.length"
            :value="extraction?.edition_id"
            aria-label="提炼版本"
            :disabled="busy"
            @change="act(() => pickExtraction(($event.target as HTMLSelectElement).value))"
          >
            <option v-for="v in extracts" :key="v.edition_id" :value="v.edition_id">
              {{ title(v) }}
            </option>
          </select>
        </header>
        <p v-if="tree?.status !== 'published'">发布整本内容树后，可以生成教学提炼。</p>
        <template v-else
          ><p>基于内容树 v{{ tree.number }}</p>
          <ElButton :disabled="busy" @click="act(() => generate('extract'))">生成教学提炼</ElButton>
          <template v-if="extraction"
            ><h4>{{ chapterTitle }}</h4>
            <p v-if="!associated.length">本节尚无关联任务</p>
            <article v-for="t in associated" :key="t.task_ref.object_id">
              <strong>{{ t.name }}</strong>
              <p>{{ t.method_names.join('、') }}</p>
              <ElTag v-for="k in t.knowledge_names" :key="k">{{ k }}</ElTag><button
                @click="chooseNode(t.chapter_id)"
              >
                定位章节
              </button>
            </article>
            <p v-for="issue in extraction.issues" :key="issue" role="status">{{ issue }}</p>
            <div v-if="extraction.status === 'draft'" class="actions">
              <ElButton :disabled="busy || !chapter" @click="act(editing)">调整本节任务</ElButton
              ><ElButton
                :disabled="busy"
                type="primary"
                @click="act(() => submit(extraction!, 'publish'))"
                >发布整本教学提炼</ElButton
              ><ElButton :disabled="busy" @click="act(() => submit(extraction!, 'discard'))"
                >丢弃提炼草稿</ElButton
              >
            </div>
            <template v-else
              ><p>使用目标：{{ usage.join('、') || '暂无' }}</p>
              <ElButton :disabled="busy" @click="act(() => submit(extraction!, 'copy'))"
                >基于此版建提炼草稿</ElButton
              ></template
            ></template
          ></template
        >
      </section>
    </div>
    <ElDialog v-model="editTasks" title="调整本节任务" width="min(600px, 90vw)"
      ><p>{{ chapterTitle }} · 勾选本节采用的方法</p>
      <fieldset v-for="t in catalog" :key="t.task_ref.object_id">
        <legend>{{ t.name }}</legend>
        <label v-for="(m, i) in t.method_refs" :key="m.object_id"
          ><input v-model="selected[t.task_ref.object_id]" type="checkbox" :value="m.object_id" />{{
            t.method_names[i]
          }}</label
        >
      </fieldset>
      <p v-if="!catalog.length">请先在领域管理中建立可用任务及方法。</p>
      <template #footer
        ><ElButton @click="editTasks = false">取消</ElButton
        ><ElButton
          type="primary"
          :disabled="busy"
          @click="act(() => submit(extraction!, 'edit_tasks', taskSelection()))"
          >保存本节任务</ElButton
        ></template
      ></ElDialog
    >
  </section>
</template>
<style scoped>
.book-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.book-columns > section {
  min-width: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  padding: 14px;
}
.book-columns header,
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.book-columns h3 {
  margin: 0 0 12px;
}
.book-columns header {
  justify-content: space-between;
  margin-bottom: 10px;
}
.node-list {
  max-height: 52vh;
  overflow: auto;
  margin-bottom: 10px;
}
.node-list button {
  display: block;
  text-align: left;
  width: 100%;
  border: 0;
  border-left: 3px solid transparent;
  background: transparent;
  color: inherit;
  padding: 6px;
  overflow-wrap: anywhere;
}
.node-list .near {
  border-left-color: var(--el-color-primary-light-5);
}
.node-list .chosen {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
textarea {
  display: block;
  width: 100%;
  box-sizing: border-box;
}
.actions {
  margin-top: 12px;
}
.actions :deep(.el-button) {
  margin: 0;
}
article {
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 10px 0;
}
.problem {
  color: var(--el-color-danger);
}
fieldset label {
  display: block;
}
@media (max-width: 1000px) {
  .book-columns {
    grid-template-columns: 1fr 1fr;
  }
  .book-columns > section:last-child {
    grid-column: 1/-1;
  }
}
@media (max-width: 650px) {
  .book-columns {
    grid-template-columns: 1fr;
  }
}
</style>
