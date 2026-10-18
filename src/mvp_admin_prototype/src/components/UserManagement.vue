<script setup lang="ts">
import { ref, computed } from 'vue';
import { adminUsers } from '../data';
import type { AdminUser, UserRole } from '../types';

const roleFilter = ref<UserRole | 'all'>('all');
const statusFilter = ref('all');
const searchQuery = ref('');

const filteredUsers = computed(() => {
  return adminUsers.filter(u => {
    if (roleFilter.value !== 'all' && u.role !== roleFilter.value) return false;
    if (statusFilter.value !== 'all' && u.status !== statusFilter.value) return false;
    if (searchQuery.value && !u.name.includes(searchQuery.value) && !u.email.includes(searchQuery.value)) return false;
    return true;
  });
});

const roleConfig: Record<UserRole, { label: string; color: string; bg: string }> = {
  student: { label: '学生', color: '#2d6a4f', bg: '#e8f5ee' },
  teacher: { label: '教师', color: '#4a6fa5', bg: '#e8f0f8' },
  admin: { label: '管理员', color: '#7a5a9a', bg: '#f0e8f8' },
};

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: '活跃', color: '#2d8a5e' },
  inactive: { label: '未激活', color: '#8a99a8' },
  pending: { label: '待审核', color: '#c9942a' },
};

const stats = computed(() => ({
  total: adminUsers.length,
  students: adminUsers.filter(u => u.role === 'student').length,
  teachers: adminUsers.filter(u => u.role === 'teacher').length,
  active: adminUsers.filter(u => u.status === 'active').length,
}));
</script>

<template>
  <div class="user-management">
    <div class="page-header">
      <h2>用户管理</h2>
      <button class="add-btn">+ 新增用户</button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-label">总用户数</span>
        <span class="stat-value">{{ stats.total }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">学生</span>
        <span class="stat-value">{{ stats.students }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">教师</span>
        <span class="stat-value">{{ stats.teachers }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">活跃用户</span>
        <span class="stat-value">{{ stats.active }}</span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="roleFilter" class="filter-select">
        <option value="all">全部角色</option>
        <option value="student">学生</option>
        <option value="teacher">教师</option>
        <option value="admin">管理员</option>
      </select>
      <select v-model="statusFilter" class="filter-select">
        <option value="all">全部状态</option>
        <option value="active">活跃</option>
        <option value="inactive">未激活</option>
        <option value="pending">待审核</option>
      </select>
      <input v-model="searchQuery" type="text" placeholder="搜索用户名或邮箱..." class="filter-search" />
    </div>

    <!-- 用户列表 -->
    <div class="user-table">
      <div class="table-header">
        <span class="col-user">用户</span>
        <span class="col-role">角色</span>
        <span class="col-detail">详情</span>
        <span class="col-status">状态</span>
        <span class="col-time">最后活跃</span>
        <span class="col-action">操作</span>
      </div>
      <div v-for="user in filteredUsers" :key="user.id" class="table-row">
        <span class="col-user">
          <div class="user-avatar">{{ user.name.charAt(0) }}</div>
          <div class="user-info">
            <span class="user-name">{{ user.name }}</span>
            <span class="user-email">{{ user.email }}</span>
          </div>
        </span>
        <span class="col-role">
          <span class="role-tag" :style="{ color: roleConfig[user.role].color, background: roleConfig[user.role].bg }">
            {{ roleConfig[user.role].label }}
          </span>
        </span>
        <span class="col-detail">
          <template v-if="user.role === 'student'">
            <span class="detail-item">{{ user.grade }}</span>
            <span class="detail-item">交互 {{ user.totalInteractions }}次</span>
            <span class="detail-item">掌握度 {{ user.avgMastery }}%</span>
          </template>
          <template v-else-if="user.role === 'teacher'">
            <span class="detail-item">{{ user.classes?.join('、') }}</span>
            <span class="detail-item">{{ user.studentCount }}名学生</span>
          </template>
          <template v-else>
            <span class="detail-item">系统管理</span>
          </template>
        </span>
        <span class="col-status">
          <span class="status-dot" :style="{ background: statusConfig[user.status].color }"></span>
          {{ statusConfig[user.status].label }}
        </span>
        <span class="col-time mono">{{ user.lastActive }}</span>
        <span class="col-action">
          <button class="action-btn">编辑</button>
          <button class="action-btn danger">禁用</button>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-management { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.add-btn { background: #2d6a4f; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.add-btn:hover { background: #245440; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { display: block; font-size: 24px; font-weight: 700; color: #1a3a2e; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.filter-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; }
.filter-search { flex: 1; min-width: 200px; padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; }
.filter-search:focus { outline: none; border-color: #2d6a4f; }
.user-table { flex: 1; background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; }
.table-header { display: flex; padding: 12px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 12px; font-weight: 600; color: #5a6b7a; flex-shrink: 0; }
.table-row { display: flex; padding: 14px 16px; border-bottom: 1px solid #f5f7fa; align-items: center; font-size: 13px; }
.col-user { width: 220px; flex-shrink: 0; display: flex; align-items: center; gap: 10px; }
.user-avatar { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; flex-shrink: 0; }
.user-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.user-name { font-weight: 600; color: #2c3e50; }
.user-email { font-size: 11px; color: #8a99a8; }
.col-role { width: 80px; flex-shrink: 0; }
.role-tag { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.col-detail { flex: 1; display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; }
.detail-item { font-size: 11px; background: #f0f4f7; padding: 2px 8px; border-radius: 4px; color: #5a6b7a; white-space: nowrap; }
.col-status { width: 80px; flex-shrink: 0; display: flex; align-items: center; gap: 6px; font-size: 12px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.col-time { width: 110px; flex-shrink: 0; font-size: 12px; color: #8a99a8; }
.col-action { width: 120px; flex-shrink: 0; display: flex; gap: 6px; }
.action-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 4px 10px; border-radius: 4px; font-size: 12px; cursor: pointer; font-family: inherit; }
.action-btn:hover { background: #f0f4f7; }
.action-btn.danger { color: #b85c3c; border-color: #e8c4b8; }
.action-btn.danger:hover { background: #fdf0ed; }
.mono { font-family: Consolas, Monaco, monospace; }
</style>
