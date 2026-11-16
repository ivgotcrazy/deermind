<script setup lang="ts">
import { ref } from 'vue';
import { useSession } from './session';
import UsageConfirmation from './UsageConfirmation.vue';

defineProps<{ role: 'student' | 'admin' }>();
const { session, phase, busy, error, refresh, signIn, signOut } = useSession();
const login = ref('');
const password = ref('');

async function submit() {
  const value = password.value;
  password.value = '';
  await signIn(login.value, value);
}
</script>

<template>
  <section class="auth-card" aria-label="登录身份" :aria-busy="busy || phase === 'checking'">
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="phase === 'checking'" role="status">
      {{ busy ? '正在处理登录，请稍候…' : '正在确认登录状态…' }}
    </p>
    <template v-else-if="phase === 'unavailable'">
      <button type="button" :disabled="busy" @click="refresh()">重新检查连接</button>
    </template>
    <form v-else-if="phase === 'anonymous'" @submit.prevent="submit">
      <h2>登录 DeerMind</h2>
      <p class="muted">使用已分配的账号登录。</p>
      <label for="login">账号</label>
      <input
        id="login"
        v-model="login"
        name="username"
        autocomplete="username"
        required
        :disabled="busy"
      />
      <label for="password">密码</label>
      <input
        id="password"
        v-model="password"
        type="password"
        name="password"
        autocomplete="current-password"
        aria-describedby="password-help"
        required
        :disabled="busy"
      />
      <p id="password-help" class="muted">密码为 15–128 个字符。</p>
      <button type="submit" :disabled="busy">登录</button>
    </form>
    <template v-else-if="session">
      <div class="identity">
        <p>
          已登录：<strong>{{ session.account.display_name }}</strong>
        </p>
        <button type="button" class="secondary" :disabled="busy" @click="signOut">退出登录</button>
      </div>
      <template v-if="session.account.role !== role">
        <p>当前账号{{ session.account.role === 'admin' ? '属于管理端' : '属于学生端' }}。</p>
        <a :href="session.account.role === 'admin' ? '/admin/' : '/student/'">前往对应入口</a>
      </template>
      <UsageConfirmation
        v-else-if="role === 'student' && session.account.usage_gaps.length"
        :key="session.session_id"
        :session-id="session.session_id"
        :csrf-token="session.csrf_token"
        @changed="refresh()"
      />
      <slot v-else :key="session.session_id" />
    </template>
  </section>
</template>

<style scoped>
.auth-card {
  background: white;
  border: 1px solid var(--color-line);
  border-radius: 0.75rem;
  padding: clamp(1rem, 3vw, 2rem);
}
form {
  max-width: 25rem;
}
h2 {
  margin: 0;
  font-size: 1.25rem;
}
.muted {
  color: var(--color-muted);
  font-size: 0.875rem;
}
label {
  display: block;
  margin-top: 1rem;
  margin-bottom: 0.25rem;
}
input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--color-line);
  border-radius: 0.375rem;
  font: inherit;
}
button {
  padding: 0.625rem 1.25rem;
  border: 1px solid var(--color-accent);
  border-radius: 0.375rem;
  background: var(--color-accent);
  color: white;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: wait;
}
button:focus-visible,
input:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}
.secondary {
  background: white;
  color: var(--color-accent);
}
.identity {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}
[role='alert'] {
  color: #943f31;
}
</style>
