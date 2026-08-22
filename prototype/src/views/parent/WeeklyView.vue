<script setup lang="ts">
import { weeklyReport } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const trend = [52, 58, 62, 68]
const weeks = ['W1', 'W2', 'W3', '本周']

function exportReport() {
  // 原型：仅模拟导出
  alert('原型演示：导出学情报告（PDF）')
}
</script>

<template>
  <div class="weekly">
    <h2 class="title">学情周报 · {{ weeklyReport.week }}</h2>

    <section class="card">
      <div class="rate-head">
        <span>数学掌握率</span>
        <span class="rate">{{ weeklyReport.masteredRate }}% <em>{{ weeklyReport.rateTrend }}</em></span>
      </div>
      <div class="bar">
        <div class="fill" :style="{ width: weeklyReport.masteredRate + '%' }"></div>
      </div>
      <div class="trend">
        <div v-for="(v, i) in trend" :key="i" class="col">
          <span class="val">{{ v }}%</span>
          <span class="pillar" :class="{ cur: i === trend.length - 1 }" :style="{ height: v * 1.6 + 'px' }"></span>
          <span class="wk">{{ weeks[i] }}</span>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="sec-title">薄弱点清单（按紧急度）</div>
      <ul class="weak">
        <li v-for="w in weeklyReport.weakness" :key="w.kp" class="w-item">
          <span class="pill pill-focus">需关注</span>
          <div class="info">
            <div class="kp">{{ w.kp }}</div>
            <div class="meta">{{ w.type }} · 本周 {{ w.count }} 次</div>
          </div>
        </li>
        <li class="w-item ok">
          <span class="pill pill-mastered">已掌握</span>
          <div class="info">
            <div class="kp">分数乘法计算</div>
            <div class="meta">本周复习通过</div>
          </div>
        </li>
      </ul>
    </section>

    <section class="card">
      <div class="sec-title">下周建议</div>
      <p class="sugg">{{ weeklyReport.suggestion }}</p>
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
.trend {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 8px;
  height: 150px;
}
.col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.val {
  font-size: 10px;
  opacity: 0.7;
}
.pillar {
  width: 22px;
  border-radius: 8px 8px 0 0;
  background: var(--color-secondary-soft);
}
.pillar.cur {
  background: var(--color-primary);
}
.wk {
  font-size: 11px;
  opacity: 0.7;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.weak {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.w-item {
  display: flex;
  gap: 10px;
  align-items: center;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}
.info .kp {
  font-weight: 700;
  font-size: 14px;
}
.info .meta {
  font-size: 12px;
  opacity: 0.7;
}
.sugg {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 12px;
}
</style>
