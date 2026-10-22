<script setup lang="ts">
import { computed } from 'vue';
import { sessionsForSpace, catalogForSpace } from '../workspace';
import type { Session } from '../../../structure/state';
import ClassroomProgress from '../../../structure/ClassroomProgress.vue';
const props = defineProps<{space:string}>();
const emit = defineEmits<{continueLearning:[session?:Session];startAction:[text:string,chapter?:string];navigate:[page:'status'];history:[]}>();
const sessions = computed(() => sessionsForSpace(props.space));
const recent = computed(() => sessions.value.find(s=>s.real));
const stats = computed(() => [
 {label:'已保存对话',value:String(sessions.value.filter(s=>s.real).length),icon:'💬'},
 {label:'交流记录',value:String(sessions.value.filter(s=>s.real).reduce((n,s)=>n+(s.realTurns||0),0)),icon:'📝'},
 {label:'学习用时',value:'未统计',icon:'⏱️'}, {label:'已确认错题',value:'待评价',icon:'📚'},
]);
const dimensions = ['独立完成','理解与解释','迁移应用','延迟保持'];
</script>
<template><div class="home-page">
 <div class="space-header"><div class="space-info"><span class="space-icon">🔢</span><div><h2>{{ space==='school'?'数学 · 北师大版六年级上册':'校外数学' }}</h2><span class="space-sub">当前学习空间</span></div></div><ClassroomProgress learner="S0001" :space="space" :catalog="catalogForSpace(space)"/></div>
 <div class="stats-card"><div class="stats-header"><span class="stats-title-icon">📊</span><span class="stats-header-title">学习统计</span><span class="stats-updated">本空间累计</span></div><div class="stats-grid"><div v-for="s in stats" :key="s.label" class="stat-card"><span class="stat-icon">{{ s.icon }}</span><span class="stat-value">{{ s.value }}</span><span class="stat-label">{{ s.label }}</span></div></div><p class="data-caption">对话与消息按实际记录计数；每天总使用时间不超过 30 分钟。</p></div>
 <div class="target-assessment-card"><div class="ta-header"><span class="ta-title-icon">🎯</span><span class="ta-header-title">当前学习目标评估</span><button @click="emit('navigate','status')">查看详情 →</button></div><div class="ta-main"><div class="ta-target-row"><span class="ta-target-name">{{ space==='school'?'分数的应用':'教材待准备' }}</span><span class="ta-status-badge" style="color:#6b7a8a;background:#f0f3f6">待评价</span></div><p class="ta-meta">实际对话已保存，正式学习评价尚未接入。</p></div><div class="ta-dimensions"><div v-for="d in dimensions" :key="d" class="ta-dim-item"><div class="ta-dim-top"><span class="ta-dim-icon">?</span><span class="ta-dim-label">{{ d }}</span></div><div class="ta-dim-bottom"><span class="ta-dim-status">尚无正式判断</span></div></div></div></div>
 <div class="task-card"><div class="task-header"><span class="task-title-icon">📋</span><span class="task-header-title">接下来学什么</span><button @click="emit('history')">对话历史</button></div><div class="task-list">
 <button v-if="recent" class="task-item task-primary" @click="emit('continueLearning',recent)"><span class="task-icon">▶️</span><span class="task-content"><span class="task-tag">继续学习</span><span class="task-title">分数的应用</span><span class="task-desc">{{ recent.date }} · 对话与未提交输入已保留</span></span><span class="task-arrow">→</span></button>
 <button v-if="space==='school'" class="task-item" @click="emit('startAction','我想学懂分数的应用，请先帮我确定一个合适的开始点。','fractions')"><span class="task-icon">📖</span><span class="task-content"><span class="task-title">聊聊分数的应用</span><span class="task-desc">讲解、追问和练习在左侧连续展开</span></span><span class="task-arrow">→</span></button>
 <p v-else class="data-caption">校外教材尚未准备。本空间不会借用校内的个人记录。</p>
 </div></div>
</div></template>

<style scoped>
.home-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.space-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.space-info { display: flex; align-items: center; gap: 12px; }
.space-icon { font-size: 32px; }
.space-info h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.space-sub { font-size: 12px; color: #8a99a8; }
.classroom-progress {
  display: flex; align-items: center; gap: 10px;
  background: #f0f7f4; border: 1px solid #c8e0d4;
  padding: 8px 14px; border-radius: 8px;
}
.cp-label { font-size: 12px; color: #5a7a6a; }
.cp-chapter { font-size: 13px; font-weight: 600; color: #1b4332; }
.cp-update {
  background: none; border: 1px solid #2d6a4f; color: #2d6a4f;
  padding: 3px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.cp-update:hover { background: #2d6a4f; color: white; }

/* ===== 待完成任务卡片 ===== */
.task-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.task-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.task-title-icon { font-size: 18px; }
.task-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.task-count { font-size: 11px; color: #8a99a8; background: #f0f4f2; padding: 2px 8px; border-radius: 10px; }

.task-list { display: flex; flex-direction: column; gap: 10px; }
.task-item {
  display: flex; align-items: center; gap: 14px;
  background: #fafcfb; border: 1px solid #e8ede9; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; transition: all 0.2s;
}
.task-item:hover { border-color: #2d6a4f; background: #f0f7f3; box-shadow: 0 2px 8px rgba(45,106,79,0.08); }
.task-item.task-primary {
  background: linear-gradient(135deg, #f0f7f3, #e8f5ee);
  border-color: #b8d8c4;
}
.task-item.task-primary:hover { background: linear-gradient(135deg, #e8f5ee, #d4edda); }
.task-icon { font-size: 22px; flex-shrink: 0; }
.task-content { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.task-top { display: flex; align-items: center; gap: 8px; }
.task-tag { font-size: 11px; font-weight: 600; color: #5a7a6a; background: #e0f0e8; padding: 2px 8px; border-radius: 4px; }
.task-priority { font-size: 10px; font-weight: 600; color: #b85c3c; background: #fdf0eb; padding: 2px 6px; border-radius: 4px; }
.task-title { font-size: 15px; font-weight: 700; color: #1a3a2e; }
.task-desc { font-size: 12px; color: #8a99a8; }
.task-arrow { font-size: 18px; color: #8a99a8; flex-shrink: 0; }
.task-item:hover .task-arrow { color: #2d6a4f; }

/* ===== 当前学习目标评估卡片 ===== */
.target-assessment-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.ta-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.ta-title-icon { font-size: 18px; }
.ta-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.ta-updated { font-size: 11px; color: #8a99a8; }

.ta-main { margin-bottom: 12px; }
.ta-target-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.ta-target-name { font-size: 17px; font-weight: 700; color: #1a3a2e; }
.ta-status-badge {
  font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 12px;
}
.ta-meta { font-size: 11px; color: #8a99a8; }

.ta-evidence-row {
  display: flex; align-items: center; gap: 6px;
  background: #f7faf8; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 14px;
  font-size: 12px;
}
.ta-evidence-label { color: #5a7a6a; font-weight: 600; margin-right: 4px; }
.ta-evidence-positive { color: #2d6a4f; font-weight: 600; }
.ta-evidence-negative { color: #b85c3c; font-weight: 600; }
.ta-evidence-pending { color: #8a6a2a; font-weight: 600; }
.ta-evidence-conflict { color: #c0392b; font-weight: 700; }
.ta-evidence-divider { color: #c0c8d0; }

.ta-dimensions {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
}
.ta-dim-item {
  background: #fafcfb; border: 1px solid #e8ede9; border-radius: 8px;
  padding: 10px 12px;
}
.ta-dim-top {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 6px;
}
.ta-dim-icon {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}
.ta-dim-label { font-size: 12px; font-weight: 600; color: #2c3e50; }
.ta-dim-bottom {
  display: flex; flex-direction: column; gap: 1px;
  padding-left: 28px;
}
.ta-dim-status { font-size: 11px; font-weight: 600; }
.ta-dim-evidence { font-size: 10px; color: #8a99a8; }

/* ===== 学习统计卡片 ===== */
.stats-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.stats-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.stats-title-icon { font-size: 18px; }
.stats-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.stats-updated { font-size: 11px; color: #8a99a8; background: #f0f4f2; padding: 2px 8px; border-radius: 10px; }

.stats-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
}
.stat-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 10px;
  padding: 14px; display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.stat-icon { font-size: 18px; }
.stat-value { font-size: 18px; font-weight: 700; color: #1a3a2e; }
.stat-label { font-size: 11px; color: #8a99a8; }

.section { margin-bottom: 20px; }
.section h3 { margin: 0 0 12px 0; font-size: 14px; color: #1a3a2e; }

.trend-bars {
  display: flex; justify-content: space-around; align-items: flex-end;
  height: 120px; background: white; border: 1px solid #e1e8ed;
  border-radius: 10px; padding: 16px;
}
.trend-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; }
.trend-bar-wrap { height: 60px; display: flex; align-items: flex-end; }
.trend-bar { width: 24px; background: linear-gradient(180deg, #52b788, #2d6a4f); border-radius: 4px 4px 0 0; min-height: 4px; }
.trend-value { font-size: 11px; font-weight: 600; color: #2c3e50; }
.trend-date { font-size: 10px; color: #8a99a8; }

.weak-list { display: flex; flex-direction: column; gap: 8px; }
.weak-item {
  display: flex; justify-content: space-between; align-items: center;
  background: #fef5f0; border: 1px solid #f0d0c0; border-radius: 8px;
  padding: 12px 14px;
}
.weak-info { display: flex; flex-direction: column; gap: 2px; }
.weak-name { font-size: 13px; font-weight: 600; color: #8a3a1a; }
.weak-reason { font-size: 11px; color: #a06a5a; }
.weak-mastery { font-size: 16px; font-weight: 700; color: #b85c3c; }

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
  .secondary-actions { grid-template-columns: 1fr; }
}

.space-header{flex-wrap:wrap;gap:12px}.space-info h2{font-size:17px}.space-header :deep(.classroom-context){margin:0;max-width:100%;background:#f0f7f4;border:1px solid #c8e0d4;padding:8px 12px;border-radius:8px}.space-header :deep(.classroom-value){font-weight:600;color:#1b4332}.space-header :deep(button){color:#2d6a4f;border:1px solid #b8d4c2;border-radius:5px;background:white;font-size:12px;padding:5px 10px}
.task-item{width:100%;text-align:left;font-family:inherit}.data-caption{font-size:11px;color:#809084;margin-top:12px;line-height:1.6}.ta-header button,.task-header button{font-size:12px;border:0;background:none;color:#2d6a4f;cursor:pointer}.ta-dimensions{grid-template-columns:repeat(4,minmax(0,1fr))}.ta-dim-label{overflow-wrap:anywhere}.ta-dim-status{color:#7b8981}.home-page{min-width:0;container-type:inline-size}.stats-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.stat-value{font-size:22px}.stat-label{font-size:11px}
@container(max-width:520px){.ta-dimensions{grid-template-columns:repeat(2,minmax(0,1fr))}.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.space-header{align-items:flex-start}.space-info h2{font-size:15px}.ta-header{flex-wrap:wrap}.ta-header-title{font-size:13px}.ta-target-name{font-size:16px}.stat-value{font-size:20px}}

</style>
