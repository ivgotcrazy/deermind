<script setup lang="ts">
import { computed } from 'vue';
import type { Span } from '../types';

const props = defineProps<{
  spans: Span[];
  totalDuration: number;
  selectedSpanId: string | null;
}>();

const emit = defineEmits<{ select: [spanId: string] }>();

const statusColor: Record<string, string> = {
  success: '#2d8a5e',
  failed: '#b85c3c',
  partial: '#c9942a',
  skipped: '#9aaab8',
  running: '#4a6fa5',
};

const statusBg: Record<string, string> = {
  success: 'rgba(45,138,94,0.15)',
  failed: 'rgba(184,92,60,0.15)',
  partial: 'rgba(201,148,42,0.15)',
  skipped: 'rgba(154,170,184,0.1)',
  running: 'rgba(74,111,165,0.15)',
};

const flatSpans = computed(() => {
  const result: (Span & { depth: number })[] = [];
  function flatten(spans: Span[], depth: number) {
    for (const span of spans) {
      result.push({ ...span, depth });
      if (span.children && span.children.length > 0) {
        flatten(span.children, depth + 1);
      }
    }
  }
  flatten(props.spans, 0);
  return result;
});

function barWidth(duration: number): number {
  return Math.max((duration / props.totalDuration) * 100, 0.5);
}

function barLeft(startTime: number): number {
  return (startTime / props.totalDuration) * 100;
}

function formatTime(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

const typeIcon: Record<string, string> = {
  'turn.start': '▶',
  'turn.end': '■',
  'observation.generate': '🧠',
  'observation.validate': '✓',
  'observation.commit': '📌',
  'policy.evaluate': '⚖️',
  'action.execute': '▶️',
  'evidence.interpret': '🔍',
  'belief.infer': '📊',
  'llm.invoke': '🤖',
};
</script>

<template>
  <div class="waterfall">
    <div class="waterfall-header">
      <span class="col-name">操作</span>
      <span class="col-bar">时间线 (总 {{ formatTime(totalDuration) }})</span>
      <span class="col-duration">耗时</span>
    </div>
    <div class="waterfall-body">
      <div
        v-for="span in flatSpans"
        :key="span.spanId"
        class="waterfall-row"
        :class="{ selected: selectedSpanId === span.spanId, child: span.depth > 0 }"
        :style="{ paddingLeft: (span.depth * 20 + 8) + 'px' }"
        @click="emit('select', span.spanId)"
      >
        <span class="row-name">
          <span class="type-icon">{{ typeIcon[span.type] || '•' }}</span>
          <span class="name-text">{{ span.label }}</span>
        </span>
        <div class="row-bar-container">
          <div
            class="row-bar"
            :style="{
              left: barLeft(span.startTime) + '%',
              width: barWidth(span.duration) + '%',
              background: statusBg[span.status],
              borderLeft: '3px solid ' + statusColor[span.status],
            }"
          ></div>
        </div>
        <span class="row-duration" :style="{ color: statusColor[span.status] }">
          {{ span.duration > 0 ? formatTime(span.duration) : '—' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.waterfall {
  font-size: 12px;
  user-select: none;
}
.waterfall-header {
  display: flex;
  padding: 8px 12px;
  background: #f0f4f7;
  border-bottom: 1px solid #e1e8ed;
  font-weight: 600;
  color: #5a6b7a;
  font-size: 11px;
}
.col-name { width: 200px; flex-shrink: 0; }
.col-bar { flex: 1; }
.col-duration { width: 70px; text-align: right; flex-shrink: 0; }
.waterfall-body { max-height: 500px; overflow-y: auto; }
.waterfall-row {
  display: flex;
  align-items: center;
  padding: 6px 12px 6px 8px;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fa;
  transition: background 0.1s;
}
.waterfall-row:hover { background: #f5f9f7; }
.waterfall-row.selected { background: #e8f5ee; }
.waterfall-row.child { font-size: 11px; }
.row-name {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.type-icon { font-size: 12px; width: 16px; text-align: center; flex-shrink: 0; }
.name-text { overflow: hidden; text-overflow: ellipsis; }
.row-bar-container {
  flex: 1;
  height: 20px;
  position: relative;
  background: #fafbfc;
  border-radius: 3px;
  margin: 0 10px;
}
.row-bar {
  position: absolute;
  top: 2px;
  height: 16px;
  border-radius: 2px;
  min-width: 2px;
}
.row-duration {
  width: 70px;
  text-align: right;
  flex-shrink: 0;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
</style>
