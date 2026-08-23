<script setup lang="ts">
import { ref } from 'vue'
import { errorList, type ErrorDetail } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const filter = ref<'全部' | '短期掌握' | '攻克中' | '需关注'>('全部')
const openId = ref<string | null>(null)

const filters: ('全部' | '短期掌握' | '攻克中' | '需关注')[] = ['全部', '短期掌握', '攻克中', '需关注']

const list = () => (filter.value === '全部' ? errorList : errorList.filter((e) => e.status === filter.value))

const statusPill = (s: string) =>
  s === '短期掌握' ? 'pill-mastered' : s === '攻克中' ? 'pill-inprogress' : 'pill-focus'

function toggle(e: ErrorDetail) {
  openId.value = openId.value === e.id ? null : e.id
}
</script>

<template>
  <div class="errors">
    <h2 class="title">错题详情</h2>
    <p class="sub">高参与档可见 · 供家长了解孩子错因</p>

    <div class="filters">
      <button
        v-for="f in filters"
        :key="f"
        class="chip"
        :class="{ on: filter === f }"
        @click="filter = f"
      >
        {{ f }}
      </button>
    </div>

    <div class="list">
      <section v-for="e in list()" :key="e.id" class="card item" @click="toggle(e)">
        <div class="item-top">
          <span class="pill" :class="statusPill(e.status)">{{ e.status }}</span>
          <span class="time">{{ e.time }}</span>
        </div>
        <div class="item-main">
          <span class="kp">{{ e.kp }}</span>
          <span class="attr">{{ e.attribution }}</span>
        </div>
        <p class="text">{{ e.text }}</p>

        <div v-if="openId === e.id" class="detail">
          <div class="timeline">
            <span v-for="(t, i) in e.timeline" :key="t" class="step">
              <span class="dot" :class="{ done: true }"></span>{{ t }}
              <Icon v-if="i < e.timeline.length - 1" name="back" :size="12" class="arrow" />
            </span>
          </div>
          <p class="sugg">小鹿建议：按当前闭环继续巩固，留意间隔复习。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.errors {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.sub {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.7;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 2px solid var(--color-line);
  background: #fff;
  color: var(--color-text);
  font-size: 13px;
  padding: 6px 14px;
}
.chip.on {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item {
  cursor: pointer;
}
.item-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.time {
  font-size: 12px;
  opacity: 0.6;
}
.item-main {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}
.kp {
  font-weight: 800;
  font-size: 15px;
}
.attr {
  font-size: 12px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: 2px 10px;
  border-radius: 999px;
}
.text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  opacity: 0.85;
}
.detail {
  margin-top: 12px;
  border-top: 1px dashed var(--color-line);
  padding-top: 12px;
}
.timeline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text);
}
.step {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.arrow {
  opacity: 0.4;
  transform: rotate(180deg);
}
.detail .sugg {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--color-primary);
}
</style>
