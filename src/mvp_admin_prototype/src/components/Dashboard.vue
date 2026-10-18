<script setup lang="ts">
import { metricCards, trendData, rejectionReasons, alerts } from '../data';

const emit = defineEmits<{
  goTraceList: [filter?: string];
  goTraceDetail: [traceId: string];
}>();

function maxVal(key: 'interactions' | 'validationPass' | 'latencyP95'): number {
  return Math.max(...trendData.map(d => d[key]));
}
</script>

<template>
  <div class="dashboard">
    <div class="page-header">
      <h2>运行总览</h2>
      <select class="time-select">
        <option>最近 1 小时</option>
        <option selected>最近 24 小时</option>
        <option>最近 7 天</option>
        <option>自定义</option>
      </select>
    </div>

    <!-- 指标卡片 -->
    <div class="metric-grid">
      <div v-for="m in metricCards" :key="m.label" class="metric-card" @click="emit('goTraceList')">
        <span class="metric-label">{{ m.label }}</span>
        <span class="metric-value">{{ m.value }}</span>
        <span class="metric-change" :class="{ positive: m.positive, negative: !m.positive }">{{ m.change }}</span>
      </div>
    </div>

    <div class="dashboard-row">
      <!-- 趋势图 -->
      <div class="panel trend-panel">
        <h3>关键指标趋势（24h）</h3>
        <div class="trend-chart">
          <div class="trend-legend">
            <span><i class="dot" style="background:#2d6a4f"></i>交互轮次</span>
            <span><i class="dot" style="background:#c9942a"></i>验证通过率</span>
            <span><i class="dot" style="background:#4a6fa5"></i>延迟P95(s)</span>
          </div>
          <svg width="100%" height="160" viewBox="0 0 600 160" preserveAspectRatio="none">
            <!-- 网格 -->
            <line v-for="i in 4" :key="i" x1="50" :y1="20 + i*30" x2="580" :y2="20 + i*30" stroke="#f0f4f7" stroke-width="1"/>
            <!-- 交互轮次 -->
            <polyline
              :points="trendData.map((d,i) => `${50 + i*90},${140 - (d.interactions/maxVal('interactions'))*100}`).join(' ')"
              fill="none" stroke="#2d6a4f" stroke-width="2"/>
            <!-- 验证通过率 -->
            <polyline
              :points="trendData.map((d,i) => `${50 + i*90},${140 - (d.validationPass/100)*100}`).join(' ')"
              fill="none" stroke="#c9942a" stroke-width="2" stroke-dasharray="4,2"/>
            <!-- 延迟 -->
            <polyline
              :points="trendData.map((d,i) => `${50 + i*90},${140 - (d.latencyP95/maxVal('latencyP95'))*100}`).join(' ')"
              fill="none" stroke="#4a6fa5" stroke-width="2" stroke-dasharray="2,2"/>
            <!-- X轴标签 -->
            <text v-for="(d,i) in trendData" :key="'x'+i" :x="50 + i*90" y="155" text-anchor="middle" font-size="9" fill="#8a99a8">{{ d.time }}</text>
          </svg>
        </div>
      </div>

      <!-- 拒绝原因 -->
      <div class="panel rejection-panel">
        <h3>Validation 拒绝原因 Top 5</h3>
        <div class="rejection-list">
          <div v-for="(r, i) in rejectionReasons" :key="r.reason" class="rejection-item">
            <span class="rejection-rank">{{ i + 1 }}</span>
            <span class="rejection-name">{{ r.reason }}</span>
            <div class="rejection-bar">
              <div class="rejection-fill" :style="{ width: (r.count / rejectionReasons[0].count * 100) + '%' }"></div>
            </div>
            <span class="rejection-count">{{ r.count }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 异常列表 -->
    <div class="panel alert-panel">
      <h3>⚠️ 待处理异常（{{ alerts.length }}）</h3>
      <div class="alert-list">
        <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.severity"
          @click="alert.traceId && emit('goTraceDetail', alert.traceId)">
          <span class="alert-icon">
            <span v-if="alert.severity === 'critical'">🔴</span>
            <span v-else-if="alert.severity === 'warning'">🟡</span>
            <span v-else>🔵</span>
          </span>
          <div class="alert-content">
            <div class="alert-header">
              <span class="alert-time">{{ alert.time }}</span>
              <span class="alert-title">{{ alert.title }}</span>
            </div>
            <p class="alert-desc">{{ alert.description }}</p>
          </div>
          <span v-if="alert.traceId" class="alert-link">查看 Trace →</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard { padding: 20px 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.time-select { padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; }
.metric-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.metric-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; cursor: pointer; transition: box-shadow 0.15s; }
.metric-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.metric-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 8px; }
.metric-value { display: block; font-size: 28px; font-weight: 700; color: #1a3a2e; margin-bottom: 4px; }
.metric-change { font-size: 12px; font-weight: 500; }
.metric-change.positive { color: #2d8a5e; }
.metric-change.negative { color: #b85c3c; }
.dashboard-row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 20px; }
.panel { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; }
.panel h3 { margin: 0 0 14px 0; font-size: 14px; color: #1a3a2e; }
.trend-legend { display: flex; gap: 16px; margin-bottom: 8px; font-size: 11px; color: #5a6b7a; }
.trend-legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }
.rejection-list { display: flex; flex-direction: column; gap: 10px; }
.rejection-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.rejection-rank { width: 18px; height: 18px; background: #f0f4f7; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; color: #5a6b7a; flex-shrink: 0; }
.rejection-name { width: 130px; color: #3a4a5a; flex-shrink: 0; font-size: 11px; }
.rejection-bar { flex: 1; height: 8px; background: #f0f4f7; border-radius: 4px; overflow: hidden; }
.rejection-fill { height: 100%; background: linear-gradient(90deg, #b85c3c, #d4726a); border-radius: 4px; }
.rejection-count { width: 24px; text-align: right; font-weight: 600; color: #2c3e50; }
.alert-panel { margin-bottom: 20px; }
.alert-list { display: flex; flex-direction: column; gap: 8px; }
.alert-item { display: flex; align-items: center; gap: 12px; padding: 12px; border-radius: 8px; cursor: pointer; transition: background 0.15s; }
.alert-item:hover { background: #f7f9fa; }
.alert-item.critical { background: #fdf0ed; }
.alert-item.warning { background: #fef9f0; }
.alert-icon { font-size: 16px; flex-shrink: 0; }
.alert-content { flex: 1; min-width: 0; }
.alert-header { display: flex; gap: 10px; align-items: center; margin-bottom: 2px; }
.alert-time { font-size: 11px; color: #8a99a8; font-variant-numeric: tabular-nums; }
.alert-title { font-size: 13px; font-weight: 600; color: #2c3e50; }
.alert-desc { margin: 0; font-size: 12px; color: #6a7a8a; }
.alert-link { font-size: 12px; color: #2d6a4f; font-weight: 500; flex-shrink: 0; }
@media (max-width: 1200px) {
  .metric-grid { grid-template-columns: repeat(3, 1fr); }
  .dashboard-row { grid-template-columns: 1fr; }
}
</style>
