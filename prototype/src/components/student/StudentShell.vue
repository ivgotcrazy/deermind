<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const route = useRoute()
const router = useRouter()
const showSpaces = ref(false)

const nav = [
  { to: '/student/home', icon: 'home', label: '今日' },
  { to: '/student/wrongbook', icon: 'bookmark', label: '错题' },
  { to: '/student/learn', icon: 'book', label: '学习' },
  { to: '/student/record', icon: 'clock', label: '记录' },
]

/* 全屏重流程（拍照/确认/讲题/读题/Teach-back/设置/登录）：隐藏壳层导航 */
const fullscreen = computed(() => route.meta.fullscreen === true)

function pickSpace(id: string) {
  store.switchSpace(id)
  showSpaces.value = false
}
</script>

<template>
  <div class="student-shell">
    <!-- 移动/平板：顶部空间切换 + 设置 -->
    <header v-if="!fullscreen" class="topbar">
      <div class="space-trigger" @click="showSpaces = !showSpaces">
        <Icon name="book" :size="16" />
        <span class="space-name">{{ store.activeSpace?.name ?? '学习空间' }}</span>
        <Icon name="chevronDown" :size="14" />
      </div>
      <div v-if="showSpaces" class="space-menu">
        <div class="space-head">我的学习空间</div>
        <div
          v-for="sp in store.ev.spaces"
          :key="sp.id"
          class="space-opt"
          :class="{ on: sp.id === store.activeSpaceId }"
          @click="pickSpace(sp.id)"
        >
          <div class="so-name">
            {{ sp.name }}
            <span v-if="sp.id === store.activeSpaceId" class="so-cur">当前</span>
          </div>
          <div class="so-meta">{{ sp.textbook }}</div>
          <div class="so-prog">当前：{{ sp.progress }}</div>
        </div>
      </div>
      <div class="spacer"></div>
      <button class="icon-btn" title="设置" @click="router.push('/student/settings')">
        <Icon name="settings" :size="20" />
      </button>
    </header>

    <!-- 移动/平板：底部 Tab -->
    <nav v-if="!fullscreen" class="tabbar">
      <RouterLink
        v-for="n in nav"
        :key="n.to"
        :to="n.to"
        class="tab"
        :class="{ active: route.path === n.to }"
      >
        <Icon :name="n.icon" :size="22" />
        <span>{{ n.label }}</span>
      </RouterLink>
    </nav>

    <!-- 桌面：左侧 Rail（含空间切换） -->
    <aside v-if="!fullscreen" class="rail">
      <div class="rail-brand" @click="showSpaces = !showSpaces">
        <Icon name="book" :size="18" />
        <span class="rail-space">{{ store.activeSpace?.name ?? '学习空间' }}</span>
        <Icon name="chevronDown" :size="14" />
      </div>
      <div v-if="showSpaces" class="space-menu rail-menu">
        <div class="space-head">我的学习空间</div>
        <div
          v-for="sp in store.ev.spaces"
          :key="sp.id"
          class="space-opt"
          :class="{ on: sp.id === store.activeSpaceId }"
          @click="pickSpace(sp.id)"
        >
          <div class="so-name">
            {{ sp.name }}
            <span v-if="sp.id === store.activeSpaceId" class="so-cur">当前</span>
          </div>
          <div class="so-meta">{{ sp.textbook }}</div>
          <div class="so-prog">当前：{{ sp.progress }}</div>
        </div>
      </div>

      <div class="rail-nav">
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
      </div>
      <div class="rail-foot">
        <button class="rail-item" @click="router.push('/student/settings')">
          <Icon name="settings" :size="18" />
          <span>设置</span>
        </button>
      </div>
    </aside>

    <!-- 内容区 -->
    <main class="body">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.student-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-background);
  position: relative;
}

/* ---------- 顶栏（移动/平板） ---------- */
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid var(--color-line);
  position: relative;
  z-index: 20;
}
.space-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 14px;
  padding: 7px 12px;
  border-radius: 14px;
  cursor: pointer;
  max-width: 70%;
}
.space-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.spacer {
  flex: 1;
}
.icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--color-text);
  opacity: 0.8;
}
.space-menu {
  position: absolute;
  top: 52px;
  left: 14px;
  min-width: 240px;
  background: #fff;
  border-radius: 16px;
  box-shadow: var(--shadow-clay);
  border: 3px solid rgba(79, 70, 229, 0.08);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 30;
}
.space-head {
  font-size: 11px;
  font-weight: 800;
  color: var(--color-secondary);
  padding: 4px 8px 2px;
}
.space-opt {
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
}
.space-opt.on {
  background: var(--color-primary-soft);
}
.so-name {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--color-text);
}
.so-cur {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: 999px;
  padding: 1px 7px;
  margin-left: 4px;
}
.so-meta {
  font-size: 11.5px;
  opacity: 0.7;
  margin-top: 2px;
}
.so-prog {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--color-primary);
  margin-top: 2px;
}

/* ---------- 底部 Tab（移动/平板） ---------- */
.tabbar {
  display: flex;
  border-top: 1px solid var(--color-line);
  background: #fff;
  padding: 6px 4px 8px;
  z-index: 10;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  text-decoration: none;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
}
.tab.active {
  color: var(--color-primary);
}

/* ---------- 左侧 Rail（桌面） ---------- */
.rail {
  display: none;
}

.body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.body > * {
  flex: 1;
  min-width: 0;
}

/* 桌面 / Pad：左 Rail + 右侧内容（产品以 Pad 为主，≥768px 起用 Rail） */
@media (min-width: 768px) {
  .student-shell {
    flex-direction: row;
  }
  .topbar,
  .tabbar {
    display: none;
  }
  .rail {
    display: flex;
    flex-direction: column;
    width: 200px;
    flex-shrink: 0;
    background: #fff;
    border-right: 1px solid var(--color-line);
    padding: 14px 12px;
    position: relative;
    z-index: 20;
  }
  .rail-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: var(--color-primary-soft);
    color: var(--color-primary);
    border-radius: 14px;
    font-family: var(--font-head);
    font-weight: 700;
    font-size: 13.5px;
    cursor: pointer;
  }
  .rail-space {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rail-menu {
    left: 12px;
    top: 66px;
  }
  .rail-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 14px;
  }
  .rail-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 12px;
    font-size: 13.5px;
    font-weight: 700;
    color: #64748b;
    text-decoration: none;
    cursor: pointer;
    border: 0;
    background: transparent;
    font-family: var(--font-body);
    text-align: left;
  }
  .rail-item:hover {
    background: var(--color-primary-soft);
  }
  .rail-item.active {
    background: var(--color-primary-soft);
    color: var(--color-primary);
  }
  .rail-foot {
    margin-top: auto;
    border-top: 1px solid var(--color-line);
    padding-top: 8px;
  }
}
</style>
