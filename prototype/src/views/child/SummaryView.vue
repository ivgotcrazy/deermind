<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

function finish() {
  store.todayTaskDone = true
  router.push('/child/home')
}
</script>

<template>
  <div class="summary">
    <section class="card hero">
      <DeerAvatar :size="72" />
      <h2>今天的闭环完成啦！</h2>
      <p>把一个错题真正学会了，真棒！</p>
      <!-- 无 emoji 规则用于图标；此处为文案语气词 -->
    </section>

    <section class="card">
      <div class="sec-title">掌握度更新</div>
      <div class="row">
        <span class="pill pill-inprogress">攻克中 →</span>
        <span class="pill pill-mastered">短期掌握</span>
        <span class="kp">求一个数的几分之几</span>
      </div>
      <p class="note">已自动进入间隔复习计划：第 1 天 → 第 3 天 → 第 7 天 → 长期掌握</p>
    </section>

    <section class="card">
      <div class="sec-title">明天小鹿建议</div>
      <ul class="sugg">
        <li><Icon name="doc" :size="16" /> 读题训练 · 应用题 1 道</li>
        <li><Icon name="refresh" :size="16" /> 复习「求一个数的几分之几」（第 1 天）</li>
        <li><Icon name="camera" :size="16" /> 拍 1 道新错题</li>
      </ul>
    </section>

    <button class="btn btn-primary btn-block" @click="finish">完成，回到首页</button>
  </div>
</template>

<style scoped>
.summary {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 8px;
}
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 6px;
  background: linear-gradient(135deg, #eef2ff, #dcfce7);
}
.hero h2 {
  margin: 4px 0 0;
  font-family: var(--font-head);
  font-size: 19px;
}
.hero p {
  margin: 0;
  font-size: 14px;
  opacity: 0.8;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.pill {
  font-size: 13px;
  font-weight: 700;
  padding: 5px 12px;
  border-radius: 999px;
}
.kp {
  font-weight: 700;
}
.note {
  margin: 10px 0 0;
  font-size: 13px;
  opacity: 0.8;
  line-height: 1.6;
}
.sugg {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sugg li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-primary);
}
</style>
