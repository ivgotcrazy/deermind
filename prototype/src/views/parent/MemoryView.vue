<script setup lang="ts">
import { ref } from 'vue'
import { memoryItems, type MemoryItem } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const items = ref<MemoryItem[]>([...memoryItems])
const tab = ref<'全部' | '事实' | '偏好' | '状态'>('全部')
const tabs: ('全部' | '事实' | '偏好' | '状态')[] = ['全部', '事实', '偏好', '状态']

const list = () => (tab.value === '全部' ? items.value : items.value.filter((i) => i.type === tab.value))
const typePill = (t: string) =>
  t === '事实' ? 'pill-mastered' : t === '偏好' ? 'pill-inprogress' : 'pill-focus'

function remove(id: string) {
  items.value = items.value.filter((i) => i.id !== id)
}
</script>

<template>
  <div class="memory">
    <h2 class="title">小鹿的记忆</h2>
    <p class="sub">从每次对话中提炼，让小鹿越来越懂女儿；可随时删除</p>

    <div class="tabs">
      <button v-for="t in tabs" :key="t" class="chip" :class="{ on: tab === t }" @click="tab = t">{{ t }}</button>
    </div>

    <div class="list">
      <section v-for="m in list()" :key="m.id" class="card item">
        <div class="top">
          <span class="pill" :class="typePill(m.type)">{{ m.type }}</span>
          <button class="icon-btn sm" title="删除" @click="remove(m.id)"><Icon name="close" :size="16" /></button>
        </div>
        <p class="content">{{ m.content }}</p>
        <div class="meta">
          <span>{{ m.source }} · {{ m.time }}</span>
          <span class="conf">置信度 {{ Math.round(m.confidence * 100) }}%</span>
        </div>
      </section>
    </div>

    <p v-if="!list().length" class="empty">暂无记忆，多和女儿一起学习吧</p>
  </div>
</template>

<style scoped>
.memory {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.sub {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.7;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 2px solid var(--color-line);
  background: #fff;
  color: var(--color-text);
}
.chip.on {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item .top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.pill {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.icon-btn.sm {
  width: 30px;
  height: 30px;
  border-radius: 8px;
}
.content {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.6;
}
.meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  opacity: 0.6;
}
.empty {
  text-align: center;
  font-size: 13px;
  opacity: 0.5;
  padding: 20px;
}
</style>
