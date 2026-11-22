<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, post, postAccepted } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import type { RichContent as StructuredContent } from '../../../shared/content/types';
import type { DomainSession } from '../domain/api';
import type { MaterialDetail } from './api';
import MaterialIntakePanel from './MaterialIntakePanel.vue';
import type { AdoptedCandidate } from './MaterialIntakePanel.vue';

type Schema = components['schemas'];
type Candidate = {
  candidate_id: string;
  kind: string;
  body: { title: string; content: StructuredContent; teaching_aids?: StructuredContent[] };
};
const { material, session } = defineProps<{ material: MaterialDetail; session: DomainSession }>();
const lifecycle = new AbortController();
const history = ref<Schema['MaterialMessageView'][]>([]);
const draft = ref('');
const file = ref('');
const first = ref(1);
const last = ref(1);
const busy = ref(false);
const notice = ref('');
const error = ref('');
const pending = ref<Schema['MaterialMessageInput']>();
const proposed = ref<Candidate[]>([]);
const retirements = ref<string[]>([]);
const candidateBatch = ref<Schema['PreviousMaterialBatch']>();
const reference = ref<Schema['PreviousMaterialBatch']>();
const decisionRevision = ref<number>();
const decisionState = ref('');
const completeCandidate = ref(false);
const deciding = ref(false);
const completedRevision = ref(material.content_revision);
const adopted = ref<(Candidate & AdoptedCandidate)[]>([]);
const pendingDecision = ref<Schema['DecideMaterialBatch']>();
const params = { import_id: material.textbook.import_id };
let scheduled: ReturnType<typeof setTimeout> | undefined;
const opts = { session, signal: lifecycle.signal };
const draftKey = `material-draft:${session.session_id}:${params.import_id}`;
const requestKey = `${draftKey}:request`;

function saveValue(key: string, value: string) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    // 浏览器禁用存储时仍保留当前页面的草稿及请求。
  }
}

watch(draft, (value) => saveValue(draftKey, value));
watch(pending, (command) => saveValue(requestKey, command ? JSON.stringify(command) : ''));

function showError(cause: unknown) {
  if (!lifecycle.signal.aborted)
    error.value = cause instanceof Error ? cause.message : '无法读取教材助手。';
}

async function update() {
  const page = await get('/api/m1/material-imports/{import_id}/messages', { ...opts, params });
  history.value = page.items;
  busy.value = Boolean(page.active_request_ref);
  const command = pending.value;
  if (command) {
    const receipt = await get('/api/m1/requests/receipt', {
      ...opts,
      query: {
        action: 'product.converse_material_assistant',
        resource_kind: 'material_import',
        resource_id: params.import_id,
        request_id: command.request_id,
      },
    });
    if (receipt.receipt_state === 'accepted' && draft.value.trim() === command.message) {
      draft.value = '';
    }
    if (
      receipt.receipt_state === 'completed' &&
      receipt.result &&
      'candidate_batch_refs' in receipt.result
    ) {
      const candidate = receipt.result.candidate_batch_refs[0];
      if (candidate) await read(candidate.id);
      notice.value =
        receipt.result.outcome === 'needs_input' ? '等待补充材料。' : '本轮处理已结束。';
      if (draft.value.trim() === command.message) draft.value = '';
      pending.value = undefined;
    }
  }
  if ((busy.value || pending.value) && !lifecycle.signal.aborted) schedule();
}

function schedule() {
  clearTimeout(scheduled);
  scheduled = setTimeout(() => {
    void update().catch((cause: unknown) => {
      showError(cause);
      if ((busy.value || pending.value) && !lifecycle.signal.aborted) schedule();
    });
  }, 1800);
}

async function read(batch: string) {
  const snapshot = await get('/api/m1/material-imports/{import_id}/candidate-batches/{batch_id}', {
    ...opts,
    params: { ...params, batch_id: batch },
  });
  proposed.value = snapshot.items as unknown as Candidate[];
  const changes = snapshot.batch.write_set;
  retirements.value = Array.isArray(changes)
    ? changes.flatMap((change) =>
        change &&
        typeof change === 'object' &&
        'action' in change &&
        change.action === 'retire' &&
        'title' in change &&
        typeof change.title === 'string'
          ? [change.title]
          : [],
      )
    : [];
  decisionState.value = String(snapshot.batch.decision_state);
  decisionRevision.value =
    typeof snapshot.batch.decision_revision === 'number'
      ? snapshot.batch.decision_revision
      : undefined;
  const coverage = snapshot.batch.coverage;
  completeCandidate.value =
    !!coverage &&
    typeof coverage === 'object' &&
    'complete' in coverage &&
    coverage.complete === true;
  if (typeof snapshot.batch.batch_revision === 'number') {
    candidateBatch.value = { batch_id: batch, batch_revision: snapshot.batch.batch_revision };
  }
}

async function readAdopted() {
  const snapshot = await get('/api/m1/material-imports/{import_id}/contents', { ...opts, params });
  adopted.value = snapshot.items as unknown as (Candidate & AdoptedCandidate)[];
  completedRevision.value = snapshot.content_revision;
}

async function decide(decision: 'adopt' | 'decline') {
  if (!candidateBatch.value || !decisionRevision.value || deciding.value) return;
  const batch = candidateBatch.value;
  deciding.value = true;
  error.value = '';
  const command =
    pendingDecision.value?.decision === decision &&
    pendingDecision.value.batch_ref.batch_id === batch.batch_id
      ? pendingDecision.value
      : {
          request_id: crypto.randomUUID(),
          batch_ref: batch,
          decision,
          expected_revision: decisionRevision.value,
        };
  pendingDecision.value = command;
  try {
    try {
      await post(
        '/api/m1/material-imports/{import_id}/candidate-batches/{batch_id}/decision',
        command,
        {
          ...opts,
          params: { ...params, batch_id: batch.batch_id },
        },
      );
    } catch (cause) {
      const saved = await get('/api/m1/requests/receipt', {
        ...opts,
        query: {
          action: 'product.decide_material_candidate',
          resource_kind: 'material_import',
          resource_id: params.import_id,
          request_id: command.request_id,
        },
      });
      if (saved.receipt_state !== 'completed') throw cause;
    }
    pendingDecision.value = undefined;
    notice.value = decision === 'adopt' ? '已采用。' : '已记录不采用。';
    await Promise.all([read(batch.batch_id), readAdopted()]);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status < 500) pendingDecision.value = undefined;
    showError(cause);
  } finally {
    deciding.value = false;
  }
}

async function send(whole = false) {
  if (busy.value) return;
  const value = whole ? '请解析整本教材。' : draft.value.trim();
  if (!value) return;
  error.value = '';
  notice.value = '正在处理。';
  busy.value = true;
  const command = pending.value ?? {
    request_id: crypto.randomUUID(),
    message: value,
    previous_batch_ref: whole ? null : (reference.value ?? null),
    selection:
      !whole && file.value
        ? {
            import_id: params.import_id,
            scope: 'batch' as const,
            basis_revision: completedRevision.value,
            source_refs: [
              { source_id: file.value, first_page: first.value, last_page: last.value },
            ],
          }
        : null,
  };
  pending.value = command;
  try {
    await postAccepted('/api/m1/material-imports/{import_id}/messages', command, {
      ...opts,
      params,
    });
    if (draft.value.trim() === command.message) draft.value = '';
    reference.value = undefined;
    await update();
  } catch (cause) {
    if (cause instanceof ApiError && cause.status < 500) pending.value = undefined;
    busy.value = false;
    notice.value = '';
    showError(cause);
    schedule();
  }
}

onMounted(() => {
  try {
    draft.value = sessionStorage.getItem(draftKey) ?? '';
    const stored = sessionStorage.getItem(requestKey);
    if (stored) pending.value = JSON.parse(stored) as Schema['MaterialMessageInput'];
  } catch {
    saveValue(requestKey, '');
  }
  void update().catch(showError);
  void readAdopted().catch(showError);
});
onBeforeUnmount(() => {
  clearTimeout(scheduled);
  lifecycle.abort();
});
</script>

<template>
  <section class="material-assistant" aria-label="教材助手">
    <h4>教材助手</h4>
    <ol v-if="history.length">
      <li v-for="entry in history" :key="entry.message_id">
        <b>{{ entry.role === 'user' ? '你' : '教材助手' }}</b>
        <p v-for="part in entry.body" :key="part.part_id">{{ part.text }}</p>
        <button
          v-for="item in entry.explicit_refs.filter((ref) => ref.type === 'candidate_batch')"
          :key="item.id"
          type="button"
          @click="read(item.id).catch(showError)"
        >
          核对候选
        </button>
      </li>
    </ol>
    <form class="material-assistant" @submit.prevent="send()">
      <div v-if="reference">
        已引用上一批候选。
        <button type="button" @click="reference = undefined">移除引用</button>
      </div>
      <label>
        引用原件
        <select v-model="file">
          <option value="">选择要核对的文件</option>
          <option
            v-for="source in material.sources"
            :key="source.source_ref.id"
            :value="source.source_ref.id"
          >
            {{ source.original_name }}
          </option>
        </select>
      </label>
      <div v-if="file">
        <label>开始页 <input v-model.number="first" type="number" min="1" required /></label>
        <label>结束页 <input v-model.number="last" type="number" :min="first" required /></label>
      </div>
      <label>给教材助手发消息 <textarea v-model="draft" maxlength="4096" rows="3" /></label>
      <div>
        <button type="submit" :disabled="busy || !draft.trim()">发送</button>
        <button type="button" :disabled="busy" @click="send(true)">解析整本</button>
      </div>
    </form>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-else-if="busy" role="status">正在处理上一条消息。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <section v-if="candidateBatch" aria-label="待核对候选">
      <h4>待核对候选</h4>
      <button
        v-if="candidateBatch"
        type="button"
        :disabled="busy"
        @click="reference = candidateBatch"
      >
        引用这批候选继续修正
      </button>
      <article v-for="item in proposed" :key="item.candidate_id">
        <h5>{{ item.body.title }}</h5>
        <RichContent :content="item.body.content" />
        <details v-if="item.body.teaching_aids?.length">
          <summary>教学辅助</summary>
          <RichContent
            v-for="(aid, index) in item.body.teaching_aids"
            :key="index"
            :content="aid"
          />
        </details>
      </article>
      <ul v-if="retirements.length">
        <li v-for="title in retirements" :key="title">拟从教材解析结果撤下：{{ title }}</li>
      </ul>
      <div v-if="decisionState === 'pending'">
        <button type="button" :disabled="deciding || !completeCandidate" @click="decide('adopt')">
          采用
        </button>
        <button type="button" :disabled="deciding" @click="decide('decline')">不采用</button>
      </div>
    </section>
    <section v-if="adopted.length" aria-label="已采用内容">
      <h4>已采用内容</h4>
      <article v-for="item in adopted" :key="item.candidate_id">
        <h5>{{ item.body.title }}</h5>
        <RichContent :content="item.body.content" />
        <details v-if="item.body.teaching_aids?.length">
          <summary>教学辅助</summary>
          <RichContent
            v-for="(aid, index) in item.body.teaching_aids"
            :key="index"
            :content="aid"
          />
        </details>
      </article>
      <MaterialIntakePanel
        :items="adopted"
        :import-id="params.import_id"
        :domain-id="material.textbook.domain_id"
        :session="session"
      />
    </section>
  </section>
</template>

<style scoped>
.material-assistant,
.material-assistant label {
  display: grid;
  gap: 0.7rem;
}
.material-assistant li p {
  white-space: pre-wrap;
}
</style>
