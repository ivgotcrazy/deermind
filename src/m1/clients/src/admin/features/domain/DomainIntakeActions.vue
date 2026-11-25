<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, post, postAccepted } from '../../../shared/api/http';
import type { DomainSession } from './api';

type Schema = components['schemas'];
const { item, domainId, session } = defineProps<{
  item: Schema['IntakeView'];
  domainId: string;
  session: DomainSession;
}>();
const emit = defineEmits<{ saved: [] }>();
const lifecycle = new AbortController();
const opts = { session, signal: lifecycle.signal };
const dialog = ref<HTMLDialogElement>();
const mode = ref<'associate' | 'discard'>('associate');
const choices = ref<Schema['MemberRow'][]>([]);
const parent = ref<Schema['InstanceView']>();
const parentMethods = ref<Schema['SolutionRef'][]>([]);
const addMethod = ref(false);
const chosen = ref('');
const definition = ref('');
const conditions = ref('');
const confirm = ref(false);
const busy = ref(false);
const status = ref('');
const error = ref('');
const evidence = ref<Schema['AnalysisReceipt']>();
const params = { domain_id: domainId, item_id: item.item_ref.id };
const needsMethod = computed(() => {
  const method = choices.value.find((row) => row.object_ref.object_id === chosen.value)?.object_ref;
  return (
    item.kind === 'reference' &&
    method?.kind === 'solution' &&
    !parentMethods.value.some(
      (row) => row.object_id === method.object_id && row.version === method.version,
    )
  );
});
let actionId: string | undefined;
let checkingId: string | undefined;
let timer: ReturnType<typeof setTimeout> | undefined;

function explain(cause: unknown) {
  if (!lifecycle.signal.aborted)
    error.value = cause instanceof Error ? cause.message : '暂时无法处理这条待入库内容。';
}

async function open(next: 'associate' | 'discard') {
  if (busy.value) return;
  mode.value = next;
  error.value = '';
  status.value = '';
  dialog.value?.showModal();
  if (next === 'discard') return;
  try {
    const kind =
      item.kind === 'task_instance' ? 'task' : item.kind === 'reference' ? 'solution' : 'kc';
    if (kind === 'solution') {
      parent.value = await get('/api/m1/domains/{domain_id}/intake-items/{item_id}/parent', {
        ...opts,
        params,
      });
      const task = parent.value.content.task_ref;
      const snapshot = await get('/api/m1/domains/{domain_id}/objects/{object_id}', {
        ...opts,
        params: { domain_id: domainId, object_id: task.object_id },
        query: { version: task.version },
      });
      const content = snapshot.object.content;
      parentMethods.value = 'method_refs' in content ? (content.method_refs ?? []) : [];
    }
    const lists = await get('/api/m1/domains/{domain_id}/objects', {
      ...opts,
      params: { domain_id: domainId },
      query: { kinds: [kind], limit: 100 },
    });
    choices.value = lists.items;
  } catch (cause) {
    explain(cause);
  }
}

function paragraph(text: string): Schema['CreateKnowledgeRequest']['definition']['definition'] {
  return {
    schema_version: '1',
    role: 'definition',
    data_tables: [],
    source_refs: [],
    blocks: [
      {
        block_id: 'text',
        type: 'paragraph',
        provenance: { source_refs: [], transformation: 'generated', note: '' },
        payload: { spans: [{ type: 'text', text }] },
      },
    ],
  };
}

type Confirmations = 'confirm_add_method' | 'confirm_discard_children';
type IntakeCommand = Omit<
  Schema['IntakeAction'],
  'request_id' | 'expected_revision' | Confirmations
> &
  Partial<Pick<Schema['IntakeAction'], Confirmations>>;

async function apply(data: IntakeCommand) {
  if (!item.item_ref.revision) throw new Error('请刷新这条待入库内容。');
  actionId ??= crypto.randomUUID();
  try {
    await post(
      '/api/m1/domains/{domain_id}/intake-items/{item_id}/actions',
      {
        confirm_add_method: false,
        confirm_discard_children: false,
        ...data,
        request_id: actionId,
        expected_revision: item.item_ref.revision,
      },
      { ...opts, params },
    );
  } catch (cause) {
    const saved = await get('/api/m1/requests/receipt', {
      ...opts,
      query: {
        action: 'domain.process_intake',
        resource_kind: 'domain',
        resource_id: domainId,
        request_id: actionId,
      },
    });
    if (saved.receipt_state !== 'completed') {
      if (cause instanceof ApiError && cause.status < 500) actionId = undefined;
      throw cause;
    }
  }
  dialog.value?.close();
  emit('saved');
}

async function readCheck(task: Schema['TaskRef'], solution?: Schema['SolutionRef']) {
  if (!checkingId || lifecycle.signal.aborted) return;
  try {
    const outcome = await get('/api/m1/requests/receipt', {
      ...opts,
      query: {
        action: 'domain.classify_instance',
        resource_kind: 'domain',
        resource_id: domainId,
        request_id: checkingId,
      },
    });
    if (outcome.receipt_state === 'accepted') {
      timer = setTimeout(() => void readCheck(task, solution), 2200);
      return;
    }
    if (outcome.receipt_state !== 'completed' || !outcome.result || !('output' in outcome.result))
      throw new Error(outcome.error?.message ?? '归类没有完成。');
    evidence.value = outcome.result;
    checkingId = undefined;
    if (!evidence.value.output.results.every((entry) => entry.result === 'matched')) {
      status.value = '归类未通过。';
      busy.value = false;
      return;
    }
    const check = evidence.value.check_ref;
    if (solution && parent.value) {
      await apply({
        action: 'associate_solution',
        solution_ref: solution,
        task_instance_ref: parent.value.instance_ref,
        expected_version: parent.value.instance_ref.version,
        confirm_add_method: needsMethod.value && addMethod.value,
        expected_task_version: task.version,
        classification_check_ref: check,
      });
    } else {
      await apply({ action: 'associate_task', task_ref: task, classification_check_ref: check });
    }
  } catch (cause) {
    explain(cause);
  }
  busy.value = false;
}

async function submit() {
  if (busy.value) return;
  const reference = choices.value.find(
    (entry) => entry.object_ref.object_id === chosen.value,
  )?.object_ref;
  busy.value = true;
  error.value = '';
  status.value = '';
  evidence.value = undefined;
  try {
    if (mode.value === 'discard') {
      await apply({ action: 'discard', confirm_discard_children: confirm.value });
    } else if (item.kind === 'kc') {
      if (reference?.kind === 'kc') {
        await apply({ action: 'add_kc', existing_kc_ref: reference });
      } else {
        if (!definition.value.trim() || !conditions.value.trim())
          throw new Error('请输入知识含义和适用条件。');
        await apply({
          action: 'add_kc',
          definition: {
            name: item.title,
            definition: paragraph(definition.value.trim()),
            applicability: paragraph(conditions.value.trim()),
          },
        });
      }
    } else {
      const task = reference?.kind === 'task' ? reference : parent.value?.content.task_ref;
      const solution = reference?.kind === 'solution' ? reference : undefined;
      if (!task || (item.kind === 'reference' && !solution))
        throw new Error('请选择对应的领域定义。');
      if (needsMethod.value && !addMethod.value)
        throw new Error('请确认将这条方法加入题目采用的任务。');
      checkingId ??= crypto.randomUUID();
      await postAccepted(
        '/api/m1/domains/{domain_id}/classification-checks',
        {
          request_id: checkingId,
          intake_item_ref: item.item_ref,
          task_ref: task,
          solution_ref: solution,
          confirm_add_method: needsMethod.value && addMethod.value,
        },
        { ...opts, params: { domain_id: domainId } },
      );
      status.value = '正在核对是否符合所选定义…';
      await readCheck(task, solution);
      return;
    }
  } catch (cause) {
    explain(cause);
  }
  busy.value = false;
}

onBeforeUnmount(() => {
  lifecycle.abort();
  clearTimeout(timer);
});
</script>

<template>
  <button type="button" class="secondary" @click="open('associate')">
    {{
      item.kind === 'kc' ? '添加知识成分' : item.kind === 'task_instance' ? '关联任务' : '关联方法'
    }}
  </button>
  <slot />
  <button type="button" class="destructive" @click="open('discard')">删除</button>
  <dialog ref="dialog" aria-label="处理待入库内容">
    <form @submit.prevent="submit">
      <h3>{{ mode === 'discard' ? '删除待入库内容' : '选择领域定义' }}</h3>
      <p>{{ item.title }}</p>
      <fieldset :disabled="busy">
        <template v-if="mode === 'associate'">
          <label
            >领域定义
            <select v-model="chosen">
              <option value="">{{ item.kind === 'kc' ? '新建知识成分' : '请选择' }}</option>
              <option
                v-for="entry in choices"
                :key="entry.object_ref.object_id"
                :value="entry.object_ref.object_id"
              >
                {{ entry.name }}
              </option>
            </select>
          </label>
          <label v-if="needsMethod">
            <input v-model="addMethod" type="checkbox" /> 同时把该方法加入本题采用的任务
          </label>
          <template v-if="item.kind === 'kc' && !chosen">
            <label>知识含义 <textarea v-model="definition" required /></label>
            <label>适用条件 <textarea v-model="conditions" required /></label>
          </template>
        </template>
        <label v-else-if="item.kind === 'task_instance'">
          <input v-model="confirm" type="checkbox" /> 一同移除该题尚待入库的解法
        </label>
      </fieldset>
      <p v-if="status" role="status">{{ status }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <ul v-if="evidence">
        <li v-for="assessment in evidence.output.results" :key="assessment.candidate_key">
          <p v-for="finding in assessment.findings" :key="finding.criterion">
            {{ finding.conclusion }}
          </p>
          <p v-for="issue in assessment.issues" :key="issue">{{ issue }}</p>
        </li>
      </ul>
      <footer class="editor-footer">
        <button type="button" class="secondary" @click="dialog?.close()">关闭</button
        ><button type="submit" :disabled="busy">
          {{ mode === 'discard' ? '确认删除' : '确认' }}
        </button>
      </footer>
    </form>
  </dialog>
</template>
