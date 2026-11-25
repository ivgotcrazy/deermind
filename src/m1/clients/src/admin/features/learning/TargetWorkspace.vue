<script setup lang="ts">
import { ElButton, ElTabPane, ElTabs } from 'element-plus';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post } from '../../../shared/api/http';
import { listDomains, type DomainSession } from '../domain/api';
import type { TextbookRow } from '../materials/api';
import CourseApplication from './CourseApplication.vue';
import TargetPromptChoices from './TargetPromptChoices.vue';
import { promptPreview, type Choices } from '../interaction/promptPreview';
import { methodKey, methodNames } from './methodNames';

type Schema = components['schemas'];
type Target = Schema['TargetView'];
type Claim = Schema['ClaimView'];
type Goal = Schema['GoalItemDraft'];
type Association = Schema['ChapterAssociationView'];
type Chapter = { id: string; title: string; revision: number; tasks: Association[] };
type Item = { draft: Goal; key: string; claim: Claim };
const props = defineProps<{ session: DomainSession }>();
const { guides, bindings } = promptPreview(props.session.session_id);
const promptChoices = ref<Choices>({});
const targetKey = (target: Target) =>
  target.target_ref.target_id + ':' + target.target_ref.revision;
const lifecycle = new AbortController();
const domains = ref<Schema['DomainRow'][]>();
const domainId = ref('');
const activeDomain = computed(() =>
  domains.value?.find((row) => row.object_ref.object_id === domainId.value),
);
const loadingBooks = ref(false);
const books = ref<TextbookRow[]>([]);
const bookId = ref('');
const targets = ref<Target[]>([]);
const claims = ref<Schema['ClaimRow'][]>([]);
const chapters = ref<Chapter[]>([]);
const draftItems = ref<Item[]>([]);
const claimId = ref('');
const editing = ref<Target>();
const creating = ref(false);
const panel = ref<'edit' | 'application'>('edit');
const title = ref('');
const names = ref<Record<string, string>>({});
const error = ref('');
const status = ref('');
const busy = ref(false);
const activeBook = computed(() => books.value.find((book) => book.textbook_id === bookId.value));
const targetChapters = computed(() => {
  const selected = new Set(editing.value?.items.flatMap((item) => item.chapter_refs));
  return chapters.value
    .filter((chapter) => selected.has(chapter.id))
    .map((chapter) => chapter.title);
});
const path = '/api/m1/learning-targets';
const compare = (a: { object_id: string; version: number }, b: typeof a) =>
  a.object_id === b.object_id && a.version === b.version;

async function loadBook(book: TextbookRow) {
  busy.value = true;
  try {
    const session = props.session;
    const [targetList, claimList, content] = await Promise.all([
      get(path, { session, query: { textbook_id: book.textbook_id } }),
      get('/api/m1/evaluation/claims', { session, query: { domain_id: book.domain_id } }),
      get('/api/m1/material-imports/{import_id}/contents', {
        session,
        params: { import_id: book.import_id },
      }),
    ]);
    chapters.value = await Promise.all(
      content.chapters.flatMap((chapter) => {
        if (
          typeof chapter.chapter_id !== 'string' ||
          typeof chapter.title !== 'string' ||
          typeof chapter.revision !== 'number'
        )
          return [];
        const { chapter_id, title, revision } = chapter;
        return [
          get('/api/m1/textbooks/{textbook_id}/chapters/{chapter_id}/associations', {
            session,
            params: { textbook_id: book.textbook_id, chapter_id },
          }).then((data) => ({ id: chapter_id, title, revision, tasks: data.items })),
        ];
      }),
    );
    targets.value = targetList.items;
    claims.value = claimList.items;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

function reset() {
  promptChoices.value = {};
  panel.value = 'edit';
  editing.value = undefined;
  creating.value = false;
  title.value = '';
  draftItems.value = [];
  names.value = {};
  claimId.value = '';
}

function createTarget() {
  reset();
  creating.value = true;
}

watch(domainId, async (id, _, onCleanup) => {
  bookId.value = '';
  books.value = [];
  error.value = '';
  loadingBooks.value = !!id;
  if (!id) return;
  const controller = new AbortController();
  onCleanup(() => controller.abort());
  try {
    const rows: TextbookRow[] = [];
    let cursor: string | undefined;
    do {
      const page = await get('/api/m1/textbooks', {
        session: props.session,
        signal: controller.signal,
        query: { domain_id: id, cursor },
      });
      rows.push(...page.items);
      cursor = page.next_cursor ?? undefined;
    } while (cursor);
    if (controller.signal.aborted) return;
    books.value = rows;
    if (rows.length === 1 && rows[0]) bookId.value = rows[0].textbook_id;
  } catch (caught) {
    if (!controller.signal.aborted) error.value = (caught as Error).message;
  } finally {
    if (!controller.signal.aborted) loadingBooks.value = false;
  }
});

watch(activeBook, (book) => {
  reset();
  claims.value = [];
  targets.value = [];
  chapters.value = [];
  status.value = '';
  error.value = '';
  if (book) void loadBook(book);
});
void listDomains(props.session, lifecycle.signal)
  .then((data) => {
    domains.value = data.items;
  })
  .catch((caught: Error) => {
    if (!lifecycle.signal.aborted) error.value = caught.message;
  });
onBeforeUnmount(() => lifecycle.abort());

async function readClaim(ref: Schema['ClaimRef']) {
  const result = await get('/api/m1/evaluation/claims/{claim_id}', {
    session: props.session,
    params: { claim_id: ref.claim_id },
    query: { revision: ref.revision },
  });
  const claim = result.claim;
  const labels = await methodNames(
    props.session,
    claim.definition.domain_id,
    claim.definition.methods.map((method) => method.method_ref),
  );
  names.value = { ...names.value, ...labels };
  return claim;
}

async function addGoal() {
  const row = claims.value.find((entry) => entry.claim_ref.claim_id === claimId.value);
  if (!row) return;
  try {
    const claim = await readClaim(row.claim_ref);
    draftItems.value.push({
      key: crypto.randomUUID(),
      claim,
      draft: {
        title: claim.definition.title,
        claim_ref: row.claim_ref,
        chapter_refs: [],
        task_conditions: { description: '' },
        method_mode: 'each',
        methods: [],
      },
    });
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}

async function open(target: Target) {
  busy.value = true;
  try {
    draftItems.value = await Promise.all(
      target.items.map(async (draft) => ({
        key: draft.item_id,
        claim: await readClaim(draft.claim_ref),
        draft: structuredClone(JSON.parse(JSON.stringify(draft)) as Goal),
      })),
    );
    editing.value = target;
    promptChoices.value = { ...bindings.get(targetKey(target)) };
    creating.value = false;
    panel.value = 'edit';
    title.value = target.title;
    status.value = '';
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

function options(item: Item) {
  return chapters.value.filter((chapter) =>
    chapter.tasks.some((association) =>
      compare(association.task_ref, item.claim.definition.task_ref),
    ),
  );
}
function sources(item: Item, method: Schema['SolutionRef']) {
  return options(item).filter(
    (chapter) =>
      item.draft.chapter_refs.includes(chapter.id) &&
      chapter.tasks.some(
        (association) =>
          compare(association.task_ref, item.claim.definition.task_ref) &&
          association.method_refs.some((choice) => compare(choice, method)),
      ),
  );
}
function refreshSources(item: Item) {
  for (const method of item.draft.methods)
    method.chapter_refs = sources(item, method.method_ref).map((chapter) => chapter.id);
  item.draft.methods = item.draft.methods.filter((method) => method.chapter_refs.length > 0);
}
function selection(item: Item, method: Schema['SolutionRef']) {
  return item.draft.methods.find((entry) => compare(entry.method_ref, method));
}
function select(item: Item, method: Schema['SolutionRef'], checked: boolean) {
  if (!checked) {
    item.draft.methods = item.draft.methods.filter((entry) => !compare(entry.method_ref, method));
    return;
  }
  const chosen: Schema['MethodRequirement'] = {
    method_ref: method,
    chapter_refs: sources(item, method).map((chapter) => chapter.id),
    aspects: [],
  };
  item.draft.methods =
    item.draft.method_mode === 'specified' ? [chosen] : [...item.draft.methods, chosen];
}
function toggleAspect(
  method: Schema['MethodRequirement'],
  claim: Claim,
  aspect: string,
  checked: boolean,
) {
  if (checked)
    method.aspects.push({
      aspect_ref: { claim_ref: claim.claim_ref, aspect_code: aspect },
      condition_values: {},
    });
  else method.aspects = method.aspects.filter((rule) => rule.aspect_ref.aspect_code !== aspect);
}

async function save() {
  const book = activeBook.value;
  if (!book) return;
  busy.value = true;
  error.value = '';
  try {
    const data = {
      title: title.value,
      textbook_id: book.textbook_id,
      request_id: crypto.randomUUID(),
      items: draftItems.value.map((item) => item.draft),
    };
    const { result } = await post(
      path,
      editing.value
        ? {
            ...data,
            action: 'update',
            target_id: editing.value.target_ref.target_id,
            expected_revision: editing.value.target_ref.revision,
          }
        : { ...data, action: 'create' },
      { session: props.session },
    );
    await loadBook(book);
    bindings.set(targetKey(result.target), { ...promptChoices.value });
    await open(result.target);
    status.value = `已保存修订 ${result.target.target_ref.revision}`;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section aria-label="目标管理">
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <template v-if="!editing && !creating">
      <h1 class="target-title">目标管理</h1>
      <div class="admin-list-toolbar target-filters">
        <label for="target-domain">领域</label>
        <select id="target-domain" v-model="domainId" :disabled="busy || !domains?.length">
          <option value="">请选择领域</option>
          <option
            v-for="row in domains"
            :key="row.object_ref.object_id"
            :value="row.object_ref.object_id"
          >
            {{ row.name }}
          </option>
        </select>
        <label for="target-book">教材</label>
        <select id="target-book" v-model="bookId" :disabled="busy || loadingBooks || !books.length">
          <option value="">{{ domainId ? '请选择教材' : '请先选择领域' }}</option>
          <option v-for="book in books" :key="book.textbook_id" :value="book.textbook_id">
            {{ book.metadata.title }}
          </option>
        </select>
        <ElButton type="primary" :disabled="busy || !activeBook" @click="createTarget"
          >新建目标</ElButton
        >
      </div>
      <p v-if="!error && !domains" role="status">正在读取领域…</p>
      <p v-else-if="loadingBooks" role="status">正在读取该领域的教材…</p>
      <p v-else-if="busy" role="status">正在读取学习目标…</p>
      <table v-else-if="targets.length" aria-label="已保存的学习目标" class="admin-data-table">
        <thead>
          <tr>
            <th>学习目标</th>
            <th>目标版本</th>
            <th>目标项</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="target in targets" :key="target.target_ref.target_id">
            <td>
              <button
                type="button"
                :aria-label="target.title + ' · v' + target.target_ref.revision"
                @click="open(target)"
              >
                {{ target.title }}
              </button>
            </td>
            <td>v{{ target.target_ref.revision }}</td>
            <td>{{ target.items.length }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="!error" class="target-empty" role="status">
        <template v-if="!domains?.length">暂无可选领域。</template>
        <template v-else-if="!domainId">请先选择领域和教材。</template>
        <template v-else-if="!books.length">该领域暂无教材。</template>
        <template v-else-if="!activeBook">请选择教材，查看该教材的学习目标。</template>
        <template v-else>这本教材还没有学习目标。</template>
      </p>
    </template>
    <template v-else-if="activeBook">
      <header class="target-heading">
        <p class="target-breadcrumb">
          <ElButton link aria-label="返回学习目标列表" :disabled="busy" @click="reset"
            >目标管理</ElButton
          >
          <span aria-hidden="true">/</span>
          <span>{{ activeDomain?.name }}</span>
          <span aria-hidden="true">/</span>
          <span>{{ activeBook.metadata.title }}</span>
          <span aria-hidden="true">/</span>
          <span>{{ editing?.title ?? '新建目标' }}</span>
        </p>
        <h1 class="target-title">{{ editing?.title ?? '新建目标' }}</h1>
        <p class="target-meta">
          {{ activeBook.metadata.title
          }}<template v-if="targetChapters.length"> · {{ targetChapters.join('、') }}</template>
        </p>
      </header>
      <ElTabs v-model="panel" class="target-tabs" aria-label="目标详情">
        <ElTabPane label="编辑目标" name="edit">
          <form class="admin-editor editor-panel target-editor" @submit.prevent="save">
            <fieldset :disabled="busy">
              <label>目标名称 <input v-model="title" required maxlength="160" /></label>
              <TargetPromptChoices v-model="promptChoices" :guides="guides" />
              <label
                >选用 Claim
                <select v-model="claimId">
                  <option value="">选择 Claim</option>
                  <option
                    v-for="claim in claims"
                    :key="claim.claim_ref.claim_id"
                    :value="claim.claim_ref.claim_id"
                  >
                    {{ claim.title }} · v{{ claim.claim_ref.revision }}
                  </option>
                </select></label
              >
              <button type="button" :disabled="!claimId" @click="addGoal">添加目标项</button>
              <fieldset v-for="item in draftItems" :key="item.key">
                <legend>{{ item.claim.definition.title }}</legend>
                <label>条目名称 <input v-model="item.draft.title" required /></label>
                <label
                  >任务范围
                  <textarea v-model="item.draft.task_conditions.description" maxlength="4096" />
                </label>
                <label
                  >达标方式
                  <select v-model="item.draft.method_mode">
                    <option value="specified">指定一种方法</option>
                    <option value="any_one">任选一种方法</option>
                    <option value="each">所选方法分别达标</option>
                  </select></label
                >
                <fieldset>
                  <legend>适用章节</legend>
                  <p v-if="!options(item).length">教材尚未采用这个 Task 版本。</p>
                  <label v-for="chapter in options(item)" :key="chapter.id">
                    <input
                      v-model="item.draft.chapter_refs"
                      type="checkbox"
                      :value="chapter.id"
                      @change="refreshSources(item)"
                    />
                    {{ chapter.title }}
                  </label>
                </fieldset>
                <fieldset
                  v-for="(method, index) in item.claim.definition.methods"
                  :key="method.method_ref.object_id"
                >
                  <label
                    ><input
                      type="checkbox"
                      :checked="!!selection(item, method.method_ref)"
                      :disabled="sources(item, method.method_ref).length === 0"
                      @change="
                        select(item, method.method_ref, ($event.target as HTMLInputElement).checked)
                      "
                    />
                    {{ names[methodKey(method.method_ref)] ?? `方法 ${index + 1}` }} · v{{
                      method.method_ref.version
                    }}
                  </label>
                  <small>{{
                    sources(item, method.method_ref)
                      .map((chapter) => chapter.title)
                      .join('、')
                  }}</small>
                  <template
                    v-for="chosen in item.draft.methods.filter((entry) =>
                      compare(entry.method_ref, method.method_ref),
                    )"
                    :key="chosen.method_ref.object_id"
                  >
                    <label v-for="aspect in item.claim.definition.aspects" :key="aspect.code">
                      <input
                        type="checkbox"
                        :checked="
                          chosen.aspects.some(
                            (entry) => entry.aspect_ref.aspect_code === aspect.code,
                          )
                        "
                        @change="
                          toggleAspect(
                            chosen,
                            item.claim,
                            aspect.code,
                            ($event.target as HTMLInputElement).checked,
                          )
                        "
                      />
                      {{ aspect.label }}
                    </label>
                  </template>
                </fieldset>
                <button
                  type="button"
                  @click="draftItems = draftItems.filter((entry) => entry !== item)"
                >
                  移除目标项
                </button>
              </fieldset>
              <button type="submit" :disabled="!draftItems.length">保存目标</button>
            </fieldset>
          </form>
          <ul v-if="editing?.gaps.length" class="editor-notices" aria-label="准备缺项">
            <li v-for="gap in editing.gaps" :key="gap.path + gap.code">{{ gap.message }}</li>
          </ul>
        </ElTabPane>
        <ElTabPane label="检查与应用" name="application" :disabled="!editing">
          <CourseApplication
            v-if="editing"
            :key="editing.target_ref.target_id + ':' + editing.target_ref.revision"
            :session="session"
            :target="editing"
            :import-id="activeBook.import_id"
            :textbook-title="activeBook.metadata.title"
            :chapters="chapters"
          />
        </ElTabPane>
      </ElTabs>
    </template>
  </section>
</template>

<style scoped>
.target-filters {
  display: grid;
  grid-template-columns: auto minmax(10rem, 17rem) auto minmax(10rem, 21rem) 1fr;
}
.target-filters select {
  width: 100%;
  min-width: 0;
}
.target-empty {
  margin: 0;
  padding: 32px 16px;
  text-align: center;
  background: white;
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
@media (max-width: 1050px) {
  .target-filters {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .target-filters .el-button {
    grid-column: 2;
  }
}
.target-breadcrumb {
  display: flex;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 0.8125rem;
}
.target-breadcrumb :deep(.el-button) {
  color: inherit;
  font-size: inherit;
}
.target-title {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 1.875rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.target-meta {
  margin: 7px 0 17px;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
.target-tabs :deep(.el-tabs__header) {
  height: 43px;
  margin: 0 0 23px;
  background: white;
}
.target-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--el-border-color);
}
.target-tabs :deep(.el-tabs__item) {
  justify-content: flex-start;
  height: 43px;
  min-width: 112px;
  padding: 0 12px !important;
}
.target-tabs :deep(.el-tabs__item:last-child) {
  min-width: 135px;
}
.target-tabs :deep(.el-tabs__item.is-active) {
  font-weight: 600;
}
fieldset {
  display: grid;
  gap: 0.75rem;
  border: 1px solid #cbd8d2;
  padding: 0.75rem;
  margin-block: 0.75rem;
}
label,
small {
  display: block;
}
form textarea {
  display: block;
  min-width: min(28rem, 100%);
}
</style>
