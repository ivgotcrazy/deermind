<script setup lang="ts">
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const ev = useEvidenceStore()

function toggleStudent(id: string) {
  const s = ev.students.find((x) => x.id === id)
  if (s) s.status = s.status === 'active' ? 'paused' : 'active'
}

function createStudent() {
  alert('原型演示：创建学生账号（家长全权，不限数量）')
}
</script>

<template>
  <div class="accounts">
    <h2 class="title">学生账号 <span class="demo">{{ DEMO_NOTE }}</span></h2>

    <section class="card">
      <div class="sec-title">家长账号</div>
      <div class="parent-row">
        <div class="who">
          <span class="avatar">妈</span>
          <div>
            <div class="name">妈妈（自行注册）</div>
            <div class="meta">零强制投入：默认只收异常提醒与周报</div>
          </div>
        </div>
      </div>
      <p class="note">家长对学习空间与学生账号拥有全权；管理员只读（PRD §3.2 权限矩阵）。</p>
    </section>

    <section class="card">
      <div class="sec-title">学生账号列表（家长全权生命周期）</div>
      <ul class="list">
        <li v-for="s in ev.students" :key="s.id" class="item">
          <div class="avatar" :class="{ paused: s.status === 'paused' }">
            {{ s.nickname.slice(0, 1) }}
          </div>
          <div class="info">
            <div class="name">
              {{ s.nickname }}
              <span class="pill" :class="s.status === 'active' ? 'ok' : 'off'">
                {{ s.status === 'active' ? '正常' : '已暂停' }}
              </span>
            </div>
            <div class="meta">
              {{ s.username }} · {{ s.grade }} · {{ s.spaces }} 个空间 · 创建于 {{ s.createdAt }}
            </div>
          </div>
          <button class="btn-ghost small" @click="toggleStudent(s.id)">
            {{ s.status === 'active' ? '暂停' : '恢复' }}
          </button>
        </li>
      </ul>
      <button class="btn btn-indigo btn-block" @click="createStudent">
        <Icon name="plus" :size="18" /> 新建学生账号
      </button>
    </section>

    <section class="card note-card">
      <div class="sec-title">账号规则</div>
      <ul class="rules">
        <li>家长自行注册，创建学生账号（账号 + 密码登录，不绑设备）</li>
        <li>家长可随时暂停 / 恢复 / 删除学生账号</li>
        <li>管理员仅协助重置家长账号，不触碰学生数据</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.accounts {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 19px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.demo {
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: 999px;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.parent-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.who {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.avatar.paused {
  background: #cbd5e1;
}
.name {
  font-weight: 700;
  font-size: 14px;
}
.meta {
  font-size: 12px;
  opacity: 0.7;
  margin-top: 2px;
}
.tier-seg {
  display: flex;
  gap: 6px;
}
.tier {
  border: 1.5px solid var(--color-line);
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text);
}
.tier.on {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.note {
  font-size: 12px;
  opacity: 0.7;
  margin: 8px 0 0;
}
.list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.info {
  flex: 1;
  min-width: 0;
}
.pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  margin-left: 6px;
}
.pill.ok {
  background: var(--color-cta-soft);
  color: #15803d;
}
.pill.off {
  background: #f1f5f9;
  color: #64748b;
}
.btn-ghost.small {
  border: 1.5px solid var(--color-primary);
  color: var(--color-primary);
  background: transparent;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.rules {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
}
</style>
