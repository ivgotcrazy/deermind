<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { spaces } from '@/data/mock'
import Icon from './Icon.vue'
import DeerAvatar from './DeerAvatar.vue'
import PrdNote from './PrdNote.vue'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const space = computed(() => spaces.find((s) => s.id === store.activeSpaceId) ?? spaces[0])
const isHome = computed(() => route.path === '/child/home')

const nav = [
  { to: '/child/home', icon: 'home', label: '首页' },
  { to: '/child/photo', icon: 'camera', label: '拍题' },
  { to: '/child/summary', icon: 'chart', label: '进度' },
  { to: '/child/home', icon: 'user', label: '我的' },
]

function goBack() {
  router.back()
}
</script>

<template>
  <div class="child-shell">
    <PrdNote v-if="store.prdNote" />
    <header class="top">
      <button v-if="!isHome" class="icon-btn" aria-label="返回" @click="goBack">
        <Icon name="back" :size="20" />
      </button>
      <div v-else class="avatar-wrap"><DeerAvatar :size="40" /></div>
      <div class="space-info">
        <div class="space-name">{{ space.name }}</div>
        <div class="space-progress">
          <span class="dot dot-amber"></span> {{ space.progress.chapter }}
        </div>
      </div>
      <div class="top-right">
        <span class="streak">3 天</span>
      </div>
    </header>

    <main class="body">
      <div class="inner">
        <RouterView />
      </div>
    </main>

    <nav class="tabbar">
      <RouterLink
        v-for="n in nav"
        :key="n.label"
        :to="n.to"
        class="tab"
        :class="{ active: route.path === n.to }"
      >
        <Icon :name="n.icon" :size="24" />
        <span>{{ n.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.child-shell {
  height: 100%;
  display: grid;
  grid-template-areas: 'top' 'body' 'nav';
  grid-template-rows: auto 1fr auto;
  background: var(--color-background);
  position: relative;
}
.top {
  grid-area: top;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px 8px;
}
.avatar-wrap {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.space-info {
  flex: 1;
  min-width: 0;
}
.space-name {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 15px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.space-progress {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  opacity: 0.75;
  margin-top: 2px;
}
.top-right .streak {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 13px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: 4px 10px;
  border-radius: 999px;
}
.body {
  grid-area: body;
  overflow-y: auto;
  padding: 6px 14px 14px;
}
.inner {
  max-width: 1040px;
  margin: 0 auto;
  width: 100%;
}
.tabbar {
  grid-area: nav;
  display: flex;
  border-top: 2px solid rgba(79, 70, 229, 0.08);
  background: #fff;
  padding: 6px 4px 8px;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 0;
  text-decoration: none;
  color: #9CA3AF;
  font-size: 11px;
  font-weight: 700;
  border-radius: 12px;
  transition: color var(--ease-soft);
}
.tab.active {
  color: var(--color-primary);
}

/* 平板/桌面：导航切换为左侧 Rail（Material 3 模式） */
@media (min-width: 768px) {
  .child-shell {
    grid-template-areas: 'top top' 'nav body';
    grid-template-columns: 96px 1fr;
    grid-template-rows: auto 1fr;
  }
  .tabbar {
    flex-direction: column;
    border-top: none;
    border-right: 2px solid rgba(79, 70, 229, 0.08);
    padding: 12px 6px;
    gap: 4px;
  }
  .tab {
    padding: 10px 4px;
  }
}
</style>
