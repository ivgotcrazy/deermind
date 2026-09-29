<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ocrSample } from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const captured = ref(false)
const scanning = ref(false)

function shoot() {
  captured.value = true
  scanning.value = true
  setTimeout(() => {
    scanning.value = false
    router.push('/student/confirm')
  }, 1800)
}
</script>

<template>
  <div class="page">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.push('/student/home')"><Icon name="back" :size="20" /></button>
      <span class="ttl">拍错题</span>
    </header>

    <div class="cam" :class="{ shot: captured }">
      <div v-if="!captured" class="cam-empty">
        <Icon name="camera" :size="46" />
        <p>把错题放在框里，拍下来</p>
        <p class="sub">支持最多 3 张 · 拍照或相册</p>
      </div>
      <template v-else>
        <div class="fake-photo">
          <span class="hint">{{ ocrSample.imageHint }}</span>
          <p class="stem">{{ ocrSample.text }}</p>
        </div>
        <div v-if="scanning" class="scan"><span></span></div>
        <p v-if="scanning" class="scan-text">小鹿正在识别题目…</p>
      </template>
    </div>

    <button v-if="!captured" class="shutter" @click="shoot">
      <Icon name="camera" :size="30" />
    </button>
    <p class="tip">OCR 识别后进入确认页，识别文本可修改</p>
  </div>
</template>

<style scoped>
.page {
  max-width: 560px;
  margin: 0 auto;
  height: 100%;
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
.cam {
  flex: 1;
  border-radius: var(--radius-card);
  background: #1e1b4b;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  color: #fff;
}
.cam-empty {
  text-align: center;
  color: #c7d2fe;
}
.cam-empty p {
  margin: 10px 0 0;
  font-size: 15px;
}
.cam-empty .sub {
  font-size: 13px;
  opacity: 0.7;
}
.fake-photo {
  background: #fffbeb;
  color: var(--color-ink);
  border-radius: 12px;
  padding: 18px;
  width: 82%;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
}
.fake-photo .hint {
  font-size: 12px;
  color: #9ca3af;
}
.fake-photo .stem {
  font-size: 15px;
  line-height: 1.7;
}
.scan {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.scan span {
  position: absolute;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, #22d3ee, transparent);
  animation: scan 1.4s linear infinite;
}
@keyframes scan {
  0% {
    top: 0%;
  }
  100% {
    top: 100%;
  }
}
.scan-text {
  position: absolute;
  bottom: 24px;
  font-size: 14px;
  color: #a5f3fc;
}
.shutter {
  align-self: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 4px solid #fff;
  background: var(--color-cta);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-clay);
}
.tip {
  text-align: center;
  font-size: 12px;
  opacity: 0.6;
  margin: 0;
}
</style>
