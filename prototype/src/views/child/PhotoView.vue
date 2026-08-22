<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { sampleError } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const router = useRouter()

const state = ref<'idle' | 'capturing' | 'recognizing' | 'done'>('idle')

function takePhoto() {
  state.value = 'capturing'
  setTimeout(() => {
    state.value = 'recognizing'
    setTimeout(() => {
      state.value = 'done'
    }, 1600)
  }, 700)
}

function confirm() {
  router.push('/child/attribution')
}
</script>

<template>
  <div class="photo">
    <h2 class="title">拍一道错题</h2>
    <p class="desc">对着作业/试卷/练习册拍照，小鹿会帮你分析~</p>

    <!-- 拍照区 -->
    <div class="capture" :class="state" @click="state === 'idle' && takePhoto()">
      <template v-if="state === 'idle'">
        <div class="camera-ring"><Icon name="camera" :size="40" /></div>
        <p>点击拍照</p>
      </template>
      <template v-else-if="state === 'capturing'">
        <div class="flash"></div>
        <p>咔嚓！</p>
      </template>
      <template v-else-if="state === 'recognizing'">
        <div class="spinner"></div>
        <p>小鹿正在识别题目…</p>
      </template>
      <template v-else>
        <div class="sheet">
          <p class="sheet-text">{{ sampleError.ocrText }}</p>
          <span class="sheet-src">{{ sampleError.imageHint }}</span>
        </div>
      </template>
    </div>

    <!-- 识别结果 -->
    <section v-if="state === 'done'" class="card result">
      <div class="result-head">
        <span class="chip">已识别 · 人教版六上 练习三 P13-3</span>
      </div>
      <p class="q">{{ sampleError.ocrText }}</p>
      <p class="meta">知识点：求一个数的几分之几　·　你的答案：{{ sampleError.wrongAnswer }}</p>
      <button class="btn btn-primary btn-block" @click="confirm">确认，开始分析 →</button>
    </section>
  </div>
</template>

<style scoped>
.photo {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 4px;
}
.title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 20px;
}
.desc {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.75;
}
.capture {
  height: 240px;
  border-radius: var(--radius-lg);
  border: 3px dashed var(--color-secondary);
  background: var(--color-primary-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  color: var(--color-primary);
  position: relative;
  overflow: hidden;
  text-align: center;
}
.capture p {
  margin: 0;
  font-weight: 700;
}
.camera-ring {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  border: 3px solid var(--color-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.flash {
  position: absolute;
  inset: 0;
  background: #fff;
  animation: flash 0.5s ease-out forwards;
}
@keyframes flash {
  from { opacity: 1; }
  to { opacity: 0; }
}
.spinner {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 4px solid var(--color-secondary);
  border-top-color: var(--color-primary);
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.sheet {
  padding: 16px;
  text-align: left;
}
.sheet-text {
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--color-text);
}
.sheet-src {
  display: inline-block;
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.7;
}
.result-head {
  margin-bottom: 8px;
}
.q {
  margin: 0 0 8px;
  font-size: 15px;
  line-height: 1.6;
}
.meta {
  margin: 0 0 14px;
  font-size: 12px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: 8px 10px;
  border-radius: 10px;
}
</style>
