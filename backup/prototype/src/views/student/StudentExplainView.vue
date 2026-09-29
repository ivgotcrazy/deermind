<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import {
  ocrSample,
  attributionQuestions,
  attributionResult,
  explainContent,
  practiceQuestions,
  variantQuestion,
} from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()

const step = ref(0) // 0 归因 / 1 讲解 / 2 练习 / 3 变式 / 4 完成
const q = ref(0) // 归因第几问
const a = ref('')
const attribution = ref('')
const angle = ref(0)
const tts = ref(false)

const practiceSel = ref<(number | null)[]>(practiceQuestions.map(() => null))
const practiceChecked = ref(false)
const practicePass = computed(() =>
  practiceChecked.value && practiceQuestions.every((x, i) => x.answer === practiceSel.value[i]),
)

const variantSel = ref<number | null>(null)
const idea = ref('')
const variantChecked = ref(false)

const steps = ['归因', '讲解', '练习', '变式', '完成']
const stepLabel = computed(() => steps[step.value])

function pickAnswer(ans: string) {
  a.value = ans
  if (q.value === 0) {
    // 简化的归因：由第二问判定
    q.value = 1
  } else {
    attribution.value = ans.includes('算错') || ans.includes('最后一步')
      ? attributionResult.careless
      : ans.includes('看不懂') ? attributionResult.reading : attributionResult.concept
    setTimeout(() => (step.value = 1), 600)
  }
}

function checkPractice() {
  practiceChecked.value = true
  if (practicePass.value) {
    setTimeout(() => (step.value = 3), 700)
  }
}

function submitVariant() {
  if (!variantChecked.value) {
    variantChecked.value = true
    return
  }
  // 做对 + 一句话思路 → 变式（即时迁移）通过 → 证据入账 → 短期已会
  store.onExplainComplete()
  step.value = 4
}

function finish() {
  router.push('/student/home')
}
</script>

<template>
  <div class="page">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.push('/student/home')"><Icon name="back" :size="20" /></button>
      <span class="ttl">讲题 · {{ stepLabel }}</span>
      <div class="dots">
        <i v-for="(s, i) in steps" :key="s" :class="{ on: step >= i }"></i>
      </div>
    </header>

    <div class="stem-card">
      <div class="row-title">题目</div>
      <p class="stem">{{ ocrSample.text }}</p>
      <span class="kp-tag">{{ ocrSample.kp }}</span>
    </div>

    <!-- 归因 -->
    <section v-if="step === 0" class="card">
      <div class="row-title">🤔 先搞清楚错在哪（第 {{ q + 1 }} 问）</div>
      <p class="att-q">{{ attributionQuestions[q].q }}</p>
      <div class="opts">
        <button
          v-for="o in attributionQuestions[q].options"
          :key="o"
          class="opt"
          :class="{ sel: a === o }"
          @click="pickAnswer(o)"
        >
          {{ o }}
        </button>
      </div>
      <p v-if="attribution" class="att-result">判断：{{ attribution }}</p>
    </section>

    <!-- 讲解 -->
    <section v-else-if="step === 1" class="card">
      <div class="row-title">📖 {{ explainContent.kp }} <span class="src">来源 · {{ explainContent.source }}</span></div>
      <div class="tabs">
        <button v-for="(ang, i) in explainContent.angles" :key="i" class="tab" :class="{ on: angle === i }" @click="angle = i">
          {{ ang.title }}
        </button>
      </div>
      <p class="explain">{{ explainContent.angles[angle].text }}</p>
      <div class="actions">
        <button class="ghost" @click="tts = !tts"><Icon :name="tts ? 'volumeOff' : 'speaker'" :size="16" /> {{ tts ? '朗读中' : '朗读' }}</button>
        <button class="primary" @click="step = 2">懂了，练几道 <Icon name="play" :size="15" /></button>
      </div>
    </section>

    <!-- 练习 -->
    <section v-else-if="step === 2" class="card">
      <div class="row-title">✏️ 基础练习（3 道，全对进变式）</div>
      <div v-for="(p, i) in practiceQuestions" :key="i" class="quiz-item">
        <div class="quiz-q">{{ i + 1 }}. {{ p.q }}</div>
        <div class="quiz-opts">
          <button
            v-for="(o, j) in p.options"
            :key="j"
            class="opt"
            :class="{
              sel: practiceSel[i] === j,
              right: practiceChecked && p.answer === j,
              wrong: practiceChecked && practiceSel[i] === j && p.answer !== j,
            }"
            :disabled="practiceChecked"
            @click="practiceSel[i] = j"
          >
            {{ o }}
          </button>
        </div>
      </div>
      <div class="actions">
        <button class="primary" :disabled="practiceChecked || practiceSel.some((s) => s === null)" @click="checkPractice">
          提交
        </button>
      </div>
      <p v-if="practiceChecked && practicePass" class="ok">全对！进入变式验收～</p>
      <p v-if="practiceChecked && !practicePass" class="bad">有错的，我们换种讲法再看一遍 👉 回看讲解</p>
    </section>

    <!-- 变式 -->
    <section v-else-if="step === 3" class="card">
      <div class="row-title">🔀 变式 · 即时迁移（LEARNING → SHORT）</div>
      <p class="quiz-q">{{ variantQuestion.q }}</p>
      <div class="quiz-opts">
        <button
          v-for="(o, j) in variantQuestion.options"
          :key="j"
          class="opt"
          :class="{ sel: variantSel === j, right: variantChecked && variantQuestion.answer === j, wrong: variantChecked && variantSel === j && variantQuestion.answer !== j }"
          :disabled="variantChecked"
          @click="variantSel = j"
        >
          {{ o }}
        </button>
      </div>
      <p class="att-q">再用一句话说说你怎么想的：</p>
      <textarea v-model="idea" class="ocr" rows="2" placeholder="总页数乘 1/4 就是第一天看的…"></textarea>
      <div class="actions">
        <button class="primary" :disabled="variantSel === null || !idea.trim()" @click="submitVariant">
          {{ variantChecked ? '确认，我掌握了' : '提交验收' }}
        </button>
      </div>
      <p v-if="variantChecked" class="ok">做对 + 思路清楚 → 变式通过，证据入账 ✓</p>
    </section>

    <!-- 完成 -->
    <section v-else class="card done">
      <div class="row-title">🎉 搞定！</div>
      <p class="done-text">「{{ explainContent.kp }}」已判定「短期掌握」（UNKNOWN ≠ 已掌握，仍需稳定证据）。接下来按遗忘曲线安排复习，再做一道迁移题验证稳定性。</p>
      <button class="primary" @click="finish">回到首页 <Icon name="play" :size="15" /></button>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 560px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px 24px;
}
.top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0 4px;
}
.ttl {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 18px;
}
.icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--color-text);
}
.dots {
  margin-left: auto;
  display: flex;
  gap: 5px;
}
.dots i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-line);
}
.dots i.on {
  background: var(--color-cta);
}
.stem-card,
.card {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.row-title {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 14px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.src {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-secondary);
}
.stem {
  font-size: 15px;
  line-height: 1.7;
  margin: 0;
}
.kp-tag {
  align-self: flex-start;
  font-size: 12px;
  font-weight: 700;
  background: var(--color-secondary-soft);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: 999px;
}
.att-q {
  font-size: 14.5px;
  font-weight: 700;
  margin: 4px 0 0;
}
.opts,
.quiz-opts,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.opt {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13.5px;
  padding: 9px 14px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-text);
  font-weight: 600;
}
.opt.sel {
  background: var(--color-primary);
  color: #fff;
}
.opt.right {
  background: var(--color-cta);
  color: #fff;
}
.opt.wrong {
  background: var(--color-danger);
  color: #fff;
}
.att-result,
.ok,
.bad {
  font-size: 13.5px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 12px;
  margin: 0;
}
.att-result {
  background: var(--color-warning-soft);
  color: #b45309;
}
.ok {
  background: var(--color-cta-soft);
  color: #15803d;
}
.bad {
  background: var(--color-danger-soft);
  color: #b91c1c;
}
.tabs {
  display: flex;
  gap: 8px;
}
.tab {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.tab.on {
  background: var(--color-primary);
  color: #fff;
}
.explain {
  font-size: 14.5px;
  line-height: 1.75;
  margin: 0;
}
.ghost,
.primary {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13.5px;
  padding: 9px 14px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.primary {
  background: var(--color-cta);
  color: #fff;
}
.primary:disabled {
  opacity: 0.5;
  cursor: default;
}
.quiz-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.quiz-q {
  font-size: 14.5px;
  font-weight: 700;
}
.ocr {
  width: 100%;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  padding: 10px;
  font-family: var(--font-body);
  font-size: 14px;
  resize: vertical;
}
.done-text {
  font-size: 14.5px;
  line-height: 1.7;
  margin: 0;
}
</style>
