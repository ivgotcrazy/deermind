<script setup lang="ts">
import { ref } from 'vue'
import { spaces } from '@/data/mock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const readAloud = ref(true)
const remind = ref(true)
const space = spaces[0]

const stats = [
  { label: '学习天数', value: '12 天' },
  { label: '连续打卡', value: '3 天' },
  { label: '已掌握知识点', value: '5 个' },
]
</script>

<template>
  <div class="profile">
    <h2 class="title">我的</h2>

    <!-- 档案卡 -->
    <section class="card hero">
      <DeerAvatar :size="72" />
      <div class="hero-info">
        <div class="name">小鹿的学伴</div>
        <div class="stats">
          <span v-for="s in stats" :key="s.label" class="stat"><b>{{ s.value }}</b>{{ s.label }}</span>
        </div>
      </div>
    </section>

    <!-- 设置 -->
    <section class="card">
      <div class="sec-title">设置</div>
      <label class="row">
        <span><Icon name="speaker" :size="18" /> 讲解朗读</span>
        <input type="checkbox" v-model="readAloud" />
      </label>
      <label class="row">
        <span><Icon name="calendar" :size="18" /> 放学学习提醒</span>
        <input type="checkbox" v-model="remind" />
      </label>
      <div class="row static"><span><Icon name="chart" :size="18" /> 每日目标时长</span><b>30 分钟</b></div>
    </section>

    <!-- 防沉迷 -->
    <section class="card guard">
      <div class="sec-title">护眼防沉迷</div>
      <p>每次学习 25 分钟会自动休息 5 分钟；达到每日时长后会锁定，休息好了再来～</p>
    </section>

    <!-- 当前空间 -->
    <section class="card">
      <div class="sec-title">当前学习空间</div>
      <div class="space">{{ space.name }}</div>
      <div class="space-prog">{{ space.progress.chapter }} · {{ space.progress.unit }}</div>
    </section>

    <section class="card about">
      <div class="sec-title">关于</div>
      <p>呦鹿智伴 DeerMind · 产品原型 v1.5<br />知你所短，伴你所长</p>
    </section>
  </div>
</template>

<style scoped>
.profile {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 20px;
}
.hero {
  display: flex;
  align-items: center;
  gap: 16px;
}
.hero-info .name {
  font-weight: 800;
  font-size: 17px;
  margin-bottom: 6px;
}
.stats {
  display: flex;
  gap: 14px;
  font-size: 12px;
  opacity: 0.75;
}
.stats b {
  display: block;
  font-size: 15px;
  color: var(--color-primary);
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-line);
}
.row:last-child {
  border-bottom: none;
}
.row span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.row input {
  accent-color: var(--color-primary);
  width: 18px;
  height: 18px;
}
.row.static b {
  color: var(--color-primary);
}
.guard {
  border-top: 4px solid var(--color-warning);
}
.guard p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}
.space {
  font-weight: 700;
}
.space-prog {
  font-size: 13px;
  opacity: 0.7;
}
.about p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.8;
}
</style>
