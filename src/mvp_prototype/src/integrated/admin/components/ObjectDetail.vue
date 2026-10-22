<script setup lang="ts">
import { computed } from 'vue';
import { semanticObjects } from '../data';

const props = defineProps<{ objectId: string }>();
const emit = defineEmits<{ back: []; goTrace: [traceId: string] }>();

const obj = computed(() => semanticObjects.find(o => o.id === props.objectId));

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  committed: { label: '已承诺', color: '#2d8a5e', bg: '#e8f5ee' },
  rejected: { label: '已拒绝', color: '#b85c3c', bg: '#fdf0ed' },
  superseded: { label: '已取代', color: '#8a99a8', bg: '#f0f4f7' },
};
</script>

<template>
  <div class="object-detail" v-if="obj">
    <div class="detail-topbar">
      <button class="back-btn" @click="emit('back')">← 返回列表</button>
      <span class="obj-id mono">{{ obj.id }}</span>
      <span class="obj-summary">{{ obj.summary }}</span>
      <span class="obj-status" :style="{ color: statusConfig[obj.status].color, background: statusConfig[obj.status].bg }">
        {{ statusConfig[obj.status].label }}
      </span>
    </div>

    <div class="detail-body">
      <!-- 基本信息 -->
      <div class="section">
        <h3>基本信息</h3>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">类型</span><span class="info-value">{{ obj.subType }}</span></div>
          <div class="info-item"><span class="info-label">学生</span><span class="info-value">{{ obj.studentName }}</span></div>
          <div class="info-item"><span class="info-label">当前版本</span><span class="info-value">v{{ obj.currentVersion }}</span></div>
          <div class="info-item"><span class="info-label">创建时间</span><span class="info-value">{{ obj.createdAt }}</span></div>
        </div>
      </div>

      <!-- 当前内容 -->
      <div class="section">
        <h3>当前内容 (v{{ obj.currentVersion }})</h3>
        <pre class="content-block">{{ obj.versions[0].content }}</pre>
      </div>

      <!-- 版本历史 -->
      <div class="section">
        <h3>版本历史</h3>
        <div class="version-list">
          <div v-for="(v, i) in obj.versions" :key="v.version" class="version-item" :class="{ current: i === 0 }">
            <div class="version-header">
              <span class="version-tag">v{{ v.version }}</span>
              <span v-if="i === 0" class="current-badge">当前</span>
              <span class="version-date">{{ v.date }}</span>
            </div>
            <p class="version-change">{{ v.change }}</p>
            <div class="version-trace">
              <span>关联 Trace:</span>
              <button class="trace-link" @click="emit('goTrace', v.traceId)">{{ v.traceId }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 被引用情况 -->
      <div class="section" v-if="obj.referencedBy.length > 0">
        <h3>被引用情况</h3>
        <div class="ref-list">
          <div v-for="ref in obj.referencedBy" :key="ref.id" class="ref-item">
            <span class="ref-type">{{ ref.type }}</span>
            <span class="ref-id mono">{{ ref.id }}</span>
            <span class="ref-label">{{ ref.label }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else style="padding:24px"><h2>{{ objectId }}</h2><p>当前示例只准备了列表信息，尚无这个对象的详细版本与引用记录。</p><button @click="emit('back')">返回列表</button></div>
</template>

<style scoped>
.object-detail { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.detail-topbar { display: flex; align-items: center; gap: 12px; padding: 12px 20px; background: white; border-bottom: 1px solid #e1e8ed; flex-shrink: 0; }
.back-btn { background: none; border: none; color: #2d6a4f; font-size: 13px; cursor: pointer; font-family: inherit; font-weight: 500; padding: 4px 8px; border-radius: 4px; }
.back-btn:hover { background: #f0f7f3; }
.obj-id { font-size: 12px; color: #5a6b7a; background: #f0f4f7; padding: 3px 8px; border-radius: 4px; }
.obj-summary { font-size: 14px; font-weight: 600; color: #2c3e50; flex: 1; }
.obj-status { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.mono { font-family: Consolas, Monaco, monospace; }
.detail-body { flex: 1; overflow-y: auto; padding: 20px 24px; }
.section { margin-bottom: 24px; }
.section h3 { margin: 0 0 12px 0; font-size: 14px; color: #1a3a2e; padding-bottom: 8px; border-bottom: 1px solid #e1e8ed; }
.info-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: 11px; color: #8a99a8; text-transform: uppercase; }
.info-value { font-size: 13px; color: #2c3e50; font-weight: 500; }
.content-block { background: #1e293b; color: #a5d6a7; padding: 16px; border-radius: 8px; font-size: 12px; line-height: 1.7; overflow-x: auto; margin: 0; }
.version-list { display: flex; flex-direction: column; gap: 10px; }
.version-item { background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 12px 16px; }
.version-item.current { border-color: #2d6a4f; background: #f0f7f3; }
.version-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.version-tag { font-weight: 700; color: #2d6a4f; font-size: 13px; }
.current-badge { background: #2d6a4f; color: white; padding: 1px 8px; border-radius: 8px; font-size: 10px; font-weight: 600; }
.version-date { font-size: 12px; color: #8a99a8; margin-left: auto; }
.version-change { margin: 0 0 8px 0; font-size: 13px; color: #3a4a5a; }
.version-trace { font-size: 12px; color: #5a6b7a; display: flex; align-items: center; gap: 6px; }
.trace-link { background: none; border: none; color: #2d6a4f; cursor: pointer; font-family: Consolas, Monaco, monospace; font-size: 12px; text-decoration: underline; padding: 0; }
.ref-list { display: flex; flex-direction: column; gap: 8px; }
.ref-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: #f7f9fa; border-radius: 6px; }
.ref-type { font-size: 11px; background: #e8f0f8; color: #3a5a7a; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; font-weight: 600; }
.ref-id { font-size: 12px; color: #5a6b7a; }
.ref-label { font-size: 13px; color: #2c3e50; }
</style>
