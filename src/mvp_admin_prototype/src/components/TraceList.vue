<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { traceList, learningSpaces } from '../data';
import type { Trace } from '../types';

const emit = defineEmits<{ goDetail: [traceId: string] }>();

const statusFilter = ref('all');
const studentFilter = ref('all');
const lsFilter = ref('all');
const timeRange = ref('today');

// 时间段选项
const timeRanges = [
  { value: 'today', label: '今天' },
  { value: '7days', label: '最近7天' },
  { value: '30days', label: '最近30天' },
  { value: 'all', label: '全部时间' },
];

// 学生列表
const students = [...new Set(traceList.map(t => t.studentName))];

// 当前学生下的 Learning Space
const currentStudentLS = computed(() => {
  if (studentFilter.value === 'all') return [];
  return learningSpaces.filter(ls => ls.studentName === studentFilter.value);
});

// 学生变化时重置 LS 筛选
watch(studentFilter, () => {
  lsFilter.value = 'all';
});

// 过滤后的 Trace
const filteredTraces = computed(() => {
  return traceList.filter(t => {
    if (statusFilter.value !== 'all' && t.status !== statusFilter.value) return false;
    if (studentFilter.value !== 'all' && t.studentName !== studentFilter.value) return false;
    if (lsFilter.value !== 'all' && t.lsId !== lsFilter.value) return false;
    // 时间段过滤（原型简化：所有数据都是今天的）
    return true;
  });
});

// 全局统计（基于过滤后的数据）
const stats = computed(() => {
  const list = filteredTraces.value;
  const total = list.length;
  const normal = list.filter(t => t.status === 'normal').length;
  const partial = list.filter(t => t.status === 'partial').length;
  const error = list.filter(t => t.status === 'error').length;
  const idle = list.filter(t => t.status === 'idle').length;
  const avgDuration = total > 0 ? (list.reduce((s, t) => s + t.duration, 0) / total / 1000).toFixed(1) : '0';
  const studentCount = new Set(list.map(t => t.studentName)).size;
  const lsCount = new Set(list.map(t => t.lsId)).size;
  const errorRate = total > 0 ? ((error / total) * 100).toFixed(0) : '0';
  return { total, normal, partial, error, idle, avgDuration, studentCount, lsCount, errorRate };
});

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  normal: { label: '正常', color: '#2d8a5e', bg: '#e8f5ee' },
  partial: { label: '部分', color: '#c9942a', bg: '#fef5e0' },
  error: { label: '异常', color: '#b85c3c', bg: '#fdf0ed' },
  idle: { label: '空转', color: '#8a99a8', bg: '#f0f4f7' },
};

function formatDuration(ms: number): string {
  return (ms / 1000).toFixed(1) + 's';
}
</script>

<template>
  <div class="trace-list">
    <div class="page-header">
      <h2>交互审查</h2>
      <button class="export-btn">导出 JSON</button>
    </div>

    <!-- 全局统计 -->
    <div class="stats-grid">
      <div class="stat-card primary">
        <span class="stat-label">交互总数</span>
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-sub">{{ stats.studentCount }}名学生 · {{ stats.lsCount }}个学习空间</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">正常</span>
        <span class="stat-value" style="color:#2d8a5e">{{ stats.normal }}</span>
        <span class="stat-sub">{{ stats.total > 0 ? ((stats.normal / stats.total) * 100).toFixed(0) : 0 }}%</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">部分成功</span>
        <span class="stat-value" style="color:#c9942a">{{ stats.partial }}</span>
        <span class="stat-sub">{{ stats.total > 0 ? ((stats.partial / stats.total) * 100).toFixed(0) : 0 }}%</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">异常</span>
        <span class="stat-value" style="color:#b85c3c">{{ stats.error }}</span>
        <span class="stat-sub">异常率 {{ stats.errorRate }}%</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">平均耗时</span>
        <span class="stat-value">{{ stats.avgDuration }}s</span>
        <span class="stat-sub">端到端处理</span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-group">
        <label class="filter-label">状态</label>
        <select v-model="statusFilter" class="filter-select">
          <option value="all">全部</option>
          <option value="normal">正常</option>
          <option value="partial">部分成功</option>
          <option value="error">异常</option>
          <option value="idle">空转</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">学生</label>
        <select v-model="studentFilter" class="filter-select">
          <option value="all">全部学生</option>
          <option v-for="s in students" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">学习空间</label>
        <select v-model="lsFilter" class="filter-select" :disabled="studentFilter === 'all'">
          <option value="all">全部学习空间</option>
          <option v-for="ls in currentStudentLS" :key="ls.id" :value="ls.id">
            {{ ls.subject }}·{{ ls.textbook }}{{ ls.grade }}
          </option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label">时间段</label>
        <select v-model="timeRange" class="filter-select">
          <option v-for="r in timeRanges" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </div>
    </div>

    <!-- 列表 -->
    <div class="trace-table">
      <div class="table-header">
        <span class="col-time">时间</span>
        <span class="col-student">学生</span>
        <span class="col-ls">学习空间</span>
        <span class="col-chapter">章节</span>
        <span class="col-summary">Trace 摘要</span>
        <span class="col-duration">耗时</span>
        <span class="col-status">状态</span>
        <span class="col-action">操作</span>
      </div>
      <div
        v-for="trace in filteredTraces"
        :key="trace.traceId"
        class="table-row"
        @click="emit('goDetail', trace.traceId)"
      >
        <span class="col-time mono">{{ trace.startTime.split(' ')[1] }}</span>
        <span class="col-student">{{ trace.studentName }}</span>
        <span class="col-ls">{{ trace.lsName }}</span>
        <span class="col-chapter">{{ trace.chapter }}</span>
        <span class="col-summary">{{ trace.summary }}</span>
        <span class="col-duration mono">{{ formatDuration(trace.duration) }}</span>
        <span class="col-status">
          <span class="status-tag" :style="{ color: statusConfig[trace.status].color, background: statusConfig[trace.status].bg }">
            {{ statusConfig[trace.status].label }}
          </span>
        </span>
        <span class="col-action"><button class="detail-btn">详情 →</button></span>
      </div>
    </div>

    <div class="pagination">
      <span>共 {{ filteredTraces.length }} 条</span>
      <div class="page-buttons">
        <button disabled>上一页</button>
        <button class="active">1</button>
        <button>2</button>
        <button>3</button>
        <button>下一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-list { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.export-btn { background: white; border: 1px solid #d0d7de; color: #3a4a5a; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.export-btn:hover { background: #f0f4f7; }

/* 全局统计 */
.stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; }
.stat-card.primary { border-left: 3px solid #2d6a4f; }
.stat-label { font-size: 11px; color: #8a99a8; }
.stat-value { font-size: 24px; font-weight: 700; color: #1a3a2e; line-height: 1.2; }
.stat-sub { font-size: 11px; color: #5a7a6a; }

/* 筛选栏 */
.filter-bar { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; align-items: flex-end; }
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-label { font-size: 11px; color: #8a99a8; font-weight: 500; }
.filter-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; min-width: 140px; }
.filter-select:disabled { background: #f5f7fa; color: #b0b8c0; cursor: not-allowed; }
.filter-select:focus { outline: none; border-color: #2d6a4f; }

/* 列表 */
.trace-table { flex: 1; background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; }
.table-header { display: flex; padding: 12px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 12px; font-weight: 600; color: #5a6b7a; flex-shrink: 0; }
.table-row { display: flex; padding: 12px 16px; border-bottom: 1px solid #f5f7fa; cursor: pointer; transition: background 0.1s; align-items: center; font-size: 13px; }
.table-row:hover { background: #f5f9f7; }
.col-time { width: 80px; flex-shrink: 0; }
.col-student { width: 70px; flex-shrink: 0; font-weight: 500; }
.col-ls { width: 140px; flex-shrink: 0; color: #4a6fa5; font-size: 12px; }
.col-chapter { width: 90px; flex-shrink: 0; color: #5a6b7a; }
.col-summary { flex: 1; color: #3a4a5a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 12px; }
.col-duration { width: 60px; flex-shrink: 0; color: #5a6b7a; font-variant-numeric: tabular-nums; }
.col-status { width: 70px; flex-shrink: 0; }
.col-action { width: 80px; flex-shrink: 0; text-align: right; }
.mono { font-family: Consolas, Monaco, monospace; font-size: 12px; }
.status-tag { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.detail-btn { background: none; border: none; color: #2d6a4f; font-size: 12px; cursor: pointer; font-family: inherit; font-weight: 500; }
.detail-btn:hover { text-decoration: underline; }
.pagination { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; font-size: 12px; color: #8a99a8; flex-shrink: 0; }
.page-buttons { display: flex; gap: 4px; }
.page-buttons button { padding: 4px 10px; border: 1px solid #d0d7de; background: white; border-radius: 4px; font-size: 12px; cursor: pointer; font-family: inherit; }
.page-buttons button.active { background: #2d6a4f; color: white; border-color: #2d6a4f; }
.page-buttons button:disabled { opacity: 0.4; cursor: not-allowed; }

@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
