<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { masteryPillars } from '@/data/mock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

const tasks = [
  { label: '复习 · 分数乘法（间隔第 3 天）', done: false },
  { label: '新学 · 求一个数的几分之几', done: false },
  { label: '读题训练 · 应用题 1 道', done: false },
]
const doneCount = computed(() => (store.todayTaskDone ? tasks.length : store.variantPassed ? 2 : 0))

const pillClass = (s: string) => (s === 'mastered' ? 'pill-mastered' : s === 'inprogress' ? 'pill-inprogress' : 'pill-focus')
const pillLabel = (s: string) => (s === 'mastered' ? '已掌握' : s === 'inprogress' ? '攻克中' : '需关注')
</script>

<template>
  <div class="home">
    <!-- 小鹿问候 -->
    <section class="card greet">
      <DeerAvatar :size="64" />
      <div>
        <h2>嗨，今天也要加油呀！</h2>
        <p>今天任务：复习 1 个 · 新学 1 个 · 读题 1 道</p>
        <div class="steps">
          <span v-for="i in 3" :key="i" class="step" :class="{ on: i <= doneCount }"></span>
        </div>
      </div>
    </section>

    <!-- 今日任务 -->
    <section class="card task-card">
      <div class="card-head">
        <h3>今日任务</h3>
        <span class="chip">{{ doneCount }}/3</span>
      </div>
      <ul class="tasks">
        <li v-for="(task, i) in tasks" :key="i" class="task" :class="{ done: i < doneCount }">
          <span class="tick" :class="{ on: i < doneCount }">
            <Icon v-if="i < doneCount" name="check" :size="14" />
          </span>
          {{ task.label }}
        </li>
      </ul>
      <button v-if="!store.todayTaskDone" class="btn btn-primary btn-block" @click="router.push('/child/photo')">
        <Icon name="camera" :size="18" /> 拍错题，开始学习
      </button>
      <div v-else class="all-done">
        <Icon name="check" :size="20" /> 今日任务已完成，真棒！
      </div>
    </section>

    <!-- 快捷入口 -->
    <section class="quick">
      <button class="card pressable quick-item" @click="router.push('/child/photo')">
        <Icon name="camera" :size="26" />
        <span>拍错题</span>
      </button>
      <button class="card pressable quick-item" @click="router.push('/child/summary')">
        <Icon name="refresh" :size="26" />
        <span>复习</span>
      </button>
      <button class="card pressable quick-item" @click="router.push('/child/reading')">
        <Icon name="doc" :size="26" />
        <span>读题训练</span>
      </button>
    </section>

    <!-- 掌握度概览 -->
    <section class="card pillar-card">
      <div class="card-head">
        <h3>本周掌握度</h3>
        <span class="chip">68%</span>
      </div>
      <ul class="pillars">
        <li v-for="p in masteryPillars" :key="p.kp" class="pillar">
          <span class="pill" :class="pillClass(p.state)">{{ pillLabel(p.state) }}</span>
          <span class="kp-name">{{ p.kp }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr;
  padding-top: 4px;
}
/* 平板/桌面：Bento 自适应网格 */
@media (min-width: 768px) {
  .home {
    grid-template-columns: 1fr 1fr;
    grid-template-areas: 'g g' 't p' 'q q';
    align-items: stretch;
  }
  .greet { grid-area: g; }
  .task-card { grid-area: t; }
  .pillar-card { grid-area: p; }
  .quick { grid-area: q; }
}
.greet {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
}
.greet h2 {
  margin: 0 0 4px;
  font-family: var(--font-head);
  font-size: 17px;
}
.greet p {
  margin: 0 0 8px;
  font-size: 12px;
  opacity: 0.8;
}
.steps {
  display: flex;
  gap: 6px;
}
.step {
  width: 34px;
  height: 8px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.15);
  transition: background var(--ease-soft);
}
.step.on {
  background: var(--color-cta);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.card-head h3 {
  margin: 0;
  font-family: var(--font-head);
  font-size: 15px;
}
.tasks {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.task {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}
.task.done {
  opacity: 0.6;
  text-decoration: line-through;
}
.tick {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--color-line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.tick.on {
  background: var(--color-cta);
  border-color: var(--color-cta);
}
.all-done {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--color-cta);
  font-weight: 700;
  padding: 10px;
  background: var(--color-cta-soft);
  border-radius: 12px;
}
.quick {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 8px;
  border: none;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}
.pillars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pillar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.kp-name {
  font-size: 14px;
}
</style>
