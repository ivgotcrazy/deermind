<script setup lang="ts">
import type { SemanticEvent } from '../types';

defineProps<{ events: SemanticEvent[] }>();
const emit = defineEmits<{ selectSpan: [spanId: string] }>();

const statusConfig: Record<string, { icon: string; color: string; bg: string }> = {
  committed: { icon: '✓', color: '#2d8a5e', bg: '#e8f5ee' },
  rejected: { icon: '✗', color: '#b85c3c', bg: '#fdf0ed' },
  updated: { icon: '↻', color: '#4a6fa5', bg: '#e8f0f8' },
  selected: { icon: '★', color: '#c9942a', bg: '#fef5e0' },
};

const typeLabel: Record<string, string> = {
  observation: 'Observation',
  policy: 'Policy',
  belief: 'Belief',
};
</script>

<template>
  <div class="semantic-timeline">
    <h5>语义对象时间线</h5>
    <div class="timeline">
      <div
        v-for="(event, i) in events"
        :key="event.id"
        class="timeline-item"
        @click="emit('selectSpan', event.spanId)"
      >
        <div class="timeline-dot" :style="{ background: statusConfig[event.status].color }">
          {{ statusConfig[event.status].icon }}
        </div>
        <div v-if="i < events.length - 1" class="timeline-line"></div>
        <div class="timeline-content" :style="{ borderLeftColor: statusConfig[event.status].color }">
          <div class="timeline-header">
            <span class="event-type">{{ typeLabel[event.type] }}</span>
            <span class="event-status" :style="{ color: statusConfig[event.status].color, background: statusConfig[event.status].bg }">
              {{ event.status }}
            </span>
          </div>
          <p class="event-label">{{ event.label }}</p>
          <p class="event-detail">{{ event.detail }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.semantic-timeline { padding: 12px 16px; background: #fafbfc; border-top: 1px solid #e1e8ed; }
.semantic-timeline h5 { margin: 0 0 12px 0; font-size: 12px; color: #5a6b7a; font-weight: 600; }
.timeline { position: relative; }
.timeline-item { position: relative; padding-left: 32px; margin-bottom: 12px; cursor: pointer; }
.timeline-item:last-child { margin-bottom: 0; }
.timeline-dot {
  position: absolute;
  left: 0;
  top: 2px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: white;
  z-index: 1;
}
.timeline-line {
  position: absolute;
  left: 10px;
  top: 24px;
  width: 2px;
  height: calc(100% + 4px);
  background: #e1e8ed;
}
.timeline-content {
  background: white;
  border: 1px solid #e1e8ed;
  border-left: 3px solid #ccc;
  border-radius: 6px;
  padding: 8px 12px;
  transition: box-shadow 0.15s;
}
.timeline-content:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.timeline-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.event-type { font-size: 10px; font-weight: 600; color: #8a99a8; text-transform: uppercase; }
.event-status { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; }
.event-label { margin: 0 0 2px 0; font-size: 12px; font-weight: 600; color: #2c3e50; }
.event-detail { margin: 0; font-size: 11px; color: #6a7a8a; }
</style>
