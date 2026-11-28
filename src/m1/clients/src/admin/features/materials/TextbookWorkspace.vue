<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ApiError, get, post } from '../../../shared/api/http';
import { listDomains } from '../domain/api';
import type { DomainRow, DomainSession } from '../domain/api';
import DomainCreateDialog from '../domain/DomainCreateDialog.vue';
import { detail, listTextbooks, readReceipt, receive, upload } from './api';
import type { MaterialDetail, MaterialFile, ReceiveCommand, TextbookRow } from './api';
import { ElButton, ElEmpty, ElMessageBox } from 'element-plus';
import BookOriginal from './BookOriginal.vue';
import EditionWorkspace from './EditionWorkspace.vue';

const { session } = defineProps<{ session: DomainSession }>();
const lifecycle = new AbortController();
const books = ref<TextbookRow[]>([]);
const domains = ref<DomainRow[]>([]);
const domainFilter = ref('');
const domainDialog = ref<InstanceType<typeof DomainCreateDialog>>();
const domainNames = computed(
  () => new Map(domains.value.map((row) => [row.object_ref.object_id, row.name])),
);
const listError = ref('');
const loadingBooks = ref(true);
let listRequest: AbortController | undefined;
const bookCursor = ref<string>();
const selected = ref<MaterialDetail>();
const dialog = ref<HTMLDialogElement>();
const deleteDialog = ref<HTMLDialogElement>();
const bookViews = [
  { id: 'files', label: '教材原件' },
  { id: 'tree', label: '内容树' },
  { id: 'extraction', label: '教学提炼' },
  { id: 'work', label: '工作台' },
] as const;
const bookView = ref<(typeof bookViews)[number]['id']>('files');

const deleting = ref(false);
const deletingBook = ref<MaterialDetail>();
const deleteError = ref('');
let deleteRequest: string | undefined;
const title = ref('');
const domain = ref('');
const source = ref('');
const edition = ref('');
const filter = ref('');
const files = ref<File[]>([]);
const fileInput = ref<HTMLInputElement>();
const beginningOrder = ref(1);
const busy = ref(false);
const progress = ref('');
const error = ref('');
const resultNotice = ref('');
const pending = ref<ReceiveCommand>();
const appending = ref(false);
const hasBook = computed(() => Boolean(selected.value));
const stages = {
  ready: '待解析',
  processing: '解析中',
  review: '待核对',
  needs_input: '待补充',
  failed: '解析未完成',
  adopted: '教材已采用',
} as const;

function moveFile(index: number, distance: number) {
  const moved = files.value.splice(index, 1);
  files.value.splice(index + distance, 0, ...moved);
}

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

async function loadBooks(cursor?: string) {
  listRequest?.abort();
  const request = new AbortController();
  listRequest = request;
  loadingBooks.value = true;
  listError.value = '';
  if (!cursor) {
    bookCursor.value = undefined;
    books.value = [];
  }
  try {
    const response = await listTextbooks(
      session,
      { name: filter.value.trim(), domain_id: domainFilter.value || undefined, cursor },
      request.signal,
    );
    if (request.signal.aborted) return;
    books.value = cursor ? [...books.value, ...response.items] : response.items;
    bookCursor.value = response.next_cursor ?? undefined;
  } catch (cause) {
    if (!request.signal.aborted) listError.value = message(cause, '无法读取教材列表。');
  } finally {
    if (!request.signal.aborted) loadingBooks.value = false;
  }
}
watch([domainFilter, filter], () => void loadBooks());

async function read(id: string, cursor?: string) {
  const response = await detail(session, id, cursor);
  if (cursor && selected.value?.textbook.textbook_id === id) {
    selected.value = {
      ...response.import,
      sources: [...selected.value.sources, ...response.import.sources],
    };
  } else {
    if (selected.value?.textbook.textbook_id !== id) {
      bookView.value = 'files';
    }
    selected.value = response.import;
  }
}

async function openDelete(id: string) {
  deleteError.value = '';
  try {
    deletingBook.value = (await detail(session, id)).import;
    deleteRequest = undefined;
    deleteDialog.value?.showModal();
  } catch (cause) {
    error.value = message(cause, '无法核对要删除的导入。');
  }
}

async function removeImport() {
  const book = deletingBook.value;
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

async function selectCreatedDomain(id: string) {
  busy.value = true;
  domain.value = id;
  error.value = '';
  try {
    domains.value = (await listDomains(session, lifecycle.signal)).items;
  } catch (cause) {
    error.value = message(cause, '领域已创建，暂时无法读取领域列表。');
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
  domain.value = append ? (selected.value?.textbook.domain_id ?? '') : domainFilter.value;
  beginningOrder.value = append ? (selected.value?.sources.at(-1)?.order ?? 0) + 1 : 1;
  files.value = [];
  if (fileInput.value) fileInput.value.value = '';
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
  if (command.kind === 'domain') resultNotice.value = '教材已创建，可以导入原件。';
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
    if (!appending.value) {
      await store({
        kind: 'domain',
        scope: chosen.object_ref.object_id,
        body: {
          request_id: crypto.randomUUID(),
          files: [],
          domain_ref: chosen.object_ref,
          title: title.value,
          source: source.value || title.value,
          edition: edition.value || null,
        },
      });
      return;
    }
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
    if (!current) throw new Error('教材尚未选定。');
    await store(
      {
        kind: 'material_import',
        scope: current.textbook.import_id,
        body: { ...command, expected_revision: current.source_revision },
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

async function removeOriginals() {
  const item = selected.value;
  if (!item || busy.value) return;
  try {
    await ElMessageBox.confirm('移除本教材的全部原页？教材条目将保留。', '删除教材原件', {
      type: 'warning',
      confirmButtonText: '删除原件',
      cancelButtonText: '取消',
    });
  } catch {
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    await post(
      '/api/m1/material-imports/{import_id}/originals/remove',
      {
        request_id: crypto.randomUUID(),
        expected_revision: item.revision,
        confirmed_scope_ref: item.deletion_scope_ref,
      },
      { session, params: { import_id: item.textbook.import_id } },
    );
    await read(item.textbook.textbook_id);
    resultNotice.value = '原件已删除，可重新导入。';
  } catch (cause) {
    error.value = message(cause, '删除原件失败。');
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  void loadBooks();
  try {
    domains.value = (await listDomains(session, lifecycle.signal)).items;
    const book = new URLSearchParams(window.location.search).get('textbook');
    if (book) {
      await show(book);
      if (new URLSearchParams(window.location.search).has('extraction')) bookView.value = 'work';
    }
  } catch (cause) {
    error.value = message(cause, '无法加载教材管理。');
  }
});
onBeforeUnmount(() => {
  lifecycle.abort();
  listRequest?.abort();
});
</script>

<template>
  <section class="admin-editor material-workspace" aria-label="教材管理">
    <h1 v-if="!hasBook" class="admin-page-title">教材管理</h1>
    <p v-if="resultNotice" role="status">{{ resultNotice }}</p>
    <p v-if="error && !dialog?.open" role="alert">{{ error }}</p>

    <template v-if="!hasBook">
      <form class="admin-list-toolbar textbook-filters" @submit.prevent="loadBooks()">
        <label for="textbook-domain">领域</label>
        <select id="textbook-domain" v-model="domainFilter" aria-label="按领域查找">
          <option value="">全部领域</option>
          <option
            v-for="row in domains"
            :key="row.object_ref.object_id"
            :value="row.object_ref.object_id"
          >
            {{ row.name }}
          </option>
        </select>
        <label for="textbook-name">教材名称</label
        ><input
          id="textbook-name"
          v-model="filter"
          type="search"
          maxlength="512"
          placeholder="按教材名称搜索"
        />
        <button type="submit" class="secondary" :disabled="busy">搜索</button>
        <button type="button" class="primary toolbar-end" :disabled="busy" @click="open(false)">
          创建教材
        </button>
      </form>
      <p v-if="listError" role="alert">{{ listError }}</p>
      <table v-if="books.length" class="admin-data-table" aria-label="教材列表">
        <thead>
          <tr>
            <th>教材名称</th>
            <th>所属领域</th>
            <th>版次</th>
            <th>来源</th>
            <th>导入进度</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="book in books" :key="book.textbook_id">
            <td>
              <button type="button" :disabled="busy" @click="show(book.textbook_id)">
                {{ book.metadata.title }}
              </button>
            </td>
            <td>{{ domainNames.get(book.domain_id) ?? '领域不可用' }}</td>
            <td>{{ book.metadata.edition || '—' }}</td>
            <td>{{ book.metadata.source }}</td>
            <td>{{ stages[book.processing] }}</td>
            <td>
              <button type="button" :disabled="busy" @click="show(book.textbook_id)">
                查看教材
              </button>
              <ElButton link type="danger" :disabled="busy" @click="openDelete(book.textbook_id)"
                >删除</ElButton
              >
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="loadingBooks" class="editor-empty" role="status">正在读取教材…</p>
      <p v-else-if="!listError" class="editor-empty" role="status">
        {{
          filter.trim() ? '没有符合条件的教材。' : domainFilter ? '该领域暂无教材。' : '暂无教材。'
        }}
      </p>
      <button
        v-if="bookCursor"
        type="button"
        :disabled="busy || loadingBooks"
        @click="loadBooks(bookCursor)"
      >
        更多教材
      </button>
    </template>

    <template v-else-if="selected">
      <p class="admin-crumb">
        <button
          type="button"
          aria-label="返回教材列表"
          :disabled="busy"
          @click="
            selected = undefined;
            resultNotice = '';
            loadBooks();
          "
        >
          教材管理
        </button>
        / {{ selected.textbook.metadata.title }}
      </p>
      <h1 class="admin-page-title">{{ selected.textbook.metadata.title }}</h1>
      <p>
        所属领域 · {{ domainNames.get(selected.textbook.domain_id) ?? '领域不可用' }} ·
        {{ selected.textbook.metadata.source
        }}<span v-if="selected.textbook.metadata.edition">
          · {{ selected.textbook.metadata.edition }}</span
        >
      </p>
      <nav class="editor-tabs" aria-label="教材详情视图">
        <button
          v-for="view in bookViews"
          :key="view.id"
          type="button"
          :aria-pressed="bookView === view.id"
          @click="bookView = view.id"
        >
          {{ view.label }}
        </button>
      </nav>
      <section v-if="bookView === 'files'" class="editor-panel originals" aria-label="教材原件">
        <div class="material-actions">
          <h3>教材原件</h3>
          <ElButton
            v-if="selected.sources.length"
            text
            type="danger"
            :disabled="busy"
            @click="removeOriginals"
            >删除原件</ElButton
          >
        </div>
        <BookOriginal
          v-if="selected.sources.length"
          :key="selected.source_revision"
          :book="selected.textbook.textbook_id"
          :session="session"
        />
        <ElEmpty v-else description="尚未导入教材原件"
          ><ElButton type="primary" @click="open(true)">导入教材</ElButton></ElEmpty
        >
      </section>
      <EditionWorkspace
        v-else
        :key="selected.textbook.textbook_id"
        :view="bookView"
        :book-title="selected.textbook.metadata.title"
        :book="selected.textbook.textbook_id"
        :import-id="selected.textbook.import_id"
        :session="session"
        @work="bookView = 'work'"
      />
    </template>

    <dialog ref="deleteDialog" aria-label="删除教材">
      <form class="material-form" @submit.prevent="removeImport">
        <h3>删除教材</h3>
        <p>
          确认删除《{{
            deletingBook?.textbook.metadata.title
          }}》？已有发布的内容树或学习空间时无法删除。
        </p>
        <p v-if="deleteError" role="alert">{{ deleteError }}</p>
        <footer class="editor-footer">
          <button
            type="button"
            class="secondary"
            :disabled="deleting"
            @click="deleteDialog?.close()"
          >
            取消</button
          ><button type="submit" :disabled="deleting">确认删除</button>
        </footer>
      </form>
    </dialog>
    <dialog ref="dialog" aria-labelledby="material-editor-title" @cancel.prevent>
      <form class="material-form" @submit.prevent="submit">
        <h3 id="material-editor-title">{{ appending ? '导入原件' : '创建教材' }}</h3>
        <template v-if="!appending">
          <div class="upload-domain">
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
            <button
              type="button"
              class="secondary"
              :disabled="busy || !!pending"
              @click="domainDialog?.open()"
            >
              新建领域
            </button>
          </div>
          <button
            v-if="domain && !domainNames.has(domain)"
            type="button"
            class="secondary"
            :disabled="busy"
            @click="selectCreatedDomain(domain)"
          >
            重新读取所属领域
          </button>
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
            <input v-model.trim="source" maxlength="512" :disabled="busy || Boolean(pending)"
          /></label>
          <label
            >版次
            <input v-model.trim="edition" maxlength="512" :disabled="busy || Boolean(pending)"
          /></label>
        </template>
        <label v-if="appending"
          >教材文件
          <input
            ref="fileInput"
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            multiple
            :disabled="busy || Boolean(pending)"
            @change="choose"
        /></label>
        <ol v-if="files.length" class="upload-order" aria-label="原件顺序">
          <li v-for="(file, index) in files" :key="file.name + index">
            {{ file.name }}
            <button
              type="button"
              :disabled="busy || !!pending || index === 0"
              @click="moveFile(index, -1)"
            >
              上移
            </button>
            <button
              type="button"
              :disabled="busy || !!pending || index === files.length - 1"
              @click="moveFile(index, 1)"
            >
              下移
            </button>
          </li>
        </ol>
        <p v-if="progress" role="status">{{ progress }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="material-actions">
          <button type="button" :disabled="busy || Boolean(pending)" @click="dialog?.close()">
            取消
          </button>
          <button type="submit" :disabled="busy || (!pending && !domainNames.has(domain))">
            {{ pending ? '继续本次登记' : appending ? '导入原件' : '创建教材' }}
          </button>
        </div>
      </form>
    </dialog>
    <DomainCreateDialog
      ref="domainDialog"
      :session="session"
      select-on-save
      @saved="selectCreatedDomain"
    />
  </section>
</template>

<style scoped>
.originals {
  min-height: 380px;
}
.originals .el-empty {
  min-height: 300px;
}
.upload-domain {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
}
.textbook-filters input,
.textbook-filters select {
  flex: 1 1 10rem;
  min-width: 0;
}
.material-actions,
.material-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.material-actions h3 {
  margin-right: auto;
}
.material-list {
  padding: 0;
  list-style: none;
  margin: 12px 0 0;
}
.material-list li {
  padding: 8px 0;
  border-top: 1px solid var(--el-border-color-light);
}
.material-list span {
  margin-left: auto;
  color: var(--el-text-color-secondary);
}
.material-workspace > .editor-tabs {
  margin: 20px 0 16px;
}
</style>
