<script setup lang="ts">
import { ElButton, ElDialog, ElInput, ElTag } from 'element-plus';
import { computed, ref } from 'vue';
import type { DomainSession } from '../domain/api';
import PromptText from './PromptText.vue';
import { activities, promptPreview, statusNames, type Activity, type Guide } from './promptPreview';

const props = defineProps<{ session: DomainSession }>();
const { guides } = promptPreview(props.session.session_id);
const kind = ref<Activity>('explanation');
const label = computed(() => activities.find((entry) => entry.id === kind.value)!.name);
const rows = computed(() => guides.value.filter((entry) => entry.activity === kind.value));
const opened = ref(false);
const mode = ref<'read' | 'edit'>('read');
const selected = ref<Guide>();
const formName = ref('');
const body = ref('');
const preview = ref(false);
const notice = ref('');

function show(row?: Guide, editing = false) {
  selected.value = row;
  formName.value = row?.name ?? '';
  body.value = row?.body ?? '';
  preview.value = false;
  mode.value = editing ? 'edit' : 'read';
  notice.value = '';
  opened.value = true;
}
const draftVersion = computed(() => {
  const row = selected.value;
  if (!row || row.status === 'draft') return row?.version ?? 1;
  return (
    1 +
    Math.max(
      ...guides.value.filter((entry) => entry.family === row.family).map((entry) => entry.version),
    )
  );
});
const canSave = computed(() => formName.value.trim() && body.value.trim());

function save(status: 'draft' | 'published') {
  if (!canSave.value) return;
  const source = selected.value;
  const row: Guide = {
    id: source?.status === 'draft' ? source.id : crypto.randomUUID(),
    family: source?.family ?? crypto.randomUUID(),
    activity: kind.value,
    name: formName.value.trim(),
    body: body.value.trim(),
    version: draftVersion.value,
    status,
  };
  guides.value = [row, ...guides.value.filter((entry) => entry.id !== row.id)];
  opened.value = false;
  notice.value =
    row.name +
    ' · v' +
    row.version +
    (status === 'draft' ? ' 已存为草稿。' : ' 已发布，可在目标中选择。');
}

function close(done: () => void) {
  const dirty =
    mode.value === 'edit' &&
    (body.value !== (selected.value?.body ?? '') ||
      formName.value !== (selected.value?.name ?? ''));
  if (!dirty || window.confirm('放弃尚未保存的修改？')) done();
}
function remove(row: Guide) {
  if (row.status === 'retired') return;
  const draft = row.status === 'draft';
  if (
    !window.confirm(draft ? '删除这份草稿？' : '停用这个版本？已有选择保留，新目标将不能再选用。')
  )
    return;
  if (draft) guides.value = guides.value.filter((entry) => entry.id !== row.id);
  else row.status = 'retired';
  notice.value = row.name + ' · v' + row.version + (draft ? ' 已删除。' : ' 已停用。');
}
</script>

<template>
  <section class="admin-editor guides" aria-label="交互活动">
    <h1 class="admin-page-title">交互活动</h1>
    <p class="review-note">交互预览 · 修改仅在当前页签内保留，刷新后恢复示例。</p>
    <nav class="editor-tabs" aria-label="活动类型">
      <button
        v-for="entry in activities"
        :key="entry.id"
        type="button"
        :aria-pressed="kind === entry.id"
        @click="
          kind = entry.id;
          notice = '';
        "
      >
        {{ entry.name }}
      </button>
    </nav>
    <section class="editor-panel">
      <header class="editor-row">
        <h2>{{ label }} Prompt</h2>
        <ElButton type="primary" @click="show(undefined, true)">新建 Prompt</ElButton>
      </header>
      <p v-if="notice" role="status">{{ notice }}</p>
      <table v-if="rows.length" class="admin-data-table" :aria-label="label + ' Prompt 列表'">
        <thead>
          <tr>
            <th>Prompt 名称</th>
            <th>版本</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <th scope="row">{{ row.name }}</th>
            <td>v{{ row.version }}</td>
            <td>
              <ElTag
                :type="
                  row.status === 'published'
                    ? 'success'
                    : row.status === 'draft'
                      ? 'warning'
                      : 'info'
                "
                >{{ statusNames[row.status] }}</ElTag
              >
            </td>
            <td>
              <div class="admin-row-actions">
                <button type="button" @click="show(row)">查看</button>
                <button type="button" @click="show(row, true)">编辑</button>
                <button
                  v-if="row.status !== 'retired'"
                  type="button"
                  class="destructive"
                  @click="remove(row)"
                >
                  {{ row.status === 'draft' ? '删除' : '停用' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="editor-empty">还没有{{ label }} Prompt。</p>
    </section>
    <ElDialog
      v-model="opened"
      :title="mode === 'read' ? selected?.name : selected ? '编辑 Prompt' : '新建 Prompt'"
      width="min(720px, 94vw)"
      top="6vh"
      :before-close="close"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <p class="guide-meta">
        {{ label }} · v{{ mode === 'read' ? selected?.version : draftVersion }}
        <template v-if="mode === 'read' && selected">
          · {{ statusNames[selected.status] }}</template
        >
        <template v-else-if="selected && selected.status !== 'draft'"> · 将保存为新版本</template>
      </p>
      <PromptText v-if="mode === 'read'" :body="body" />
      <div v-else class="guide-editor">
        <label
          >Prompt 名称<ElInput v-model="formName" maxlength="100" placeholder="输入名称"
        /></label>
        <div class="editor-row">
          <label for="activity-prompt-body">正文</label
          ><ElButton link @click="preview = !preview">{{
            preview ? '继续编辑' : '预览正文'
          }}</ElButton>
        </div>
        <PromptText v-if="preview" :body="body" />
        <textarea
          v-else
          id="activity-prompt-body"
          v-model="body"
          rows="12"
          placeholder="写下活动目标、方法及边界，可用 ## 标记小标题。"
        />
      </div>
      <template #footer>
        <ElButton @click="close(() => (opened = false))">{{
          mode === 'read' ? '关闭' : '取消'
        }}</ElButton>
        <template v-if="mode === 'edit'">
          <ElButton :disabled="!canSave" @click="save('draft')">保存草稿</ElButton>
          <ElButton type="primary" :disabled="!canSave" @click="save('published')"
            >发布版本</ElButton
          >
        </template>
      </template>
    </ElDialog>
  </section>
</template>

<style scoped>
.guides > nav {
  margin: 18px 0 16px;
}
.review-note,
.guide-meta {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.guide-meta {
  margin: 0 0 18px;
}
.guides table {
  margin-top: 16px;
}
.guides thead th:first-child {
  width: 44%;
}
.guide-editor {
  display: grid;
  gap: 8px;
}
.guide-editor label {
  display: grid;
  gap: 6px;
}
.guide-editor textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  font: inherit;
  line-height: 1.75;
  resize: vertical;
  border: 1px solid var(--el-border-color);
}
.guide-editor .editor-row {
  margin-top: 8px;
}
:deep(.el-dialog__body) {
  max-height: 62vh;
  overflow: auto;
}
@media (max-width: 620px) {
  .guides thead th:first-child {
    width: auto;
  }
  .guides :is(td, th) {
    padding: 8px;
  }
}
</style>
