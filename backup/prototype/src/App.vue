<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useEvidenceStore } from '@/stores/evidence'
import { useStudentChat } from '@/stores/studentChat'
import Icon from '@/components/Icon.vue'
import DeerAvatar from '@/components/DeerAvatar.vue'

const store = useAppStore()
const ev = useEvidenceStore()
const chat = useStudentChat()
const router = useRouter()

function goStudent() {
  store.setMode('child')
  router.push('/student/home')
}
function goParent() {
  store.setMode('parent')
  router.push('/parent/today')
}
function goAdmin() {
  store.setMode('admin')
  router.push('/admin')
}
function onReset() {
  store.resetAll()
  ev.resetAll() // 三端共享证据状态一并重置
  chat.logout() // 清空学生端对话，回到登录页，演示可重跑
  router.push('/student/login')
}

/* 响应式断点指示（手机 / 平板） */
const bp = ref('手机')
const bpClass = computed(() =>
  bp.value.startsWith('手机') ? 'is-mobile' : bp.value.startsWith('平板竖屏') ? 'is-tablet' : 'is-wide',
)
function measure() {
  const w = window.innerWidth
  bp.value = w < 640 ? '手机' : w < 1024 ? '平板竖屏' : '平板横屏/桌面'
}
onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
})
onBeforeUnmount(() => window.removeEventListener('resize', measure))
</script>

<template>
  <div
    class="app"
    :class="{
      'child-mode': store.mode === 'child',
      'parent-mode': store.mode === 'parent',
      'admin-mode': store.mode === 'admin',
    }"
  >
    <!-- 顶部工具栏（响应式） -->
    <header class="toolbar">
      <div class="brand">
        <DeerAvatar :size="34" />
        <span class="name">呦鹿智伴 <em>DeerMind</em></span>
        <span class="bp" :class="bpClass">{{ bp }}</span>
      </div>

      <div class="seg">
        <button :class="{ on: store.mode === 'child' }" @click="goStudent">学生端</button>
        <button :class="{ on: store.mode === 'parent' }" @click="goParent">家长端</button>
        <button :class="{ on: store.mode === 'admin' }" @click="goAdmin">管理员端</button>
      </div>

      <div class="actions">
        <label class="toggle" title="PRD 对照注释">
          <input type="checkbox" v-model="store.prdNote" />
          <span>PRD</span>
        </label>
        <button class="icon-btn" title="重置" @click="onReset">
          <Icon name="refresh" :size="18" />
        </button>
      </div>
    </header>

    <!-- 内容视口（响应式全屏） -->
    <main class="viewport">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(1000px 500px at 20% -10%, #e0e7ff 0%, transparent 60%),
    radial-gradient(800px 400px at 90% 110%, #dcfce7 0%, transparent 60%),
    #f4f5fb;
}

/* ---------- 顶部工具栏（响应式） ---------- */
.toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(79, 70, 229, 0.1);
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: auto;
}
.brand .name {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 18px;
  color: var(--color-primary);
}
.brand .name em {
  font-style: normal;
  font-size: 12px;
  color: var(--color-secondary);
  margin-left: 2px;
}
.bp {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.bp.is-mobile { background: #e0e7ff; color: var(--color-primary); }
.bp.is-tablet { background: #dcfce7; color: #15803d; }
.bp.is-wide { background: #fef3c7; color: #b45309; }

.seg {
  display: flex;
  gap: 6px;
}
.seg button {
  padding: 8px 16px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  background: #fff;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
  transition: all var(--ease-soft);
}
.seg button.on {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  cursor: pointer;
}
.toggle input {
  accent-color: var(--color-primary);
  width: 15px;
  height: 15px;
  margin: 0;
}

/* 小屏：压缩工具栏 */
@media (max-width: 640px) {
  .toolbar { gap: 8px; padding: 8px 10px; }
  .brand .name em { display: none; }
  .toggle span { display: none; }
  .toggle { padding: 8px; }
}

/* ---------- 内容视口 ---------- */
.viewport {
  flex: 1;
  overflow: hidden;
  display: flex;
}
.viewport > * {
  flex: 1;
  min-width: 0;
}
</style>
