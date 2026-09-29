<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import { teachbackContent } from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()

const step = ref(0) // 0-2 引导问题
const text = ref('')
const checklist = ref<boolean[]>(teachbackContent.checklist.map(() => false))
const done = ref(false)

function next() {
  if (step.value < 2) {
    step.value++
    text.value = ''
    return
  }
  done.value = true
  store.onTeachBackDone()
}

function finish() {
  router.push('/student/home')
}
</script>

<template>
  <div class="page">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.push('/student/home')"><Icon name="back" :size="20" /></button>
      <span class="ttl">讲给小鹿听 · Teach-back</span>
    </header>

    <section class="card intro">
      <div class="row-title">🗣️ 把「{{ teachbackContent.kp }}」讲给小鹿听</div>
      <p class="hint">能讲清楚，才是真的会了。跟着小鹿一步步来～（P-C7 · 元认知训练）</p>
    </section>

    <template v-if="!done">
      <section class="card step">
        <div class="step-tag">第 {{ step + 1 }} 步 / 共 3 步</div>
        <p class="guide">{{ teachbackContent.steps[step].guide }}</p>
        <textarea
          v-model="text"
          rows="3"
          :placeholder="teachbackContent.steps[step].hint"
          class="ta"
        ></textarea>
      </section>

      <section class="card check">
        <div class="row-title">要点核对（讲到就打勾）</div>
        <button
          v-for="(item, i) in teachbackContent.checklist"
          :key="i"
          class="check"
          :class="{ on: checklist[i] }"
          @click="checklist[i] = !checklist[i]"
        >
          {{ checklist[i] ? '✓' : '○' }} {{ item }}
        </button>
        <div class="actions">
          <button class="primary" :disabled="!text.trim()" @click="next">
            {{ step < 2 ? '下一步' : '核对完成' }}
            <Icon name="play" :size="15" />
          </button>
        </div>
      </section>
    </template>

    <section v-else class="card done">
      <div class="row-title">🎉 讲得真清楚！</div>
      <p class="done-text">
        全部要点都说到位了，Teach-back 证据已入账（权重较高）。小鹿会根据这些证据调整对「{{ teachbackContent.kp }}」的判断～
      </p>
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
  font-size: 15px;
}
.hint {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  opacity: 0.8;
}
.step-tag {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 4px 10px;
  border-radius: 999px;
  align-self: flex-start;
}
.guide {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.6;
  margin: 0;
}
.ta {
  width: 100%;
  border: 2px solid var(--color-line);
  border-radius: 14px;
  padding: 10px;
  font-family: var(--font-body);
  font-size: 14px;
  resize: vertical;
}
.check {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  text-align: left;
  font-size: 13.5px;
  font-weight: 700;
  padding: 9px 12px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-text);
}
.check.on {
  background: var(--color-cta-soft);
  color: #15803d;
}
.actions {
  display: flex;
  margin-top: 2px;
}
.primary {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13.5px;
  padding: 10px 16px;
  border-radius: 14px;
  background: var(--color-cta);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.primary:disabled {
  opacity: 0.5;
  cursor: default;
}
.done-text {
  font-size: 14.5px;
  line-height: 1.7;
  margin: 0;
}
</style>
