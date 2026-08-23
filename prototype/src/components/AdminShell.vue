<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import Icon from './Icon.vue'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const nav = [
  { to: '/admin', icon: 'chart', label: 'Dashboard' },
  { to: '/admin/knowledge', icon: 'doc', label: '知识点' },
  { to: '/admin/decisions', icon: 'sparkles', label: '决策理由' },
  { to: '/admin/rules', icon: 'settings', label: '规则配置' },
]

function exitToStudent() {
  store.setMode('child')
  router.push('/student/home')
}
</script>

<template>
  <div class="admin-shell">
    <header class="top">
      <div class="brand">
        <span class="badge">管理员端</span>
        <span class="sub">Evidence Debugger · 只读调试</span>
      </div>
      <button class="exit" @click="exitToStudent">
        <Icon name="back" :size="16" /> 返回学生端
      </button>
    </header>

    <div class="body">
      <aside class="rail">
        <RouterLink
          v-for="n in nav"
          :key="n.to"
          :to="n.to"
          class="rail-item"
          :class="{ active: route.path === n.to }"
        >
          <Icon :name="n.icon" :size="18" />
          <span>{{ n.label }}</span>
        </RouterLink>
      </aside>

      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-background);
}
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.badge {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: var(--color-primary);
  padding: 4px 12px;
  border-radius: 6px;
  letter-spacing: 0.02em;
}
.sub {
  font-size: 12px;
  color: #64748b;
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
  cursor: pointer;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.rail {
  width: 168px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 10px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
}
.rail-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  text-decoration: none;
  transition: background 0.15s ease;
}
.rail-item:hover {
  background: #f1f5f9;
}
.rail-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  min-width: 0;
}

/* <768px：导航折叠为顶部横向 Tab */
@media (max-width: 768px) {
  .body {
    flex-direction: column;
  }
  .rail {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
    padding: 8px 10px;
  }
  .rail-item {
    white-space: nowrap;
    flex-shrink: 0;
  }
}
</style>
