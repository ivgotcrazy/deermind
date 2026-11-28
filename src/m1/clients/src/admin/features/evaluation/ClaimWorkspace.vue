<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';
import { get, post } from '../../../shared/api/http';
import { editionPath, type BookTypes, type Edition } from '../../../shared/book/editions';
import type { DomainSession } from '../domain/api';
import BookModelScope from '../materials/BookModelScope.vue';
import { generateBookDraft } from '../materials/generation';
const { session } = defineProps<{ session: DomainSession }>();
type Model = BookTypes['AssessmentModel'];
type Claim = BookTypes['TaskStandard'];
type Book = BookTypes['TextbookListItem'];
const modelPath = '/api/m1/evaluation/textbooks/{book}/extractions/{extraction}/models';
const aspects = {
  independent: '独立完成',
  understanding: '理解与解释',
  transfer: '迁移',
  retention: '保持',
} as const;
const book = ref<Book>(),
  source = ref<Edition>(),
  models = ref<Model[]>([]),
  selected = ref<Model>();
const generation = ref(false),
  name = ref(''),
  focus = ref(''),
  editOpen = ref(false),
  draft = ref<Claim>(),
  busy = ref(false),
  error = ref(''),
  notice = ref('');
const stop = new AbortController();
let revision = 0;
const tasks = computed(() =>
  Array.from(new Map(source.value?.entries.map((t) => [t.task_ref.object_id, t])).values()),
);
const current = computed(() =>
  tasks.value.find((t) => t.task_ref.object_id === draft.value?.task_id),
);
async function scope(b?: Book, edition?: BookTypes['EditionInfo']) {
  const token = ++revision;
  book.value = b;
  models.value = [];
  source.value = undefined;
  selected.value = undefined;
  error.value = '';
  notice.value = '';
  if (!b || !edition) return;
  try {
    const [value, sets] = await Promise.all([
      get(editionPath, {
        session,
        signal: stop.signal,
        params: { book: b.textbook_id, edition: edition.edition_id },
      }),
      get(modelPath, {
        session,
        signal: stop.signal,
        params: { book: b.textbook_id, extraction: edition.edition_id },
      }),
    ]);
    if (token === revision) {
      source.value = value;
      models.value = sets;
    }
  } catch (e) {
    if (token === revision && !stop.signal.aborted) error.value = (e as Error).message;
  }
}
onBeforeUnmount(() => stop.abort());
async function reload(id?: string) {
  const token = revision;
  if (!book.value || !source.value) return;
  const items = await get(modelPath, {
    session,
    signal: stop.signal,
    params: { book: book.value.textbook_id, extraction: source.value.edition_id },
  });
  if (token === revision) {
    models.value = items;
    selected.value = items.find((m) => m.model_id === id);
  }
}
async function generate() {
  const b = book.value,
    src = source.value,
    token = revision;
  if (!b || !src || !name.value.trim() || busy.value) return;
  busy.value = true;
  generation.value = false;
  notice.value = '正在按任务生成整套评估标准，可离开后查看。';
  error.value = '';
  try {
    const id = await generateBookDraft(
      { session, signal: stop.signal },
      b.import_id,
      {
        action: 'assess',
        edition_id: src.edition_id,
        revision: src.revision,
        model_name: name.value.trim(),
      },
      focus.value.trim() || name.value.trim(),
    );
    if (token === revision) {
      await reload(id);
      notice.value = '草稿已生成，请逐任务核对。';
    }
  } catch (e) {
    if (token === revision && !stop.signal.aborted) {
      error.value = (e as Error).message;
      notice.value = '';
    }
  } finally {
    busy.value = false;
  }
}
function openTask(t: BookTypes['MapTask']) {
  const existing = selected.value?.claims.find((c) => c.task_id === t.task_ref.object_id);
  draft.value = {
    task_id: t.task_ref.object_id,
    title: existing?.title ?? t.name,
    description: existing?.description ?? '',
    methods: t.method_refs.map((m) => {
      const rule = existing?.methods.find((r) => r.method_id === m.object_id);
      return {
        method_id: m.object_id,
        pass_description: rule?.pass_description ?? '',
        fail_description: rule?.fail_description ?? '',
        unknown_description: rule?.unknown_description ?? '',
        aspects: (Object.keys(aspects) as (keyof typeof aspects)[]).map((aspect) => ({
          aspect,
          evidence: rule?.aspects.find((a) => a.aspect === aspect)?.evidence ?? '',
        })),
      };
    }),
  };
  editOpen.value = true;
  error.value = '';
}
async function save(action: 'save' | 'publish') {
  const s = selected.value,
    b = book.value,
    src = source.value,
    token = revision;
  if (!s || !b || !src || busy.value) return;
  if (action === 'publish') {
    try {
      await ElMessageBox.confirm(
        '发布「' + s.name + '」整套标准？发布后只读，可在创建目标时选取其中的 Claim。',
        '发布评估标准',
        { confirmButtonText: '发布', cancelButtonText: '取消' },
      );
    } catch {
      return;
    }
  }
  busy.value = true;
  error.value = '';
  try {
    const claims =
      action === 'save' && draft.value
        ? [
            ...s.claims.filter(
              (c) =>
                c.task_id !== draft.value!.task_id &&
                tasks.value.some((t) => t.task_ref.object_id === c.task_id),
            ),
            draft.value,
          ]
        : null;
    const saved = await post(
      '/api/m1/evaluation/textbooks/{book}/extractions/{extraction}/models/{model}',
      { request_id: crypto.randomUUID(), revision: s.revision, action, claims },
      {
        session,
        signal: stop.signal,
        params: { book: b.textbook_id, extraction: src.edition_id, model: s.model_id },
      },
    );
    if (token === revision) {
      editOpen.value = false;
      await reload(saved.model_id);
      notice.value = action === 'publish' ? '整套评估标准已发布。' : '判据已保存。';
    }
  } catch (e) {
    if (token === revision && !stop.signal.aborted) error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="admin-editor">
    <h1 class="admin-page-title">评估管理</h1>
    <BookModelScope :session="session" @change="scope" />
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="error && !editOpen" role="alert">{{ error }}</p>
    <section class="editor-panel">
      <header class="panel-heading">
        <div>
          <h2>{{ selected ? selected.name : '评估标准' }}</h2>
          <p v-if="source">基于教学提炼 v{{ source.number }} · {{ tasks.length }} 项任务</p>
        </div>
        <div v-if="selected">
          <ElButton @click="selected = undefined">返回版本列表</ElButton
          ><ElButton
            v-if="selected.status === 'draft'"
            type="primary"
            :loading="busy"
            @click="save('publish')"
            >发布整套标准</ElButton
          ><ElTag v-else type="success">已发布</ElTag>
        </div>
        <div v-else>
          <ElButton
            v-if="source"
            :disabled="busy"
            @click="reload().catch((e) => (error = e.message))"
            >刷新</ElButton
          ><ElButton
            type="primary"
            :disabled="!source || busy"
            @click="
              name = '';
              focus = '';
              generation = true;
            "
            >生成评估草稿</ElButton
          >
        </div>
      </header>
      <ElEmpty v-if="!source" description="先选择领域、教材和已发布的教学提炼" :image-size="72" />
      <ElTable v-else-if="!selected" :data="models" empty-text="这版提炼尚无评估标准"
        ><ElTableColumn prop="name" label="评估标准" min-width="150" /><ElTableColumn
          label="版本"
          width="80"
          ><template #default="{ row }">v{{ row.number }}</template></ElTableColumn
        ><ElTableColumn label="状态"
          ><template #default="{ row }"
            ><ElTag :type="row.status === 'published' ? 'success' : 'info'">{{
              row.status === 'published' ? '已发布' : '草稿'
            }}</ElTag></template
          ></ElTableColumn
        ><ElTableColumn label="已起草任务"
          ><template #default="{ row }"
            >{{ row.claims.length }} / {{ tasks.length }}</template
          ></ElTableColumn
        ><ElTableColumn label="操作" width="100"
          ><template #default="{ row }"
            ><ElButton link type="primary" @click="selected = row as Model">{{
              row.status === 'published' ? '查看' : '编辑'
            }}</ElButton></template
          ></ElTableColumn
        ></ElTable
      >
      <ElTable v-else :data="tasks" row-key="name"
        ><ElTableColumn prop="name" label="任务" /><ElTableColumn label="Claim"
          ><template #default="{ row }">{{
            selected?.claims.find((c) => c.task_id === row.task_ref.object_id)?.title ?? '待补充'
          }}</template></ElTableColumn
        ><ElTableColumn label="操作" width="100"
          ><template #default="{ row }"
            ><ElButton link type="primary" @click="openTask(row as Edition['entries'][number])">{{
              selected?.status === 'draft' ? '编辑判据' : '查看判据'
            }}</ElButton></template
          ></ElTableColumn
        ></ElTable
      >
    </section>
    <ElDialog
      v-model="generation"
      title="生成评估草稿"
      width="min(500px,92vw)"
      :close-on-click-modal="false"
      ><ElForm label-position="top"
        ><ElFormItem label="标准名称"
          ><ElInput v-model="name" maxlength="160" placeholder="例如：概念理解" /></ElFormItem
        ><ElFormItem label="本套标准的侧重点"
          ><ElInput
            v-model="focus"
            type="textarea"
            :rows="3"
            placeholder="例如：重点观察学生是否说清分率对应的整体" /></ElFormItem></ElForm
      ><template #footer
        ><ElButton @click="generation = false">取消</ElButton
        ><ElButton type="primary" :disabled="!name.trim() || busy" @click="generate"
          >开始生成</ElButton
        ></template
      ></ElDialog
    >
    <ElDialog
      v-model="editOpen"
      :title="current?.name ?? '任务判据'"
      width="min(700px,94vw)"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <article
        v-if="draft && selected?.status === 'published'"
        class="criteria-body criteria-reading"
      >
        <header>
          <h3>{{ draft.title }}</h3>
          <p class="field-label">可观察的学习表现</p>
          <p>{{ draft.description }}</p>
        </header>
        <section v-for="(m, i) in draft.methods" :key="m.method_id">
          <h3>{{ current?.method_names[i] }}</h3>
          <dl>
            <dt>通过</dt>
            <dd>{{ m.pass_description }}</dd>
            <dt>未通过</dt>
            <dd>{{ m.fail_description }}</dd>
            <dt>证据不足</dt>
            <dd>{{ m.unknown_description }}</dd>
            <template v-for="a in m.aspects" :key="a.aspect"
              ><dt>{{ aspects[a.aspect] }}的证据</dt>
              <dd>{{ a.evidence }}</dd></template
            >
          </dl>
        </section>
      </article>
      <ElForm v-else-if="draft" class="criteria-body" label-position="top"
        ><ElFormItem label="Claim 名称"><ElInput v-model="draft.title" /></ElFormItem
        ><ElFormItem label="可观察的学习表现"
          ><ElInput v-model="draft.description" type="textarea"
        /></ElFormItem>
        <section v-for="(m, i) in draft.methods" :key="m.method_id">
          <h3>{{ current?.method_names[i] }}</h3>
          <ElFormItem label="通过"
            ><ElInput v-model="m.pass_description" type="textarea" /></ElFormItem
          ><ElFormItem label="未通过"
            ><ElInput v-model="m.fail_description" type="textarea" /></ElFormItem
          ><ElFormItem label="证据不足"
            ><ElInput v-model="m.unknown_description" type="textarea"
          /></ElFormItem>
          <ElFormItem v-for="a in m.aspects" :key="a.aspect" :label="aspects[a.aspect] + '的证据'"
            ><ElInput v-model="a.evidence" type="textarea"
          /></ElFormItem></section
      ></ElForm>
      <p v-if="error" role="alert">{{ error }}</p>
      <template #footer
        ><ElButton @click="editOpen = false">关闭</ElButton
        ><ElButton
          v-if="selected?.status === 'draft'"
          type="primary"
          :loading="busy"
          @click="save('save')"
          >保存判据</ElButton
        ></template
      ></ElDialog
    >
  </section>
</template>
<style scoped>
.criteria-body {
  max-height: min(58vh, 660px);
  overflow-y: auto;
  padding-right: 10px;
  scrollbar-gutter: stable;
}
.criteria-reading {
  color: var(--el-text-color-primary);
  line-height: 1.65;
}
.criteria-reading h3 {
  margin: 0 0 12px;
  font-size: 16px;
}
.criteria-reading p {
  margin: 4px 0;
  white-space: pre-line;
}
.criteria-reading .field-label,
.criteria-reading dt {
  color: var(--el-text-color-regular);
  font-weight: 600;
}
.criteria-reading section {
  margin-top: 20px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 16px;
}
.criteria-reading dl {
  display: grid;
  grid-template-columns: minmax(6em, 9em) 1fr;
  gap: 12px 16px;
  margin: 0;
}
.criteria-reading dd {
  margin: 0;
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.panel-heading h2 {
  margin: 0;
  font-size: 17px;
}
.panel-heading p {
  margin: 5px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
