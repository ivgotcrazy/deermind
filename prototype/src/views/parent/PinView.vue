<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/Icon.vue'

const router = useRouter()
const pin = ref('')
const error = ref(false)

function press(d: string) {
  error.value = false
  if (pin.value.length < 4) pin.value += d
  if (pin.value.length === 4) {
    setTimeout(() => {
      if (pin.value === '0000') router.push('/parent/spaces')
      else {
        error.value = true
        pin.value = ''
      }
    }, 300)
  }
}
function clearPin() {
  pin.value = ''
  error.value = false
}
</script>

<template>
  <div class="pin">
    <div class="lock"><Icon name="lock" :size="40" /></div>
    <h2>家长模式</h2>
    <p class="sub">请输入家长密码进入（演示密码：0000）</p>

    <div class="dots">
      <span v-for="i in 4" :key="i" :class="{ filled: i <= pin.length }"></span>
    </div>
    <p v-if="error" class="err">密码不对，再试一次</p>

    <div class="pad">
      <button v-for="n in 9" :key="n" class="key" @click="press(String(n))">{{ n }}</button>
      <button class="key" @click="clearPin"><Icon name="close" :size="18" /></button>
      <button class="key" @click="press('0')">0</button>
      <button class="key ghost" @click="clearPin">清除</button>
    </div>
  </div>
</template>

<style scoped>
.pin {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 20px;
  gap: 8px;
}
.lock {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
h2 {
  margin: 4px 0 0;
  font-size: 20px;
}
.sub {
  margin: 0 0 8px;
  font-size: 13px;
  opacity: 0.75;
}
.dots {
  display: flex;
  gap: 14px;
  margin: 8px 0;
}
.dots span {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--color-line);
  transition: all var(--ease-soft);
}
.dots span.filled {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.err {
  margin: 0;
  color: var(--color-danger);
  font-size: 13px;
  font-weight: 700;
}
.pad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 240px;
  margin-top: 8px;
}
.key {
  height: 60px;
  border-radius: 16px;
  border: none;
  background: #fff;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  box-shadow: var(--shadow-md);
  transition: all var(--ease-soft);
}
.key:active {
  transform: scale(0.94);
}
.key.ghost {
  font-size: 14px;
  color: var(--color-primary);
}
</style>
