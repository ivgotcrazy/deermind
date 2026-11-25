<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import { ElButton } from 'element-plus';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';
import EvidenceSource from './EvidenceSource.vue';

type Schema = components['schemas'];
const props = defineProps<{
  session: DomainSession;
  spaceId: string;
  subject: string;
  evidenceSubjects: Record<string, string>;
}>();
const trace = ref<HTMLDialogElement>();
const evidenceList = ref<Schema['EvidenceSummary'][]>([]);
const evidence = ref<Schema['EvidenceView']>();
const source = ref<Schema['SourceExcerpt']>();
const evidenceCursor = ref<string>();
const traceError = ref('');
const traceLoading = ref(false);
const traceSelection = ref<{ result_id: string; item_id: string } | { event_id: string }>();
let traceRequest = 0;

const linkedQuestion = ref<Schema['SourceExcerpt']>();
const back = ref<InstanceType<typeof ElButton>>();
const listButtons = ref<HTMLElement>();
const lastChosen = ref('');
const originalTime = computed(() => {
  const item = evidenceList.value.find(
    (row) => row.evidence_ref.id === evidence.value?.evidence_id,
  );
  return source.value && item?.timed_event_id === source.value.event_id ? item.occurred_at : null;
});
const sourceLabels = { detection: '正式检测', answer: '学生作答', teaching: '教学机会' };
const listTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: 'long',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});
const aspects: Record<string, string> = {
  independent: '独立',
  understanding: '理解',
  transfer: '迁移',
  retention: '保持',
};
const qualifications: Record<string, string> = {
  eligible: '符合评价条件',
  ineligible: '不符合评价条件',
  unknown: '依据不足',
};

function evidenceState(item: { verdict?: string | null; qualification: string }) {
  if (item.verdict === 'positive') return '正向证据';
  if (item.verdict === 'negative') return '反向证据';
  return qualifications[item.qualification] ?? '待确认';
}

function percent(value?: number | null) {
  return value == null ? '未观测' : `${(100 * value).toFixed(1)}%`;
}

function openTrace(selection: NonNullable<typeof traceSelection.value>) {
  traceSelection.value = selection;
  evidenceList.value = [];
  evidence.value = undefined;
  source.value = undefined;
  evidenceCursor.value = undefined;
  trace.value?.showModal();
  void readEvidenceList();
}

async function readEvidenceList(cursor?: string) {
  const scope_id = props.spaceId;
  const selection = traceSelection.value;
  if (!scope_id || !selection) return;
  const request = ++traceRequest;
  traceLoading.value = true;
  traceError.value = '';
  try {
    const data = await get('/api/m1/evaluation/spaces/{scope_id}/basis', {
      session: props.session,
      params: { scope_id },
      query: { view: 'item_id' in selection ? 'target' : 'event', ...selection, cursor },
    });
    if (request !== traceRequest) return;
    evidenceList.value = cursor
      ? [...evidenceList.value, ...(data.items ?? [])]
      : (data.items ?? []);
    evidenceCursor.value = data.next_cursor ?? undefined;
  } catch (caught) {
    if (request === traceRequest) traceError.value = (caught as Error).message;
  } finally {
    if (request === traceRequest) traceLoading.value = false;
  }
}

async function readEvidence(evidence_id: string, event_id?: string) {
  const scope_id = props.spaceId;
  if (!scope_id) return;
  const request = ++traceRequest;
  source.value = undefined;
  traceLoading.value = true;
  traceError.value = '';
  try {
    const data = await get('/api/m1/evaluation/spaces/{scope_id}/basis', {
      session: props.session,
      params: { scope_id },
      query: { view: 'evidence', evidence_id, event_id },
    });
    if (request !== traceRequest) return;
    linkedQuestion.value = undefined;
    if (data.source && data.evidence) {
      const allowed = data.evidence.source_refs.map((ref) => ref.event_id);
      for (const part of data.source.content) {
        if (!part || typeof part !== 'object' || Array.isArray(part)) continue;
        const questionId = 'task_use_event_id' in part ? part.task_use_event_id : undefined;
        if (
          typeof questionId !== 'string' ||
          !allowed.includes(questionId) ||
          questionId === event_id
        )
          continue;
        const linked = await get('/api/m1/evaluation/spaces/{scope_id}/basis', {
          session: props.session,
          params: { scope_id },
          query: { view: 'evidence', evidence_id, event_id: questionId },
        });
        if (request !== traceRequest) return;
        linkedQuestion.value = linked.source ?? undefined;
        break;
      }
    }
    evidence.value = data.evidence ?? undefined;
    source.value = data.source ?? undefined;
  } catch (caught) {
    if (request === traceRequest) traceError.value = (caught as Error).message;
  } finally {
    if (request === traceRequest) traceLoading.value = false;
  }
}

function resetTrace() {
  ++traceRequest;
  traceLoading.value = false;
  traceSelection.value = undefined;
}

function backToEvidenceList() {
  ++traceRequest;
  traceLoading.value = false;
  traceError.value = '';
  evidence.value = undefined;
  source.value = undefined;
}

async function selectEvidence(id: string) {
  lastChosen.value = id;
  await readEvidence(id);
  if (evidence.value) {
    await nextTick();
    back.value?.ref?.focus();
  }
}
async function returnToList() {
  backToEvidenceList();
  await nextTick();
  listButtons.value
    ?.querySelector<HTMLButtonElement>(`[data-evidence="${lastChosen.value}"]`)
    ?.focus();
}
const listSubject = computed(() => {
  const groups = new Set(
    evidenceList.value.map((item) => props.evidenceSubjects[item.evidence_ref.id]),
  );
  return groups.size === 1 ? [...groups][0] || props.subject : props.subject;
});
const sources = computed(() => {
  const refs = evidence.value?.source_refs ?? [];
  return [...new Set(refs.map((ref) => ref.event_id))].map((id) => ({
    id,
    answer: refs.some((ref) => ref.event_id === id && ref.path === '/answer'),
  }));
});
defineExpose({ openTrace });
</script>
<template>
  <dialog ref="trace" class="trace-drawer" aria-labelledby="evidence-title" @close="resetTrace">
    <header>
      <ElButton v-if="evidence" ref="back" link type="primary" @click="returnToList"
        >返回证据列表</ElButton
      >
      <ElButton v-else @click="trace?.close()">关闭</ElButton>
      <h2 id="evidence-title">评价证据</h2>
      <p>{{ (evidence && evidenceSubjects[evidence.evidence_id]) || listSubject }}</p>
    </header>
    <p v-if="traceLoading" role="status">正在读取评价依据。</p>
    <p v-if="traceError" role="alert">{{ traceError }}</p>
    <template v-if="evidence">
      <span class="trace-tag" :data-verdict="evidence.verdict">{{ evidenceState(evidence) }}</span>
      <h3>{{ evidence.qualification === 'eligible' ? '评价依据' : '资格判定依据' }}</h3>
      <p>{{ evidence.reason }}</p>
      <div class="trace-change">
        {{ aspects[evidence.aspect_code] ?? evidence.aspect_code }} ·
        <template v-if="evidence.belief_change?.update_kind === 'observation'"
          >观测概率 {{ percent(evidence.belief_change.p_obs_before) }} →
          {{ percent(evidence.belief_change.p_obs_after) }}</template
        >
        <template v-else-if="evidence.belief_change"
          >教学后的估计 {{ percent(evidence.belief_change.p_current_before) }} →
          {{ percent(evidence.belief_change.p_current_after) }}</template
        >
        <template v-else>本条证据未更新概率。</template>
      </div>
      <h4>来源事件</h4>
      <div class="source-actions">
        <ElButton
          v-for="(item, index) in sources"
          :key="item.id"
          link
          type="primary"
          @click="readEvidence(evidence.evidence_id, item.id)"
          >{{
            item.answer
              ? '查看原始作答'
              : '查看来源事实' + (sources.length > 1 ? ' ' + (index + 1) : '')
          }}</ElButton
        >
      </div>
      <EvidenceSource
        v-if="source"
        :excerpt="source"
        :paths="evidence.source_refs.filter((ref) => ref.event_id === source?.event_id)"
        :question="linkedQuestion"
        :occurred-at="originalTime"
      />
      <details v-if="source && evidence.source_spans.length">
        <summary>评价引用的原文</summary>
        <p v-for="span in evidence.source_spans" :key="span.ref.event_id + span.quote">
          {{ span.quote }}
        </p>
      </details>
    </template>
    <div v-else ref="listButtons" class="trace-list">
      <div v-for="item in evidenceList" :key="item.evidence_ref.id">
        <p v-if="item.occurred_at || item.source_activity" class="trace-origin">
          <time v-if="item.occurred_at" :datetime="item.occurred_at">{{
            listTime.format(new Date(item.occurred_at))
          }}</time>
          <span v-if="item.occurred_at && item.source_activity" aria-hidden="true"> · </span>
          {{ item.source_activity ? sourceLabels[item.source_activity] : '' }}
        </p>
        <article>
          <button
            type="button"
            :data-evidence="item.evidence_ref.id"
            @click="selectEvidence(item.evidence_ref.id)"
          >
            {{ aspects[item.aspect_code] ?? item.aspect_code }} · {{ evidenceState(item) }}
          </button>
          <p>{{ item.reason }}</p>
        </article>
      </div>
      <p v-if="!evidenceList.length && !traceLoading && !traceError">暂无相关证据。</p>
      <ElButton v-if="evidenceCursor" @click="readEvidenceList(evidenceCursor)">更多证据</ElButton>
    </div>
  </dialog>
</template>
<style scoped>
.trace-drawer {
  position: fixed;
  inset: var(--admin-topbar-height) 0 0 auto;
  margin: 0;
  width: min(548px, 100%);
  height: calc(100dvh - var(--admin-topbar-height));
  max-width: 100%;
  max-height: none;
  overflow: auto;
  padding: 17px 19px 32px;
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-primary);
  line-height: 1.55;
  font-size: 15px;
  overscroll-behavior: contain;
}
.trace-drawer::backdrop {
  background: linear-gradient(
    to bottom,
    transparent var(--admin-topbar-height),
    rgb(40 58 76 / 14%) var(--admin-topbar-height)
  );
}
header {
  border-bottom: 1px solid var(--el-border-color);
  padding-bottom: 16px;
  margin-bottom: 22px;
}
header :deep(.el-button) {
  height: 32px;
  min-width: 84px;
  border-radius: 0;
  margin: 0;
}
header :deep(.is-link) {
  justify-content: flex-start;
}
h2 {
  font-size: 21px;
  line-height: 30px;
  margin: 13px 0 10px;
}
header p,
article p {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.trace-list {
  display: grid;
  gap: 16px;
}
.trace-origin {
  margin: 0 0 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
article,
.trace-change {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 13px;
  overflow-wrap: anywhere;
}
article {
  min-height: 100px;
}
article button {
  background: none;
  padding: 0;
  border: 0;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary);
  cursor: pointer;
  text-align: left;
}
article p {
  margin-top: 12px;
}
.trace-tag {
  display: inline-flex;
  padding: 4px 16px;
  font-size: 12px;
  border-radius: 4px;
  background: #fff0d6;
}
.trace-tag[data-verdict='positive'] {
  background: var(--admin-success-bg);
  color: var(--admin-success-text);
}
h3 {
  font-size: 18px;
  margin: 18px 0 10px;
}
h3 + p {
  margin: 0;
}
.trace-change {
  margin: 35px 0 27px;
  padding: 18px 14px;
  font-size: 14px;
  font-weight: 600;
}
h4 {
  font-size: 15px;
  margin: 0 0 16px;
}
.source-actions {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
details {
  margin-top: 15px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
