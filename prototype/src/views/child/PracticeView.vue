<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { practiceQuestions } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

const idx = ref(0)
const picked = ref('')
const correctCount = ref(0)

const q = computed(() => practiceQuestions[idx.value])
const options = computed(() => [q.value.answer, ...q.value.distractors])

function pick(opt: string) {
  if (picked.value) return
  picked.value = opt
  if (opt === q.value.answer) correctCount.value++
}
function next() {
  picked.value = ''
  if (idx.value < practiceQuestions.length - 1) {
    idx.value++
  } else {
    store.practiceDone = true
    store.practiceScore = correctCount.value
  }
}
const allDone = computed(() => store.practiceDone)
</script>

<template>
  <div class="practice">
    <h2 class="title">基础练习</h2>
    <p class="sub">小鹿检查一下，是不是真的会了</p>

    <div class="progress">
      <span
        v-for="(_, i) in practiceQuestions"
        :key="i"
        class="pdot"
        :class="{ on: i < idx || allDone, cur: i === idx && !allDone, right: i < idx }"
      ></span>
    </div>

    <section class="card qcard">
      <span class="chip">第 {{ idx + 1 }} / {{ practiceQuestions.length }} 题</span>
      <p class="q">{{ q.text }}</p>
      <div class="options">
        <button
          v-for="opt in options"
          :key="opt"
          class="opt"
          :class="{
            right: picked === opt && opt === q.answer,
            wrong: picked === opt && opt !== q.answer,
            dim: picked && opt !== q.answer && opt !== q.answer,
          }"
          @click="pick(opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-if="picked && picked !== q.answer" class="feedback wrong">
        再想想：求一个数的几分之几要用<b>乘法</b>哦
      </div>
      <div v-else-if="picked" class="feedback right">
        <Icon name="check" :size="16" /> 答对啦！
      </div>
      <button
        v-if="picked"
        class="btn btn-primary btn-block"
        @click="allDone ? (store.practiceScore = correctCount) : next()"
      >
        {{ allDone ? '进入变式验收 →' : '下一题 →' }}
      </button>
    </section>

    <button v-if="allDone" class="btn btn-primary btn-block" @click="router.push('/child/variant')">
      变式验收 →（看你是不是真的懂了）
    </button>
  </div>
</template>

<style scoped>
.practice {
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
.progress {
  display: flex;
  gap: 8px;
}
.pdot {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.15);
  transition: background var(--ease-soft);
}
.pdot.on {
  background: var(--color-cta);
}
.pdot.cur {
  background: var(--color-primary);
}
.qcard .q {
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
.opt.right {
  border-color: var(--color-cta);
  background: var(--color-cta-soft);
}
.opt.wrong {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}
.opt.dim {
  opacity: 0.5;
}
.feedback {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  margin-bottom: 12px;
}
.feedback.right {
  background: var(--color-cta-soft);
  color: #15803d;
  font-weight: 700;
}
.feedback.wrong {
  background: var(--color-danger-soft);
  color: #b91c1c;
}
</style>
