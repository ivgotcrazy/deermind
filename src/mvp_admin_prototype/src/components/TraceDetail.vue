<script setup lang="ts">
import { ref, computed } from 'vue';
import { detailedTrace } from '../data';
import type { Span } from '../types';
import WaterfallChart from './WaterfallChart.vue';
import SpanDetail from './SpanDetail.vue';
import SemanticTimeline from './SemanticTimeline.vue';

const props = defineProps<{ traceId: string }>();
const emit = defineEmits<{ back: [] }>();

const trace = detailedTrace;
const selectedSpanId = ref<string | null>('s5'); // 默认选中验证失败的 Span

const selectedSpan = computed((): Span | null => {
  if (!selectedSpanId.value) return null;
  function find(spans: Span[]): Span | null {
    for (const s of spans) {
      if (s.spanId === selectedSpanId.value) return s;
      if (s.children) {
        const found = find(s.children);
        if (found) return found;
      }
    }
    return null;
  }
  return find(trace.spans);
});

function handleSelectSpan(spanId: string) {
  selectedSpanId.value = spanId;
}

function copyTraceId() {
  navigator.clipboard.writeText(props.traceId);
}

const statusConfig: Record<string, { label: string; color: string }> = {
  normal: { label: '正常', color: '#2d8a5e' },
  partial: { label: '部分成功', color: '#c9942a' },
  error: { label: '异常', color: '#b85c3c' },
  idle: { label: '空转', color: '#8a99a8' },
};
</script>

<template>
  <div class="trace-detail">
    <!-- 顶部栏 -->
    <div class="detail-topbar">
      <button class="back-btn" @click="emit('back')">← 返回列表</button>
      <div class="trace-info">
        <span class="trace-id mono">{{ traceId }}</span>
        <span class="trace-student">{{ trace.studentName }}</span>
        <span class="trace-chapter">{{ trace.chapter }}</span>
        <span class="trace-time">{{ trace.startTime }}</span>
        <span class="trace-status" :style="{ color: statusConfig[trace.status].color }">
          {{ statusConfig[trace.status].label }}
        </span>
      </div>
      <div class="topbar-actions">
        <button class="action-btn" @click="copyTraceId">复制 ID</button>
        <button class="action-btn">导出 JSON</button>
        <button class="action-btn primary">重跑（换参数）</button>
      </div>
    </div>

    <!-- 学生输入 -->
    <div class="io-section input-section">
      <span class="io-label">学生输入</span>
      <p class="io-text">{{ trace.studentInput }}</p>
    </div>

    <!-- 核心区域：瀑布图 + 详情 -->
    <div class="main-area">
      <div class="waterfall-section">
        <div class="section-title">处理链路（瀑布图）</div>
        <WaterfallChart
          :spans="trace.spans"
          :total-duration="trace.duration"
          :selected-span-id="selectedSpanId"
          @select="handleSelectSpan"
        />
      </div>
      <div class="detail-section">
        <div class="section-title">Span 详情</div>
        <SpanDetail :span="selectedSpan" />
      </div>
    </div>

    <!-- 语义对象时间线 -->
    <SemanticTimeline :events="trace.semanticEvents" @select-span="handleSelectSpan" />

    <!-- 系统输出 -->
    <div class="io-section output-section">
      <span class="io-label">系统输出</span>
      <p class="io-text">{{ trace.systemOutput }}</p>
    </div>
  </div>
</template>

<style scoped>
.trace-detail { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.detail-topbar {
  display: flex; align-items: center; gap: 16px;
  padding: 12px 20px; background: white; border-bottom: 1px solid #e1e8ed; flex-shrink: 0;
}
.back-btn { background: none; border: none; color: #2d6a4f; font-size: 13px; cursor: pointer; font-family: inherit; font-weight: 500; padding: 4px 8px; border-radius: 4px; }
.back-btn:hover { background: #f0f7f3; }
.trace-info { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.trace-id { font-size: 12px; color: #5a6b7a; background: #f0f4f7; padding: 3px 8px; border-radius: 4px; }
.trace-student { font-size: 13px; font-weight: 600; color: #2c3e50; }
.trace-chapter { font-size: 12px; color: #5a6b7a; }
.trace-time { font-size: 12px; color: #8a99a8; }
.trace-status { font-size: 12px; font-weight: 600; }
.topbar-actions { display: flex; gap: 8px; flex-shrink: 0; }
.action-btn { background: white; border: 1px solid #d0d7de; color: #3a4a5a; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; }
.action-btn:hover { background: #f0f4f7; }
.action-btn.primary { background: #2d6a4f; color: white; border-color: #2d6a4f; }
.action-btn.primary:hover { background: #245440; }
.mono { font-family: Consolas, Monaco, monospace; }

.io-section { padding: 12px 20px; flex-shrink: 0; }
.input-section { background: #f0f7f3; border-bottom: 1px solid #d4e8dc; }
.output-section { background: #f5f7fa; border-top: 1px solid #e1e8ed; }
.io-label { font-size: 11px; font-weight: 600; color: #5a7a6a; text-transform: uppercase; margin-bottom: 4px; display: block; }
.output-section .io-label { color: #5a6b7a; }
.io-text { margin: 0; font-size: 14px; line-height: 1.6; color: #2c3e50; }

.main-area { flex: 1; display: flex; overflow: hidden; min-height: 0; }
.waterfall-section { flex: 1.2; display: flex; flex-direction: column; border-right: 1px solid #e1e8ed; background: white; min-width: 0; }
.detail-section { flex: 1; display: flex; flex-direction: column; background: #fafbfc; min-width: 0; }
.section-title { padding: 10px 16px; font-size: 12px; font-weight: 600; color: #5a6b7a; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; flex-shrink: 0; }
.waterfall-section :deep(.waterfall) { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.waterfall-section :deep(.waterfall-body) { flex: 1; overflow-y: auto; }
.detail-section :deep(.span-detail) { flex: 1; overflow-y: auto; }
</style>
