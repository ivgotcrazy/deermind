<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { parentSettings } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const tier = ref('low')
const daily = ref(parentSettings.dailyLimit)
const lock = ref(false)

function exportPdf() {
  alert('原型演示：导出学情报告（PDF）')
}
function deleteAll() {
  if (confirm('确定删除全部学习数据？此操作不可恢复。')) {
    alert('原型演示：全部数据已删除')
  }
}
function adjust(d: number) {
  daily.value = Math.max(10, Math.min(120, daily.value + d))
}
</script>

<template>
  <div class="settings">
    <h2 class="title">设置</h2>

    <!-- 参与度档位 -->
    <section class="card">
      <div class="sec-title">参与度档位</div>
      <div class="tiers">
        <button
          v-for="t in parentSettings.tierOptions"
          :key="t.id"
          class="tier"
          :class="{ on: tier === t.id }"
          @click="tier = t.id"
        >
          <span class="label">{{ t.label }}</span>
          <span class="desc">{{ t.desc }}</span>
        </button>
      </div>
    </section>

    <!-- 每日时长 -->
    <section class="card">
      <div class="sec-title">每日学习时长</div>
      <div class="stepper">
        <button class="icon-btn" @click="adjust(-5)"><Icon name="close" :size="18" /></button>
        <span class="value">{{ daily }} 分钟</span>
        <button class="icon-btn" @click="adjust(5)"><Icon name="plus" :size="18" /></button>
      </div>
    </section>

    <!-- 安全锁（预留） -->
    <section class="card">
      <div class="row">
        <span>启动安全锁（预留）</span>
        <input type="checkbox" v-model="lock" disabled />
      </div>
      <p class="hint">后续版本提供，用于防止孩子误开家长端。</p>
    </section>

    <!-- 数据管理 -->
    <section class="card">
      <div class="sec-title">数据管理</div>
      <div class="links">
        <button class="link" @click="router.push('/parent/memory')"><Icon name="sparkles" :size="16" /> 查看小鹿的记忆</button>
        <button class="link" @click="exportPdf"><Icon name="upload" :size="16" /> 导出学情报告（PDF）</button>
        <button class="link danger" @click="deleteAll"><Icon name="close" :size="16" /> 删除全部数据</button>
      </div>
    </section>

    <section class="card about">
      <div class="sec-title">关于</div>
      <p>呦鹿智伴 DeerMind · 家长端原型 v1.5<br />知你所短，伴你所长</p>
    </section>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 20px;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 12px;
}
.tiers {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tier {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  font-family: inherit;
  transition: all var(--ease-soft);
}
.tier.on {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.tier .label {
  font-weight: 700;
  font-size: 14px;
}
.tier .desc {
  font-size: 12px;
  opacity: 0.65;
}
.stepper {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stepper .value {
  font-weight: 800;
  font-size: 18px;
  min-width: 90px;
  text-align: center;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
}
.row input {
  accent-color: var(--color-primary);
  width: 18px;
  height: 18px;
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  opacity: 0.6;
}
.links {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--color-line);
  border-radius: 12px;
  background: #fff;
  font-size: 14px;
  font-family: inherit;
}
.link.danger {
  color: var(--color-danger);
  border-color: var(--color-danger-soft);
}
.about p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.8;
}
</style>
