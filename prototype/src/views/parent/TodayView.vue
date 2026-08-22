<script setup lang="ts">
import { dailyReport } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const stats = [
  { label: '学习时长', value: dailyReport.items[0].value, icon: 'chart' },
  { label: '完成知识点', value: dailyReport.items[1].value, icon: 'check' },
  { label: '错题闭环', value: dailyReport.items[2].value, icon: 'doc' },
]

const records = [
  { time: '17:02', text: '完成「求一个数的几分之几」读题训练（3 步）' },
  { time: '17:12', text: '完成讲解 + 3 道基础练习（全对）' },
  { time: '17:20', text: '变式验收通过 → 短期掌握' },
]
</script>

<template>
  <div class="today">
    <h2 class="title">今日学习 · {{ dailyReport.date }}</h2>

    <div class="stats">
      <div v-for="s in stats" :key="s.label" class="stat">
        <Icon :name="s.icon" :size="20" />
        <span class="v">{{ s.value }}</span>
        <span class="l">{{ s.label }}</span>
      </div>
    </div>

    <section class="card">
      <div class="sec-title">学习记录</div>
      <ul class="records">
        <li v-for="r in records" :key="r.time">
          <span class="t">{{ r.time }}</span>{{ r.text }}
        </li>
      </ul>
    </section>

    <section class="card alert">
      <div class="alert-head">
        <Icon name="sparkles" :size="18" />
        <span>异常提醒</span>
      </div>
      <p>{{ dailyReport.alert }}</p>
      <p class="sugg">建议：明天继续 1 道应用题读题训练（约 8 分钟）</p>
    </section>
  </div>
</template>

<style scoped>
.today {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 19px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.stat {
  background: #fff;
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--color-primary);
  box-shadow: var(--shadow-clay);
}
.stat .v {
  font-size: 16px;
  font-weight: 800;
  color: var(--color-text);
}
.stat .l {
  font-size: 11px;
  opacity: 0.7;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.records {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.records li {
  font-size: 13px;
  line-height: 1.5;
}
.records .t {
  color: var(--color-primary);
  font-weight: 700;
  margin-right: 6px;
}
.alert {
  border-top: 4px solid var(--color-warning);
}
.alert-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
  color: #b45309;
  margin-bottom: 6px;
}
.alert p {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.6;
}
.alert .sugg {
  color: var(--color-primary);
}
</style>
