<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { readingSteps, sampleError } from '@/data/mock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

const step = computed(() => readingSteps[store.readingStep])
const showHint = ref(false)
const redoVisible = ref(false)
const redoPassed = ref(false)
const selectedRedo = ref('')

const redoOptions = [
  '5/6 × 2/3 = 5/9（米）',
  '5/6 − 2/3 = 1/6（米）',
  '5/6 ÷ 2/3 = 5/4（米）',
]

function nextStep() {
  showHint.value = false
  if (store.readingStep < 2) {
    store.readingStep++
  } else {
    redoVisible.value = true
  }
}

function pickRedo(opt: string) {
  selectedRedo.value = opt
  redoPassed.value = opt === redoOptions[0]
}
</script>

<template>
  <div class="reading">
    <h2 class="title">读题训练</h2>
    <p class="sub">不急着算，先把题目读明白（归因：审题失误）</p>

    <!-- 原题 -->
    <section class="card problem">
      <span class="chip">原题</span>
      <p class="q">{{ sampleError.ocrText }}</p>
    </section>

    <!-- 当前步骤 -->
    <section v-if="!redoVisible" class="card step">
      <div class="step-head">
        <span class="step-no">{{ step.id.slice(1) }}/3</span>
        <span class="step-title">{{ step.title }}</span>
      </div>
      <div class="deer-line">
        <DeerAvatar :size="44" />
        <div class="bubble">{{ step.prompt }}</div>
      </div>
      <button class="btn btn-soft btn-block" @click="showHint = !showHint">
        {{ showHint ? '收起提示' : '看一下提示' }}
      </button>
      <div v-if="showHint" class="hint">{{ step.hint }}</div>
      <button class="btn btn-primary btn-block" @click="nextStep">
        {{ store.readingStep < 2 ? '下一步 →' : '我读明白了，重做原题' }}
      </button>
    </section>

    <!-- 重做原题 -->
    <section v-else class="card redo">
      <span class="chip">重做原题</span>
      <p class="q">{{ sampleError.ocrText }}</p>
      <div class="options">
        <button
          v-for="opt in redoOptions"
          :key="opt"
          class="opt"
          :class="{
            right: redoPassed && selectedRedo === opt,
            wrong: redoPassed && selectedRedo === opt && selectedRedo !== redoOptions[0],
          }"
          @click="pickRedo(opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-if="redoPassed" class="pass">
        <Icon name="check" :size="18" /> 做对了！数量关系掌握得很好
      </div>
      <button v-if="redoPassed" class="btn btn-primary btn-block" @click="router.push('/child/explain')">
        复习概念讲解 →（巩固）
      </button>
    </section>
  </div>
</template>

<style scoped>
.reading {
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
.problem .q,
.redo .q {
  margin: 10px 0 0;
  font-size: 15px;
  line-height: 1.7;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.step-no {
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.step-title {
  font-weight: 700;
}
.deer-line {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.bubble {
  flex: 1;
  background: var(--color-primary-soft);
  padding: 12px 14px;
  border-radius: 16px;
  border-top-left-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
}
.hint {
  margin: 10px 0;
  padding: 10px 12px;
  background: var(--color-warning-soft);
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  animation: fade 0.3s ease;
}
@keyframes fade {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 12px 0;
}
.opt {
  text-align: left;
  padding: 14px;
  border: 2px solid var(--color-line);
  border-radius: 14px;
  background: #fff;
  font-size: 14px;
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
.pass {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-cta);
  font-weight: 700;
  margin-bottom: 12px;
  padding: 10px;
  background: var(--color-cta-soft);
  border-radius: 12px;
}
</style>
