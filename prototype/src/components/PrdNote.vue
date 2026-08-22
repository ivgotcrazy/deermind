<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const refs: Record<string, string> = {
  '/child/home': 'PRD §3.4 J3 · §4.1 首页 · §5.1~5.6 · 学习空间 §5.10',
  '/child/photo': 'PRD §5.1 错题拍照与 OCR',
  '/child/attribution': 'PRD §5.2 归因对话 · §8.2 决策树 · §5.10 范围护栏',
  '/child/reading': 'PRD §5.5 读题训练 · §8.6 · 归因=审题失误',
  '/child/explain': 'PRD §5.3 讲解（绑定教材+TTS）· §8.3 · §6.3',
  '/child/practice': 'PRD §5.4 基础练习（预置题库）',
  '/child/variant': 'PRD §5.4 变式验收 · §8.4 三不变一变 · 短期掌握',
  '/child/summary': 'PRD §5.6 间隔复习 · §6.1 掌握度状态机 · §9 指标',
  '/parent/spaces': 'PRD §5.10 学习空间 · J1 · §7 learning_space',
  '/parent/space-create': 'PRD §5.10 空间创建/教材绑定 · J1',
  '/parent/today': 'PRD §5.8 日报（中参与档）· J5 · 异常告警',
  '/parent/weekly': 'PRD §5.8 周报 · J5 · 三色掌握度',
}

const note = computed(() => refs[route.path] || '')
</script>

<template>
  <div v-if="note" class="prd-note">
    <span class="prd-tag">PRD 对照</span>
    <span>{{ note }}</span>
  </div>
</template>

<style scoped>
.prd-note {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--color-line);
  box-shadow: var(--shadow-md);
  font-size: 11px;
  color: var(--color-primary);
  pointer-events: none;
}
.prd-tag {
  flex-shrink: 0;
  background: var(--color-primary);
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 10px;
}
</style>
