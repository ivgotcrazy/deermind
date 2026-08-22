<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { spaces, type Space } from '@/data/mock'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const list = ref<Space[]>(spaces)

const typeLabel = (t: string) => (t === 'school' ? '学校' : '辅导班')
</script>

<template>
  <div class="spaces">
    <h2 class="title">学习空间</h2>
    <p class="sub">每个空间绑定教材、维护进度，小鹿在空间内辅导</p>

    <div class="list">
      <button
        v-for="s in list"
        :key="s.id"
        class="card space"
        :style="{ '--sc': s.color }"
        @click="router.push('/parent/today')"
      >
        <div class="space-top">
          <span class="type">{{ typeLabel(s.type) }}</span>
          <span class="sem">{{ s.semester }}</span>
        </div>
        <div class="space-name">{{ s.name }}</div>
        <div class="books">
          <span v-for="b in s.textbooks" :key="b.name" class="book">{{ b.name }}</span>
        </div>
        <div class="prog">
          <span class="dot dot-amber"></span>
          {{ s.progress.chapter }} · {{ s.progress.unit }}
        </div>
      </button>
    </div>

    <button class="btn btn-primary btn-block" @click="router.push('/parent/space-create')">
      <Icon name="plus" :size="18" /> 新建学习空间
    </button>
    <p class="hint">报辅导班后可再建一个空间，独立绑定教材与进度</p>
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
  font-size: 20px;
}
.sub {
  margin: -6px 0 0;
  font-size: 13px;
  opacity: 0.75;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.space {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-left: 5px solid var(--sc);
  width: 100%;
  font-family: inherit;
}
.space-top {
  display: flex;
  justify-content: space-between;
}
.type {
  font-size: 12px;
  font-weight: 700;
  color: var(--sc);
  background: color-mix(in srgb, var(--sc) 12%, white);
  padding: 2px 10px;
  border-radius: 999px;
}
.sem {
  font-size: 12px;
  opacity: 0.6;
}
.space-name {
  font-weight: 800;
  font-size: 16px;
}
.books {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.book {
  font-size: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: 8px;
}
.prog {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  opacity: 0.85;
}
.hint {
  margin: 0;
  text-align: center;
  font-size: 12px;
  opacity: 0.6;
}
</style>
