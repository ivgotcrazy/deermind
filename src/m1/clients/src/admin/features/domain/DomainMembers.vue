<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import { listMembers, readDefinitionReceipt, readMember, saveMember } from './api';
import type {
  DomainSession,
  MemberKind,
  MemberRef,
  MemberRequest,
  MemberRow,
  MemberView,
  TaskParameter,
} from './api';
import type { RichContent as StoredContent } from '../../../shared/content/types';

const { domainId, kind, session } = defineProps<{
  domainId: string;
  kind: MemberKind;
  session: DomainSession;
}>();
const signal = new AbortController();
const storageKey = `deermind-${kind}-pending:${session.account.account_id}:${domainId}`;
const label = kind === 'kc' ? '知识成分' : '任务';
const knowledgeFields = [
  ['definition', '含义', true],
  ['applicability', '适用条件', true],
  ['examples', '正例', false],
  ['non_examples', '反例', false],
] as const;
const taskFields = [
  ['responsibility', '认知责任', false],
  ['expected_output', '预期表现', false],
  ['completion_conditions', '完成条件', false],
  ['applicability', '适用条件', false],
  ['boundaries', '适用边界', false],
] as const;
const fields = kind === 'kc' ? knowledgeFields : taskFields;
type Field = (typeof fields)[number][0];

const mode = ref<'create' | 'update' | 'soft_delete'>('create');
const filter = ref('');
const rows = ref<MemberRow[]>([]);
const cursor = ref<string | null>(null);
const listBusy = ref(false);
const detailBusy = ref(false);
const error = ref('');
const status = ref('');
const detail = ref<MemberView>();
const head = ref(0);
const history = ref<number | null>(null);
const dialog = ref<HTMLDialogElement>();
const name = ref('');
const note = ref('');
const draft = ref<Partial<Record<Field, string>>>({});
const parameters = ref<TaskParameter[]>([]);
const pending = ref<MemberRequest>();
const saveBusy = ref(false);
const saveError = ref('');
const canRetry = ref(false);
const storageFailed = ref(false);
const canEdit = computed(
  () =>
    detail.value &&
    !detail.value.is_identity_deleted &&
    detail.value.object_ref.version === head.value,
);

function storedField(field: Field) {
  // 各类型只渲染登记的正文键，名称和参数通过各自的显式控件读取。
  const content = detail.value?.content as Partial<Record<Field, StoredContent | null>> | undefined;
  return content?.[field];
}

const displayedFields = computed(() =>
  fields.flatMap(([field, fieldLabel]) => {
    const content = storedField(field);
    return content ? [{ field, fieldLabel, content }] : [];
  }),
);
const storedParameters = computed(() => {
  const content = detail.value?.content;
  return content && 'parameters' in content ? (content.parameters ?? []) : [];
});

function plainText(content: StoredContent | null | undefined): string | null {
  if (!content) return '';
  if (
    content.data_tables.length ||
    content.source_refs.length ||
    content.blocks.some(
      (block) =>
        block.type !== 'paragraph' ||
        block.provenance.transformation !== 'generated' ||
        block.provenance.note ||
        block.provenance.source_refs.length ||
        block.payload.spans.length !== 1 ||
        block.payload.spans[0]?.type !== 'text',
    )
  ) {
    return null;
  }
  return content.blocks
    .map((block) => {
      const span = block.type === 'paragraph' ? block.payload.spans[0] : undefined;
      return span?.type === 'text' ? span.text : '';
    })
    .join('\n');
}

function contentFor(field: Field): StoredContent | null {
  const original = mode.value === 'update' ? storedField(field) : null;
  const text = draft.value[field]?.trim() ?? '';
  const oldText = plainText(original);
  if (original && (oldText === null || oldText === draft.value[field])) {
    return original;
  }
  if (!text) return null;
  return {
    role: 'definition',
    schema_version: '1',
    blocks: text.split('\n').map((line, index) => ({
      type: 'paragraph',
      block_id: `p-${index + 1}`,
      payload: { spans: [{ type: 'text', text: line }] },
      provenance: { transformation: 'generated', source_refs: [], note: '' },
    })),
    data_tables: [],
    source_refs: [],
  };
}

async function loadList(next = false) {
  listBusy.value = true;
  error.value = '';
  try {
    const result = await listMembers(
      domainId,
      kind,
      session,
      signal.signal,
      filter.value,
      next ? (cursor.value ?? undefined) : undefined,
    );
    rows.value = next ? [...rows.value, ...result.items] : result.items;
    cursor.value = result.next_cursor;
  } catch (cause) {
    if (!signal.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '列表读取失败。';
    cursor.value = null;
  } finally {
    listBusy.value = false;
  }
}

async function showDetail(objectId: string, version?: number, newest = true) {
  detailBusy.value = true;
  error.value = '';
  try {
    const result = await readMember(domainId, objectId, kind, session, signal.signal, version);
    detail.value = result;
    history.value = result.object_ref.version;
    if (newest) head.value = result.object_ref.version;
  } catch (cause) {
    if (!signal.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '详情读取失败。';
  } finally {
    detailBusy.value = false;
  }
}

function open(modeValue: typeof mode.value) {
  mode.value = modeValue;
  if (!pending.value) {
    saveError.value = '';
    status.value = '';
    name.value = modeValue === 'create' ? '' : (detail.value?.content.name ?? '');
    note.value = '';
    for (const [field] of fields) {
      draft.value[field] = modeValue === 'create' ? '' : (plainText(storedField(field)) ?? '');
    }
    parameters.value =
      modeValue !== 'create' ? storedParameters.value.map((parameter) => ({ ...parameter })) : [];
  }
  dialog.value?.showModal();
}

function remember(body?: MemberRequest) {
  pending.value = body;
  try {
    if (body) sessionStorage.setItem(storageKey, JSON.stringify(body));
    else sessionStorage.removeItem(storageKey);
  } catch {
    storageFailed.value = true;
  }
}

async function saved(ref: MemberRef) {
  const removed = pending.value?.action === 'soft_delete';
  remember();
  dialog.value?.close();
  status.value = removed ? `${label}已移除。可在此查看旧版本。` : `${label}已保存。`;
  await Promise.all([loadList(), showDetail(ref.object_id, ref.version)]);
}

async function recover() {
  if (!pending.value || saveBusy.value) return;
  saveBusy.value = true;
  canRetry.value = false;
  saveError.value = '';
  try {
    const result = await readDefinitionReceipt(pending.value.request_id, session, signal.signal);
    if (
      result.receipt_state === 'completed' &&
      result.result &&
      'object_ref' in result.result &&
      result.result.object_ref.kind === kind
    ) {
      await saved(result.result.object_ref);
    } else if (result.receipt_state === 'not_found') {
      canRetry.value = true;
      saveError.value = '暂未查到保存结果，可以用原请求重试。';
    } else {
      saveError.value = result.error?.message ?? '暂时无法确认保存结果。';
    }
  } catch (cause) {
    saveError.value = cause instanceof Error ? cause.message : '暂时无法查询保存结果。';
  } finally {
    saveBusy.value = false;
  }
}

async function send(body: MemberRequest) {
  remember(body);
  saveBusy.value = true;
  canRetry.value = false;
  saveError.value = '';
  try {
    const { result } = await saveMember(body, session, signal.signal);
    if (result.object_ref.kind !== kind) throw new Error('保存结果缺少领域对象引用。');
    await saved(result.object_ref);
  } catch (cause) {
    if (cause instanceof ApiError && [400, 401, 403, 404, 409, 413].includes(cause.status)) {
      remember();
      saveError.value = cause.message;
    } else {
      saveBusy.value = false;
      await recover();
    }
  } finally {
    saveBusy.value = false;
  }
}

function submit() {
  if (pending.value || saveBusy.value) return;
  const base = {
    request_id: crypto.randomUUID(),
    change_note: note.value.trim(),
  } as const;
  const current = detail.value?.object_ref;
  if (!base.change_note) return;
  if (mode.value === 'soft_delete') {
    if (current) {
      const deletion = { ...base, action: mode.value, expected_version: current.version } as const;
      void send(
        current.kind === 'kc'
          ? { ...deletion, object_kind: 'kc', object_ref: current }
          : { ...deletion, object_kind: 'task', object_ref: current },
      );
    }
    return;
  }
  if (!name.value.trim()) return;
  if (kind === 'task') {
    const parameterNames = parameters.value.map((parameter) => parameter.name.trim());
    if (new Set(parameterNames).size !== parameterNames.length) {
      saveError.value = '参数名称重复。';
      return;
    }
    const body = {
      ...base,
      object_kind: 'task',
      definition: {
        name: name.value.trim(),
        responsibility: contentFor('responsibility'),
        expected_output: contentFor('expected_output'),
        completion_conditions: contentFor('completion_conditions'),
        applicability: contentFor('applicability'),
        boundaries: contentFor('boundaries'),
        parameters: parameters.value,
      },
    } as const;
    if (mode.value === 'create') {
      void send({ ...body, action: 'create', domain_id: domainId });
    } else if (current?.kind === 'task') {
      void send({
        ...body,
        action: 'update',
        object_ref: current,
        expected_version: current.version,
      });
    }
    return;
  }
  const definition = contentFor('definition');
  const applicability = contentFor('applicability');
  if (!definition || !applicability) return;
  const value = {
    name: name.value.trim(),
    definition,
    applicability,
    examples: contentFor('examples'),
    non_examples: contentFor('non_examples'),
  };
  if (mode.value === 'create') {
    void send({
      ...base,
      object_kind: 'kc',
      action: mode.value,
      domain_id: domainId,
      definition: value,
    });
  } else if (current?.kind === 'kc') {
    void send({
      ...base,
      object_kind: 'kc',
      action: mode.value,
      object_ref: current,
      expected_version: current.version,
      definition: value,
    });
  }
}

onMounted(() => {
  void loadList();
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw) {
      pending.value = JSON.parse(raw) as MemberRequest;
      void recover();
    }
  } catch {
    storageFailed.value = true;
  }
});
onBeforeUnmount(() => signal.abort());
</script>

<template>
  <section class="members">
    <header class="bar">
      <h3>{{ label }}</h3>
      <button v-if="pending" type="button" @click="open('create')">核对保存结果</button>
      <button v-else type="button" class="primary" @click="open('create')">新建{{ label }}</button>
    </header>
    <form class="bar" @submit.prevent="loadList()">
      <label
        >按名称查找 <input v-model="filter" type="search" maxlength="512" :disabled="listBusy"
      /></label>
      <button type="submit" :disabled="listBusy">查找</button>
    </form>
    <p v-if="status" role="status">{{ status }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="listBusy" role="status">正在读取{{ label }}…</p>
    <p v-else-if="!rows.length && !error">这里还没有符合条件的{{ label }}。</p>
    <ul v-if="rows.length" class="results">
      <li v-for="row in rows" :key="row.object_ref.object_id">
        <button type="button" :disabled="detailBusy" @click="showDetail(row.object_ref.object_id)">
          {{ row.name }} <small>v{{ row.object_ref.version }}</small>
        </button>
      </li>
    </ul>
    <button v-if="cursor" type="button" :disabled="listBusy" @click="loadList(true)">
      加载更多
    </button>
    <section v-if="detail" class="reading" aria-labelledby="member-detail-title">
      <header class="bar">
        <h4 id="member-detail-title">
          {{ detail.content.name }} <small>v{{ detail.object_ref.version }}</small>
        </h4>
        <div v-if="canEdit" class="bar">
          <button type="button" :disabled="!!pending || detailBusy" @click="open('update')">
            编辑
          </button>
          <button type="button" :disabled="!!pending || detailBusy" @click="open('soft_delete')">
            移除
          </button>
        </div>
      </header>
      <p v-if="detail.is_identity_deleted">已移除</p>
      <form
        v-if="head > 1"
        class="bar"
        @submit.prevent="history && showDetail(detail.object_ref.object_id, history, false)"
      >
        <label
          >版本 <input v-model.number="history" type="number" min="1" :max="head" required
        /></label>
        <button type="submit" :disabled="detailBusy">查看版本</button>
      </form>
      <section v-for="{ field, fieldLabel, content } in displayedFields" :key="field" class="field">
        <h5>{{ fieldLabel }}</h5>
        <RichContent :content="content" />
      </section>
      <section v-if="storedParameters.length" class="field">
        <h5>参数</h5>
        <dl class="parameters">
          <template v-for="parameter in storedParameters" :key="parameter.name">
            <dt>{{ parameter.name }} · {{ parameter.type }}</dt>
            <dd>{{ parameter.meaning }}。{{ parameter.constraints }}</dd>
          </template>
        </dl>
      </section>
      <ul v-if="kind === 'task' && detail.gaps?.length" class="gaps" aria-label="待补齐内容">
        <li v-for="gap in detail.gaps" :key="gap.path">{{ gap.message }}</li>
      </ul>
    </section>

    <dialog
      ref="dialog"
      aria-labelledby="member-form-title"
      @cancel.prevent="!saveBusy && dialog?.close()"
    >
      <form @submit.prevent="submit">
        <h3 id="member-form-title">
          {{
            pending
              ? '核对保存结果'
              : mode === 'create'
                ? '新建' + label
                : mode === 'update'
                  ? '编辑' + label
                  : '移除' + label
          }}
        </h3>
        <p v-if="pending">请求已保留。请先确认保存结果。</p>
        <template v-else>
          <p v-if="mode === 'soft_delete'">
            将从列表移除「{{ detail?.content.name }}」，已有版本仍可查阅。
          </p>
          <template v-else>
            <label>名称 <input v-model="name" required /></label>
            <label v-for="[field, fieldLabel, required] in fields" :key="field">
              {{ fieldLabel }}
              <textarea
                v-if="mode === 'create' || plainText(storedField(field)) !== null"
                v-model="draft[field]"
                :required="required"
                rows="2"
              />
              <span v-else>保留已有内容。</span>
            </label>
            <details v-if="kind === 'task'" :open="parameters.length > 0">
              <summary>参数（可选）</summary>
              <fieldset v-for="(parameter, index) in parameters" :key="index">
                <legend>参数 {{ index + 1 }}</legend>
                <label>参数名称 <input v-model="parameter.name" required /></label>
                <label>含义 <input v-model="parameter.meaning" required /></label>
                <label>类型 <input v-model="parameter.type" required /></label>
                <label>约束 <input v-model="parameter.constraints" required /></label>
                <button type="button" @click="parameters.splice(index, 1)">移除参数</button>
              </fieldset>
              <button
                type="button"
                @click="parameters.push({ name: '', meaning: '', type: '', constraints: '' })"
              >
                添加参数
              </button>
            </details>
          </template>
          <label>变更原因 <input v-model="note" required /></label>
        </template>
        <p v-if="saveError" role="alert">{{ saveError }}</p>
        <p v-if="saveBusy" role="status">正在处理…</p>
        <p v-if="storageFailed && pending">浏览器无法暂存请求，请在刷新前核对。</p>
        <div class="actions">
          <button type="button" :disabled="saveBusy" @click="dialog?.close()">
            {{ pending ? '关闭' : '取消' }}
          </button>
          <button v-if="!pending" type="submit" class="primary" :disabled="saveBusy">
            {{ mode === 'soft_delete' ? '确认移除' : '保存' }}
          </button>
          <template v-else>
            <button type="button" :disabled="saveBusy" @click="recover">查询保存结果</button>
            <button
              v-if="canRetry"
              type="button"
              class="primary"
              :disabled="saveBusy"
              @click="send(pending)"
            >
              用原请求重试
            </button>
          </template>
        </div>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.members,
.reading {
  display: grid;
  gap: 0.9rem;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #ddd6c7;
}
.bar,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
}
header.bar {
  justify-content: space-between;
}
.actions {
  justify-content: flex-end;
}
h3,
h4,
h5,
p {
  margin: 0;
}
small {
  color: #5d635a;
  font-weight: normal;
}
.field {
  display: grid;
  gap: 0.4rem;
}
.results {
  display: grid;
  gap: 0.35rem;
  padding: 0;
  margin: 0;
  list-style: none;
}
.results button {
  width: 100%;
  text-align: start;
}
button,
input,
textarea {
  font: inherit;
  padding: 0.38rem 0.65rem;
  border: 1px solid #d5cdbf;
  border-radius: 0.4rem;
  color: inherit;
  background: #fffdf8;
}
button {
  cursor: pointer;
}
button:disabled {
  opacity: 0.55;
  cursor: default;
}
button:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 2px solid #346348;
  outline-offset: 2px;
}
.primary {
  color: white;
  background: #28513c;
  border-color: #28513c;
}
dialog {
  max-width: min(33rem, calc(100% - 2rem));
  width: 100%;
  border: 1px solid #d5cdbf;
  border-radius: 0.7rem;
  background: #fffdf8;
  max-height: calc(100dvh - 2rem);
}
dialog::backdrop {
  background: #151c1855;
}
dialog form,
dialog label {
  display: grid;
  gap: 0.55rem;
}
.parameters,
.parameters dd {
  margin: 0;
}
.parameters dd + dt {
  margin-top: 0.5rem;
}
.gaps {
  margin: 0;
  padding-inline-start: 1.4rem;
  color: #5d635a;
}
fieldset {
  margin-block: 0.5rem;
  border: 1px solid #ddd6c7;
}
fieldset label {
  margin-bottom: 0.45rem;
}
</style>
