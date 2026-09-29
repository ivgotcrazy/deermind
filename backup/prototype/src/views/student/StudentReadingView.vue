<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import { readingTask } from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()

const step = ref(0) // 0 圈信息 / 1 复述 / 2 数量关系+重做 / 3 完成
const picked = ref<boolean[]>([false, false, false])
const restate = ref('')
const redoSel = ref<number | null>(null)
const redoChecked = ref(false)
const redoOptions = ['60 千克', '40 千克', '90 千克', '30 千克']
const redoAnswer = 1

const steps = ['圈信息', '复述', '数量关系', '完成']

function next() {
  step.value++
  if (step.value === 3) {
    store.onReadingDone()
  }
}

function checkRedo() {
  redoChecked.value = true
}
</script>

<template>
  <div class="page">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.push('/student/home')"><Icon name="back" :size="20" /></button>
      <span class="ttl">读题训练 · {{ steps[step] }}</span>
      <div class="dots">
        <i v-for="(s, i) in steps" :key="s" :class="{ on: step >= i }"></i>
      </div>
    </header>

    <div class="stem-card">
      <div class="row-title">题目</div>
      <p class="stem">{{ readingTask.stem }}</p>
      <div class="q-target">要求出：{{ readingTask.target }}</div>
    </div>

    <!-- 圈信息 -->
    <section v-if="step === 0" class="card">
      <div class="row-title">🔍 第 1 步：圈出关键信息</div>
      <button
        v-for="(info, i) in readingTask.info"
        :key="i"
        class="info"
        :class="{ on: picked[i] }"
        @click="picked[i] = !picked[i]"
      >
        {{ picked[i] ? '✓' : '○' }} {{ info }}
      </button>
      <p class="tip">把条件和问题都圈出来（点一下）</p>
      <div class="actions">
        <button class="primary" :disabled="!picked.every(Boolean)" @click="next">下一步</button>
      </div>
    </section>

    <!-- 复述 -->
    <section v-else-if="step === 1" class="card">
      <div class="row-title">🗣️ 第 2 步：用自己的话复述题意</div>
      <p class="q-text">求什么？给了哪些条件？说给小鹿听～</p>
      <textarea v-model="restate" class="ocr" rows="3" placeholder="一共有 60 千克苹果，分给五年级 2/3，问五年级分到多少…"></textarea>
      <p class="tip">小鹿只确认、不评判，说错也没关系</p>
      <div class="actions">
        <button class="primary" :disabled="!restate.trim()" @click="next">下一步</button>
      </div>
    </section>

    <!-- 数量关系 + 重做 -->
    <section v-else-if="step === 2" class="card">
      <div class="row-title">🧮 第 3 步：数量关系 + 重做</div>
      <p class="relation">五年级分得 = 总数 × 2/3</p>
      <p class="q-text">现在重做这道题：</p>
      <div class="quiz-opts">
        <button
          v-for="(o, i) in redoOptions"
          :key="i"
          class="opt"
          :class="{ sel: redoSel === i, right: redoChecked && redoAnswer === i, wrong: redoChecked && redoSel === i && redoAnswer !== i }"
          :disabled="redoChecked"
          @click="redoSel = i"
        >
          {{ o }}
        </button>
      </div>
      <div class="actions">
        <button class="primary" :disabled="redoSel === null || redoChecked" @click="checkRedo">提交</button>
        <button v-if="redoChecked" class="primary" @click="next">完成训练</button>
      </div>
      <p v-if="redoChecked && redoSel === redoAnswer" class="ok">对！60 × 2/3 = 40 千克 ✓</p>
      <p v-else-if="redoChecked" class="bad">再想想：总数乘比例哦</p>
    </section>

    <!-- 完成 -->
    <section v-else class="card done">
      <div class="row-title">🎉 读题三步掌握啦！</div>
      <p class="done-text">以后遇到应用题：先圈信息 → 复述 → 找数量关系，就不容易漏条件啦。</p>
      <button class="primary" @click="router.push('/student/home')">回到首页</button>
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
}
.stem {
  font-size: 15px;
  line-height: 1.7;
  margin: 0;
}
.q-target {
  align-self: flex-start;
  font-size: 13px;
  font-weight: 700;
  background: var(--color-warning-soft);
  color: #b45309;
  padding: 4px 10px;
  border-radius: 999px;
}
.info {
  text-align: left;
  border: 2px solid var(--color-line);
  background: var(--color-white);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  color: var(--color-text);
}
.info.on {
  border-color: var(--color-cta);
  background: var(--color-cta-soft);
  font-weight: 700;
}
.tip {
  font-size: 12px;
  opacity: 0.6;
  margin: 0;
}
.actions,
.quiz-opts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.primary {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13.5px;
  padding: 9px 16px;
  border-radius: 14px;
  background: var(--color-cta);
  color: #fff;
}
.primary:disabled {
  opacity: 0.5;
  cursor: default;
}
.q-text {
  font-size: 14.5px;
  font-weight: 700;
  margin: 0;
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
.relation {
  font-size: 15px;
  font-weight: 700;
  text-align: center;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 10px;
  border-radius: 12px;
  margin: 0;
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
.ok,
.bad {
  font-size: 13.5px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 12px;
  margin: 0;
}
.ok {
  background: var(--color-cta-soft);
  color: #15803d;
}
.bad {
  background: var(--color-danger-soft);
  color: #b91c1c;
}
.done-text {
  font-size: 14.5px;
  line-height: 1.7;
  margin: 0;
}
</style>
