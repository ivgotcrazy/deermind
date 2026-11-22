<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError, get, post } from '../../../shared/api/http';
import { listDomains } from '../domain/api';
import type { DomainRow, DomainSession } from '../domain/api';
import { detail, download, listTextbooks, readReceipt, receive, upload } from './api';
import type { MaterialDetail, MaterialFile, ReceiveCommand, SourceView, TextbookRow } from './api';
import MaterialAssistantPanel from './MaterialAssistantPanel.vue';
import ChapterAssociationsPanel from './ChapterAssociationsPanel.vue';

const { session } = defineProps<{ session: DomainSession }>();
const lifecycle = new AbortController();
const books = ref<TextbookRow[]>([]);
const domains = ref<DomainRow[]>([]);
const bookCursor = ref<string>();
const selected = ref<MaterialDetail>();
const dialog = ref<HTMLDialogElement>();
const deleteDialog = ref<HTMLDialogElement>();
const materialTab = ref<'content' | 'associations'>('content');
const deleting = ref(false);
const deleteError = ref('');
let deleteRequest: string | undefined;
const title = ref('');
const domain = ref('');
const source = ref('');
const edition = ref('');
const filter = ref('');
const files = ref<File[]>([]);
const beginningOrder = ref(1);
const busy = ref(false);
const progress = ref('');
const error = ref('');
const resultNotice = ref('');
const pending = ref<ReceiveCommand>();
const appending = ref(false);
const bookFilter = ref('');
const hasBook = computed(() => Boolean(selected.value));

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

async function loadBooks(cursor?: string) {
  const name = filter.value.trim();
  const response = await listTextbooks(session, name, cursor);
  books.value = cursor ? [...books.value, ...response.items] : response.items;
  bookCursor.value = response.next_cursor ?? undefined;
  bookFilter.value = name;
}

async function read(id: string, cursor?: string) {
  const response = await detail(session, id, cursor);
  if (cursor && selected.value?.textbook.textbook_id === id) {
    selected.value = {
      ...response.import,
      sources: [...selected.value.sources, ...response.import.sources],
    };
  } else {
    if (selected.value?.textbook.textbook_id !== id) materialTab.value = 'content';
    selected.value = response.import;
  }
}

async function openDelete() {
  const current = selected.value;
  if (!current) return;
  deleteError.value = '';
  try {
    await read(current.textbook.textbook_id);
    deleteRequest = undefined;
    deleteDialog.value?.showModal();
  } catch (cause) {
    error.value = message(cause, '无法核对要删除的导入。');
  }
}

async function removeImport() {
  const book = selected.value;
  if (!book || deleting.value) return;
  deleting.value = true;
  deleteError.value = '';
  deleteRequest ??= crypto.randomUUID();
  const opts = { session, signal: lifecycle.signal };
  try {
    try {
      await post(
        '/api/m1/material-imports/{import_id}/delete',
        {
          request_id: deleteRequest,
          expected_revision: book.revision,
          confirmed_scope_ref: book.deletion_scope_ref,
        },
        { ...opts, params: { import_id: book.textbook.import_id } },
      );
    } catch (cause) {
      const receipt = await get('/api/m1/requests/receipt', {
        ...opts,
        query: {
          action: 'product.delete_material_import',
          resource_kind: 'material_import',
          resource_id: book.textbook.import_id,
          request_id: deleteRequest,
        },
      });
      if (receipt.receipt_state !== 'completed') throw cause;
    }
    deleteDialog.value?.close();
    selected.value = undefined;
    resultNotice.value = '教材导入已删除。';
    await loadBooks();
  } catch (cause) {
    deleteError.value = message(cause, '无法删除此次导入。');
  } finally {
    deleting.value = false;
  }
}

async function show(id: string, cursor?: string) {
  busy.value = true;
  error.value = '';
  try {
    await read(id, cursor);
  } catch (cause) {
    error.value = message(cause, '无法读取教材。');
  } finally {
    busy.value = false;
  }
}

async function search(next = false) {
  busy.value = true;
  error.value = '';
  try {
    if (!next || bookFilter.value === filter.value.trim())
      await loadBooks(next ? bookCursor.value : undefined);
  } catch (cause) {
    error.value = message(cause, '无法读取教材列表。');
  } finally {
    busy.value = false;
  }
}

function open(append: boolean) {
  appending.value = append;
  error.value = '';
  resultNotice.value = '';
  title.value = '';
  source.value = '';
  edition.value = '';
  domain.value = append ? (selected.value?.textbook.domain_id ?? '') : '';
  beginningOrder.value = append ? (selected.value?.sources.at(-1)?.order ?? 0) + 1 : 1;
  files.value = [];
  dialog.value?.showModal();
}

function choose(event: Event) {
  const input = event.target;
  if (input instanceof HTMLInputElement) files.value = Array.from(input.files ?? []);
}

async function store(command: ReceiveCommand, uploadFailures: string[] = []) {
  pending.value = command;
  let result;
  try {
    result = (await receive(session, command)).result;
  } catch (cause) {
    const stored = await readReceipt(session, command);
    if (stored.state === 'rejected') {
      pending.value = undefined;
      throw new Error(stored.error ?? '原件登记被拒绝。', { cause });
    }
    if (!stored.result) {
      if (cause instanceof ApiError && cause.status < 500) pending.value = undefined;
      throw cause;
    }
    result = stored.result;
  }
  pending.value = undefined;
  dialog.value?.close();
  resultNotice.value =
    `已登记 ${result.received.length} 份原件。` +
    (uploadFailures.length ? `未上传：${uploadFailures.join('；')}。` : '') +
    (result.failed.length ? `未登记 ${result.failed.length} 份收据。` : '');
  await loadBooks();
  await read(result.textbook_id);
}

async function submit() {
  busy.value = true;
  error.value = '';
  try {
    if (pending.value) {
      await store(pending.value);
      return;
    }
    const chosen = domains.value.find((row) => row.object_ref.object_id === domain.value);
    if (!chosen) throw new Error('请先选择有效领域。');
    if (!files.value.length) throw new Error('请选择教材文件。');
    if (
      files.value.length > 600 ||
      files.value.reduce((sum, file) => sum + file.size, 0) > 2 * 1024 ** 3
    ) {
      throw new Error('一次最多上传 600 份文件且总量不超过 2 GiB。');
    }
    const current = appending.value ? selected.value : undefined;
    const accepted: MaterialFile[] = [];
    const failed: string[] = [];
    for (const [index, file] of files.value.entries()) {
      progress.value = `正在上传 ${index + 1}/${files.value.length}`;
      try {
        accepted.push(
          await upload(
            session,
            file,
            chosen.object_ref,
            beginningOrder.value + index,
            current?.textbook.import_id,
          ),
        );
      } catch (cause) {
        failed.push(`${file.name}（${message(cause, '上传失败')}）`);
      }
    }
    if (!accepted.length) throw new Error(failed.join('；'));
    progress.value = '正在登记原件';
    const command = { request_id: crypto.randomUUID(), files: accepted };
    await store(
      current
        ? {
            kind: 'material_import',
            scope: current.textbook.import_id,
            body: { ...command, expected_revision: current.source_revision },
          }
        : {
            kind: 'domain',
            scope: chosen.object_ref.object_id,
            body: {
              ...command,
              domain_ref: chosen.object_ref,
              title: title.value,
              source: source.value,
              edition: edition.value || null,
            },
          },
      failed,
    );
  } catch (cause) {
    error.value = message(cause, '未能确定保存结果，请重试本次登记。');
  } finally {
    busy.value = false;
    progress.value = '';
  }
}

async function getFile(item: SourceView) {
  error.value = '';
  try {
    await download(session, item);
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : message(cause, '读取文件失败。');
  }
}

onMounted(async () => {
  try {
    const [available] = await Promise.all([listDomains(session, lifecycle.signal), loadBooks()]);
    domains.value = available.items;
  } catch (cause) {
    error.value = message(cause, '无法加载教材管理。');
  }
});
onBeforeUnmount(() => lifecycle.abort());
</script>

<template>
  <section class="auth-card material-workspace" aria-label="教材管理">
    <h2>教材管理</h2>
    <p v-if="resultNotice" role="status">{{ resultNotice }}</p>
    <p v-if="error && !dialog?.open" role="alert">{{ error }}</p>

    <template v-if="!hasBook">
      <form class="material-actions" @submit.prevent="search()">
        <label>教材名称 <input v-model="filter" type="search" maxlength="512" /></label>
        <button type="submit" :disabled="busy">搜索</button>
        <button type="button" :disabled="busy" @click="open(false)">上传教材</button>
      </form>
      <ul v-if="books.length" class="material-list">
        <li v-for="book in books" :key="book.textbook_id">
          <button type="button" :disabled="busy" @click="show(book.textbook_id)">
            {{ book.metadata.title }}
          </button>
          <span>{{ book.metadata.source }}</span>
        </li>
      </ul>
      <p v-else>暂无教材。</p>
      <button v-if="bookCursor" type="button" :disabled="busy" @click="search(true)">
        更多教材
      </button>
    </template>

    <template v-else-if="selected">
      <button type="button" :disabled="busy" @click="selected = undefined">返回教材列表</button>
      <h3>{{ selected.textbook.metadata.title }}</h3>
      <p>
        {{ selected.textbook.metadata.source
        }}<span v-if="selected.textbook.metadata.edition">
          · {{ selected.textbook.metadata.edition }}</span
        >
      </p>
      <div class="material-actions">
        <h4>教材原件</h4>
        <button
          type="button"
          :disabled="busy || Boolean(selected.next_source_cursor)"
          @click="open(true)"
        >
          补充原件
        </button>
        <button type="button" class="secondary" :disabled="busy" @click="openDelete">
          删除导入
        </button>
      </div>
      <ol class="material-list">
        <li v-for="item in selected.sources" :key="item.source_ref.id">
          <button type="button" @click="getFile(item)">{{ item.original_name }}</button>
          <span>{{ item.page_count }} 页 · 顺序 {{ item.order }}</span>
        </li>
      </ol>
      <button
        v-if="selected.next_source_cursor"
        type="button"
        :disabled="busy"
        @click="show(selected.textbook.textbook_id, selected.next_source_cursor)"
      >
        更多原件
      </button>
      <nav aria-label="教材工作区">
        <button
          type="button"
          class="secondary"
          :aria-pressed="materialTab === 'content'"
          @click="materialTab = 'content'"
        >
          解析内容
        </button>
        <button
          type="button"
          class="secondary"
          :aria-pressed="materialTab === 'associations'"
          @click="materialTab = 'associations'"
        >
          章节关联
        </button>
      </nav>
      <MaterialAssistantPanel
        v-show="materialTab === 'content'"
        :key="selected.textbook.import_id"
        :material="selected"
        :session="session"
      />
      <ChapterAssociationsPanel
        v-if="materialTab === 'associations'"
        :material="selected"
        :session="session"
      />
    </template>

    <dialog ref="deleteDialog" aria-label="删除教材导入">
      <form class="material-form" @submit.prevent="removeImport">
        <h3>删除教材导入</h3>
        <p>此操作会停止未完成的教材处理，保留原件以及已经入库的领域内容。</p>
        <p v-if="deleteError" role="alert">{{ deleteError }}</p>
        <button type="submit" :disabled="deleting">确认删除</button>
        <button type="button" class="secondary" :disabled="deleting" @click="deleteDialog?.close()">
          取消
        </button>
      </form>
    </dialog>
    <dialog ref="dialog" aria-labelledby="material-editor-title" @cancel.prevent>
      <form class="material-form" @submit.prevent="submit">
        <h3 id="material-editor-title">{{ appending ? '补充原件' : '上传教材' }}</h3>
        <template v-if="!appending">
          <label
            >所属领域
            <select v-model="domain" required :disabled="busy || Boolean(pending)">
              <option value="">请选择领域</option>
              <option
                v-for="row in domains"
                :key="row.object_ref.object_id"
                :value="row.object_ref.object_id"
              >
                {{ row.name }}
              </option>
            </select></label
          >
          <label
            >教材名称
            <input
              v-model.trim="title"
              required
              maxlength="512"
              :disabled="busy || Boolean(pending)"
          /></label>
          <label
            >来源说明
            <input
              v-model.trim="source"
              required
              maxlength="512"
              :disabled="busy || Boolean(pending)"
          /></label>
          <label
            >版次
            <input v-model.trim="edition" maxlength="512" :disabled="busy || Boolean(pending)"
          /></label>
        </template>
        <label
          >教材文件
          <input
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            multiple
            :disabled="busy || Boolean(pending)"
            @change="choose"
        /></label>
        <p v-if="files.length">{{ files.map((file) => file.name).join('、') }}</p>
        <p v-if="progress" role="status">{{ progress }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="material-actions">
          <button type="button" :disabled="busy || Boolean(pending)" @click="dialog?.close()">
            取消
          </button>
          <button type="submit" :disabled="busy">
            {{ pending ? '继续本次登记' : '上传并登记' }}
          </button>
        </div>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.material-workspace,
.material-form,
.material-form label {
  display: grid;
  gap: 0.8rem;
}
.material-actions,
.material-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.7rem;
}
.material-list {
  display: grid;
  gap: 0.7rem;
}
dialog {
  width: min(30rem, calc(100% - 2rem));
  border: 1px solid #d7dfd6;
  border-radius: 0.8rem;
  color: inherit;
  padding: 1.5rem;
}
dialog::backdrop {
  background: rgb(21 39 32 / 45%);
}
</style>
