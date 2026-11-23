<script setup lang="ts">
import type { components } from '../../../../../contracts/generated/http/schema';
import { activityLabels } from './activityLabels';

type Activity = components['schemas']['ActivityView'];
type Page = components['schemas']['ActivityPage'];
type Query = { parent?: string; cursor?: string };

defineProps<{ page?: Page; branches: Record<string, Page>; expanded: Record<string, boolean> }>();
defineEmits<{
  locate: [activity: Activity];
  toggle: [id: string];
  more: [query: Query];
  resume: [activity: Activity];
}>();

const time = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' });
</script>

<template>
  <ul class="activities">
    <li v-for="activity in page?.items" :key="activity.activity_ref.activity_id">
      <div class="activity">
        <div class="metadata">
          <time :datetime="activity.started_at">{{
            time.format(new Date(activity.started_at))
          }}</time>
          <span>{{ activityLabels[activity.type] }}</span>
        </div>
        <div class="activity-actions">
          <button type="button" @click="$emit('locate', activity)">{{ activity.name }}</button>
          <button
            v-if="activity.has_children"
            type="button"
            :aria-label="
              (expanded[activity.activity_ref.activity_id] ? '收起' : '展开') + activity.name
            "
            :aria-expanded="!!expanded[activity.activity_ref.activity_id]"
            @click="$emit('toggle', activity.activity_ref.activity_id)"
          >
            {{ expanded[activity.activity_ref.activity_id] ? '−' : '+' }}
          </button>
          <button
            v-if="activity.run_state === 'paused'"
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
</template>

<style scoped>
.activities {
  list-style: none;
  padding: 0;
  margin: 0;
}
.activities .activities {
  margin-left: 0.625rem;
  padding-left: 0.5rem;
  border-left: 1px solid var(--color-line);
}
.activity {
  padding-block: 0.5rem;
}
.metadata,
.activity-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}
.metadata {
  color: var(--color-muted);
  font-size: 0.76rem;
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
button:hover {
  text-decoration: underline;
}
</style>
