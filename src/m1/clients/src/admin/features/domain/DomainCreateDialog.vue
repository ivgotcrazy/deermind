<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import { createDomain, readCreateReceipt, type DomainSession } from './api';
import { clearCreateDraft, readCreateDraft, saveCreateDraft, type CreateDraft } from './draft';

const { session, selectOnSave = false } = defineProps<{
  session: DomainSession;
  selectOnSave?: boolean;
}>();
const emit = defineEmits<{ saved: [id: string] }>();
const lifecycle = new AbortController();
const dialog = ref<HTMLDialogElement>();
const coverage = ref('');
const description = ref('');
const name = ref('');
const pending = ref<CreateDraft | null>(null);
const busy = ref<'saving' | 'checking' | null>(null);
const saveError = ref('');
const saveStatus = ref('');
const canRetry = ref(false);
const storageUnavailable = ref(false);

function openCreate() {
  if (!pending.value) {
    name.value = '';
    coverage.value = '';
    description.value = '';
    saveError.value = '';
    saveStatus.value = '';
  }
  dialog.value?.showModal();
}

function closeCreate() {
  if (!busy.value) dialog.value?.close();
}

function clearPending() {
  pending.value = null;
  canRetry.value = false;
  clearCreateDraft();
}

function saved(id: string) {
  clearPending();
  dialog.value?.close();
  emit('saved', id);
}

async function recover() {
  const draft = pending.value;
  if (!draft) return;
  canRetry.value = false;
  try {
    const receipt = await readCreateReceipt(draft, session, lifecycle.signal);
    if (lifecycle.signal.aborted) return;
    if (receipt.state === 'completed') {
      saved(receipt.domainId);
    } else if (receipt.state === 'not_found') {
      canRetry.value = true;
      saveStatus.value = '暂未查到保存记录。可以再次查询，或用原请求重试。';
    } else if (receipt.state === 'rejected') {
      clearPending();
      saveStatus.value = '';
      saveError.value = receipt.message ?? '这次保存未通过，请检查名称后再提交。';
    } else {
      saveStatus.value = '保存结果仍待核对，请稍后查询。';
    }
  } catch {
    if (!lifecycle.signal.aborted) saveStatus.value = '暂时无法核对保存结果，请稍后查询。';
  }
}

async function checkReceipt() {
  if (busy.value) return;
  busy.value = 'checking';
  try {
    await recover();
  } finally {
    busy.value = null;
  }
}

async function sendDraft(draft: CreateDraft) {
  if (busy.value) return;
  busy.value = 'saving';
  canRetry.value = false;
  saveError.value = '';
  saveStatus.value = '';
  try {
    const result = await createDomain(draft, session, lifecycle.signal);
    if (!lifecycle.signal.aborted) saved(result.result.object_ref.object_id);
  } catch (error) {
    if (lifecycle.signal.aborted) return;
    if (error instanceof ApiError && error.status < 500) {
      clearPending();
      saveError.value = error.message;
    } else {
      busy.value = 'checking';
      await recover();
    }
  } finally {
    busy.value = null;
  }
}

function submit() {
  if (busy.value || pending.value || !name.value.trim()) return;
  const draft = {
    request_id: crypto.randomUUID(),
    name: name.value.trim(),
    coverage: coverage.value.trim(),
    description: description.value.trim(),
  };
  pending.value = draft;
  try {
    saveCreateDraft(session.account.account_id, draft);
  } catch {
    storageUnavailable.value = true;
  }
  void sendDraft(draft);
}

function retry() {
  if (canRetry.value && pending.value) void sendDraft(pending.value);
}

onMounted(() => {
  try {
    pending.value = readCreateDraft(session.account.account_id);
  } catch {
    storageUnavailable.value = true;
  }
  if (pending.value) {
    name.value = pending.value.name;
    coverage.value = pending.value.coverage ?? '';
    description.value = pending.value.description ?? '';
    if (!selectOnSave) {
      openCreate();
      void checkReceipt();
    }
  }
});

onBeforeUnmount(() => lifecycle.abort());
defineExpose({ open: openCreate, pending });
</script>

<template>
  <dialog ref="dialog" aria-labelledby="create-domain-title" @cancel.prevent="closeCreate">
    <form :aria-busy="!!busy" @submit.prevent="submit">
      <h2 id="create-domain-title">
        {{ pending && !busy ? '核对领域保存' : selectOnSave ? '新建所属领域' : '新建领域' }}
      </h2>
      <label for="new-domain-name">领域名称</label>
      <input
        id="new-domain-name"
        v-model="name"
        autocomplete="off"
        :disabled="!!pending || !!busy"
        required
      />
      <template v-if="selectOnSave || coverage || description">
        <label for="new-domain-coverage">覆盖范围（选填）</label>
        <input id="new-domain-coverage" v-model="coverage" :disabled="!!pending || !!busy" />
        <label for="new-domain-description">领域说明（选填）</label>
        <textarea
          id="new-domain-description"
          v-model="description"
          rows="2"
          :disabled="!!pending || !!busy"
        />
      </template>
      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <p v-if="busy || saveStatus" role="status">
        {{
          busy === 'saving' ? '正在保存…' : busy === 'checking' ? '正在核对保存结果…' : saveStatus
        }}
      </p>
      <p v-if="storageUnavailable && pending" class="muted">
        当前浏览器无法暂存该请求，请在刷新前核对结果。
      </p>
      <div class="dialog-actions">
        <button type="button" class="secondary" :disabled="!!busy" @click="closeCreate">
          {{ pending ? '关闭' : '取消' }}
        </button>
        <button v-if="!pending" type="submit" class="primary" :disabled="!name.trim() || !!busy">
          {{ selectOnSave ? '创建并选用' : '保存领域' }}
        </button>
        <template v-else>
          <button type="button" class="secondary" :disabled="!!busy" @click="checkReceipt">
            查询保存结果
          </button>
          <button v-if="canRetry" type="button" class="primary" :disabled="!!busy" @click="retry">
            用原请求重试
          </button>
        </template>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
