<script setup lang="ts">
import { ElAlert, ElButton, ElInput } from 'element-plus';
import { ref } from 'vue';

const props = defineProps<{
  phase: 'checking' | 'anonymous' | 'unavailable';
  busy: boolean;
  error: string;
  signIn: (login: string, password: string) => Promise<void>;
  retry: () => Promise<void>;
}>();

const login = ref('');
const password = ref('');
const submitting = ref(false);

async function submit() {
  if (props.busy) return;
  submitting.value = true;
  const value = password.value;
  password.value = '';
  try {
    await props.signIn(login.value, value);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="admin-sign-in" aria-labelledby="admin-login-title">
    <header class="admin-topbar">
      <strong>DeerMind</strong>
      <span>管理后台</span>
      <a href="/student/">学生端</a>
    </header>
    <main class="login-area">
      <div class="login-card">
        <h1 id="admin-login-title">登录管理后台</h1>
        <p class="login-hint">使用已分配的管理员账号。</p>
        <ElAlert v-if="error && !busy" :title="error" type="error" :closable="false" show-icon />
        <form v-if="phase === 'anonymous' || submitting" :aria-busy="busy" @submit.prevent="submit">
          <div class="login-field">
            <label for="admin-account">账号</label>
            <ElInput
              id="admin-account"
              v-model="login"
              name="username"
              autocomplete="username"
              autocapitalize="none"
              :spellcheck="false"
              :disabled="busy"
              size="large"
              required
            />
          </div>
          <div class="login-field">
            <label for="admin-password">密码</label>
            <ElInput
              id="admin-password"
              v-model="password"
              name="password"
              autocomplete="current-password"
              type="password"
              show-password
              :disabled="busy"
              size="large"
              required
            />
          </div>
          <ElButton type="primary" native-type="submit" :loading="busy">{{
            busy ? '正在登录…' : '登录'
          }}</ElButton>
        </form>
        <ElButton v-else-if="phase === 'unavailable'" :disabled="busy" @click="retry">
          重新检查连接
        </ElButton>
        <p v-else role="status" class="login-hint">正在确认登录状态…</p>
      </div>
    </main>
  </section>
</template>

<style scoped>
.admin-topbar {
  min-height: var(--admin-topbar-height);
}
.admin-topbar a {
  margin-inline-start: auto;
  padding: 0.25rem;
  text-decoration: none;
  font-size: 0.8125rem;
}
.admin-topbar a:hover {
  text-decoration: underline;
}
.login-area {
  display: grid;
  min-height: calc(100dvh - var(--admin-topbar-height));
  max-width: none;
  align-content: center;
  justify-items: center;
  padding: 2rem 1rem 5rem;
}
.login-card {
  display: grid;
  gap: 0.75rem;
  width: min(100%, 26rem);
  padding: 1.75rem 2rem 2rem;
  border: 1px solid var(--el-border-color);
  border-block-start: 3px solid var(--el-color-primary);
  border-radius: 5px;
  background: white;
}
.login-card h1 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 1.625rem;
  line-height: 1.35;
}
.login-hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.875rem;
}
.login-card form {
  display: grid;
  gap: 1.125rem;
  margin-top: 0.5rem;
}
.login-field {
  display: grid;
  gap: 0.375rem;
}
.login-field label {
  font-size: 0.875rem;
  font-weight: 600;
}
.login-card form :deep(.el-button) {
  width: 100%;
  height: 42px;
  margin-top: 0.375rem;
}
@media (max-width: 30rem) {
  .admin-topbar {
    gap: 1rem;
    padding-inline: 1rem;
  }
  .login-card {
    padding-inline: 1.25rem;
  }
}
</style>
