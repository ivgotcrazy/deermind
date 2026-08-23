<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { mogiQuestions } from '@/data/mock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const router = useRouter()

const step = ref<'intro' | 'quiz' | 'result'>('intro')
const idx = ref(0)
const picked = ref('')
const correct = ref(0)

const q = () => mogiQuestions[idx.value]
const opts = () => mogiQuestions[idx.value].options

function pick(opt: string) {
  if (picked.value) return
  picked.value = opt
  if (opt === q().answer) correct.value++
}
function next() {
  picked.value = ''
  if (idx.value < mogiQuestions.length - 1) idx.value++
  else step.value = 'result'
}
function start() {
  idx.value = 0
  correct.value = 0
  step.value = 'quiz'
}
</script>

<template>
  <div class="mogi">
    <!-- 介绍 -->
    <section v-if="step === 'intro'" class="card intro">
      <DeerAvatar :size="88" />
      <h2>初次见面，我是小鹿！</h2>
      <p>在开始之前，我们先做一个小测试（3 道题），让我看看你现在的水平，这样我就能帮你安排合适的学习啦。</p>
      <p class="hint">不会也没关系，答错了我们会一起学！</p>
      <button class="btn btn-primary btn-block" @click="start">开始摸底 →</button>
    </section>

    <!-- 摸底题 -->
    <section v-else-if="step === 'quiz'" class="card">
      <div class="qhead">
        <span class="chip">摸底 {{ idx + 1 }} / {{ mogiQuestions.length }}</span>
        <span class="kp">{{ q().kp }}</span>
      </div>
      <p class="q">{{ q().text }}</p>
      <div class="options">
        <button
          v-for="opt in opts()"
          :key="opt"
          class="opt"
          :class="{ right: picked === opt && opt === q().answer, wrong: picked === opt && opt !== q().answer }"
          @click="pick(opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-if="picked && picked === q().answer" class="fb right"><Icon name="check" :size="16" /> 答对啦！</div>
      <div v-else-if="picked" class="fb wrong">没关系，小鹿会帮你把这块补上</div>
      <button v-if="picked" class="btn btn-primary btn-block" @click="next">
        {{ idx < mogiQuestions.length - 1 ? '下一题 →' : '看结果 →' }}
      </button>
    </section>

    <!-- 结果 -->
    <section v-else class="card result">
      <DeerAvatar :size="72" />
      <h2>摸底完成！答对 {{ correct }} / {{ mogiQuestions.length }}</h2>
      <p>小鹿为你生成了初始学习画像：</p>
      <ul class="pillars">
        <li><span class="pill pill-mastered">已掌握</span> 分数乘法计算</li>
        <li><span class="pill pill-inprogress">攻克中</span> 求一个数的几分之几</li>
        <li><span class="pill pill-focus">需关注</span> 分数应用题</li>
      </ul>
      <p class="sugg">建议今天从「求一个数的几分之几」开始，小鹿会一步步带你。</p>
      <button class="btn btn-primary btn-block" @click="router.push('/child/home')">开始今日学习 →</button>
    </section>
  </div>
</template>

<style scoped>
.mogi {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.intro {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}
.intro h2 {
  margin: 4px 0 0;
  font-family: var(--font-head);
  font-size: 20px;
}
.intro p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}
.hint {
  color: var(--color-primary);
}
.qhead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.kp {
  font-size: 12px;
  opacity: 0.7;
}
.q {
  margin: 0 0 12px;
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
.result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}
.result h2 {
  margin: 4px 0 0;
  font-size: 18px;
}
.result p {
  margin: 0;
  font-size: 14px;
}
.pillars {
  list-style: none;
  margin: 4px 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  text-align: left;
}
.pillars li {
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
.sugg {
  color: var(--color-primary);
}
</style>
