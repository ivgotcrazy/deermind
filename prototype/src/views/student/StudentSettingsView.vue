<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import { studentInfo } from '@/data/studentMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()
const tts = ref(true)
const volume = ref(80)

function logout() {
  store.logout()
  router.push('/student/login')
}
</script>

<template>
  <div class="settings">
    <header class="top">
      <button class="icon-btn" title="返回" @click="router.push('/student/home')"><Icon name="back" :size="20" /></button>
      <span class="ttl">设置</span>
      <span class="spacer"></span>
    </header>

    <section class="card">
      <div class="row-title">账号信息</div>
      <div class="row"><span>用户名</span><span class="val">{{ studentInfo.username }}</span></div>
      <div class="row"><span>昵称</span><span class="val">{{ studentInfo.nickname }}</span></div>
      <div class="row"><span>年级</span><span class="val">{{ studentInfo.grade }}</span></div>
      <p class="note">账号由爸爸妈妈创建；改昵称/头像请找家长端</p>
    </section>

    <section class="card">
      <div class="row-title">朗读</div>
      <div class="row">
        <span>讲解朗读</span>
        <label class="switch"><input v-model="tts" type="checkbox" /><i></i></label>
      </div>
      <div class="row">
        <span>音量</span>
        <input v-model.number="volume" type="range" min="0" max="100" class="range" />
        <span class="val">{{ volume }}%</span>
      </div>
    </section>

    <section class="card">
      <div class="row-title">使用情况（防沉迷 · 仅记录不打断）</div>
      <div class="row"><span>今日使用</span><span class="val">{{ store.ev.attention.todayFocusMinutes }} 分钟</span></div>
      <p class="note">小鹿只帮你计时、不打断你学习；时长也会同步给爸爸妈妈的日报</p>
    </section>

    <button class="btn logout" @click="logout">退出登录</button>
    <p class="ver">呦鹿智伴 · 原型 v0.1（学生端）</p>
  </div>
</template>

<style scoped>
.settings {
  max-width: 560px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
  padding: 0 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0 4px;
}
.ttl {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 18px;
}
.spacer {
  flex: 1;
}
.icon-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--color-text);
}
.card {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.row-title {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 14px;
  color: var(--color-text);
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  gap: 10px;
}
.val {
  opacity: 0.8;
  font-weight: 600;
}
.note {
  font-size: 12px;
  opacity: 0.6;
  margin: 0;
}
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.switch i {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--color-line);
  transition: 0.2s;
}
.switch i::after {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  top: 3px;
  left: 3px;
  transition: 0.2s;
}
.switch input:checked + i {
  background: var(--color-cta);
}
.switch input:checked + i::after {
  left: 23px;
}
.range {
  flex: 1;
  max-width: 200px;
}
.btn.logout {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 15px;
  padding: 12px;
  border-radius: var(--radius-btn);
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.ver {
  text-align: center;
  font-size: 12px;
  opacity: 0.5;
  margin: 0;
}
</style>
