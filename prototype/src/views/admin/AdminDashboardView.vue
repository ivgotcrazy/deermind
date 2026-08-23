<script setup lang="ts">
import { computed } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE, STATE_LABEL, type MasteryState } from '@/data/sharedMock'
import StateBadge from '@/components/admin/StateBadge.vue'

const ev = useEvidenceStore()

const kpis = computed(() => [
  { label: '活跃空间', value: ev.spaces.filter((s) => s.status === 'active').length, icon: 'doc' },
  { label: '知识点', value: ev.concepts.length, icon: 'chart' },
  { label: '证据总数', value: ev.evidence.length, icon: 'check' },
  { label: '决策记录', value: ev.decisions.length, icon: 'sparkles' },
  { label: '主动动作已用', value: `${ev.attention.todayProactiveActions}/${ev.rules.dailyProactiveActionLimit}`, icon: 'calendar' },
])

const dist = computed(() => {
  const d: Record<MasteryState, number> = { unknown: 0, learning: 0, short: 0, stable: 0 }
  ev.concepts.forEach((c) => {
    const s = ev.snapshotOf(c.id)?.status ?? 'unknown'
    d[s] += 1
  })
  return d
})
const distList = computed(() =>
  (['stable', 'short', 'learning', 'unknown'] as MasteryState[]).map((s) => ({
    state: s,
    count: dist.value[s],
    pct: Math.round((dist.value[s] / ev.concepts.length) * 100),
  })),
)

const recent = computed(() => ev.decisions.slice(-5).reverse())
</script>

<template>
  <div class="dash">
    <div class="page-head">
      <h1>Dashboard</h1>
      <p class="desc">证据驱动学习决策引擎 · 运行总览（{{ DEMO_NOTE }}）</p>
    </div>

    <div class="kpis">
      <div v-for="k in kpis" :key="k.label" class="kpi">
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-value">{{ k.value }}</div>
      </div>
    </div>

    <div class="grid">
      <section class="panel">
        <div class="panel-title">掌握度分布（知识点）</div>
        <div class="dist">
          <div v-for="d in distList" :key="d.state" class="dist-row">
            <span class="dist-label">{{ STATE_LABEL[d.state] }}</span>
            <div class="dist-bar">
              <div class="dist-fill" :class="d.state" :style="{ width: Math.max(d.pct, 4) + '%' }"></div>
            </div>
            <span class="dist-count">{{ d.count }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title">最近决策（政策引擎）</div>
        <ul class="flow">
          <li v-for="d in recent" :key="d.id" class="flow-item">
            <span class="flow-time">{{ d.time }}</span>
            <div class="flow-body">
              <div class="flow-kp">
                {{ d.kpName }}
                <span class="move"><StateBadge :state="d.fromState" /> → <StateBadge :state="d.toState" /></span>
              </div>
              <div class="flow-action">{{ d.action }}</div>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <footer class="foot">{{ DEMO_NOTE }} · 阈值/公式见《系统设计.md》</footer>
  </div>
</template>

<style scoped>
.dash {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-head h1 {
  margin: 0;
  font-size: 20px;
}
.page-head .desc {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: #64748b;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.kpi {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
}
.kpi-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}
.kpi-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-text);
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 12px;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
}
.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 12px;
}
.dist {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dist-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dist-label {
  width: 64px;
  font-size: 12.5px;
  color: #475569;
  flex-shrink: 0;
}
.dist-bar {
  flex: 1;
  height: 12px;
  background: #f1f5f9;
  border-radius: 999px;
  overflow: hidden;
}
.dist-fill {
  height: 100%;
  border-radius: 999px;
}
.dist-fill.stable {
  background: #22c55e;
}
.dist-fill.short {
  background: #84cc16;
}
.dist-fill.learning {
  background: #f59e0b;
}
.dist-fill.unknown {
  background: #cbd5e1;
}
.dist-count {
  width: 24px;
  text-align: right;
  font-weight: 700;
  font-size: 13px;
}
.flow {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.flow-item {
  display: flex;
  gap: 10px;
}
.flow-time {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  flex-shrink: 0;
  padding-top: 2px;
}
.flow-body {
  flex: 1;
  border-left: 2px solid #eef2ff;
  padding-left: 10px;
}
.flow-kp {
  font-size: 13.5px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.move {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.flow-action {
  font-size: 12.5px;
  color: #475569;
  margin-top: 2px;
}
.foot {
  font-size: 11.5px;
  color: #94a3b8;
}
</style>
