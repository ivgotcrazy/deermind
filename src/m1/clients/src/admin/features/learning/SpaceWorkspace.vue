<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElButton, ElInput } from 'element-plus';
import EvidenceDrawer from './EvidenceDrawer.vue';
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
const drawer = ref<InstanceType<typeof EvidenceDrawer>>();
const traceTitle = ref('');
const evidenceSubjects = computed(() => {
  const result: Record<string, string> = {};
  for (const item of goal.value?.current?.result.items ?? []) {
    for (const method of item.methods) {
      for (const aspect of method.aspects) {
        const name = methodLabels.value[methodKey(method.method_ref)];
        for (const evidence of aspect.evidence_refs) {
          result[evidence.id] = [aspects[aspect.aspect_code] ?? aspect.aspect_code, name]
            .filter(Boolean)
            .join(' · ');
        }
      }
    }
  }
  return result;
});
function openTrace(
  selection: { result_id: string; item_id: string } | { event_id: string },
  title: string,
) {
  traceTitle.value = title;
  drawer.value?.openTrace(selection);
}
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
  independent: '独立完成',
  understanding: '理解',
  transfer: '迁移',
  retention: '保持',
};
function time(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
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
  <section aria-label="学习空间" class="space-workspace">
    <h1 v-if="!selected" class="admin-page-title">学习空间</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="!selected">
      <form class="admin-list-toolbar" @submit.prevent="list()">
        <label for="student-search">学生姓名</label>
        <ElInput id="student-search" v-model="search" placeholder="输入学生姓名" clearable />
        <ElButton type="primary" native-type="submit">搜索</ElButton>
      </form>
      <p v-if="spaces && !spaces.length">没有符合条件的学习空间。</p>
      <table v-else-if="spaces" class="admin-data-table">
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
            <td>
              {{ space.target_title }} · 课程 v{{ space.application_version }} · 目标 v{{
                space.target_revision
              }}
            </td>
          </tr>
        </tbody>
      </table>
      <ElButton v-if="next" @click="list(next)">更多空间</ElButton>
    </template>
    <template v-else>
      <header class="space-heading">
        <p class="space-crumb">
          <ElButton
            link
            aria-label="返回空间列表"
            @click="
              selected = undefined;
              goal = undefined;
              events = undefined;
            "
            >学习空间</ElButton
          >
          / {{ selected.student_name }}
        </p>
        <h1 class="admin-page-title">{{ selected.target_title }}</h1>
        <p>{{ selected.student_name }} · {{ selected.textbook_title }}</p>
        <div class="space-versions">
          <span>课程 v{{ selected.application_version }}</span
          ><span>目标 v{{ selected.target_revision }}</span>
        </div>
      </header>
      <nav aria-label="空间详情" class="space-tabs">
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
        <section class="result-overview" aria-label="当前目标结果">
          <div>
            <p>当前目标结果</p>
            <strong role="status">{{
              goal.current ? state(goal.current.result) : '待计算'
            }}</strong>
          </div>
          <div class="evaluation-status">
            <span
              class="status-badge"
              :data-kind="
                !goal.pending && !goal.evaluation_processing && goal.current ? 'met' : 'pending'
              "
              >{{
                goal.evaluation_processing === 'failed'
                  ? '本次评价失败'
                  : goal.pending || goal.evaluation_processing === 'pending' || !goal.current
                    ? '等待评价'
                    : '本次评价已完成'
              }}</span
            >
            <small v-if="goal.current"
              >已沿用该空间创建时选用的要求 · {{ time(goal.current.created_at) }}</small
            >
            <small v-if="goal.evaluation_processing">当前保留上一次结果。</small>
            <ElButton
              v-if="goal.pending || goal.evaluation_processing || !goal.current"
              link
              @click="show('goal')"
              >刷新结果</ElButton
            >
          </div>
        </section>
        <template v-if="goal.current">
          <article v-for="item in goal.current.result.items" :key="item.item_id" class="goal-card">
            <header>
              <h2>
                {{
                  adoption?.snapshot.items.find((entry) => entry.item_id === item.item_id)?.title ??
                  goal.target_title
                }}
              </h2>
              <ElButton
                @click="
                  openTrace(
                    { result_id: goal.current.goal_evaluation_id, item_id: item.item_id },
                    adoption?.snapshot.items.find((entry) => entry.item_id === item.item_id)
                      ?.title ?? goal.target_title,
                  )
                "
                >查看评价证据</ElButton
              >
            </header>
            <section
              v-for="(method, index) in item.methods"
              :key="methodKey(method.method_ref)"
              class="goal-method"
            >
              <p>{{ methodLabels[methodKey(method.method_ref)] ?? '方法 ' + (index + 1) }}</p>
              <div v-for="aspect in method.aspects" :key="aspect.aspect_code" class="aspect-row">
                <strong>{{ aspects[aspect.aspect_code] ?? aspect.aspect_code }}</strong>
                <span class="status-badge" :data-kind="aspect.attainment">{{ state(aspect) }}</span>
                <span>{{ aspect.evidence_refs.length }} 条关联证据</span>
              </div>
            </section>
            <p v-if="!item.methods.length">{{ state(item) }}</p>
          </article>
        </template>
      </template>
      <template v-else-if="tab === 'events'">
        <div class="admin-list-toolbar">
          <label
            >事件类型
            <select v-model="eventType" @change="loadEvents()">
              <option value="">全部</option>
              <option v-for="(label, key) in names" :key="key" :value="key">{{ label }}</option>
            </select></label
          >
        </div>
        <p v-if="events && !events.length">没有符合条件的空间事件。</p>
        <table v-else-if="events" class="admin-data-table">
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
                <button
                  type="button"
                  @click="
                    openTrace(
                      { event_id: event.event_id },
                      names[event.event_type] ?? event.event_type,
                    )
                  "
                >
                  查看相关证据
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <ElButton v-if="nextEvent" @click="loadEvents(nextEvent)">更多事件</ElButton>
      </template>
    </template>
    <EvidenceDrawer
      v-if="selected"
      ref="drawer"
      :key="selected.space_id"
      :session="session"
      :space-id="selected.space_id"
      :subject="traceTitle"
      :evidence-subjects="evidenceSubjects"
    />
  </section>
</template>
<style scoped>
.space-workspace {
  font-size: 14px;
  line-height: 1.55;
  color: var(--el-text-color-primary);
}
.space-workspace :deep(.adopted-content) {
  background: white;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 18px;
}
.space-workspace :deep(.adopted-content nav) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.space-workspace :deep(.adopted-content button) {
  border: 1px solid var(--el-border-color);
  background: white;
  color: var(--el-text-color-regular);
  padding: 8px 14px;
  cursor: pointer;
  font: inherit;
}
.space-workspace :deep(.adopted-content button[aria-pressed='true']) {
  color: var(--el-color-primary);
  background: var(--admin-selected);
}
.space-workspace > .el-button {
  margin-top: 16px;
}
.space-heading p {
  margin: 6px 0 11px;
  color: var(--el-text-color-secondary);
}
.space-heading .space-crumb {
  margin: 0 0 12px;
  font-size: 13px;
}
.space-crumb :deep(.el-button) {
  color: inherit;
  font-size: inherit;
}
.space-versions {
  display: flex;
  gap: 10px;
}
.space-versions span,
.status-badge {
  display: inline-block;
  justify-self: start;
  text-align: center;
  font-size: 12px;
  border-radius: 4px;
  line-height: 24px;
  padding: 0 14px;
  background: var(--el-fill-color-light);
}
.space-versions span:first-child {
  color: var(--el-color-primary);
  background: var(--admin-selected);
}
.space-tabs {
  display: flex;
  margin: 26px 0 22px;
  background: white;
  border-bottom: 1px solid var(--el-border-color);
}
.space-tabs button {
  height: 42px;
  padding: 0 14px;
  margin-right: 25px;
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  font: inherit;
  color: var(--el-text-color-regular);
  cursor: pointer;
}
.space-tabs button[aria-pressed='true'] {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
  font-weight: 600;
}
.result-overview,
.goal-card {
  border: 1px solid var(--el-border-color);
  background: white;
  border-radius: 4px;
  padding: 14px 16px;
}
.result-overview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-height: 96px;
}
.result-overview p,
.goal-method p {
  color: var(--el-text-color-secondary);
  margin: 0 0 7px;
}
.result-overview strong {
  font-size: 22px;
}
.evaluation-status {
  display: grid;
  justify-items: end;
  gap: 12px;
  text-align: right;
}
.evaluation-status .status-badge {
  justify-self: end;
}
.evaluation-status small {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.status-badge {
  background: #fff0d6;
  color: #71491c;
}
.status-badge[data-kind='met'] {
  background: var(--admin-success-bg);
  color: var(--admin-success-text);
}
.goal-card {
  margin-top: 26px;
  min-height: 170px;
}
.goal-card header {
  display: flex;
  gap: 16px;
  align-items: start;
  justify-content: space-between;
  position: relative;
  padding-right: 135px;
}
.goal-card h2 {
  margin: 0;
  font-size: 17px;
  line-height: 24px;
}
.goal-card header :deep(.el-button) {
  position: absolute;
  right: 4px;
  height: 40px;
  border-radius: 0;
}
.goal-method p {
  margin: 8px 135px 22px 0;
}
.aspect-row {
  display: grid;
  grid-template-columns: minmax(130px, 24%) minmax(100px, 19%) 1fr;
  align-items: center;
  gap: 0;
  min-height: 60px;
  border-top: 1px solid var(--el-border-color);
  font-size: 13px;
}
.aspect-row > span:last-child {
  color: var(--el-text-color-secondary);
}
@media (max-width: 700px) {
  .result-overview {
    align-items: start;
    flex-direction: column;
  }
  .aspect-row {
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .goal-card header {
    padding-right: 0;
    flex-wrap: wrap;
  }
  .goal-card header :deep(.el-button) {
    position: static;
  }
  .goal-method p {
    margin-right: 0;
  }
}
</style>
