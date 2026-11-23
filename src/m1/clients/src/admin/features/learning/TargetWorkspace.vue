<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';
import { listTextbooks, type TextbookRow } from '../materials/api';
import CourseApplication from './CourseApplication.vue';

type Schema = components['schemas'];
type Target = Schema['TargetView'];
type Claim = Schema['ClaimView'];
type Goal = Schema['GoalItemDraft'];
type Association = Schema['ChapterAssociationView'];
type Chapter = { id: string; title: string; revision: number; tasks: Association[] };
type Item = { draft: Goal; key: string; claim: Claim };
const props = defineProps<{ session: DomainSession }>();
const books = ref<TextbookRow[]>([]);
const bookId = ref('');
const targets = ref<Target[]>([]);
const claims = ref<Schema['ClaimRow'][]>([]);
const chapters = ref<Chapter[]>([]);
const draftItems = ref<Item[]>([]);
const claimId = ref('');
const editing = ref<Target>();
const title = ref('');
const error = ref('');
const status = ref('');
const busy = ref(false);
const activeBook = computed(() => books.value.find((book) => book.textbook_id === bookId.value));
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
  editing.value = undefined;
  title.value = '';
  draftItems.value = [];
  claimId.value = '';
}

watch(activeBook, (book) => {
  reset();
  claims.value = [];
  targets.value = [];
  chapters.value = [];
  status.value = '';
  error.value = '';
  if (book) void loadBook(book);
});
void listTextbooks(props.session, '')
  .then((data) => {
    books.value = data.items;
  })
  .catch((caught: Error) => {
    error.value = caught.message;
  });

async function readClaim(ref: Schema['ClaimRef']) {
  const result = await get('/api/m1/evaluation/claims/{claim_id}', {
    session: props.session,
    params: { claim_id: ref.claim_id },
    query: { revision: ref.revision },
  });
  return result.claim;
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
        task_conditions: { description: '', parameter_values: {} },
        method_mode: 'each',
        methods: [],
      },
    });
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}

async function open(target: Target) {
  try {
    draftItems.value = await Promise.all(
      target.items.map(async (draft) => ({
        key: draft.item_id,
        claim: await readClaim(draft.claim_ref),
        draft: structuredClone(JSON.parse(JSON.stringify(draft)) as Goal),
      })),
    );
    editing.value = target;
    title.value = target.title;
    status.value = '';
  } catch (caught) {
    error.value = (caught as Error).message;
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
    <h2>目标管理</h2>
    <label
      >教材
      <select v-model="bookId" :disabled="busy">
        <option value="">选择教材</option>
        <option v-for="book in books" :key="book.textbook_id" :value="book.textbook_id">
          {{ book.metadata.title }}
        </option>
      </select></label
    >
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <template v-if="activeBook">
      <nav aria-label="已保存的学习目标">
        <button type="button" :disabled="busy" @click="reset">新建目标</button>
        <button
          v-for="target in targets"
          :key="target.target_ref.target_id"
          type="button"
          :disabled="busy"
          @click="open(target)"
        >
          {{ target.title }} · v{{ target.target_ref.revision }}
        </button>
      </nav>
      <form @submit.prevent="save">
        <fieldset :disabled="busy">
          <label>目标名称 <input v-model="title" required maxlength="160" /></label>
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
              v-for="method in item.claim.definition.methods"
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
                方法 {{ method.method_ref.object_id.slice(0, 8) }} · v{{
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
                      chosen.aspects.some((entry) => entry.aspect_ref.aspect_code === aspect.code)
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
      <ul v-if="editing?.gaps.length" aria-label="准备缺项">
        <li v-for="gap in editing.gaps" :key="gap.path + gap.code">{{ gap.message }}</li>
      </ul>
      <CourseApplication
        v-if="editing"
        :session="session"
        :target="editing"
        :import-id="activeBook.import_id"
        :chapters="chapters"
      />
    </template>
  </section>
</template>

<style scoped>
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
