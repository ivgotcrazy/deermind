<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError, get, post } from '../api/http';
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
const pending = ref<Command | null>(null);
const session = () => ({ session_id: props.sessionId, csrf_token: props.csrfToken });

async function load() {
  try {
    const value = await get('/api/m1/usage-conditions', {
      session: session(),
      signal: read.signal,
    });
    if (!disposed) view.value = value;
  } catch (cause) {
    if (!disposed) error.value = cause instanceof Error ? cause.message : '暂时无法读取使用条件。';
  }
}

async function recover() {
  const command = pending.value;
  if (!command || disposed) return;
  try {
    const receipt = await get('/api/m1/requests/receipt', {
      session: session(),
      signal: read.signal,
      query: {
        action: 'product.record_usage_confirmation',
        resource_kind: 'account',
        resource_id: command.confirmation.student_id,
        request_id: command.request_id,
      },
    });
    if (disposed) return;
    if (receipt.receipt_state === 'completed' && receipt.result) {
      pending.value = null;
      emit('changed');
    } else {
      error.value =
        receipt.receipt_state === 'not_found'
          ? '暂未查到这次确认。可以再次查询，或用原请求重试。'
          : '请求尚未完成，请稍后查询。';
    }
  } catch {
    if (!disposed) error.value = '暂时查不到结果，请保留页面，稍后再次查询。';
  }
}

async function submit() {
  const command = pending.value;
  if (!command || busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await post('/api/m1/usage-confirmations', command, { session: session() });
    if (!disposed) {
      pending.value = null;
      emit('changed');
    }
  } catch (cause) {
    if (disposed) return;
    if (cause instanceof ApiError && cause.status < 500) {
      pending.value = null;
      error.value = cause.message;
      if ([401, 403, 409].includes(cause.status)) emit('changed');
      else await load();
    } else await recover();
  } finally {
    if (!disposed) busy.value = false;
  }
}

async function confirm(decision: 'accepted' | 'declined') {
  if (!view.value || busy.value || pending.value) return;
  const current = view.value;
  pending.value = {
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
  await submit();
}

async function checkResult() {
  if (busy.value) return;
  busy.value = true;
  try {
    await recover();
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
      <div v-if="view.can_confirm && !pending" class="actions">
        <button type="button" :disabled="busy" @click="confirm('accepted')">我愿意参与测试</button>
        <button type="button" class="secondary" :disabled="busy" @click="confirm('declined')">
          暂不使用
        </button>
      </div>
      <div v-else-if="pending" class="actions">
        <button type="button" :disabled="busy" @click="checkResult">查询本次确认结果</button>
        <button type="button" class="secondary" :disabled="busy" @click="submit">
          用原请求重试
        </button>
      </div>
      <p v-else-if="view.allowed">测试确认已完成。聊天与教材将在后续增量接入。</p>
      <p v-else>本人意愿已记录，请等待管理员补齐其余确认。</p>
    </template>
    <p v-else-if="!error" role="status">正在读取使用条件…</p>
    <button v-if="error && !pending" type="button" @click="emit('changed')">重新检查</button>
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
