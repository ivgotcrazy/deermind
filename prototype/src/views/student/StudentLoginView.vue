<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import DeerAvatar from '@/components/DeerAvatar.vue'

const store = useStudentChat()
const router = useRouter()

onMounted(() => {
  if (store.loggedIn) router.replace('/student/home')
})

const username = ref('')
const password = ref('')
const error = ref('')

function doLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    error.value = '请输入账号和密码'
    return
  }
  store.login(username.value.trim())
  router.replace('/student/home')
}

/* 演示快捷填充 */
function demo() {
  username.value = 'xiaolu_0608'
  password.value = '******'
  doLogin()
}
</script>

<template>
  <div class="login">
    <div class="card">
      <div class="logo"><DeerAvatar :size="72" /></div>
      <h1 class="title">呦鹿智伴</h1>
      <p class="sub">欢迎回来，小鹿等你啦～</p>

      <label class="field">
        <span>账号</span>
        <input v-model="username" class="input" placeholder="家长帮你创建的账号" @keyup.enter="doLogin" />
      </label>
      <label class="field">
        <span>密码</span>
        <input v-model="password" type="password" class="input" placeholder="请输入密码" @keyup.enter="doLogin" />
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn" @click="doLogin">登 录</button>
      <button class="link" @click="demo">演示账号快速登录</button>
      <p class="hint">账号由家长创建，忘记密码请让爸爸妈妈在家长端重置</p>
    </div>
  </div>
</template>

<style scoped>
.login {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(600px 300px at 20% 0%, #e0e7ff 0%, transparent 60%),
    radial-gradient(500px 300px at 90% 100%, #dcfce7 0%, transparent 60%),
    var(--color-background);
}
.card {
  width: 340px;
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.logo {
  display: flex;
  justify-content: center;
}
.title {
  text-align: center;
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 26px;
  color: var(--color-primary);
  margin: 0;
}
.sub {
  text-align: center;
  font-size: 14px;
  color: var(--color-text);
  opacity: 0.8;
  margin: -4px 0 6px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  font-weight: 700;
}
.input {
  height: 42px;
  border: 2px solid var(--color-line);
  border-radius: var(--radius-input);
  padding: 0 14px;
  font-family: var(--font-body);
  font-size: 15px;
}
.input:focus {
  outline: none;
  border-color: var(--color-secondary);
}
.error {
  color: var(--color-danger);
  font-size: 13px;
  margin: 0;
}
.btn {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  background: var(--color-cta);
  padding: 12px;
  border-radius: var(--radius-btn);
  box-shadow: var(--shadow-clay-press);
}
.link {
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 700;
}
.hint {
  font-size: 12px;
  text-align: center;
  opacity: 0.65;
  margin: 0;
}
</style>
