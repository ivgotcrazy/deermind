<script setup lang="ts">
import { computed } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE, STATE_LABEL, type MasteryState } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const ev = useEvidenceStore()

const dist = computed(() => {
  const d: Record<MasteryState, number> = { unknown: 0, learning: 0, short: 0, stable: 0 }
  ev.concepts.forEach((c) => {
    const s = ev.snapshotOf(c.id)?.status ?? 'unknown'
    d[s]++
  })
  return d
})

const total = computed(() => ev.concepts.length)
const masteredRate = computed(() => Math.round(((dist.value.stable + dist.value.short) / total.value) * 100))

const transitions = computed(() => ev.decisions.slice(-8).reverse())

const stopRecords = computed(() =>
  ev.decisions.filter((d) => d.toState === 'stable' || d.action.includes('停止')),
)

const nextWeek = computed(() => {
  const unstable = ev.concepts
    .filter((c) => ev.snapshotOf(c.id)?.status === 'learning')
    .map((c) => c.name)
  const explore = ev.concepts
    .filter((c) => (ev.snapshotOf(c.id)?.status ?? 'unknown') === 'unknown')
    .map((c) => c.name)
  return { unstable, explore }
})

function exportReport() {
  alert('原型演示：导出学情报告（PDF）——数据来自共享证据账本')
}
</script>

<template>
  <div class="weekly">
    <h2 class="title">学情周报 · 8/17-8/23 <span class="demo">{{ DEMO_NOTE }}</span></h2>

    <!-- 四态分布 -->
    <section class="card">
      <div class="rate-head">
        <span>数学掌握率</span>
        <span class="rate">{{ masteredRate }}% <em>较上周 +6%</em></span>
      </div>
      <div class="bar">
        <div class="fill" :style="{ width: masteredRate + '%' }"></div>
      </div>
      <div class="dist">
        <div v-for="s in (['stable', 'short', 'learning', 'unknown'] as MasteryState[])" :key="s" class="d-col">
          <span class="d-num">{{ dist[s] }}</span>
          <span class="d-pill" :class="s"></span>
          <span class="d-label">{{ STATE_LABEL[s] }}</span>
        </div>
      </div>
    </section>

    <!-- 状态变化（决策记录） -->
    <section class="card">
      <div class="sec-title">本周状态变化（政策引擎决策）</div>
      <ul class="tl">
        <li v-for="d in transitions" :key="d.id" class="tl-item">
          <span class="t">{{ d.time }}</span>
          <div class="tl-body">
            <div class="kp">
              {{ d.kpName }}
              <span class="move">{{ STATE_LABEL[d.fromState] }} → {{ STATE_LABEL[d.toState] }}</span>
            </div>
            <div class="action">{{ d.action }}</div>
            <div class="reason">{{ d.reason }}</div>
          </div>
        </li>
      </ul>
    </section>

    <!-- 停止决策记录（减负） -->
    <section class="card">
      <div class="sec-title">减负 · 停止决策记录</div>
      <ul class="stop">
        <li v-for="d in stopRecords" :key="d.id" class="stop-item">
          <span class="pill pill-mastered">已停止</span>
          <div class="info">
            <div class="kp">{{ d.kpName }}</div>
            <div class="meta">{{ d.time }} · {{ d.reason }}</div>
          </div>
        </li>
        <li v-if="!stopRecords.length" class="muted">本周暂无停止决策</li>
      </ul>
    </section>

    <!-- 下周建议 -->
    <section class="card">
      <div class="sec-title">下周建议</div>
      <p class="sugg">
        待巩固：{{ nextWeek.unstable.join('、') || '—' }}；可探索（UNKNOWN 静默，等反证）：{{ nextWeek.explore.join('、') || '—' }}。每天 15-30 分钟即可，少学一点但学得更牢。
      </p>
    </section>

    <button class="btn btn-primary btn-block" @click="exportReport">
      <Icon name="upload" :size="18" /> 导出学情报告（PDF）
    </button>
  </div>
</template>

<style scoped>
.weekly {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 19px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.demo {
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: 999px;
}
.rate-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-weight: 800;
  margin-bottom: 10px;
}
.rate {
  font-size: 24px;
}
.rate em {
  font-style: normal;
  font-size: 14px;
  color: var(--color-cta);
}
.bar {
  height: 12px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  overflow: hidden;
  margin-bottom: 16px;
}
.fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-cta));
}
.dist {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.d-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.d-num {
  font-size: 18px;
  font-weight: 800;
}
.d-pill {
  width: 28px;
  height: 8px;
  border-radius: 999px;
}
.d-pill.stable {
  background: var(--color-cta);
}
.d-pill.short {
  background: #84cc16;
}
.d-pill.learning {
  background: var(--color-warning);
}
.d-pill.unknown {
  background: #cbd5e1;
}
.d-label {
  font-size: 11px;
  opacity: 0.75;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.tl {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tl-item {
  display: flex;
  gap: 10px;
}
.tl-item .t {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  flex-shrink: 0;
  padding-top: 2px;
}
.tl-body {
  flex: 1;
  border-left: 2px solid var(--color-primary-soft);
  padding-left: 10px;
}
.kp {
  font-weight: 700;
  font-size: 14px;
}
.move {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 1px 8px;
  border-radius: 999px;
  margin-left: 6px;
}
.action {
  font-size: 12.5px;
  margin-top: 2px;
}
.reason {
  font-size: 12px;
  opacity: 0.7;
  margin-top: 2px;
}
.stop {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.stop-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}
.pill-mastered {
  background: var(--color-cta-soft);
  color: #15803d;
}
.info .kp {
  font-weight: 700;
  font-size: 14px;
}
.info .meta {
  font-size: 12px;
  opacity: 0.7;
}
.muted {
  opacity: 0.6;
  font-size: 13px;
}
.sugg {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.7;
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 12px;
}
</style>
