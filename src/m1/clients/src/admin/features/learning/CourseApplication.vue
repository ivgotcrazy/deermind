<script setup lang="ts">
import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElCheckboxGroup,
  ElDialog,
  ElPopover,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';
import { computed, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, post } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';

type Schema = components['schemas'];
type Chapter = { id: string; title: string; revision: number };
const props = defineProps<{
  session: DomainSession;
  target: Schema['TargetView'];
  importId: string;
  textbookTitle: string;
  chapters: Chapter[];
}>();
const selected = ref<string[]>([]);
const check = ref<Schema['CourseCheckResult']>();
const error = ref('');
const status = ref('');
const busy = ref(false);
const dialog = ref(false);
const head = ref<Schema['ApplicationHead']>();
const previousHead = ref<Schema['ApplicationHead']>();
const appliedTarget = ref<Schema['TargetView']>();
const applied = ref<Schema['CourseApplyResult']>();
const pending = ref<Schema['CourseConfirmCommand']>();
const activities = ['explanation', 'question_answer', 'detection', 'free_chat'] as const;
const labels = {
  reading: '教材阅读',
  explanation: '讲解与答疑',
  qa: '讲解与答疑',
  practice_feedback: '练习反馈',
  detection: '正式检测',
  evaluation: '评价',
};
const states = { ready: '就绪', limited: '受限', blocked: '阻止应用' };
const severity = { ready: 0, limited: 1, blocked: 2 };
const explanations = {
  reading: '已采用本章教材内容。',
  explanation: '已核对章节关联与讲解、答疑配置。',
  qa: '已核对章节关联与讲解、答疑配置。',
  practice_feedback: '已核对练习与当题反馈所需内容。',
  detection: '可按目标要求准备题单。',
  evaluation: '已核对目标要求的评价依据。',
};

const chosenChapters = computed(() =>
  props.chapters.filter((chapter) => selected.value.includes(chapter.id)),
);
const nextVersion = computed(() =>
  head.value ? (head.value.application_version ?? 0) + 1 : undefined,
);
const caption = computed(() =>
  [props.textbookTitle, ...chosenChapters.value.map((chapter) => chapter.title)].join(' · '),
);
const readiness = computed(() => {
  const rows = new Map<
    string,
    {
      subject: string;
      purpose: Schema['Purpose'];
      status: Schema['PurposeCheck']['status'];
      issues: Set<string>;
    }
  >();
  for (const row of check.value?.readiness ?? []) {
    const purpose = row.purpose === 'qa' ? 'explanation' : row.purpose;
    const key = `${row.subject_ref.id}:${purpose}`;
    const item = rows.get(key) ?? {
      subject:
        props.chapters.find((chapter) => chapter.id === row.subject_ref.id)?.title ??
        props.target.title,
      purpose,
      status: 'ready' as const,
      issues: new Set<string>(),
    };
    if (severity[row.status] > severity[item.status]) item.status = row.status;
    for (const reason of row.reasons) item.issues.add(reason.message);
    rows.set(key, item);
  }
  return [...rows.values()].map((row) => ({
    subject: row.subject,
    purpose: labels[row.purpose],
    status: states[row.status],
    tag: row.status === 'ready' ? 'success' : row.status === 'limited' ? 'warning' : 'danger',
    issues:
      [...row.issues].join(' ') ||
      (row.status === 'ready' ? explanations[row.purpose] : '请核对相关依据。'),
  }));
});

function describeMethods(target: Schema['TargetView']) {
  const [item] = target.items;
  if (target.items.length !== 1 || !item) return `${target.items.length} 项学习要求`;
  if (item.methods.length === 1) return '掌握一种解法';
  if (item.method_mode === 'each' && item.methods.length === 2) return '两种解法都要掌握';
  if (item.method_mode === 'each') return `${item.methods.length} 种解法都要掌握`;
  if (item.method_mode === 'any_one') return '任选一种解法';
  return '按目标要求掌握指定解法';
}

watch(
  () => props.target.target_ref,
  () => {
    selected.value = Array.from(new Set(props.target.items.flatMap((item) => item.chapter_refs)));
    check.value = undefined;
    status.value = '';
    error.value = '';
    head.value = undefined;
    appliedTarget.value = undefined;
    previousHead.value = undefined;
    applied.value = undefined;
    void readHead();
  },
  { immediate: true },
);
watch(selected, () => {
  check.value = undefined;
  applied.value = undefined;
  previousHead.value = undefined;
  status.value = '';
});

async function inspect() {
  busy.value = true;
  error.value = '';
  status.value = '';
  applied.value = undefined;
  previousHead.value = undefined;
  check.value = undefined;
  try {
    const session = props.session;
    const target = props.target;
    const chosen = props.chapters.filter((chapter) => selected.value.includes(chapter.id));
    const [current, configs, chapters] = await Promise.all([
      get('/api/m1/course-applications/current', {
        session,
        query: { textbook_id: target.textbook_id, target_id: target.target_ref.target_id },
      }),
      Promise.all(
        activities.map(async (activity_type) => {
          try {
            const view = await get('/api/m1/interaction/activity-configs/{activity_type}', {
              session,
              params: { activity_type },
            });
            return view.config_ref;
          } catch (caught) {
            if (caught instanceof ApiError && caught.status === 404) return undefined;
            throw caught;
          }
        }),
      ),
      Promise.all(
        chosen.map(async (chapter) => {
          const content = await get('/api/m1/material-imports/{import_id}/contents', {
            session,
            params: { import_id: props.importId },
            query: { chapter_id: chapter.id },
          });
          return {
            chapter_id: chapter.id,
            revision: chapter.revision,
            content_refs: content.items.flatMap((item) =>
              item.validity === 'current' &&
              typeof item.candidate_id === 'string' &&
              typeof item.candidate_revision === 'number'
                ? [
                    {
                      owner: 'product',
                      type: 'material_candidate',
                      id: item.candidate_id,
                      revision: item.candidate_revision,
                    },
                  ]
                : [],
            ),
          };
        }),
      ),
    ]);
    head.value = current;
    check.value = (
      await post(
        '/api/m1/course-applications/checks',
        {
          request_id: crypto.randomUUID(),
          textbook_id: target.textbook_id,
          target_ref: target.target_ref,
          expected_application_ref: current.application_ref,
          chapters,
          activity_config_refs: configs.filter(
            (config): config is Schema['Ref'] => config !== undefined,
          ),
        },
        { session },
      )
    ).result;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

async function apply() {
  if (!check.value?.can_apply) return;
  pending.value ??= {
    request_id: crypto.randomUUID(),
    check_ref: check.value.check_ref,
    expected_application_ref: check.value.base_application_ref,
  };
  busy.value = true;
  error.value = '';
  try {
    const { result } = await post('/api/m1/course-applications/confirmations', pending.value, {
      session: props.session,
    });
    acceptApplied(result);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status < 500 && caught.status !== 408) {
      pending.value = undefined;
      error.value = caught.message;
      if (caught.code === 'check_stale') check.value = undefined;
      dialog.value = false;
    } else {
      error.value = '暂时无法确认应用结果。请查询本次结果后再操作。';
    }
  } finally {
    busy.value = false;
  }
}

function acceptApplied(result: Schema['CourseApplyResult']) {
  previousHead.value = result.changed ? head.value : undefined;
  head.value = {
    application_ref: result.application_ref,
    application_version: result.application_version,
    target_revision: props.target.target_ref.revision,
  };
  appliedTarget.value = props.target;
  applied.value = result;
  status.value = result.changed
    ? `已发布课程 v${result.application_version}，可用于创建新的学习空间。`
    : '本次检查与已应用内容一致。';
  pending.value = undefined;
  dialog.value = false;
  error.value = '';
}

async function readReceipt() {
  if (!pending.value) return;
  busy.value = true;
  try {
    const receipt = await get('/api/m1/requests/receipt', {
      session: props.session,
      query: {
        action: 'product.confirm_course',
        resource_kind: 'textbook',
        resource_id: props.target.textbook_id,
        request_id: pending.value.request_id,
      },
    });
    const result = receipt.result;
    if (receipt.receipt_state === 'completed' && result && 'affected_spaces' in result) {
      acceptApplied(result);
    } else {
      error.value = '尚未查到应用结果，可以用原请求重试。';
    }
  } catch {
    error.value = '查询失败，请稍后再次查询。';
  } finally {
    busy.value = false;
  }
}

async function readHead() {
  const target = props.target;
  try {
    const loaded = await get('/api/m1/course-applications/current', {
      session: props.session,
      query: { textbook_id: target.textbook_id, target_id: target.target_ref.target_id },
    });
    if (target !== props.target) return;
    head.value = loaded;
    if (!loaded.target_revision) return;
    if (loaded.target_revision === target.target_ref.revision) {
      appliedTarget.value = target;
      return;
    }
    const { target: previous } = await get('/api/m1/learning-targets/{target_id}', {
      session: props.session,
      params: { target_id: target.target_ref.target_id },
      query: { revision: loaded.target_revision },
    });
    if (target === props.target && head.value?.application_ref?.id === loaded.application_ref?.id) {
      appliedTarget.value = previous;
    }
  } catch (caught) {
    if (target === props.target) error.value = (caught as Error).message;
  }
}
</script>

<template>
  <section class="course-application" aria-label="课程应用">
    <header class="version-summary">
      <div class="version-card">
        <div class="version-label">
          <span>已应用版本</span>
          <ElTag v-if="head?.application_version" type="success">当前应用</ElTag>
        </div>
        <strong v-if="head?.application_version">
          课程 v{{ head.application_version }} · 目标 v{{ head.target_revision }}
        </strong>
        <strong v-else>{{ head ? '尚未应用' : '正在读取' }}</strong>
        <p v-if="appliedTarget">{{ describeMethods(appliedTarget) }}</p>
      </div>
      <div v-if="applied?.changed" class="version-card">
        <div class="version-label"><span>之前的课程</span></div>
        <strong v-if="previousHead?.application_version">
          课程 v{{ previousHead.application_version }} · 目标 v{{ previousHead.target_revision }}
        </strong>
        <strong v-else>暂无已发布课程</strong>
        <p v-if="previousHead?.application_version">
          已选用 v{{ previousHead.application_version }} 的空间继续学习
        </p>
      </div>
      <div v-else class="version-card">
        <div class="version-label"><span>本次选用</span><ElTag type="info">本次检查</ElTag></div>
        <strong>
          <template v-if="nextVersion">课程 v{{ nextVersion }} · </template>目标 v{{
            target.target_ref.revision
          }}
        </strong>
        <p>{{ describeMethods(target) }}</p>
      </div>
    </header>

    <div class="chapter-selection">
      <span>本次选用章节</span>
      <ElPopover
        placement="bottom-start"
        trigger="click"
        :width="320"
        :disabled="busy || !!pending"
      >
        <template #reference>
          <ElButton link aria-label="调整本次选用章节" :disabled="busy || !!pending">
            {{ chosenChapters.map((chapter) => chapter.title).join('、') || '选择章节' }}
          </ElButton>
        </template>
        <ElCheckboxGroup v-model="selected" aria-label="本次选用章节" class="chapter-options">
          <ElCheckbox v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">{{
            chapter.title
          }}</ElCheckbox>
        </ElCheckboxGroup>
      </ElPopover>
    </div>

    <ElAlert
      v-if="error && !dialog"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      role="alert"
    />
    <section v-if="check" class="course-check-results" aria-label="检查结果">
      <header>
        <h2>检查结果</h2>
        <ElTag :type="check.can_apply ? 'success' : 'warning'" role="status">
          {{ check.can_apply ? '可应用' : '还有阻止应用的项目' }}
        </ElTag>
      </header>
      <ElTable :data="readiness" aria-label="课程检查结果">
        <ElTableColumn label="学生可做什么" min-width="184">
          <template #default="{ row }">
            <strong>{{ row.purpose }}</strong>
            <small v-if="chosenChapters.length > 1">{{ row.subject }}</small>
          </template>
        </ElTableColumn>
        <ElTableColumn label="准备情况" min-width="128">
          <template #default="{ row }"
            ><ElTag :type="row.tag">{{ row.status }}</ElTag></template
          >
        </ElTableColumn>
        <ElTableColumn prop="issues" label="依据与缺项" min-width="460" />
      </ElTable>
    </section>

    <footer class="course-actions">
      <p v-if="status" class="publication-status" role="status">{{ status }}</p>
      <p v-else-if="check?.can_apply && nextVersion">
        课程 v{{ nextVersion }} 应用后，学生可以用它创建新空间。已有空间继续使用原版。
      </p>
      <p v-else>检查章节准备情况后，就可以确认应用。</p>
      <div v-if="applied?.changed" class="publication-badge">
        <ElTag type="success">应用成功</ElTag>
      </div>
      <div v-else class="actions" :class="{ 'before-check': !check }">
        <ElButton v-if="!pending" :loading="busy" :disabled="!selected.length" @click="inspect">
          检查课程
        </ElButton>
        <ElButton
          v-if="check && !pending"
          type="primary"
          :disabled="busy || !check.can_apply"
          @click="dialog = true"
        >
          确认应用
        </ElButton>
        <ElButton v-if="pending && !dialog" :loading="busy" @click="readReceipt"
          >查询本次结果</ElButton
        >
        <ElButton v-if="pending && !dialog" type="primary" :disabled="busy" @click="apply"
          >用原请求重试</ElButton
        >
      </div>
    </footer>
    <ElDialog
      v-model="dialog"
      :title="'确认应用课程' + (nextVersion ? ' v' + nextVersion : '')"
      width="min(532px, calc(100vw - 2rem))"
      class="course-confirm"
      modal-class="course-confirm-overlay"
      align-center
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="!busy"
    >
      <p class="confirmation-meta">{{ caption }} · 目标 v{{ target.target_ref.revision }}</p>
      <p class="confirmation-note">
        新版会成为可选课程。<template v-if="head?.application_version"
          >已有课程 v{{ head.application_version }} 的空间继续使用原版，原学习记录保留。</template
        >
      </p>
      <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <template #footer>
        <ElButton :disabled="busy" @click="dialog = false">{{
          pending ? '稍后核对' : '取消'
        }}</ElButton>
        <ElButton v-if="pending" :loading="busy" @click="readReceipt">查询本次结果</ElButton>
        <ElButton type="primary" :loading="busy" @click="apply">
          {{ pending ? '用原请求重试' : '确认应用' }}
        </ElButton>
      </template>
    </ElDialog>
  </section>
</template>

<style scoped>
.course-application {
  display: grid;
  gap: 15px;
}
.version-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}
.version-card {
  min-height: 104px;
  padding: 11px 16px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 5px;
  background: white;
}
.version-label {
  display: flex;
  min-height: 24px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 0.75rem;
  font-weight: 600;
}
.version-card strong {
  display: block;
  margin-top: 3px;
  font-size: 1.125rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.version-card p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 0.8125rem;
  line-height: 1.55;
}
.chapter-selection {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 10px;
  font-size: 0.875rem;
  line-height: 20px;
}
.chapter-selection :deep(.el-button) {
  height: 20px;
  color: var(--el-text-color-primary);
  padding: 0;
}
.chapter-selection :deep(.el-button:hover) {
  color: var(--el-color-primary);
}
.chapter-options {
  display: grid;
}
.chapter-options :deep(.el-checkbox) {
  margin-inline-end: 0;
}
.course-check-results {
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 5px;
  background: white;
}
.course-check-results > header {
  display: flex;
  min-height: 55px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 20px 0 16px;
}
.course-check-results h2 {
  margin: 0;
  font-size: 1rem;
}
.course-check-results :deep(.el-table) {
  --el-table-header-bg-color: var(--el-fill-color-light);
  --el-table-border-color: var(--el-border-color);
  --el-table-header-text-color: var(--el-text-color-secondary);
}
.course-check-results :deep(.el-table th.el-table__cell) {
  height: 40px;
  font-size: 0.75rem;
}
.course-check-results :deep(.el-table td.el-table__cell) {
  height: 44px;
  padding-block: 8px;
  font-size: 0.8125rem;
}
.course-check-results :deep(.el-table .cell) {
  padding-inline: 16px;
  overflow-wrap: anywhere;
}
.course-check-results strong {
  color: var(--el-text-color-primary);
  font-size: 0.875rem;
  font-weight: 600;
}
.course-check-results small {
  display: block;
  color: var(--el-text-color-secondary);
}
.course-application :deep(.el-tag) {
  min-width: 58px;
  padding-inline: 12px;
  border: 0;
  border-radius: 4px;
  font-size: 0.6875rem;
  font-weight: 500;
}
.course-application :deep(.el-tag--success) {
  background: var(--admin-success-bg);
  color: var(--admin-success-text);
}
.course-application :deep(.el-tag--info) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
}
.course-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-block-start: 8px;
}
.course-actions p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.8125rem;
}
.course-actions .publication-status {
  color: var(--admin-success-text);
}
.publication-badge {
  min-height: 40px;
  display: flex;
  align-items: center;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 13px;
  flex-wrap: wrap;
  margin-inline-start: auto;
}
.actions.before-check {
  margin-inline-end: 140px;
}
.actions :deep(.el-button),
:global(.course-confirm .el-dialog__footer .el-button) {
  min-width: 116px;
  height: 40px;
  margin-left: 0;
  border-radius: 0;
}
.actions :deep(.el-button--primary),
:global(.course-confirm .el-dialog__footer .el-button--primary) {
  min-width: 124px;
}
:global(.course-confirm-overlay) {
  background-color: rgb(23 35 49 / 27%);
}
:global(.course-confirm.el-dialog) {
  --el-dialog-padding-primary: 18px;
  --el-dialog-border-radius: 6px;
  border: 1px solid var(--el-border-color);
  box-shadow: none;
}
:global(.course-confirm .el-dialog__title) {
  font-size: 1.375rem;
  font-weight: 700;
}
:global(.course-confirm .el-dialog__footer) {
  display: flex;
  justify-content: flex-end;
  gap: 13px;
  padding-top: 19px;
}
.confirmation-meta {
  margin: 5px 0 0;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
}
.confirmation-note {
  min-height: 62px;
  margin: 17px 0 0;
  color: var(--el-text-color-primary);
}
@media (max-width: 68rem) {
  .actions.before-check {
    margin-inline-end: 0;
  }
}
@media (max-width: 48rem) {
  .version-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
