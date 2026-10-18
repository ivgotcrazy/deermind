<script setup lang="ts">
import { ref } from 'vue';
import type { PageType } from './types';
import Dashboard from './components/Dashboard.vue';
import TraceList from './components/TraceList.vue';
import TraceDetail from './components/TraceDetail.vue';
import ObjectBrowser from './components/ObjectBrowser.vue';
import ObjectDetail from './components/ObjectDetail.vue';
import StudentList from './components/StudentList.vue';
import UserManagement from './components/UserManagement.vue';
import ResourceManagement from './components/ResourceManagement.vue';

const currentPage = ref<PageType>('dashboard');
const selectedTraceId = ref('');
const selectedObjectId = ref('');

const navGroups = [
  {
    label: '观测',
    items: [
      { id: 'dashboard' as PageType, label: '运行总览', icon: '📊' },
      { id: 'trace-list' as PageType, label: '交互审查', icon: '🔍' },
      { id: 'objects' as PageType, label: '空间观测', icon: '🧩' },
      { id: 'students' as PageType, label: '学生画像', icon: '👤' },
    ],
  },
  {
    label: '管理',
    items: [
      { id: 'users' as PageType, label: '用户管理', icon: '👥' },
      { id: 'resources' as PageType, label: '资源管理', icon: '📚' },
      { id: 'config' as PageType, label: '系统配置', icon: '⚙️' },
    ],
  },
];

function goDashboard() { currentPage.value = 'dashboard'; }
function goTraceList() { currentPage.value = 'trace-list'; }
function goTraceDetail(traceId: string) { selectedTraceId.value = traceId; currentPage.value = 'trace-detail'; }
function goObjects() { currentPage.value = 'objects'; }
function goObjectDetail(objectId: string) { selectedObjectId.value = objectId; currentPage.value = 'object-detail'; }
function goStudents() { currentPage.value = 'students'; }
function goUsers() { currentPage.value = 'users'; }
function goResources() { currentPage.value = 'resources'; }

function navigate(pageId: PageType) {
  if (pageId === 'dashboard') goDashboard();
  else if (pageId === 'trace-list') goTraceList();
  else if (pageId === 'objects') goObjects();
  else if (pageId === 'students') goStudents();
  else if (pageId === 'users') goUsers();
  else if (pageId === 'resources') goResources();
}
</script>

<template>
  <div class="app">
    <!-- 侧边导航 -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">🦌</span>
        <span class="brand-name">DeerMind</span>
        <span class="brand-tag">Admin</span>
      </div>
      <nav class="sidebar-nav">
        <div v-for="group in navGroups" :key="group.label" class="nav-group">
          <span class="nav-group-label">{{ group.label }}</span>
          <button
            v-for="item in group.items"
            :key="item.id"
            class="nav-item"
            :class="{ active: currentPage === item.id || (item.id === 'trace-list' && currentPage === 'trace-detail') || (item.id === 'objects' && currentPage === 'object-detail') }"
            @click="navigate(item.id)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </button>
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="user-info">
          <span class="user-avatar">A</span>
          <div class="user-detail">
            <span class="user-name">管理员</span>
            <span class="user-role">System Admin</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <Dashboard v-if="currentPage === 'dashboard'" @go-trace-list="goTraceList" @go-trace-detail="goTraceDetail" />
      <TraceList v-else-if="currentPage === 'trace-list'" @go-detail="goTraceDetail" />
      <TraceDetail v-else-if="currentPage === 'trace-detail'" :trace-id="selectedTraceId" @back="goTraceList" />
      <ObjectBrowser v-else-if="currentPage === 'objects'" @go-detail="goObjectDetail" />
      <ObjectDetail v-else-if="currentPage === 'object-detail'" :object-id="selectedObjectId" @back="goObjects" @go-trace="goTraceDetail" />
      <StudentList v-else-if="currentPage === 'students'" @go-trace="goTraceDetail" />
      <UserManagement v-else-if="currentPage === 'users'" />
      <ResourceManagement v-else-if="currentPage === 'resources'" />
      <div v-else class="placeholder">
        <h3>系统配置</h3>
        <p>模型参数、账号权限等配置功能（MVP 简化版）</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app { display: flex; height: 100vh; overflow: hidden; }
.sidebar {
  width: 200px; flex-shrink: 0; background: linear-gradient(180deg, #1a3a2e 0%, #163026 100%);
  display: flex; flex-direction: column; color: #e8f0ec;
}
.sidebar-brand { display: flex; align-items: center; gap: 8px; padding: 18px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.brand-icon { font-size: 22px; }
.brand-name { font-size: 16px; font-weight: 600; }
.brand-tag { font-size: 10px; background: rgba(255,255,255,0.15); padding: 2px 6px; border-radius: 4px; margin-left: auto; }
.sidebar-nav { flex: 1; padding: 12px 8px; overflow-y: auto; }
.nav-group { margin-bottom: 16px; }
.nav-group-label { display: block; font-size: 10px; color: rgba(232,240,236,0.4); text-transform: uppercase; padding: 0 12px; margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; }
.nav-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 10px 12px; background: none; border: none; color: rgba(232,240,236,0.7);
  font-size: 13px; cursor: pointer; border-radius: 8px; font-family: inherit;
  transition: all 0.15s; text-align: left; margin-bottom: 2px;
}
.nav-item:hover { background: rgba(255,255,255,0.08); color: #e8f0ec; }
.nav-item.active { background: rgba(64,145,108,0.25); color: #fff; font-weight: 500; }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }
.sidebar-footer { padding: 12px; border-top: 1px solid rgba(255,255,255,0.1); }
.user-info { display: flex; align-items: center; gap: 10px; }
.user-avatar { width: 32px; height: 32px; border-radius: 50%; background: #40916c; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.user-detail { display: flex; flex-direction: column; }
.user-name { font-size: 13px; font-weight: 500; }
.user-role { font-size: 10px; color: rgba(232,240,236,0.5); }
.main-content { flex: 1; overflow: hidden; background: #f5f7fa; display: flex; flex-direction: column; }
.main-content > * { flex: 1; overflow: hidden; }
.placeholder { padding: 40px; color: #8a99a8; }
.placeholder h3 { color: #5a6b7a; }
</style>
