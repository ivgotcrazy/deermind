<script setup lang="ts">
import { ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get } from '../../../shared/api/http';
import AdoptedChapter from '../../../shared/content/AdoptedChapter.vue';
import type { DomainSession } from '../domain/api';
import { methodKey, methodNames } from './methodNames';

type Schema = components['schemas'];
type EventSummary = {
  event_id: string;
  event_type: string;
  scope_event_seq: number;
  recorded_at: string;
};
const props = defineProps<{ session: DomainSession }>();
const spaces = ref<Schema['SpaceRow'][]>();
const search = ref('');
const next = ref<string>();
const selected = ref<Schema['SpaceRow']>();
const adoption = ref<Schema['AdoptionView']>();
const goal = ref<Schema['SpaceGoalView']>();
const methodLabels = ref<Record<string, string>>({});
const events = ref<EventSummary[]>();
const nextEvent = ref<number>();
const upper = ref<number>();
const error = ref('');
const tab = ref<'textbook' | 'goal' | 'events'>('textbook');
const eventType = ref('');
const trace = ref<HTMLDialogElement>();
const evidenceList = ref<Schema['EvidenceSummary'][]>([]);
const evidence = ref<Schema['EvidenceView']>();
const source = ref<Schema['SourceExcerpt']>();
const evidenceCursor = ref<string>();
const traceError = ref('');
const traceLoading = ref(false);
const traceSelection = ref<{ result_id: string; item_id: string } | { event_id: string }>();
let traceRequest = 0;
const names: Record<string, string> = {
  LearningSpaceCreated: '建立学习空间',
  LearningSpaceEntered: '进入学习空间',
  LearningSpaceAdoptionChanged: '更新课程采用',
  LearningTargetApplied: '应用目标依据',
  GoalEvaluationCompleted: '完成目标计算',
  BeliefEvaluationCompleted: '完成掌握状态计算',
  AnswerSubmitted: '提交作答',
  TeachingOpportunityClosed: '结束教学机会',
};
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
  const scope_id = selected.value?.space_id;
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
  const scope_id = selected.value?.space_id;
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
const labels = { textbook: '教材', goal: '学习目标', events: '空间事件' } as const;
function state(entry: { readiness: string; attainment?: string | null }) {
  if (entry.readiness === 'unprepared') return '准备不足';
  if (entry.attainment === 'met') return '已达标';
  if (entry.attainment === 'needs_strengthening') return '需加强';
  return '待确认';
}
async function list(cursor?: string) {
  error.value = '';
  try {
    const data = await get('/api/m1/learning-spaces', {
      session: props.session,
      query: { student_name: search.value, cursor },
    });
    spaces.value = cursor ? [...(spaces.value ?? []), ...data.items] : data.items;
    next.value = data.next_cursor ?? undefined;
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}
void list();

async function enter(space: Schema['SpaceRow']) {
  selected.value = space;
  adoption.value = undefined;
  goal.value = undefined;
  methodLabels.value = {};
  events.value = undefined;
  eventType.value = '';
  await show('textbook');
}
async function show(selection: typeof tab.value) {
  const space_id = selected.value?.space_id;
  if (!space_id) return;
  tab.value = selection;
  error.value = '';
  try {
    const options = { session: props.session, params: { space_id } };
    if (selection === 'textbook') {
      const data = await get('/api/m1/learning-spaces/{space_id}', options);
      if (selected.value?.space_id === space_id) adoption.value = data;
    }
    if (selection === 'goal') {
      const data = await get('/api/m1/learning-spaces/{space_id}/goal', options);
      const labels = await methodNames(
        props.session,
        data.domain_id,
        data.current?.result.items.flatMap((item) =>
          item.methods.map((method) => method.method_ref),
        ) ?? [],
      );
      if (selected.value?.space_id === space_id) {
        goal.value = data;
        methodLabels.value = labels;
      }
    }
    if (selection === 'events') await loadEvents();
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}

async function loadEvents(after?: number) {
  const space_id = selected.value?.space_id;
  if (!space_id) return;
  error.value = '';
  if (!after) events.value = undefined;
  try {
    const data = await get('/api/m1/learning-spaces/{space_id}/events', {
      session: props.session,
      params: { space_id },
      query: {
        event_type: eventType.value ? [eventType.value] : undefined,
        after_seq: after,
        upper_seq: after ? upper.value : undefined,
      },
    });
    if (selected.value?.space_id !== space_id) return;
    const items = Array.isArray(data.items) ? (data.items as EventSummary[]) : [];
    events.value = after ? [...(events.value ?? []), ...items] : items;
    upper.value = typeof data.upper_seq === 'number' ? data.upper_seq : undefined;
    nextEvent.value = typeof data.next_after_seq === 'number' ? data.next_after_seq : undefined;
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}
</script>

<template>
  <section aria-label="学习空间">
    <h2>学习空间</h2>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="!selected">
      <form @submit.prevent="list()">
        <label>学生姓名 <input v-model="search" /></label>
        <button type="submit">搜索</button>
      </form>
      <p v-if="spaces && !spaces.length">没有符合条件的学习空间。</p>
      <table v-else-if="spaces">
        <thead>
          <tr>
            <th>学生</th>
            <th>教材</th>
            <th>学习目标</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="space in spaces" :key="space.space_id">
            <td>
              <button type="button" @click="enter(space)">{{ space.student_name }}</button>
            </td>
            <td>{{ space.textbook_title }}</td>
            <td>{{ space.target_title }}</td>
          </tr>
        </tbody>
      </table>
      <button v-if="next" type="button" @click="list(next)">更多空间</button>
    </template>
    <template v-else>
      <button
        type="button"
        @click="
          selected = undefined;
          goal = undefined;
          events = undefined;
        "
      >
        返回空间列表
      </button>
      <h3>{{ selected.student_name }} · {{ selected.textbook_title }}</h3>
      <nav aria-label="空间详情">
        <button
          v-for="(label, key) in labels"
          :key="key"
          type="button"
          :aria-pressed="tab === key"
          @click="show(key)"
        >
          {{ label }}
        </button>
      </nav>
      <AdoptedChapter
        v-if="tab === 'textbook' && adoption"
        :session="session"
        :space="selected.space_id"
        :chapters="adoption.snapshot.chapters"
      />
      <template v-else-if="tab === 'goal' && goal">
        <h4>{{ goal.target_title }}</h4>
        <p v-if="goal.pending" role="status">该目标的计算尚未完成。</p>
        <p v-else-if="goal.evaluation_processing === 'pending'" role="status">
          新的评价正在处理，当前显示上一次结果。
        </p>
        <p v-else-if="goal.evaluation_processing === 'failed'" role="status">
          新的评价处理失败，当前保留上一次结果。
        </p>
        <template v-if="goal.current">
          <p role="status">{{ state(goal.current.result) }}</p>
          <article v-for="item in goal.current.result.items" :key="item.item_id">
            <h5>
              {{
                adoption?.snapshot.items.find((entry) => entry.item_id === item.item_id)?.title ??
                goal.target_title
              }}
            </h5>
            <p>{{ state(item) }}</p>
            <button
              type="button"
              @click="
                openTrace({ result_id: goal.current.goal_evaluation_id, item_id: item.item_id })
              "
            >
              查看评价证据
            </button>
            <section v-for="(method, index) in item.methods" :key="method.method_ref.object_id">
              <h6>{{ methodLabels[methodKey(method.method_ref)] ?? `方法 ${index + 1}` }}</h6>
              <ul>
                <li v-for="aspect in method.aspects" :key="aspect.aspect_code">
                  {{ aspects[aspect.aspect_code] ?? aspect.aspect_code }} · {{ state(aspect) }}
                </li>
              </ul>
            </section>
          </article>
        </template>
        <button type="button" @click="show('goal')">刷新结果</button>
      </template>
      <template v-else-if="tab === 'events'">
        <label
          >事件类型
          <select v-model="eventType" @change="loadEvents()">
            <option value="">全部</option>
            <option v-for="(label, key) in names" :key="key" :value="key">{{ label }}</option>
          </select></label
        >
        <p v-if="events && !events.length">没有符合条件的空间事件。</p>
        <table v-else-if="events">
          <thead>
            <tr>
              <th>序号</th>
              <th>事件</th>
              <th>发生时间</th>
              <th>证据</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in events" :key="event.event_id">
              <td>{{ event.scope_event_seq }}</td>
              <td>{{ names[event.event_type] ?? event.event_type }}</td>
              <td>
                {{
                  new Date(event.recorded_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
                }}
              </td>
              <td>
                <button type="button" @click="openTrace({ event_id: event.event_id })">
                  查看相关证据
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <button v-if="nextEvent" type="button" @click="loadEvents(nextEvent)">更多事件</button>
      </template>
    </template>
    <dialog
      ref="trace"
      class="evidence-dialog"
      aria-labelledby="evidence-title"
      @close="resetTrace"
    >
      <header>
        <h3 id="evidence-title">评价证据</h3>
        <form method="dialog"><button type="submit">关闭</button></form>
      </header>
      <p v-if="traceLoading" role="status">正在读取评价依据。</p>
      <p v-if="traceError" role="alert">{{ traceError }}</p>
      <template v-if="evidence">
        <button type="button" @click="backToEvidenceList">返回证据列表</button>
        <h4>
          {{ aspects[evidence.aspect_code] ?? evidence.aspect_code }} ·
          {{ evidenceState(evidence) }}
        </h4>
        <p>{{ evidence.reason }}</p>
        <p v-if="evidence.belief_change?.update_kind === 'observation'">
          观测概率 {{ percent(evidence.belief_change.p_obs_before) }} →
          {{ percent(evidence.belief_change.p_obs_after) }}
        </p>
        <p v-else-if="evidence.belief_change?.update_kind === 'learning_transition'">
          教学后的估计 {{ percent(evidence.belief_change.p_current_before) }} →
          {{ percent(evidence.belief_change.p_current_after) }}
        </p>
        <p v-else>本条证据未更新概率。</p>
        <ul v-if="evidence.source_spans.length">
          <li v-for="span in evidence.source_spans" :key="span.quote">{{ span.quote }}</li>
        </ul>
        <h4>来源事件</h4>
        <ul>
          <li
            v-for="event in [...new Set(evidence.source_refs.map((ref) => ref.event_id))]"
            :key="event"
          >
            <button type="button" @click="readEvidence(evidence.evidence_id, event)">
              查看来源事实
            </button>
            <small>{{ event }}</small>
          </li>
        </ul>
        <section v-if="source" aria-label="来源事实">
          <h4>来源事实</h4>
          <pre v-for="(part, index) in source.content" :key="index">{{
            typeof part === 'string' ? part : JSON.stringify(part, null, 2)
          }}</pre>
        </section>
      </template>
      <template v-else>
        <ul v-if="evidenceList.length">
          <li v-for="item in evidenceList" :key="item.evidence_ref.id">
            <button type="button" @click="readEvidence(item.evidence_ref.id)">
              {{ aspects[item.aspect_code] ?? item.aspect_code }} · {{ evidenceState(item) }}
            </button>
            <p>{{ item.reason }}</p>
          </li>
        </ul>
        <p v-else-if="!traceLoading && !traceError">暂无相关证据。</p>
        <button v-if="evidenceCursor" type="button" @click="readEvidenceList(evidenceCursor)">
          更多证据
        </button>
      </template>
    </dialog>
  </section>
</template>

<style scoped>
.evidence-dialog {
  width: min(42rem, calc(100% - 2rem));
  max-height: 85vh;
  padding: 1.5rem;
}
.evidence-dialog header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}
.evidence-dialog li {
  margin-block: 0.5rem;
}
.evidence-dialog small {
  display: block;
  overflow-wrap: anywhere;
}
.evidence-dialog pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
