<script setup lang="ts">
import { computed, ref } from 'vue'
import { reviewQuestions, reviewTasks, type ReviewTask } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const view = ref<'list' | 'answer'>('list')
const currentTask = ref<ReviewTask | null>(null)
const picked = ref('')
const passed = ref(false)
const doneIds = ref<string[]>([])

const currentQ = computed(() =>
  reviewQuestions.find((q) => q.kp === currentTask.value?.kp) ?? reviewQuestions[0],
)
const canTap = (t: ReviewTask) => t.due === '今天' && !doneIds.value.includes(t.id)

function open(t: ReviewTask) {
  currentTask.value = t
  picked.value = ''
  passed.value = false
  view.value = 'answer'
}
function pick(opt: string) {
  if (picked.value) return
  picked.value = opt
  if (opt === currentQ.value.answer) {
    passed.value = true
    doneIds.value.push(currentTask.value!.id)
  }
}
function back() {
  view.value = 'list'
  currentTask.value = null
}
</script>

<template>
  <div class="review">
    <!-- 任务列表 -->
    <template v-if="view === 'list'">
      <h2 class="title">间隔复习</h2>
      <p class="sub">按遗忘曲线 1 / 3 / 7 天复习，把"短期掌握"变成"长期掌握"</p>

      <section class="card">
        <div class="sec">今日复习任务</div>
        <ul class="tasks">
          <li v-for="t in reviewTasks" :key="t.id" class="task" :class="{ locked: t.due !== '今天' }">
            <button class="task-main" :disabled="!canTap(t)" @click="open(t)">
              <span class="tick" :class="{ on: doneIds.includes(t.id) }">
                <Icon v-if="doneIds.includes(t.id)" name="check" :size="14" />
              </span>
              <span class="info">
                <span class="kp">{{ t.kp }}</span>
                <span class="meta">间隔第 {{ t.day }} 天 · {{ t.due }}</span>
              </span>
            </button>
            <span v-if="doneIds.includes(t.id)" class="chip">已完成</span>
            <span v-else-if="t.due !== '今天'" class="chip locked">未到期</span>
          </li>
        </ul>
      </section>

      <div v-if="doneIds.length" class="done-banner">
        <Icon name="check" :size="18" /> 今日复习完成，掌握度又稳了一步！
      </div>
    </template>

    <!-- 答题 -->
    <template v-else>
      <h2 class="title">复习 · {{ currentTask?.kp }}</h2>
      <section class="card">
        <span class="chip">间隔第 {{ currentTask?.day }} 天</span>
        <p class="q">{{ currentQ.text }}</p>
        <div class="options">
          <button
            v-for="opt in currentQ.options"
            :key="opt"
            class="opt"
            :class="{ right: picked === opt && opt === currentQ.answer, wrong: picked === opt && opt !== currentQ.answer }"
            @click="pick(opt)"
          >
            {{ opt }}
          </button>
        </div>
        <div v-if="passed" class="fb right">
          <Icon name="check" :size="16" /> 复习通过！「{{ currentTask?.kp }}」离长期掌握更近了
        </div>
        <div v-else-if="picked" class="fb wrong">再想想，求一个数的几分之几用乘法哦</div>
        <button v-if="picked" class="btn btn-primary btn-block" @click="back">返回复习列表</button>
      </section>
    </template>
  </div>
</template>

<style scoped>
.review {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 20px;
}
.sub {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.75;
}
.sec {
  font-weight: 800;
  margin-bottom: 10px;
}
.tasks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.task {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  font-family: inherit;
}
.task.locked .task-main {
  opacity: 0.6;
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
.info {
  display: flex;
  flex-direction: column;
}
.kp {
  font-weight: 700;
  font-size: 14px;
}
.meta {
  font-size: 12px;
  opacity: 0.65;
}
.chip.locked {
  background: var(--color-line);
  color: #6b7280;
}
.done-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #15803d;
  font-weight: 700;
  padding: 12px;
  background: var(--color-cta-soft);
  border-radius: 12px;
}
.q {
  margin: 12px 0;
  font-size: 16px;
  line-height: 1.7;
  font-weight: 700;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}
.opt {
  text-align: left;
  padding: 14px;
  border: 2px solid var(--color-line);
  border-radius: 14px;
  background: #fff;
  font-size: 15px;
  transition: all var(--ease-soft);
}
.opt.right { border-color: var(--color-cta); background: var(--color-cta-soft); }
.opt.wrong { border-color: var(--color-danger); background: var(--color-danger-soft); }
.fb {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}
.fb.right { background: var(--color-cta-soft); color: #15803d; }
.fb.wrong { background: var(--color-danger-soft); color: #b91c1c; }
</style>
