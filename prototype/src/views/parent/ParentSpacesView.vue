<script setup lang="ts">
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const ev = useEvidenceStore()

function createSpace() {
  alert('原型演示：新建学习空间（绑定教材 → 自动派生知识点集）')
}
</script>

<template>
  <div class="spaces">
    <h2 class="title">学习空间 <span class="demo">{{ DEMO_NOTE }}</span></h2>

    <p class="intro">每个空间绑定一套教材，知识点集由教材映射自动派生（范围护栏）。空间只由家长端创建。</p>

    <section v-for="sp in ev.spaces" :key="sp.id" class="card">
      <div class="sp-head">
        <div class="sp-name">{{ sp.name }}</div>
        <span class="pill" :class="sp.status === 'active' ? 'ok' : 'off'">
          {{ sp.status === 'active' ? '进行中' : '已归档' }}
        </span>
      </div>
      <div class="row">
        <span class="k">学生</span>
        <span class="v">{{ sp.studentName }}</span>
      </div>
      <div class="row">
        <span class="k">教材</span>
        <span class="v">{{ sp.textbook }}</span>
      </div>
      <div class="row">
        <span class="k">进度</span>
        <span class="v">{{ sp.progress }}</span>
      </div>
      <div class="row">
        <span class="k">知识点集</span>
        <span class="v">绑定 {{ sp.boundKp }} · 追踪 {{ sp.trackedKp }}（追踪集 ⊆ 知识点集）</span>
      </div>
    </section>

    <button class="btn btn-indigo btn-block" @click="createSpace">
      <Icon name="plus" :size="18" /> 新建学习空间
    </button>
  </div>
</template>

<style scoped>
.spaces {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 19px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.demo {
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: 999px;
}
.intro {
  margin: 0;
  font-size: 13px;
  opacity: 0.75;
  line-height: 1.6;
}
.sp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.sp-name {
  font-weight: 800;
  font-size: 15px;
}
.pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
}
.pill.ok {
  background: var(--color-cta-soft);
  color: #15803d;
}
.pill.off {
  background: #f1f5f9;
  color: #64748b;
}
.row {
  display: flex;
  gap: 8px;
  padding: 5px 0;
  font-size: 13.5px;
  border-top: 1px dashed var(--color-line);
}
.k {
  width: 64px;
  flex-shrink: 0;
  opacity: 0.6;
  font-weight: 600;
}
.v {
  flex: 1;
}
</style>
