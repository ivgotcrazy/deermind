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
const names: Record<string, string> = {
  LearningSpaceCreated: '建立学习空间',
  LearningSpaceEntered: '进入学习空间',
  LearningSpaceAdoptionChanged: '更新课程采用',
  LearningTargetApplied: '应用目标依据',
  GoalEvaluationCompleted: '完成目标计算',
};
const aspects: Record<string, string> = {
  independent: '独立',
  understanding: '理解',
  transfer: '迁移',
  retention: '保持',
};
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
              <th>事件引用</th>
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
              <td>{{ event.event_id }}</td>
            </tr>
          </tbody>
        </table>
        <button v-if="nextEvent" type="button" @click="loadEvents(nextEvent)">更多事件</button>
      </template>
    </template>
  </section>
</template>
