<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import { createDomain, listDomains, readCreateReceipt, readDomain } from './api';
import type { DomainRow, DomainSession, DomainView, MemberKind } from './api';
import { clearCreateDraft, readCreateDraft, saveCreateDraft } from './draft';
import type { CreateDraft } from './draft';
import DomainMembers from './DomainMembers.vue';

const { session } = defineProps<{ session: DomainSession }>();
const lifecycle = new AbortController();
const dialog = ref<HTMLDialogElement>();
const heading = ref<HTMLElement>();
const rows = ref<DomainRow[] | null>(null);
const filter = ref('');
const listError = ref('');
const selected = ref('');
const memberKind = ref<MemberKind>('kc');
const detail = ref<DomainView | null>(null);
const detailError = ref('');
let detailRead: AbortController | undefined;
let listRevision = 0;

const name = ref('');
const pending = ref<CreateDraft | null>(null);
const busy = ref<'saving' | 'checking' | null>(null);
const saveError = ref('');
const saveStatus = ref('');
const canRetry = ref(false);
const storageUnavailable = ref(false);

const visible = computed(() => {
  const term = filter.value.trim().toLocaleLowerCase();
  return (rows.value ?? []).filter((row) => row.name.toLocaleLowerCase().includes(term));
});

async function loadList() {
  const revision = ++listRevision;
  listError.value = '';
  try {
    const result = await listDomains(session, lifecycle.signal);
    if (!lifecycle.signal.aborted && revision === listRevision) rows.value = result.items;
  } catch (error) {
    if (!lifecycle.signal.aborted && revision === listRevision) {
      listError.value = error instanceof ApiError ? error.message : '暂时无法读取领域列表。';
    }
  }
}

async function selectDomain(id: string) {
  detailRead?.abort();
  const read = new AbortController();
  detailRead = read;
  selected.value = id;
  detail.value = null;
  detailError.value = '';
  try {
    const result = await readDomain(id, session, read.signal);
    if (read.signal.aborted) return;
    detail.value = result;
    await nextTick();
    heading.value?.focus();
  } catch (error) {
    if (!read.signal.aborted) {
      detailError.value = error instanceof ApiError ? error.message : '暂时无法读取该领域。';
    }
  }
}

function backToList() {
  detailRead?.abort();
  selected.value = '';
}

function openCreate() {
  if (!pending.value) {
    name.value = '';
    saveError.value = '';
    saveStatus.value = '';
  }
  dialog.value?.showModal();
}

function closeCreate() {
  if (!busy.value) dialog.value?.close();
}

function clearPending() {
  pending.value = null;
  canRetry.value = false;
  clearCreateDraft();
}

function saved(id: string) {
  clearPending();
  dialog.value?.close();
  void loadList();
  void selectDomain(id);
}

async function recover() {
  const draft = pending.value;
  if (!draft) return;
  canRetry.value = false;
  try {
    const receipt = await readCreateReceipt(draft, session, lifecycle.signal);
    if (lifecycle.signal.aborted) return;
    if (receipt.state === 'completed') {
      saved(receipt.domainId);
    } else if (receipt.state === 'not_found') {
      canRetry.value = true;
      saveStatus.value = '暂未查到保存记录。可以再次查询，或用原请求重试。';
    } else if (receipt.state === 'rejected') {
      clearPending();
      saveStatus.value = '';
      saveError.value = receipt.message ?? '这次保存未通过，请检查名称后再提交。';
    } else {
      saveStatus.value = '保存结果仍待核对，请稍后查询。';
    }
  } catch {
    if (!lifecycle.signal.aborted) saveStatus.value = '暂时无法核对保存结果，请稍后查询。';
  }
}

async function checkReceipt() {
  if (busy.value) return;
  busy.value = 'checking';
  try {
    await recover();
  } finally {
    busy.value = null;
  }
}

async function sendDraft(draft: CreateDraft) {
  if (busy.value) return;
  busy.value = 'saving';
  canRetry.value = false;
  saveError.value = '';
  saveStatus.value = '';
  try {
    const result = await createDomain(draft, session, lifecycle.signal);
    if (!lifecycle.signal.aborted) saved(result.result.object_ref.object_id);
  } catch (error) {
    if (lifecycle.signal.aborted) return;
    if (error instanceof ApiError && error.status < 500) {
      clearPending();
      saveError.value = error.message;
    } else {
      busy.value = 'checking';
      await recover();
    }
  } finally {
    busy.value = null;
  }
}

function submit() {
  if (busy.value || pending.value || !name.value.trim()) return;
  const draft = { request_id: crypto.randomUUID(), name: name.value.trim() };
  pending.value = draft;
  try {
    saveCreateDraft(session.account.account_id, draft);
  } catch {
    storageUnavailable.value = true;
  }
  void sendDraft(draft);
}

function retry() {
  if (canRetry.value && pending.value) void sendDraft(pending.value);
}

onMounted(() => {
  void loadList();
  try {
    pending.value = readCreateDraft(session.account.account_id);
  } catch {
    storageUnavailable.value = true;
  }
  if (pending.value) {
    name.value = pending.value.name;
    openCreate();
    void checkReceipt();
  }
});

onBeforeUnmount(() => {
  lifecycle.abort();
  detailRead?.abort();
});
</script>

<template>
  <section class="domain-workspace" aria-label="领域管理">
    <template v-if="!selected">
      <div class="heading-row">
        <h2>领域管理</h2>
        <button type="button" class="primary" @click="openCreate">
          {{ pending ? '核对待保存领域' : '新建领域' }}
        </button>
      </div>
      <label for="domain-search" class="visually-hidden">搜索领域</label>
      <input id="domain-search" v-model="filter" type="search" placeholder="按领域名称搜索" />

      <div v-if="listError" class="feedback">
        <p role="alert">{{ listError }}</p>
        <button type="button" class="secondary" @click="loadList">重新读取</button>
      </div>
      <p v-else-if="!rows" class="feedback" role="status">正在读取领域…</p>
      <p v-else-if="!visible.length" class="feedback">
        {{ rows.length ? '没有找到匹配的领域。' : '还没有领域。' }}
      </p>
      <ul v-else class="domain-list" aria-label="领域列表">
        <li v-for="row in visible" :key="row.object_ref.object_id">
          <button type="button" class="domain-row" @click="selectDomain(row.object_ref.object_id)">
            <span>{{ row.name }}</span>
            <span class="version">v{{ row.object_ref.version }}</span>
          </button>
        </li>
      </ul>
    </template>
    <template v-else>
      <button type="button" class="back" @click="backToList">返回领域列表</button>
      <div v-if="detail" class="domain-detail">
        <h2 ref="heading" tabindex="-1">{{ detail.content.name }}</h2>
        <dl>
          <dt>版本</dt>
          <dd>v{{ detail.object_ref.version }}</dd>
          <dt>领域编号</dt>
          <dd>{{ detail.object_ref.object_id }}</dd>
        </dl>
        <section v-if="detail.content.coverage" class="domain-reading" data-rich-field="coverage">
          <h3>范围</h3>
          <RichContent :content="detail.content.coverage" />
        </section>
        <section
          v-if="detail.content.description"
          class="domain-reading"
          data-rich-field="description"
        >
          <h3>说明</h3>
          <RichContent :content="detail.content.description" />
        </section>
        <nav class="member-navigation" aria-label="领域对象">
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'kc'"
            @click="memberKind = 'kc'"
          >
            知识成分
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'task'"
            @click="memberKind = 'task'"
          >
            任务
          </button>
          <button
            type="button"
            class="secondary"
            :aria-pressed="memberKind === 'solution'"
            @click="memberKind = 'solution'"
          >
            方法
          </button>
        </nav>
        <DomainMembers
          :key="`${selected}:${memberKind}`"
          :kind="memberKind"
          :domain-id="selected"
          :session="session"
        />
      </div>
      <div v-else-if="detailError" class="feedback">
        <p role="alert">{{ detailError }}</p>
        <button type="button" class="secondary" @click="selectDomain(selected)">重新读取</button>
      </div>
      <p v-else class="feedback" role="status">正在读取领域…</p>
    </template>

    <dialog ref="dialog" aria-labelledby="create-domain-title" @cancel.prevent="closeCreate">
      <form :aria-busy="!!busy" @submit.prevent="submit">
        <h2 id="create-domain-title">{{ pending && !busy ? '核对领域保存' : '新建领域' }}</h2>
        <label for="new-domain-name">领域名称</label>
        <input
          id="new-domain-name"
          v-model="name"
          autocomplete="off"
          :disabled="!!pending || !!busy"
          required
        />
        <p v-if="saveError" role="alert">{{ saveError }}</p>
        <p v-if="busy || saveStatus" role="status">
          {{
            busy === 'saving' ? '正在保存…' : busy === 'checking' ? '正在核对保存结果…' : saveStatus
          }}
        </p>
        <p v-if="storageUnavailable && pending" class="muted">
          当前浏览器无法暂存该请求，请在刷新前核对结果。
        </p>
        <div class="dialog-actions">
          <button type="button" class="secondary" :disabled="!!busy" @click="closeCreate">
            {{ pending ? '关闭' : '取消' }}
          </button>
          <button v-if="!pending" type="submit" class="primary" :disabled="!name.trim() || !!busy">
            保存领域
          </button>
          <template v-else>
            <button type="button" class="secondary" :disabled="!!busy" @click="checkReceipt">
              查询保存结果
            </button>
            <button v-if="canRetry" type="button" class="primary" :disabled="!!busy" @click="retry">
              用原请求重试
            </button>
          </template>
        </div>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.member-navigation {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}
.member-navigation button[aria-pressed='true'] {
  border-color: #28513c;
  background: #e6eee7;
}
.domain-workspace {
  margin-top: 1rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--color-line);
}

.heading-row,
.dialog-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.heading-row {
  justify-content: space-between;
  margin-bottom: 1rem;
}

h2 {
  margin: 0;
  font-size: 1.375rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

button,
input {
  padding: 0.575rem 0.75rem;
  border-radius: 0.375rem;
  font: inherit;
}

button {
  border: 1px solid transparent;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

button:focus-visible,
input:focus-visible,
h2:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}

.primary {
  background: var(--color-accent);
  color: white;
}

.secondary {
  color: var(--color-accent);
  border-color: var(--color-line);
  background: white;
}

input {
  width: 100%;
  border: 1px solid var(--color-line);
  color: inherit;
  background: white;
}

.visually-hidden {
  clip-path: inset(50%);
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  white-space: nowrap;
}

.domain-list {
  margin: 1rem 0 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--color-line);
}

.domain-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  width: 100%;
  padding-block: 0.8rem;
  border-radius: 0;
  border-bottom-color: var(--color-line);
  text-align: left;
  overflow-wrap: anywhere;
  background: white;
  color: var(--color-accent);
  font-weight: 600;
}

.domain-row:hover {
  background: #f6f8f5;
}

.version,
.muted,
.feedback,
dt {
  color: var(--color-muted);
}

.version {
  flex-shrink: 0;
  font-size: 0.875rem;
  font-weight: 400;
}

.back {
  margin: -0.25rem 0 0.75rem -0.75rem;
  color: var(--color-accent);
  background: transparent;
  text-decoration: underline;
  text-underline-offset: 0.25em;
}

.domain-detail {
  padding: 0.375rem 0 0.375rem 1rem;
  border-left: 0.25rem solid var(--color-accent);
}

dl {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.25rem 0.875rem;
  margin: 0.75rem 0 0;
}

dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.domain-reading {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-line);
}

.domain-reading h3 {
  margin: 0 0 0.625rem;
  color: var(--color-accent);
  font-size: 1rem;
  line-height: 1.5;
}

dialog {
  width: min(100% - 2rem, 27rem);
  padding: 1.5rem;
  border: 1px solid var(--color-line);
  border-radius: 0.75rem;
  color: inherit;
  background: white;
}

dialog::backdrop {
  background: rgb(35 60 51 / 25%);
}

dialog label {
  display: block;
  margin: 1rem 0 0.25rem;
}

.dialog-actions {
  justify-content: flex-end;
  margin-top: 1.25rem;
}

[role='alert'] {
  color: #943f31;
}
</style>
