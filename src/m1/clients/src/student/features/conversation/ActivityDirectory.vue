<script setup lang="ts">
import { ChevronRight } from '@lucide/vue';
import { computed } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { activityClock, activityDay, activityLabels } from './activityLabels';

type Activity = components['schemas']['ActivityView'];
type Page = components['schemas']['ActivityPage'];
type Query = { parent?: string; cursor?: string };

const props = defineProps<{
  page?: Page;
  branches: Record<string, Page>;
  expanded: Record<string, boolean>;
  canResume: boolean;
  currentId?: string;
  historyId?: string;
  answerParentId?: string;
  groupByDay?: boolean;
}>();
defineEmits<{
  locate: [activity: Activity];
  toggle: [id: string];
  more: [query: Query];
  resume: [activity: Activity];
}>();

const groups = computed(() => {
  const items = props.page?.items ?? [];
  if (!props.groupByDay) return [{ label: '', items }];
  const grouped = new Map<string, Activity[]>();
  for (const item of items) {
    const label = activityDay(item.started_at);
    const entries = grouped.get(label) ?? [];
    entries.push(item);
    grouped.set(label, entries);
  }
  return [...grouped].map(([label, entries]) => ({ label, items: entries }));
});
const status: Record<Activity['run_state'], string> = {
  active: '进行中',
  waiting_child: '子活动进行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
  blocked: '暂时无法继续',
};
</script>

<template>
  <div v-for="group in groups" :key="group.label" class="activity-group">
    <h4 v-if="group.label">{{ group.label }}</h4>
    <ul class="activities">
      <li v-for="activity in group.items" :key="activity.activity_ref.activity_id">
        <div
          class="activity"
          :class="{
            current: currentId === activity.activity_ref.activity_id,
            highlighted: historyId
              ? historyId === activity.activity_ref.activity_id
              : currentId === activity.activity_ref.activity_id,
            branch: activity.has_children,
          }"
        >
          <button
            class="activity-name"
            type="button"
            :aria-current="currentId === activity.activity_ref.activity_id ? 'true' : undefined"
            @click="$emit('locate', activity)"
          >
            {{ activity.name }}
          </button>
          <div class="metadata">
            <span>{{ activityLabels[activity.type] }} ·</span>
            <time :datetime="activity.started_at">{{
              activityClock.format(new Date(activity.started_at))
            }}</time>
            <span class="activity-status" :class="activity.run_state">
              {{
                currentId === activity.activity_ref.activity_id
                  ? '当前'
                  : answerParentId === activity.activity_ref.activity_id
                    ? '答疑中'
                    : status[activity.run_state]
              }}
            </span>
          </div>
          <div class="activity-actions">
            <button
              v-if="activity.has_children"
              class="tree-toggle"
              type="button"
              :aria-label="
                (expanded[activity.activity_ref.activity_id] ? '收起' : '展开') + activity.name
              "
              :aria-expanded="!!expanded[activity.activity_ref.activity_id]"
              @click="$emit('toggle', activity.activity_ref.activity_id)"
            >
              <ChevronRight
                :size="16"
                :class="{ turned: expanded[activity.activity_ref.activity_id] }"
                aria-hidden="true"
              />
            </button>
            <button
              v-if="activity.run_state === 'paused' && canResume"
              type="button"
              @click="$emit('resume', activity)"
            >
              继续活动
            </button>
          </div>
        </div>
        <template v-if="expanded[activity.activity_ref.activity_id]">
          <ActivityDirectory
            v-if="branches[activity.activity_ref.activity_id]"
            :page="branches[activity.activity_ref.activity_id]"
            :branches="branches"
            :expanded="expanded"
            :can-resume="canResume"
            :current-id="currentId"
            :history-id="historyId"
            :answer-parent-id="answerParentId"
            @locate="$emit('locate', $event)"
            @toggle="$emit('toggle', $event)"
            @resume="$emit('resume', $event)"
            @more="$emit('more', $event)"
          />
          <button
            v-if="branches[activity.activity_ref.activity_id]?.next_cursor"
            type="button"
            @click="
              $emit('more', {
                parent: activity.activity_ref.activity_id,
                cursor: branches[activity.activity_ref.activity_id]?.next_cursor ?? undefined,
              })
            "
          >
            更多子活动
          </button>
        </template>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.activities {
  list-style: none;
  padding: 0;
  margin: 0;
}
.activity-group + .activity-group {
  margin-top: 1.25rem;
  padding-top: 1.125rem;
  border-top: 1px solid var(--border);
}
.activity-group h4 {
  margin: 0 0 0.5rem 0.25rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta);
  font-weight: 600;
}
.activities .activities {
  margin-inline-start: 0.25rem;
  padding-inline-start: 0.375rem;
}
.activity {
  position: relative;
  min-height: 4rem;
  margin-block: 0.25rem;
  padding: 0.625rem;
  border-radius: 0.5rem;
}
.activity.highlighted {
  background: var(--accent);
}
.activity.current::before {
  position: absolute;
  inset: 0.75rem auto 0.75rem 0.375rem;
  width: 2px;
  background: var(--primary);
  content: '';
}
.activity-name {
  display: block;
  width: 100%;
  padding-inline-start: 0.5rem;
  color: var(--foreground);
  font: var(--study-font-ui);
  font-weight: 600;
}
.activity.branch .activity-name {
  padding-inline-end: 1.25rem;
}
.activity-status {
  min-width: 3.75rem;
  margin-inline-start: auto;
  border-radius: 0.25rem;
  padding: 0.125rem 0.625rem;
  background: var(--muted);
  text-align: center;
  white-space: nowrap;
}
.activity-status.active,
.activity-status.waiting_child {
  background: #dfe8d3;
  color: var(--secondary-foreground);
}
.activity-status.paused {
  background: #f4e8d1;
  color: #714d22;
}
.metadata {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding-inline-start: 0.5rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta);
}
.metadata time {
  font-variant-numeric: tabular-nums;
}
.activity-actions {
  display: flex;
  gap: 0.375rem;
  padding-inline-start: 0.5rem;
  font: var(--study-font-meta);
}
.tree-toggle svg {
  display: block;
}
.activity-actions .tree-toggle {
  position: absolute;
  inset: 0.625rem 0.25rem auto auto;
}
.tree-toggle .turned {
  rotate: 90deg;
}
button {
  border: 0;
  padding: 0.15rem 0.25rem;
  background: transparent;
  color: var(--color-accent);
  cursor: pointer;
  font: inherit;
  text-align: start;
  overflow-wrap: anywhere;
}
button:not(:disabled):hover {
  text-decoration: underline;
}
button:disabled {
  color: var(--color-muted);
  cursor: not-allowed;
}
</style>
