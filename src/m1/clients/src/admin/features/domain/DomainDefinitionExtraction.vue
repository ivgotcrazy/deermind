<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post, postAccepted } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import type { RichContent as StructuredContent } from '../../../shared/content/types';
import type { DomainSession } from './api';

type Schema = components['schemas'];
const { item, domainId, session } = defineProps<{
  item: Schema['IntakeView'];
  domainId: string;
  session: DomainSession;
}>();
const lifecycle = new AbortController();
const active = ref(false);
const saving = ref(false);
const error = ref('');
const notice = ref('');
const result = ref<Schema['AnalysisReceipt']>();
const dialog = ref<HTMLDialogElement>();
const proposalKeys = {
  responsibility: '认知责任',
  expected_output: '预期表现',
  completion_conditions: '完成条件',
  applicability: '适用条件',
  boundaries: '适用边界',
  approach: '思路',
  rationale: '依据',
  key_process: '关键步骤',
} as const;
let timer: ReturnType<typeof setTimeout> | undefined;
let requestId: string | undefined;
let saveId: string | undefined;
const opts = { session, signal: lifecycle.signal };

function showError(cause: unknown) {
  error.value = cause instanceof Error ? cause.message : '无法完成本次操作。';
}

async function receipt() {
  if (!requestId || lifecycle.signal.aborted) return;
  try {
    const reply = await get('/api/m1/requests/receipt', {
      ...opts,
      query: {
        action: 'domain.extract_template',
        resource_kind: 'domain',
        resource_id: domainId,
        request_id: requestId,
      },
    });
    if (reply.receipt_state === 'accepted') {
      timer = setTimeout(() => void receipt(), 2500);
      return;
    }
    active.value = false;
    if (
      reply.receipt_state === 'completed' &&
      reply.result &&
      'proposed_definition' in reply.result
    ) {
      result.value = reply.result;
      requestId = undefined;
    } else {
      error.value = reply.error?.message ?? '暂未取得候选，请核对或重试。';
      if (reply.receipt_state === 'rejected') requestId = undefined;
    }
  } catch (cause) {
    active.value = false;
    if (!lifecycle.signal.aborted) showError(cause);
  }
}

async function extract() {
  if (active.value) return;
  dialog.value?.showModal();
  if (result.value) return;
  active.value = true;
  error.value = '';
  requestId ??= crypto.randomUUID();
  try {
    await postAccepted(
      '/api/m1/domains/{domain_id}/definition-candidates',
      {
        request_id: requestId,
        intake_item_ref: item.item_ref,
        template_kind: item.kind === 'task_instance' ? 'task' : 'solution',
      },
      { ...opts, params: { domain_id: domainId } },
    );
    await receipt();
  } catch (cause) {
    active.value = false;
    if (!lifecycle.signal.aborted) showError(cause);
  }
}

function content(key: string): StructuredContent | undefined {
  const value = result.value?.proposed_definition?.[key];
  return value && typeof value === 'object' ? (value as unknown as StructuredContent) : undefined;
}

async function save() {
  const definition = result.value?.proposed_definition;
  if (!definition || saving.value || notice.value) return;
  saving.value = true;
  error.value = '';
  saveId ??= crypto.randomUUID();
  const common = {
    request_id: saveId,
    domain_id: domainId,
    action: 'create' as const,
    change_note: '采用教材候选提取的定义',
    candidate_ref: result.value?.candidate_ref,
  };
  try {
    if (item.kind === 'task_instance') {
      await post(
        '/api/m1/domain-definitions',
        {
          ...common,
          object_kind: 'task',
          definition: definition as unknown as Schema['CreateTaskRequest']['definition'],
        },
        opts,
      );
    } else {
      await post(
        '/api/m1/domain-definitions',
        {
          ...common,
          object_kind: 'solution',
          definition: definition as unknown as Schema['CreateSolutionRequest']['definition'],
        },
        opts,
      );
    }
    notice.value = '定义已保存，可在待入库行选择关联。';
  } catch (cause) {
    if (!lifecycle.signal.aborted) showError(cause);
  } finally {
    saving.value = false;
  }
}

onBeforeUnmount(() => {
  lifecycle.abort();
  clearTimeout(timer);
});
</script>

<template>
  <button type="button" class="secondary" @click="extract">
    {{ item.kind === 'task_instance' ? '提取任务定义' : '提取方法定义' }}
  </button>
  <dialog ref="dialog" aria-label="核对定义候选">
    <h3>核对定义候选</h3>
    <p v-if="active" role="status">正在分析教材内容…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <template v-if="result">
      <p v-if="result.proposed_definition?.name">
        <strong>{{ result.proposed_definition.name }}</strong>
      </p>
      <template v-for="(label, key) in proposalKeys" :key="key">
        <section v-if="content(key)">
          <h4>{{ label }}</h4>
          <RichContent :content="content(key)!" />
        </section>
      </template>
      <ul v-if="result.output.unresolved.length">
        <li v-for="gap in result.output.unresolved" :key="gap">{{ gap }}</li>
      </ul>
      <button
        v-if="result.proposed_definition && !notice"
        type="button"
        :disabled="saving"
        @click="save"
      >
        确认添加定义
      </button>
    </template>
    <button type="button" class="secondary" @click="dialog?.close()">关闭</button>
  </dialog>
</template>
