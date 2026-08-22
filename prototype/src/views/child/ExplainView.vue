<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { explainContent } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const playing = ref(false)
const secondAngle = ref(false)
const ttsTimer = ref<number | null>(null)

function toggleTts() {
  if (playing.value) {
    playing.value = false
    if (ttsTimer.value) clearTimeout(ttsTimer.value)
  } else {
    playing.value = true
    ttsTimer.value = window.setTimeout(() => (playing.value = false), 5000)
  }
}
</script>

<template>
  <div class="explain">
    <h2 class="title">小鹿讲解</h2>
    <p class="sub">知识点：求一个数的几分之几</p>

    <section class="card">
      <div class="source">
        <Icon name="doc" :size="16" />
        <span>来源：{{ explainContent.source }}</span>
      </div>

      <div class="tts-row">
        <span class="kptitle">{{ explainContent.title }}</span>
        <button class="icon-btn" :class="{ playing }" aria-label="朗读" @click="toggleTts">
          <Icon :name="playing ? 'volumeOff' : 'speaker'" :size="20" />
        </button>
      </div>

      <div class="body">
        <p>{{ explainContent.body }}</p>
        <template v-if="secondAngle">
          <div class="angle">
            <span class="angle-tag">换个讲法</span>
            <p>{{ explainContent.secondAngle }}</p>
          </div>
        </template>
      </div>

      <button class="btn btn-soft btn-block" @click="secondAngle = !secondAngle">
        {{ secondAngle ? '收起另一种讲法' : '还是没懂？换一种讲法' }}
      </button>

      <div v-if="playing" class="wave">
        <span v-for="i in 5" :key="i"></span>
        <span class="wave-label">小鹿正在朗读…</span>
      </div>
    </section>

    <button class="btn btn-primary btn-block" @click="router.push('/child/practice')">
      来做 3 道练习 →（巩固）
    </button>
  </div>
</template>

<style scoped>
.explain {
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
.source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 6px 10px;
  border-radius: 10px;
  margin-bottom: 10px;
}
.tts-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.kptitle {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 17px;
}
.icon-btn.playing {
  background: var(--color-cta);
  color: #fff;
}
.body {
  font-size: 15px;
  line-height: 1.75;
  color: var(--color-text);
}
.body p {
  margin: 0 0 10px;
  white-space: pre-line;
}
.angle {
  margin: 10px 0;
  padding: 12px;
  background: var(--color-warning-soft);
  border-radius: 14px;
  animation: fade 0.3s ease;
}
.angle-tag {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  color: #b45309;
  margin-bottom: 6px;
}
@keyframes fade {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.wave {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  margin-top: 12px;
  padding: 10px;
  background: var(--color-cta-soft);
  border-radius: 12px;
}
.wave span:not(.wave-label) {
  width: 6px;
  background: var(--color-cta);
  border-radius: 2px;
  animation: wave 0.9s ease-in-out infinite;
}
.wave span:nth-child(1) { height: 10px; animation-delay: 0s; }
.wave span:nth-child(2) { height: 20px; animation-delay: 0.15s; }
.wave span:nth-child(3) { height: 28px; animation-delay: 0.3s; }
.wave span:nth-child(4) { height: 18px; animation-delay: 0.45s; }
.wave span:nth-child(5) { height: 12px; animation-delay: 0.6s; }
@keyframes wave {
  0%, 100% { transform: scaleY(0.6); }
  50% { transform: scaleY(1); }
}
.wave-label {
  margin-left: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #15803d;
}
</style>
