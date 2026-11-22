<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, postAccepted } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';

type Schema = components['schemas'];
export type AdoptedCandidate = Schema['CandidateRef'] & {
  kind: string;
  parent_ref: Schema['Ref'] | null;
  validity: string;
  body: { title: string };
};
const { items, importId, domainId, session } = defineProps<{
  items: AdoptedCandidate[];
  importId: string;
  domainId: string;
  session: DomainSession;
}>();
const selected = ref<string[]>([]);
const result = ref<Schema['IntakeSubmissionView']>();
const pending = ref<Schema['SubmitDomainIntake']>();
const sending = ref(false);
const error = ref('');
const cancel = new AbortController();
const opts = { session, signal: cancel.signal };
let timer: ReturnType<typeof setTimeout> | undefined;

const chosen = computed(() =>
  items.filter((item) => item.validity === 'current' && selected.value.includes(item.candidate_id)),
);
function refOf(item: AdoptedCandidate): Schema['CandidateRef'] {
  return {
    candidate_id: item.candidate_id,
    candidate_revision: item.candidate_revision,
    basis_revision: item.basis_revision,
  };
}

async function refresh(submissionId: string) {
  clearTimeout(timer);
  const reply = await get(
    '/api/m1/material-imports/{import_id}/intake-submissions/{submission_id}',
    {
      ...opts,
      params: { import_id: importId, submission_id: submissionId },
    },
  );
  result.value = reply;
  if (
    !cancel.signal.aborted &&
    reply.status === 'submitted' &&
    reply.delivery_state !== 'exhausted'
  )
    timer = setTimeout(() => void update(), 2000);
}

async function update() {
  if (!result.value) return;
  try {
    await refresh(result.value.submission_id);
  } catch (cause) {
    if (!cancel.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '暂时无法读取入库提交。';
  }
}

async function prepareCommand(): Promise<Schema['SubmitDomainIntake']> {
  const bindings: Schema['ParentBinding'][] = [];
  for (const item of chosen.value.filter((candidate) => candidate.kind === 'reference')) {
    const source = item.parent_ref;
    if (!source?.revision) throw new Error('此参考缺少对应题目，请让教材助手核对。');
    const parent = chosen.value.find((candidate) => candidate.candidate_id === source.id);
    if (parent) {
      bindings.push({ candidate_ref: refOf(item), parent_candidate_ref: refOf(parent) });
    } else {
      const existing = await get('/api/m1/domains/{domain_id}/material-intake-parent', {
        ...opts,
        params: { domain_id: domainId },
        query: { import_id: importId, candidate_id: source.id, revision: source.revision },
      });
      bindings.push({ candidate_ref: refOf(item), parent_item_ref: existing.item.item_ref });
    }
  }
  return {
    request_id: crypto.randomUUID(),
    adopted_content_refs: chosen.value.map(refOf),
    parent_bindings: bindings,
  };
}

async function submit() {
  if (sending.value) return;
  error.value = '';
  sending.value = true;
  try {
    const command = pending.value ?? (await prepareCommand());
    pending.value = command;
    try {
      const response = await postAccepted(
        '/api/m1/material-imports/{import_id}/intake-submissions',
        command,
        { ...opts, params: { import_id: importId } },
      );
      result.value = response.result;
    } catch (cause) {
      const receipt = await get('/api/m1/requests/receipt', {
        ...opts,
        query: {
          action: 'product.submit_domain_intake',
          resource_kind: 'material_import',
          resource_id: importId,
          request_id: command.request_id,
        },
      });
      if (
        receipt.receipt_state !== 'completed' ||
        !receipt.result ||
        !('submission_id' in receipt.result)
      )
        throw cause;
      result.value = receipt.result;
    }
    pending.value = undefined;
    selected.value = [];
    await refresh(result.value.submission_id);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status < 500) pending.value = undefined;
    if (!cancel.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '暂时无法提交入库。';
  } finally {
    sending.value = false;
  }
}

onBeforeUnmount(() => {
  cancel.abort();
  clearTimeout(timer);
});
const kinds = { kc: '知识成分', task_instance: '题目', reference: '题内参考' } as Record<
  string,
  string
>;
</script>

<template>
  <form class="intake" @submit.prevent="submit">
    <fieldset :disabled="sending || !!pending">
      <legend>选择待入库内容</legend>
      <label
        v-for="item in items.filter((candidate) => candidate.validity === 'current')"
        :key="item.candidate_id"
      >
        <input v-model="selected" type="checkbox" :value="item.candidate_id" />
        {{ kinds[item.kind] }} · {{ item.body.title }}
      </label>
    </fieldset>
    <button type="submit" :disabled="sending || (!chosen.length && !pending)">
      {{ pending && !sending ? '重试提交' : '提交领域入库' }}
    </button>
    <p v-if="result" role="status">
      {{
        result.status === 'received'
          ? '领域已接收，可在领域管理处理。'
          : result.status === 'rejected'
            ? '领域未接收。'
            : result.delivery_state === 'exhausted'
              ? '提交已保存，交接异常。'
              : '已提交，等待领域接收。'
      }}
    </p>
    <ul v-if="result?.issues.length">
      <li v-for="issue in result.issues" :key="issue.code">{{ issue.message }}</li>
    </ul>
    <button v-if="result?.status === 'submitted'" type="button" class="secondary" @click="update">
      核对提交结果
    </button>
    <p v-if="error" role="alert">{{ error }}</p>
  </form>
</template>

<style scoped>
.intake,
fieldset {
  display: grid;
  gap: 0.6rem;
  justify-items: start;
}
</style>
