<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { variantQuestion } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

const picked = ref('')
const idea = ref('')
const ideaSent = ref(false)
const recording = ref(false)

const options = [variantQuestion.answer, ...variantQuestion.distractors]

function pick(opt: string) {
  if (picked.value) return
  picked.value = opt
  if (opt === variantQuestion.answer) store.variantPassed = true
}
function sendIdea() {
  ideaSent.value = true
}
function toggleRec() {
  recording.value = !recording.value
  if (recording.value) {
    setTimeout(() => {
      recording.value = false
      idea.value = '用全长乘上用去的比例，就是 4/5 × 3/4'
      ideaSent.value = true
    }, 2200)
  }
}
</script>

<template>
  <div class="variant">
    <h2 class="title">变式验收</h2>
    <p class="sub">换了个样子，看你是不是真的懂了（三不变一变）</p>

    <section class="card qcard">
      <span class="chip">变式题</span>
      <p class="q">{{ variantQuestion.text }}</p>
      <div class="options">
        <button
          v-for="opt in options"
          :key="opt"
          class="opt"
          :class="{ right: picked === opt && opt === variantQuestion.answer, wrong: picked === opt && opt !== variantQuestion.answer }"
          @click="pick(opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-if="picked && picked !== variantQuestion.answer" class="fb wrong">再想想，求一个数的几分之几用乘法</div>
      <div v-else-if="picked" class="fb right"><Icon name="check" :size="16" /> 变式做对啦！</div>
    </section>

    <!-- 一句话思路 -->
    <section class="card idea">
      <div class="idea-head">
        <span>用一句话说说你是怎么想的？</span>
        <button class="icon-btn" :class="{ rec: recording }" aria-label="语音输入" @click="toggleRec">
          <Icon name="speaker" :size="20" />
        </button>
      </div>
      <textarea
        v-model="idea"
        class="input idea-input"
        placeholder="比如：用全长乘上 3/4 就是用了多少千克…"
        rows="3"
        :disabled="ideaSent"
      ></textarea>
      <div v-if="recording" class="recording">
        <span class="pulse"></span> 正在听你说…
      </div>
      <button v-if="!ideaSent && idea" class="btn btn-indigo btn-block" @click="sendIdea">提交思路</button>
      <div v-else-if="ideaSent" class="sent">
        <Icon name="check" :size="16" /> 思路已记录（小鹿会在以后帮你回顾）
      </div>
    </section>

    <!-- 验收通过 -->
    <section v-if="store.variantPassed && ideaSent" class="card pass-card">
      <div class="pass-title"><Icon name="check" :size="22" /> 验收通过</div>
      <p>「求一个数的几分之几」已标记为 <b>短期掌握</b>，小鹿会在 <b>1 / 3 / 7 天</b> 后提醒你复习。</p>
      <button class="btn btn-primary btn-block" @click="router.push('/child/summary')">查看今日小结 →</button>
    </section>
  </div>
</template>

<style scoped>
.variant {
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
.fb {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
}
.fb.right { background: var(--color-cta-soft); color: #15803d; }
.fb.wrong { background: var(--color-danger-soft); color: #b91c1c; }
.idea-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
  margin-bottom: 10px;
}
.icon-btn.rec {
  background: var(--color-danger);
  color: #fff;
}
.idea-input {
  font-family: inherit;
  resize: none;
}
.recording {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-danger);
  font-weight: 700;
  margin-top: 10px;
}
.pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-danger);
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.sent {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-cta);
  font-weight: 700;
  padding: 10px;
  background: var(--color-cta-soft);
  border-radius: 12px;
  margin-top: 10px;
}
.pass-card {
  border: 3px solid var(--color-cta);
  background: #fff;
}
.pass-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #15803d;
  font-weight: 800;
  font-size: 16px;
  margin-bottom: 6px;
}
.pass-card p {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.6;
}
</style>
