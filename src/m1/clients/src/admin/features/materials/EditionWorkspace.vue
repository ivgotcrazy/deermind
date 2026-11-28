<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';
import { get, post } from '../../../shared/api/http';
import {
  bookPath,
  editionPath,
  sectionOf,
  type BookSession,
  type BookTypes,
  type Edition,
  type Node,
} from '../../../shared/book/editions';
import OriginalPage from '../../../shared/book/OriginalPage.vue';
import BookTreeEditor from './BookTreeEditor.vue';
import TeachingTaskEditor from './TeachingTaskEditor.vue';
import { generateBookDraft } from './generation';
const props = defineProps<{
  book: string;
  bookTitle: string;
  session: BookSession;
  importId: string;
  view: 'tree' | 'extraction' | 'work';
}>();
const emit = defineEmits<{ work: [] }>();
type Info = BookTypes['EditionInfo'];
const versions = ref<Info[]>([]),
  pages = ref<BookTypes['BookPage'][]>([]),
  tree = ref<Edition>(),
  extraction = ref<Edition>();
const page = ref(''),
  node = ref(''),
  error = ref(''),
  feedback = ref(''),
  busy = ref(false),
  createOpen = ref(false),
  sourceTree = ref('');
const controller = new AbortController(),
  options = { session: props.session, signal: controller.signal };
const trees = computed(() => versions.value.filter((v) => v.kind === 'tree'));
const extracts = computed(() =>
  versions.value.filter((v) => v.kind === 'extraction' && v.tree_id === tree.value?.edition_id),
);
const listed = computed(() => versions.value.filter((v) => v.kind === props.view));
const title = (v: Info) => 'v' + v.number + ' · ' + (v.status === 'published' ? '已发布' : '草稿');
const treeName = (id?: string | null) => {
  const row = trees.value.find((v) => v.edition_id === id);
  return row ? '内容树 v' + row.number : '—';
};
function selectNode(id: string) {
  node.value = id;
  const n = tree.value?.nodes.find((r) => r.node_id === id);
  if (n && !n.covered_page_ids.includes(page.value)) page.value = n.covered_page_ids[0] ?? '';
}
function read(id: string) {
  return get(editionPath, { ...options, params: { book: props.book, edition: id } });
}
async function pickTree(id?: string, selected?: string) {
  const next = id ? await read(id) : undefined;
  const choices = versions.value.filter((v) => v.kind === 'extraction' && v.tree_id === id);
  const target = choices.find((v) => v.edition_id === selected) ?? choices[0];
  const nextExtraction = target ? await read(target.edition_id) : undefined;
  tree.value = next;
  extraction.value = nextExtraction;
  if (!next?.nodes.some((n) => n.node_id === node.value))
    node.value = next?.nodes.find((n) => !n.parent_id)?.node_id ?? '';
  selectNode(node.value);
}
async function refresh(preferTree?: string, preferExtract?: string) {
  versions.value = await get(bookPath, { ...options, params: { book: props.book } });
  const id = preferTree ?? tree.value?.edition_id;
  await pickTree(
    (trees.value.find((v) => v.edition_id === id) ?? trees.value[0])?.edition_id,
    preferExtract ?? extraction.value?.edition_id,
  );
}
async function act(fn: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  feedback.value = '';
  try {
    await fn();
  } catch (e) {
    if (!controller.signal.aborted) error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
onMounted(() =>
  act(async () => {
    pages.value = await get('/api/m1/textbooks/{book}/editions/pages', {
      ...options,
      params: { book: props.book },
    });
    page.value = pages.value[0]?.page_id ?? '';
    const url = new URLSearchParams(location.search);
    await refresh(url.get('tree') ?? undefined, url.get('extraction') ?? undefined);
    const source = url.get('node');
    if (source && tree.value?.nodes.some((n) => n.node_id === source)) selectNode(source);
  }),
);
onBeforeUnmount(() => controller.abort());
async function command(
  v: Info,
  action: BookTypes['EditionCommand']['action'],
  extra: Partial<BookTypes['EditionCommand']> = {},
) {
  const result = await post(
    editionPath,
    { request_id: crypto.randomUUID(), action, revision: v.revision, ...extra },
    { ...options, params: { book: props.book, edition: v.edition_id } },
  );
  await refresh(
    v.kind === 'tree' ? result.edition_id : (v.tree_id ?? undefined),
    v.kind === 'extraction' ? result.edition_id : undefined,
  );
  feedback.value =
    action === 'publish' ? '版本已发布。' : action === 'discard' ? '版本已删除。' : '草稿已保存。';
}
async function confirmAction(v: Info, action: 'publish' | 'discard' | 'copy') {
  const label = action === 'publish' ? '发布' : action === 'discard' ? '删除' : '复制';
  try {
    await ElMessageBox.confirm(
      label +
        '整本' +
        (v.kind === 'tree' ? '内容树' : '教学提炼') +
        ' v' +
        v.number +
        '？' +
        (action === 'publish'
          ? '发布后只能查看。'
          : action === 'copy'
            ? '将创建一份独立草稿。'
            : ''),
      label + '版本',
      {
        confirmButtonText: label,
        cancelButtonText: '取消',
        type: action === 'discard' ? 'warning' : 'info',
      },
    );
  } catch {
    return;
  }
  await act(() => command(v, action));
}
async function openVersion(v: Info) {
  await act(async () => {
    await pickTree(
      v.kind === 'tree' ? v.edition_id : v.tree_id!,
      v.kind === 'extraction' ? v.edition_id : undefined,
    );
    emit('work');
  });
}
async function generate() {
  const action = props.view === 'tree' ? 'tree' : 'extract';
  const source = trees.value.find((v) => v.edition_id === sourceTree.value);
  if (action === 'extract' && !source) return;
  createOpen.value = false;
  await act(async () => {
    feedback.value = '正在生成整本草稿，可离开后再查看。';
    const id = await generateBookDraft(
      options,
      props.importId,
      { action, edition_id: source?.edition_id, revision: source?.revision },
      action === 'tree' ? '解析整本教材内容树。' : '从本版内容树提炼教学任务。',
    );
    await refresh(
      action === 'tree' ? id : source?.edition_id,
      action === 'extract' ? id : undefined,
    );
    feedback.value = '草稿已生成，可在工作台编辑。';
  });
}
function create() {
  sourceTree.value = trees.value.find((v) => v.status === 'published')?.edition_id ?? '';
  createOpen.value = true;
}
async function saveTree(nodes: Node[]) {
  if (tree.value) await command(tree.value, 'edit_tree', { nodes });
}
async function saveTasks(teaching: BookTypes['TeachingModel']) {
  if (extraction.value) await command(extraction.value, 'edit_teaching', { teaching });
}
</script>
<template>
  <section class="editions">
    <p v-if="error" role="alert" class="problem">{{ error }}</p>
    <p v-if="feedback" role="status">{{ feedback }}</p>
    <section v-if="view !== 'work'" class="version-list">
      <header>
        <div>
          <h2>{{ view === 'tree' ? '内容树版本' : '教学提炼版本' }}</h2>
          <p>
            {{
              view === 'tree'
                ? '整本解析原件，草稿可在工作台逐节点编辑。'
                : '从已发布内容树生成教学任务，整本发布后可用于评估和目标。'
            }}
          </p>
        </div>
        <ElButton
          type="primary"
          :disabled="
            busy ||
            !pages.length ||
            (view === 'extraction' && !trees.some((v) => v.status === 'published'))
          "
          @click="create"
          >创建{{ view === 'tree' ? '内容树' : '教学提炼' }}</ElButton
        >
      </header>
      <ElTable :data="listed" row-key="edition_id" empty-text="暂无版本"
        ><ElTableColumn label="名称" min-width="150"
          ><template #default>{{
            bookTitle + (view === 'tree' ? ' · 内容树' : ' · 教学提炼')
          }}</template></ElTableColumn
        >
        <ElTableColumn label="版本" width="75"
          ><template #default="{ row }">v{{ row.number }}</template></ElTableColumn
        >
        <ElTableColumn v-if="view === 'extraction'" label="来源树版本" min-width="110"
          ><template #default="{ row }">{{ treeName(row.tree_id) }}</template></ElTableColumn
        >
        <ElTableColumn label="状态" width="90"
          ><template #default="{ row }"
            ><ElTag :type="row.status === 'published' ? 'success' : 'info'">{{
              row.status === 'published' ? '已发布' : '草稿'
            }}</ElTag></template
          ></ElTableColumn
        >
        <ElTableColumn label="创建时间" min-width="145"
          ><template #default="{ row }">{{
            new Date(row.created_at).toLocaleString('zh-CN', { hour12: false })
          }}</template></ElTableColumn
        >
        <ElTableColumn label="操作" min-width="175"
          ><template #default="{ row }"
            ><ElButton link type="primary" :disabled="busy" @click="openVersion(row as Info)">{{
              row.status === 'published' ? '查看' : '编辑'
            }}</ElButton
            ><ElButton
              v-if="row.status === 'published'"
              link
              :disabled="busy"
              @click="confirmAction(row as Info, 'copy')"
              >复制</ElButton
            ><ElButton
              v-else
              link
              type="primary"
              :disabled="busy"
              @click="confirmAction(row as Info, 'publish')"
              >发布</ElButton
            ><ElButton
              link
              type="danger"
              :disabled="busy"
              @click="confirmAction(row as Info, 'discard')"
              >删除</ElButton
            ></template
          ></ElTableColumn
        >
      </ElTable>
    </section>
    <div v-else class="book-columns">
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
        <h3>内容树</h3>
        <ElSelect
          v-if="trees.length"
          aria-label="内容树版本"
          :model-value="tree?.edition_id"
          :disabled="busy"
          @change="(id: string) => act(() => pickTree(id))"
          ><ElOption v-for="v in trees" :key="v.edition_id" :label="title(v)" :value="v.edition_id"
        /></ElSelect>
        <BookTreeEditor
          v-if="tree"
          :edition="tree"
          :selected="node"
          :save="saveTree"
          :busy="busy"
          @select="selectNode"
        /><ElEmpty v-else description="尚无内容树" :image-size="60" />
      </section>
      <section>
        <h3>教学提炼</h3>
        <ElSelect
          v-if="extracts.length"
          aria-label="教学提炼版本"
          :model-value="extraction?.edition_id"
          :disabled="busy"
          @change="
            (id: string) =>
              act(async () => {
                extraction = await read(id);
              })
          "
          ><ElOption
            v-for="v in extracts"
            :key="v.edition_id"
            :label="title(v)"
            :value="v.edition_id"
        /></ElSelect>
        <template v-if="tree && extraction"
          ><p v-for="(issue, i) in extraction.issues" :key="i" role="status">{{ issue }}</p>
          <TeachingTaskEditor
            :key="extraction.edition_id"
            :edition="extraction"
            :tree="tree"
            :save="saveTasks"
            :chapter="sectionOf(tree.nodes, node)"
            @source="selectNode"
          />
        </template>
        <ElEmpty
          v-else
          :description="
            tree?.status === 'draft' ? '发布这版内容树后可创建教学提炼' : '本版内容树暂无教学提炼'
          "
          :image-size="60"
        />
      </section>
    </div>
    <ElDialog
      v-model="createOpen"
      :title="view === 'tree' ? '创建内容树' : '创建教学提炼'"
      width="min(470px,92vw)"
      ><p>
        {{
          view === 'tree'
            ? '将重新解析整本原件并保存为新草稿。'
            : '请选择此次提炼依据的已发布内容树。'
        }}
      </p>
      <ElSelect v-if="view === 'extraction'" v-model="sourceTree" aria-label="依据的内容树"
        ><ElOption
          v-for="v in trees.filter((r) => r.status === 'published')"
          :key="v.edition_id"
          :label="title(v)"
          :value="v.edition_id"
      /></ElSelect>
      <template #footer
        ><ElButton @click="createOpen = false">取消</ElButton
        ><ElButton type="primary" :disabled="busy" @click="generate">开始生成</ElButton></template
      ></ElDialog
    >
  </section>
</template>
<style scoped>
.editions {
  margin-top: 18px;
}
.version-list,
.book-columns > section {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 18px;
  min-width: 0;
}
.version-list header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 15px;
}
.version-list h2,
.book-columns h3 {
  margin: 0;
  font-size: 16px;
}
.version-list header p {
  color: var(--el-text-color-secondary);
  margin: 5px 0 0;
  font-size: 13px;
}
.book-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}
.book-columns > section {
  min-height: 340px;
}
.book-columns h3 {
  margin-bottom: 14px;
}
.book-columns .el-select {
  margin-bottom: 10px;
}
.problem {
  color: var(--el-color-danger);
}
@media (max-width: 1000px) {
  .book-columns {
    grid-template-columns: repeat(3, minmax(235px, 1fr));
    overflow-x: auto;
  }
}
</style>
