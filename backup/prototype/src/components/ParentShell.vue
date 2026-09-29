<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import Icon from './Icon.vue'
import PrdNote from './PrdNote.vue'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const nav = [
  { to: '/parent/today', icon: 'calendar', label: '今日' },
  { to: '/parent/weekly', icon: 'chart', label: '周报' },
  { to: '/parent/students', icon: 'user', label: '学生' },
  { to: '/parent/spaces', icon: 'doc', label: '空间' },
]

function exitToChild() {
  store.setMode('child')
  router.push('/student/home')
}
</script>

<template>
  <div class="parent-shell">
    <PrdNote v-if="store.prdNote" />
    <header class="top">
      <div class="brand">
        <span class="badge">家长端</span>
      </div>
      <button class="exit" @click="exitToChild">
        <Icon name="back" :size="16" /> 返回孩子端
      </button>
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
        <Icon :name="n.icon" :size="22" />
        <span>{{ n.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.parent-shell {
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
  justify-content: space-between;
  padding: 12px 14px 8px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.badge {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--color-primary);
  padding: 4px 12px;
  border-radius: 999px;
}
.tier {
  font-size: 12px;
  color: var(--color-text);
  opacity: 0.75;
}
.exit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
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
  border-top: 1px solid var(--color-line);
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
  font-weight: 600;
  border-radius: 10px;
  transition: color var(--ease-soft);
}
.tab.active {
  color: var(--color-primary);
}

/* 平板/桌面：导航切换为左侧 Rail */
@media (min-width: 768px) {
  .parent-shell {
    grid-template-areas: 'top top' 'nav body';
    grid-template-columns: 96px 1fr;
    grid-template-rows: auto 1fr;
  }
  .tabbar {
    flex-direction: column;
    border-top: none;
    border-right: 1px solid var(--color-line);
    padding: 12px 6px;
    gap: 4px;
  }
  .tab {
    padding: 10px 4px;
  }
}
</style>
