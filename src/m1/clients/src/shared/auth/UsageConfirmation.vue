<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';

type Usage = components['schemas']['UsageView'];
type Command = components['schemas']['ConfirmUsageRequest'];
const props = defineProps<{ sessionId: string; csrfToken: string }>();
const emit = defineEmits<{ changed: [] }>();
const view = ref<Usage | null>(null);
const busy = ref(false);
const error = ref('');
const read = new AbortController();
let disposed = false;

async function load() {
  try {
    const response = await fetch('/api/m1/usage-conditions', {
      credentials: 'same-origin',
      cache: 'no-store',
      signal: read.signal,
      headers: { 'X-Expected-Session': props.sessionId },
    });
    if (!response.ok) throw new Error('暂时无法读取使用条件，请刷新登录状态。');
    const value: Usage = await response.json();
    if (!disposed) view.value = value;
  } catch {
    if (!disposed) error.value = '暂时无法读取使用条件，请刷新登录状态。';
  }
}

async function confirm(decision: 'accepted' | 'declined') {
  if (!view.value || busy.value) return;
  busy.value = true;
  error.value = '';
  const current = view.value;
  const command: Command = {
    request_id: crypto.randomUUID(),
    expected_revision: current.revision,
    confirmation: {
      student_id: current.student_id,
      kind: 'student_assent',
      notice_ref: current.notice_ref,
      source_ref: current.source_ref,
      decision,
    },
  };
  try {
    const response = await fetch('/api/m1/usage-confirmations', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Expected-Session': props.sessionId,
        'X-CSRF-Token': props.csrfToken,
      },
      body: JSON.stringify(command),
    });
    if (disposed) return;
    if (response.ok) emit('changed');
    else {
      error.value = '确认未完成或条件已变化，请核对后重试。';
      if (response.status === 401 || response.status === 403 || response.status === 409)
        emit('changed');
      else await load();
    }
  } catch {
    // 不自动重发决定；先读取服务端，避免将响应丢失理解为没有保存。
    if (!disposed) {
      error.value = '连接中断，已重新读取保存状态，请先核对。';
      await load();
    }
  } finally {
    if (!disposed) busy.value = false;
  }
}

onMounted(load);
onBeforeUnmount(() => {
  disposed = true;
  read.abort();
});
</script>

<template>
  <section aria-labelledby="usage-title" :aria-busy="busy">
    <h2 id="usage-title">合成账号测试 · 使用确认</h2>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="view">
      <p class="notice">{{ view.notice_text }}</p>
      <ul v-if="view.gaps.length">
        <li v-for="gap in view.gaps" :key="gap.code">{{ gap.message }}</li>
      </ul>
      <div v-if="view.can_confirm" class="actions">
        <button type="button" :disabled="busy" @click="confirm('accepted')">我愿意参与测试</button>
        <button type="button" class="secondary" :disabled="busy" @click="confirm('declined')">
          暂不使用
        </button>
      </div>
      <p v-else-if="view.allowed">测试确认已完成。聊天与教材将在后续增量接入。</p>
      <p v-else>本人意愿已记录，请等待管理员补齐其余确认。</p>
    </template>
    <p v-else-if="!error" role="status">正在读取使用条件…</p>
    <button v-if="error" type="button" @click="emit('changed')">重新检查</button>
  </section>
</template>

<style scoped>
section {
  border-top: 1px solid var(--color-line);
  margin-top: 1rem;
  padding-top: 1rem;
}
h2 {
  font-size: 1.125rem;
}
.notice {
  max-width: 50rem;
  line-height: 1.8;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.25rem;
}
button {
  padding: 0.625rem 1rem;
  border: 1px solid var(--color-accent);
  border-radius: 0.375rem;
  background: var(--color-accent);
  color: white;
  font: inherit;
  cursor: pointer;
}
.secondary {
  background: white;
  color: var(--color-accent);
}
button:disabled {
  opacity: 0.6;
  cursor: wait;
}
button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 3px;
}
[role='alert'] {
  color: #943f31;
}
</style>
