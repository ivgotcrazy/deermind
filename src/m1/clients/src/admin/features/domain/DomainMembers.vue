<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import {
  listMembers,
  readDefinitionReceipt,
  readDependencies,
  readMember,
  saveMember,
} from './api';
import DomainRelationsEditor from './DomainRelationsEditor.vue';
import KCPathChecks from './KCPathChecks.vue';
import type {
  DomainSession,
  KnowledgeRef,
  MemberKind,
  MemberRef,
  MemberRequest,
  MemberRow,
  MemberView,
  Prerequisite,
  SolutionRef,
  TaskDependencies,
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
const label = { kc: '知识成分', task: '任务', solution: '方法' }[kind];
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
const solutionFields = [
  ['approach', '方法思路', false],
  ['rationale', '方法依据', false],
  ['applicability', '适用条件', false],
  ['key_process', '关键过程', false],
] as const;
const fields = { kc: knowledgeFields, task: taskFields, solution: solutionFields }[kind];
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
const methods = ref<SolutionRef[]>([]);
const knowledge = ref<KnowledgeRef[]>([]);
const prerequisites = ref<Prerequisite[]>([]);
const catalog = ref<MemberRow[]>([]);
const catalogBusy = ref(false);
const catalogError = ref('');
const dependencies = ref<TaskDependencies>();
const dependencyBusy = ref(false);
const solutionFilter = ref('');
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
const storedKnowledge = computed(() => {
  const content = detail.value?.content;
  return content && 'kc_refs' in content ? (content.kc_refs ?? []) : [];
});
const storedMethods = computed(() => {
  const content = detail.value?.content;
  return content && 'method_refs' in content ? (content.method_refs ?? []) : [];
});

function caption(reference: MemberRef) {
  const row = catalog.value.find((item) => item.object_ref.object_id === reference.object_id);
  return `${row?.name ?? reference.object_id} · v${reference.version}`;
}

async function loadCatalog() {
  if (kind === 'kc' || catalogBusy.value) return;
  catalogBusy.value = true;
  catalogError.value = '';
  // 选择项与本领域目录一致。分页中出现修订时重新打开即可重读。
  const kinds: MemberKind[] = kind === 'task' ? ['task', 'solution', 'kc'] : ['kc'];
  try {
    const sections = await Promise.all(
      kinds.map(async (targetKind) => {
        const items: MemberRow[] = [];
        let next: string | undefined;
        do {
          const page = await listMembers(
            domainId,
            targetKind,
            session,
            signal.signal,
            '',
            next,
            100,
          );
          items.push(...page.items);
          next = page.next_cursor ?? undefined;
        } while (next);
        return items;
      }),
    );
    catalog.value = sections.flat();
  } catch (cause) {
    if (!signal.signal.aborted)
      catalogError.value = cause instanceof Error ? cause.message : '关联选项读取失败。';
  } finally {
    catalogBusy.value = false;
  }
}

async function loadDependencies() {
  const task = detail.value?.object_ref;
  if (task?.kind !== 'task') return;
  const selected = solutionFilter.value;
  dependencyBusy.value = true;
  try {
    const result = await readDependencies(domainId, task, session, signal.signal, selected);
    if (detail.value?.object_ref === task && solutionFilter.value === selected)
      dependencies.value = result;
  } catch (cause) {
    if (!signal.signal.aborted && detail.value?.object_ref === task) {
      dependencies.value = undefined;
      error.value = cause instanceof Error ? cause.message : '关系查询失败。';
    }
  } finally {
    dependencyBusy.value = false;
  }
}

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
    dependencies.value = undefined;
    solutionFilter.value = '';
    history.value = result.object_ref.version;
    if (newest) head.value = result.object_ref.version;
    await loadDependencies();
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
    const content = modeValue === 'update' ? detail.value?.content : undefined;
    methods.value =
      content && 'method_refs' in content
        ? (content.method_refs ?? []).map((ref) => ({ ...ref }))
        : [];
    knowledge.value =
      content && 'kc_refs' in content ? (content.kc_refs ?? []).map((ref) => ({ ...ref })) : [];
    prerequisites.value =
      content && 'prerequisites' in content
        ? (content.prerequisites ?? []).map((link) => ({
            ...link,
            method_refs: [...(link.method_refs ?? [])],
          }))
        : [];
    if (modeValue !== 'soft_delete') void loadCatalog();
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
      'content_ref' in result.result &&
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
      switch (current.kind) {
        case 'kc':
          void send({ ...deletion, object_kind: 'kc', object_ref: current });
          break;
        case 'task':
          void send({ ...deletion, object_kind: 'task', object_ref: current });
          break;
        case 'solution':
          void send({ ...deletion, object_kind: 'solution', object_ref: current });
          break;
      }
    }
    return;
  }
  if (!name.value.trim()) return;
  if (kind === 'solution') {
    const body = {
      ...base,
      object_kind: 'solution',
      definition: {
        name: name.value.trim(),
        approach: contentFor('approach'),
        rationale: contentFor('rationale'),
        applicability: contentFor('applicability'),
        key_process: contentFor('key_process'),
        kc_refs: knowledge.value,
      },
    } as const;
    if (mode.value === 'create') {
      void send({ ...body, action: 'create', domain_id: domainId });
    } else if (current?.kind === 'solution') {
      void send({
        ...body,
        action: 'update',
        object_ref: current,
        expected_version: current.version,
      });
    }
    return;
  }
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
        method_refs: methods.value,
        prerequisites: prerequisites.value,
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
  void loadCatalog();
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
      <section v-if="storedKnowledge.length" class="field">
        <h5>直接知识成分</h5>
        <ul class="relation-list">
          <li v-for="reference in storedKnowledge" :key="reference.object_id">
            {{ caption(reference) }}
          </li>
        </ul>
      </section>
      <section v-if="dependencies && !detailBusy" class="field" aria-label="任务关系">
        <h5>方法与先导</h5>
        <label v-if="storedMethods.length">
          查看方法
          <select v-model="solutionFilter" :disabled="dependencyBusy" @change="loadDependencies">
            <option value="">全部方法</option>
            <option
              v-for="method in storedMethods"
              :key="method.object_id"
              :value="method.object_id"
            >
              {{ caption(method) }}
            </option>
          </select>
        </label>
        <ul v-if="dependencies.method_refs.length" class="relation-list" aria-label="采用的方法">
          <li v-for="method in dependencies.method_refs" :key="method.object_id">
            {{ caption(method) }}
          </li>
        </ul>
        <KCPathChecks
          :key="`${dependencies.task_ref.object_id}:v${dependencies.task_ref.version}`"
          :dependencies="dependencies"
          :caption="caption"
          :domain-id="domainId"
          :session="session"
          :disabled="dependencyBusy"
          @changed="loadDependencies"
        />
        <section v-if="dependencies.prerequisites.length" class="field">
          <h5>先导任务</h5>
          <ul class="relation-list">
            <li v-for="link in dependencies.prerequisites" :key="link.task_ref.object_id">
              <strong>{{ caption(link.task_ref) }}</strong> · {{ link.reason }}
              <small>{{
                link.applies_to === 'all' ? '全部方法' : link.method_refs?.map(caption).join('、')
              }}</small>
            </li>
          </ul>
        </section>
      </section>
      <ul v-if="detail.gaps?.length" class="gaps" aria-label="待补齐内容">
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
            <template v-if="kind !== 'kc'">
              <p v-if="catalogBusy" role="status">正在读取关联选项…</p>
              <p v-if="catalogError" role="alert">{{ catalogError }}</p>
              <DomainRelationsEditor
                v-model:methods="methods"
                v-model:knowledge="knowledge"
                v-model:prerequisites="prerequisites"
                :kind="kind"
                :catalog="catalog"
                :owner-id="mode === 'update' ? (detail?.object_ref.object_id ?? null) : null"
              />
            </template>
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
.reading select {
  font: inherit;
  color: inherit;
  background: #fffdf8;
  border: 1px solid #d5cdbf;
  border-radius: 0.4rem;
  padding: 0.35rem;
}
.relation-list {
  margin: 0;
  padding-inline-start: 1.4rem;
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
