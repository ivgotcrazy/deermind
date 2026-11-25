<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { Button } from './components/ui/button';

const props = defineProps<{
  phase: 'checking' | 'anonymous' | 'unavailable';
  busy: boolean;
  error: string;
  signIn: (login: string, password: string) => Promise<void>;
  retry: () => Promise<void>;
}>();
const login = ref('');
const password = ref('');
const showPassword = ref(false);
const passwordInput = ref<HTMLInputElement>();
const submitted = ref(false);

async function submit() {
  if (props.busy) return;
  submitted.value = true;
  const value = password.value;
  password.value = '';
  showPassword.value = false;
  await props.signIn(login.value, value);
}

watch(
  () => [props.phase, props.busy, props.error] as const,
  async ([phase, busy, error]) => {
    if (!submitted.value || phase !== 'anonymous' || busy || !error) return;
    submitted.value = false;
    await nextTick();
    passwordInput.value?.focus();
  },
);
</script>

<template>
  <section class="student-sign-in" aria-labelledby="student-login-title">
    <div class="reading-image" aria-hidden="true"></div>
    <div class="sign-in-panel">
      <header class="sign-in-header">
        <span class="wordmark">DeerMind</span>
        <a href="/admin/">管理端</a>
      </header>
      <div class="sign-in-content">
        <h1 id="student-login-title">登录学习空间</h1>
        <p class="sign-in-intro">使用已分配的学生账号。</p>
        <p v-if="error && !busy" id="student-login-error" class="sign-in-error" role="alert">
          {{ error }}
        </p>
        <form
          v-if="phase === 'anonymous' || (submitted && busy)"
          :aria-busy="busy"
          @submit.prevent="submit"
        >
          <label for="student-login">账号</label>
          <input
            id="student-login"
            v-model="login"
            name="username"
            autocomplete="username"
            autocapitalize="none"
            :spellcheck="false"
            :disabled="busy"
            required
          />
          <label for="student-password">密码</label>
          <div class="password-field">
            <input
              id="student-password"
              ref="passwordInput"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              autocomplete="current-password"
              :aria-describedby="error && !busy ? 'student-login-error' : undefined"
              :disabled="busy"
              required
            />
            <button
              type="button"
              class="password-visibility"
              :disabled="busy"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '隐藏' : '显示' }}
            </button>
          </div>
          <Button type="submit" size="lg" class="w-full" :disabled="busy">
            {{ busy ? '正在登录…' : '登录' }}
          </Button>
          <span v-if="busy" class="sr-only" role="status">正在登录</span>
        </form>
        <Button v-else-if="phase === 'unavailable'" type="button" size="lg" @click="retry">
          重新检查连接
        </Button>
        <p v-else class="sign-in-status" role="status">正在确认登录状态…</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.student-sign-in {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100svh;
  background: var(--background);
}

.reading-image {
  min-height: 36rem;
  margin: 1rem 0 1rem 1rem;
  border-radius: 0.375rem;
  background: #35412d url('./assets/reading-desk.webp') center / cover no-repeat;
}

.sign-in-panel {
  display: grid;
  grid-template-rows: auto 1fr;
  padding: 2.5rem clamp(2rem, 5vw, 5rem) 3rem;
}

.sign-in-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.wordmark {
  color: #243a29;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: clamp(1.65rem, 2.3vw, 2.125rem);
  font-weight: 700;
  letter-spacing: -0.06em;
  line-height: 1.15;
}

.sign-in-header a {
  flex-shrink: 0;
  margin-inline-end: -0.5rem;
  color: var(--muted-foreground);
  font-size: 0.875rem;
}

.sign-in-content {
  width: min(100%, 24rem);
  margin: auto;
  padding-block: 3rem;
}

.sign-in-content h1 {
  margin: 0;
  color: #28362b;
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  font-size: clamp(2rem, 3.25vw, 3.25rem);
  font-weight: 700;
  line-height: 1.24;
}

.sign-in-intro,
.sign-in-status {
  margin: 0.75rem 0 2.25rem;
  color: var(--muted-foreground);
}

form {
  display: grid;
  gap: 0.5rem;
}

label {
  color: var(--foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

input {
  display: block;
  width: 100%;
  min-height: 3.125rem;
  padding: 0.625rem 0.875rem;
  border: 1px solid #b9bdb0;
  border-radius: 0.375rem;
  background: #fffefb;
  color: var(--foreground);
  font: inherit;
}

input:focus-visible,
button:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

label[for='student-password'] {
  margin-top: 0.75rem;
}

.password-field {
  position: relative;
}

.password-field input {
  padding-inline-end: 5rem;
}

.password-visibility {
  position: absolute;
  inset-block: 0.25rem;
  inset-inline-end: 0.25rem;
  min-width: 3.25rem;
  border: 0;
  border-radius: 0.25rem;
  background: transparent;
  color: var(--primary);
  font: inherit;
  font-size: 0.8125rem;
  cursor: pointer;
}

.password-visibility:hover:not(:disabled) {
  background: var(--accent);
}

form > button {
  margin-top: 1rem;
}

.sign-in-content > button,
form > button {
  min-height: 3.125rem;
  border: 0;
  cursor: pointer;
}

.sign-in-error {
  margin: -1rem 0 1.25rem;
  padding: 0.625rem 0.875rem;
  border-inline-start: 2px solid #a94734;
  background: #f9eee7;
  color: #832f25;
  font-size: 0.875rem;
}

@media (max-width: 47rem) {
  .student-sign-in {
    grid-template-columns: minmax(0, 1fr);
  }

  .reading-image {
    display: none;
    background-image: none;
  }

  .sign-in-panel {
    padding: 1.5rem clamp(1.25rem, 6vw, 3rem);
  }

  .sign-in-content {
    align-self: start;
    margin-block-start: clamp(2rem, 13svh, 6rem);
    padding-block: 0 2rem;
  }
}
</style>
