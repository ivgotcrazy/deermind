<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ocrSample } from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const text = ref(ocrSample.text)
const kp = ref(ocrSample.kp)

function next() {
  router.push('/student/explain')
}
</script>

<template>
  <div class="page">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.back()"><Icon name="back" :size="20" /></button>
      <span class="ttl">确认题目</span>
    </header>

    <section class="card">
      <div class="row-title">识别到的题目（可修改）</div>
      <textarea v-model="text" class="ocr" rows="4"></textarea>
    </section>

    <section class="card">
      <div class="row-title">归属知识点</div>
      <div class="chips">
        <button class="chip" :class="{ on: kp === '分数乘法' }" @click="kp = '分数乘法'">分数乘法</button>
        <button class="chip" :class="{ on: kp === '求一个数的几分之几' }" @click="kp = '求一个数的几分之几'">
          求一个数的几分之几
        </button>
        <button class="chip" :class="{ on: kp === '分数应用题' }" @click="kp = '分数应用题'">分数应用题</button>
      </div>
    </section>

    <section class="card dup">
      <div class="row-title">📎 之前录过这道题？</div>
      <p class="dup-text">「张叔叔做中国结」在 2 周前录过，当前状态：复习中。</p>
      <div class="actions">
        <button class="ghost" @click="next">作为新错题</button>
        <button class="ghost" @click="next">回到原记录</button>
      </div>
    </section>

    <button class="btn" @click="next">进入讲解 <Icon name="play" :size="16" /></button>
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
  font-size: 14px;
}
.ocr {
  width: 100%;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  padding: 10px;
  font-family: var(--font-body);
  font-size: 14.5px;
  line-height: 1.6;
  resize: vertical;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 2px solid var(--color-line);
  background: var(--color-white);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13.5px;
  padding: 7px 12px;
  border-radius: 999px;
  font-weight: 600;
}
.chip.on {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.dup-text {
  font-size: 13.5px;
  opacity: 0.85;
  margin: 0;
}
.actions {
  display: flex;
  gap: 8px;
}
.ghost {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.btn {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 15px;
  color: #fff;
  background: var(--color-cta);
  padding: 13px;
  border-radius: var(--radius-btn);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  box-shadow: var(--shadow-clay-press);
}
</style>
