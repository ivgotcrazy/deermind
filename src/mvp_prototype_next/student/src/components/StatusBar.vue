<script setup lang="ts">
import { computed } from 'vue';
import type { LearningState } from '../types';

const props = defineProps<{ state: LearningState; chatCollapsed: boolean }>();
const emit = defineEmits<{ toggleChat: []; updateProgress: [] }>();

const masteryColor = computed(() => {
  const p = props.state.masteryPercent;
  if (p >= 80) return '#2d8a5e';
  if (p >= 50) return '#c9942a';
  return '#b85c3c';
});
</script>

<template>
  <header class="status-bar">
    <div class="status-left">
      <div class="brand"><span class="brand-icon">🦌</span><span class="brand-name">DeerMind</span></div>
      <div class="divider"></div>
      <div class="chapter-info">
        <span class="chapter-label">当前章节</span>
        <span class="chapter-title">{{ state.chapterTitle }}</span>
      </div>
    </div>
    <div class="status-right">
      <div class="mastery">
        <span class="mastery-label">掌握度</span>
        <div class="mastery-bar"><div class="mastery-fill" :style="{ width: state.masteryPercent + '%', background: masteryColor }"></div></div>
        <span class="mastery-value">{{ state.masteryPercent }}%</span>
      </div>
      <div class="classroom" @click="emit('updateProgress')">
        <span class="classroom-label">学校进度</span>
        <span class="classroom-value">{{ state.classroomProgress }}</span>
        <span class="classroom-edit">更新</span>
      </div>
      <button class="chat-toggle" @click="emit('toggleChat')" :title="chatCollapsed ? '展开聊天' : '收起聊天'">
        <span v-if="chatCollapsed">💬 展开聊天</span>
        <span v-else>💬 收起</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.status-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 20px; background: linear-gradient(135deg, #1a3a2e 0%, #244c40 100%); color: #e8f0ec; border-bottom: 1px solid #2d5a4a; flex-shrink: 0; gap: 16px; }
.status-left { display: flex; align-items: center; gap: 16px; min-width: 0; }
.brand { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.brand-icon { font-size: 20px; }
.brand-name { font-weight: 600; font-size: 15px; letter-spacing: 0.3px; }
.divider { width: 1px; height: 24px; background: rgba(255,255,255,0.15); }
.chapter-info { display: flex; flex-direction: column; cursor: pointer; padding: 4px 10px; border-radius: 6px; transition: background 0.15s; min-width: 0; }
.chapter-info:hover { background: rgba(255,255,255,0.08); }
.chapter-label { font-size: 10px; color: #8fb3a3; line-height: 1.2; }
.chapter-title { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
.status-right { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.mastery { display: flex; align-items: center; gap: 8px; padding: 4px 10px; border-radius: 6px; }
.mastery-label { font-size: 11px; color: #8fb3a3; }
.mastery-bar { width: 80px; height: 6px; background: rgba(255,255,255,0.15); border-radius: 3px; overflow: hidden; }
.mastery-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.mastery-value { font-size: 12px; font-weight: 600; min-width: 32px; }
.classroom { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 10px; border-radius: 6px; transition: background 0.15s; }
.classroom:hover { background: rgba(255,255,255,0.08); }
.classroom-label { font-size: 11px; color: #8fb3a3; }
.classroom-value { font-size: 12px; font-weight: 500; max-width: 100px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.classroom-edit { font-size: 10px; color: #a8d4c0; text-decoration: underline; text-underline-offset: 2px; }
.chat-toggle { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); color: #e8f0ec; padding: 5px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
.chat-toggle:hover { background: rgba(255,255,255,0.2); }
@media (max-width: 900px) {
  .status-bar { padding: 8px 12px; flex-wrap: wrap; gap: 8px; }
  .chapter-title { max-width: 120px; }
  .mastery-bar { width: 50px; }
  .classroom-value { max-width: 70px; }
  .brand-name { display: none; }
}
</style>
