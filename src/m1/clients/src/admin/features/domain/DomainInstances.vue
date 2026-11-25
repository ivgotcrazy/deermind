<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post, postAccepted } from '../../../shared/api/http';
import RichContent from '../../../shared/content/RichContent.vue';
import type { DomainSession } from './api';

type Schema = components['schemas'];
type Content = NonNullable<Schema['InstanceCommand']['instance']>;
const { domainId, session } = defineProps<{ domainId: string; session: DomainSession }>();
const lifecycle = new AbortController();
const opts = { session, signal: lifecycle.signal, params: { domain_id: domainId } };
const endpoint = '/api/m1/domains/{domain_id}/instances';
const rows = ref<Schema['InstanceView'][]>();
const cursor = ref<string | null>(null);
const selected = ref<Schema['InstanceView']>();
const tasks = ref<Schema['MemberRow'][]>([]);
const dialog = ref<HTMLDialogElement>();
const original = ref<Schema['InstanceView']>();
const task = ref('');
const title = ref('');
const prompt = ref('');
const version = ref(1);
const note = ref('');
const error = ref('');
const status = ref('');
const busy = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

function showError(cause: unknown) {
  if (!lifecycle.signal.aborted)
    error.value = cause instanceof Error ? cause.message : '无法处理题目。';
}

async function load(next?: string) {
  try {
    const response = await get(endpoint, { ...opts, query: { cursor: next } });
    rows.value = next ? [...(rows.value ?? []), ...response.items] : response.items;
    cursor.value = response.next_cursor;
  } catch (cause) {
    showError(cause);
  }
}

async function readOlder() {
  const current = selected.value;
  if (!current) return;
  try {
    selected.value = await get('/api/m1/domains/{domain_id}/instances/{item_id}', {
      ...opts,
      params: { domain_id: domainId, item_id: current.instance_ref.object_id },
      query: { version: version.value },
    });
  } catch (cause) {
    showError(cause);
  }
}

async function open(current?: Schema['InstanceView']) {
  original.value = current;
  title.value = current?.content.title ?? '';
  task.value = current?.content.task_ref.object_id ?? '';
  prompt.value = '';
  note.value = '';
  error.value = '';
  dialog.value?.showModal();
  try {
    tasks.value = (
      await get('/api/m1/domains/{domain_id}/objects', {
        ...opts,
        query: { kinds: ['task'], limit: 100 },
      })
    ).items;
  } catch (cause) {
    showError(cause);
  }
}

async function save(command: Schema['InstanceCommand']) {
  try {
    const response = await post(endpoint, command, opts);
    selected.value = response.result;
    version.value = response.result.instance_ref.version;
    dialog.value?.close();
    status.value = '';
    await load();
  } catch (cause) {
    showError(cause);
  } finally {
    busy.value = false;
  }
}

async function awaitCheck(requestId: string, command: Schema['InstanceCommand']) {
  if (lifecycle.signal.aborted) return;
  try {
    const reply = await get('/api/m1/requests/receipt', {
      session,
      signal: lifecycle.signal,
      query: {
        action: 'domain.classify_instance',
        resource_kind: 'domain',
        resource_id: domainId,
        request_id: requestId,
      },
    });
    if (reply.receipt_state === 'accepted') {
      timer = setTimeout(() => void awaitCheck(requestId, command), 2200);
      return;
    }
    if (reply.receipt_state !== 'completed' || !reply.result || !('output' in reply.result))
      throw new Error(reply.error?.message ?? '归类检查未完成。');
    const issue = reply.result.output.results.find((item) => item.result !== 'matched');
    if (issue)
      throw new Error(
        issue.issues[0] ?? issue.findings[0]?.conclusion ?? '题目与所选定义的归类未通过。',
      );
    await save({ ...command, classification_check_ref: reply.result.check_ref });
  } catch (cause) {
    showError(cause);
    busy.value = false;
  }
}

async function submit() {
  if (busy.value) return;
  const prior = original.value;
  const taskRef =
    prior?.content.task_ref ??
    tasks.value.find((item) => item.object_ref.object_id === task.value)?.object_ref;
  if (!taskRef || taskRef.kind !== 'task') return;
  const instance: Content = prior
    ? { ...prior.content, title: title.value }
    : {
        title: title.value,
        task_ref: taskRef,
        answer_basis: null,
        source_refs: [],
        reference_solutions: [],
        statement: {
          schema_version: '1',
          role: 'statement',
          source_refs: [],
          data_tables: [],
          blocks: [
            {
              type: 'paragraph',
              block_id: 'statement',
              provenance: { source_refs: [], transformation: 'generated', note: '' },
              payload: { spans: [{ type: 'text', text: prompt.value }] },
            },
          ],
        },
      };
  const command: Schema['InstanceCommand'] = {
    action: prior ? 'update' : 'create',
    request_id: crypto.randomUUID(),
    object_ref: prior?.instance_ref,
    expected_version: prior?.instance_ref.version,
    change_note: note.value,
    instance,
  };
  busy.value = true;
  error.value = '';
  status.value = '正在核对题目与所选任务…';
  const requestId = crypto.randomUUID();
  try {
    await postAccepted(
      '/api/m1/domains/{domain_id}/classification-checks',
      {
        request_id: requestId,
        instance,
        object_ref: prior?.instance_ref,
      },
      opts,
    );
    await awaitCheck(requestId, command);
  } catch (cause) {
    showError(cause);
    busy.value = false;
  }
}

async function retire(instance: Schema['InstanceView']) {
  if (busy.value || !window.confirm('移除此题目？历史版本和引用会保留。')) return;
  busy.value = true;
  await save({
    action: 'soft_delete',
    request_id: crypto.randomUUID(),
    object_ref: instance.instance_ref,
    expected_version: instance.instance_ref.version,
    change_note: '管理员移除题目实例',
  });
}

onMounted(() => void load());
onBeforeUnmount(() => {
  lifecycle.abort();
  clearTimeout(timer);
});
</script>

<template>
  <section class="editor-panel" aria-label="题目实例">
    <div class="editor-row">
      <h3>题目实例</h3>
      <button type="button" class="primary" @click="open()">添加题目</button>
    </div>
    <p v-if="error && !dialog?.open" role="alert">{{ error }}</p>
    <p v-if="rows && !rows.length">暂无题目实例。</p>
    <ul class="editor-records">
      <li v-for="item in rows" :key="item.instance_ref.object_id">
        <button
          type="button"
          class="secondary"
          @click="
            selected = item;
            version = item.instance_ref.version;
          "
        >
          {{ item.content.title }} · v{{ item.instance_ref.version }}
        </button>
        <button type="button" class="secondary" @click="open(item)">编辑</button>
        <button type="button" class="secondary" @click="retire(item)">移除</button>
      </li>
    </ul>
    <button v-if="cursor" type="button" class="secondary" @click="load(cursor)">更多题目</button>
    <article v-if="selected">
      <h4>{{ selected.content.title }} · v{{ selected.instance_ref.version }}</h4>
      <p v-if="selected.is_deleted">已移除</p>
      <form class="version-picker" @submit.prevent="readOlder">
        <label>历史版本 <input v-model.number="version" type="number" min="1" required /></label>
        <button type="submit" class="secondary">读取版本</button>
      </form>
      <RichContent :content="selected.content.statement" />
      <details
        v-for="reference in selected.content.reference_solutions"
        :key="reference.reference_id"
      >
        <summary>题内参考 · 方法 v{{ reference.solution_ref.version }}</summary>
        <RichContent :content="reference.content" />
      </details>
    </article>
    <dialog ref="dialog" aria-label="维护题目">
      <form @submit.prevent="submit">
        <h3>{{ original ? '编辑题目' : '添加题目' }}</h3>
        <label>题目名称 <input v-model.trim="title" required :disabled="busy" /></label>
        <template v-if="!original">
          <label
            >任务
            <select v-model="task" :disabled="busy" required>
              <option value="">请选择</option>
              <option
                v-for="item in tasks"
                :key="item.object_ref.object_id"
                :value="item.object_ref.object_id"
              >
                {{ item.name }}
              </option>
            </select></label
          >
          <label>题面 <textarea v-model.trim="prompt" :disabled="busy" required /></label>
        </template>
        <label>修改说明 <input v-model.trim="note" :disabled="busy" required /></label>
        <p v-if="busy" role="status">{{ status }}</p>
        <p v-if="error" role="alert">{{ error }}</p>
        <footer class="editor-footer">
          <button type="button" class="secondary" :disabled="busy" @click="dialog?.close()">
            取消</button
          ><button type="submit" :disabled="busy">检查并保存</button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.version-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 8px;
  margin: 12px 0;
}
.version-picker input {
  max-width: 7rem;
}
</style>
