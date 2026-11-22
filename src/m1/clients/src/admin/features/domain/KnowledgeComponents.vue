<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import { listKnowledge, readDefinitionReceipt, readKnowledge, saveKnowledge } from './api';
import type {
  DomainSession,
  KnowledgeContent,
  KnowledgeRef,
  KnowledgeRequest,
  KnowledgeRow,
  KnowledgeView,
} from './api';

const { domainId, session } = defineProps<{ domainId: string; session: DomainSession }>();
const signal = new AbortController();
const storageKey = `deermind-kc-pending:${session.account.account_id}:${domainId}`;
const fields = [
  ['definition', '含义'],
  ['applicability', '适用条件'],
  ['examples', '正例'],
  ['non_examples', '反例'],
] as const;
type Field = (typeof fields)[number][0];
type Content = NonNullable<KnowledgeContent[Field]>;

const mode = ref<'create' | 'update' | 'soft_delete'>('create');
const filter = ref('');
const rows = ref<KnowledgeRow[]>([]);
const cursor = ref<string | null>(null);
const listBusy = ref(false);
const detailBusy = ref(false);
const error = ref('');
const status = ref('');
const detail = ref<KnowledgeView>();
const head = ref(0);
const history = ref<number | null>(null);
const dialog = ref<HTMLDialogElement>();
const name = ref('');
const note = ref('');
const draft = ref<Record<Field, string>>({
  definition: '',
  applicability: '',
  examples: '',
  non_examples: '',
});
const pending = ref<KnowledgeRequest>();
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

function plainText(content: KnowledgeView['content'][Field]): string | null {
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

function contentFor(field: Field): Content | null {
  const original = mode.value === 'update' ? detail.value?.content[field] : null;
  if (original && (plainText(original) === null || plainText(original) === draft.value[field])) {
    return original;
  }
  const text = draft.value[field].trim();
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
    const result = await listKnowledge(
      domainId,
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
    const result = await readKnowledge(domainId, objectId, session, signal.signal, version);
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
      draft.value[field] =
        modeValue === 'create' ? '' : (plainText(detail.value?.content[field]) ?? '');
    }
  }
  dialog.value?.showModal();
}

function remember(body?: KnowledgeRequest) {
  pending.value = body;
  try {
    if (body) sessionStorage.setItem(storageKey, JSON.stringify(body));
    else sessionStorage.removeItem(storageKey);
  } catch {
    storageFailed.value = true;
  }
}

async function saved(ref: KnowledgeRef) {
  const removed = pending.value?.action === 'soft_delete';
  remember();
  dialog.value?.close();
  status.value = removed ? '知识成分已移除。可在此查看旧版本。' : '知识成分已保存。';
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
      result.result.object_ref.kind === 'kc'
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

async function send(body: KnowledgeRequest) {
  remember(body);
  saveBusy.value = true;
  canRetry.value = false;
  saveError.value = '';
  try {
    const { result } = await saveKnowledge(body, session, signal.signal);
    if (result.object_ref.kind !== 'kc') throw new Error('保存结果缺少知识成分引用。');
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
    object_kind: 'kc',
    change_note: note.value.trim(),
  } as const;
  const current = detail.value?.object_ref;
  if (!base.change_note) return;
  if (mode.value === 'soft_delete') {
    if (current)
      void send({
        ...base,
        action: mode.value,
        object_ref: current,
        expected_version: current.version,
      });
    return;
  }
  const definition = contentFor('definition');
  const applicability = contentFor('applicability');
  if (!name.value.trim() || !definition || !applicability) return;
  const value = {
    name: name.value.trim(),
    definition,
    applicability,
    examples: contentFor('examples'),
    non_examples: contentFor('non_examples'),
  };
  if (mode.value === 'create') {
    void send({ ...base, action: mode.value, domain_id: domainId, definition: value });
  } else if (current) {
    void send({
      ...base,
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
      pending.value = JSON.parse(raw) as KnowledgeRequest;
      void recover();
    }
  } catch {
    storageFailed.value = true;
  }
});
onBeforeUnmount(() => signal.abort());
</script>

<template>
  <section class="kc">
    <header class="bar">
      <h3>知识成分</h3>
      <button v-if="pending" type="button" @click="open('create')">核对保存结果</button>
      <button v-else type="button" class="primary" @click="open('create')">新建知识成分</button>
    </header>
    <form class="bar" @submit.prevent="loadList()">
      <label
        >按名称查找 <input v-model="filter" type="search" maxlength="512" :disabled="listBusy"
      /></label>
      <button type="submit" :disabled="listBusy">查找</button>
    </form>
    <p v-if="status" role="status">{{ status }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="listBusy" role="status">正在读取知识成分…</p>
    <p v-else-if="!rows.length && !error">这里还没有符合条件的知识成分。</p>
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
    <section v-if="detail" class="reading" aria-labelledby="kc-detail-title">
      <header class="bar">
        <h4 id="kc-detail-title">
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
      <template v-for="[field, label] in fields" :key="field">
        <section v-if="detail.content[field]" class="field">
          <h5>{{ label }}</h5>
          <RichContent :content="detail.content[field]" />
        </section>
      </template>
    </section>

    <dialog
      ref="dialog"
      aria-labelledby="kc-form-title"
      @cancel.prevent="!saveBusy && dialog?.close()"
    >
      <form @submit.prevent="submit">
        <h3 id="kc-form-title">
          {{
            pending
              ? '核对保存结果'
              : mode === 'create'
                ? '新建知识成分'
                : mode === 'update'
                  ? '编辑知识成分'
                  : '移除知识成分'
          }}
        </h3>
        <p v-if="pending">请求已保留。请先确认保存结果。</p>
        <template v-else>
          <p v-if="mode === 'soft_delete'">
            将从列表移除「{{ detail?.content.name }}」，已有版本仍可查阅。
          </p>
          <template v-else>
            <label>名称 <input v-model="name" required /></label>
            <label v-for="[field, label] in fields" :key="field">
              {{ label }}
              <textarea
                v-if="mode === 'create' || plainText(detail?.content[field]) !== null"
                v-model="draft[field]"
                :required="field === 'definition' || field === 'applicability'"
                rows="2"
              />
              <span v-else>保留已有内容。</span>
            </label>
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
.kc,
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
}
dialog::backdrop {
  background: #151c1855;
}
dialog form,
dialog label {
  display: grid;
  gap: 0.55rem;
}
</style>
