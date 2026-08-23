<script setup lang="ts">
import { masteryPillars, knowledgePoints, weeklyReport } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const pillClass = (s: string) => (s === 'mastered' ? 'pill-mastered' : s === 'inprogress' ? 'pill-inprogress' : 'pill-focus')
const pillLabel = (s: string) => (s === 'mastered' ? '已掌握' : s === 'inprogress' ? '攻克中' : '需关注')

const domains = ['数与代数', '图形与几何', '应用']
const byDomain: Record<string, typeof masteryPillars> = {
  数与代数: masteryPillars,
  图形与几何: [],
  应用: [masteryPillars[2]],
}

const kpOf = (name: string) => knowledgePoints.find((k) => k.name === name)
</script>

<template>
  <div class="progress">
    <h2 class="title">学习进度</h2>

    <!-- 掌握率总览 -->
    <section class="card">
      <div class="rate-head">
        <span>数学掌握率</span>
        <span class="rate">{{ weeklyReport.masteredRate }}% <em>{{ weeklyReport.rateTrend }}</em></span>
      </div>
      <div class="bar"><div class="fill" :style="{ width: weeklyReport.masteredRate + '%' }"></div></div>
      <div class="legend">
        <span><span class="dot dot-green"></span>已掌握</span>
        <span><span class="dot dot-amber"></span>攻克中</span>
        <span><span class="dot dot-red"></span>需关注</span>
      </div>
    </section>

    <!-- 知识点掌握度（按领域下钻） -->
    <section class="card">
      <div class="sec-title">知识点掌握度</div>
      <div v-for="d in domains" :key="d" class="domain">
        <div class="domain-head">{{ d }} <span class="count">{{ byDomain[d].length }} 个</span></div>
        <ul v-if="byDomain[d].length" class="kps">
          <li v-for="p in byDomain[d]" :key="p.kp" class="kp-item">
            <span class="pill" :class="pillClass(p.state)">{{ pillLabel(p.state) }}</span>
            <div class="kp-info">
              <div class="kp-name">{{ p.kp }}</div>
              <div class="pre" v-if="kpOf(p.kp)?.prerequisites?.length">
                前置：{{ kpOf(p.kp)!.prerequisites.join(' → ') }}
              </div>
            </div>
          </li>
        </ul>
        <div v-else class="empty">暂无学习记录</div>
      </div>
    </section>

    <!-- 薄弱点 Top -->
    <section class="card">
      <div class="sec-title">薄弱点（按紧急度）</div>
      <ul class="weak">
        <li v-for="w in weeklyReport.weakness" :key="w.kp">
          <span class="pill pill-focus">需关注</span>
          <div class="kp-info">
            <div class="kp-name">{{ w.kp }}</div>
            <div class="pre">{{ w.type }} · 本周 {{ w.count }} 次</div>
          </div>
        </li>
      </ul>
      <p class="tip"><Icon name="sparkles" :size="14" /> 小鹿会优先安排这些知识点的补强</p>
    </section>
  </div>
</template>

<style scoped>
.progress {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 20px;
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
}
.fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-cta));
}
.legend {
  display: flex;
  gap: 14px;
  margin-top: 10px;
  font-size: 12px;
  opacity: 0.8;
}
.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.domain {
  margin-bottom: 12px;
}
.domain-head {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}
.count {
  font-size: 11px;
  opacity: 0.6;
  font-weight: 400;
}
.kps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kp-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}
.kp-info .kp-name {
  font-weight: 700;
  font-size: 14px;
}
.pre {
  font-size: 12px;
  opacity: 0.65;
}
.empty {
  font-size: 13px;
  opacity: 0.5;
  padding: 8px 0;
}
.weak {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.weak li {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 13px;
  color: var(--color-primary);
}
</style>
