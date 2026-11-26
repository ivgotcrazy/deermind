<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';
import type { MaterialDetail } from './api';

type Schema = components['schemas'];
type Chapter = { chapter_id: string; title: string };
const { material, session } = defineProps<{ material: MaterialDetail; session: DomainSession }>();
const lifecycle = new AbortController();
const book = material.textbook.textbook_id;
const domain = material.textbook.domain_id;
const opts = { session, signal: lifecycle.signal };
const endpoint = '/api/m1/textbooks/{textbook_id}/chapters/{chapter_id}/associations';
const selectedChapter = ref('');
const selectedTask = ref('');
const selectedMethods = ref<string[]>([]);
const sections = ref<Chapter[]>([]);
const tasks = ref<Schema['MemberRow'][]>([]);
const methods = ref<Schema['SolutionRef'][]>([]);
const methodNames = ref<Record<string, string>>({});
const associations = ref<Schema['ChapterAssociationView'][]>([]);
const editing = ref<Schema['ChapterAssociationView']>();
const dialog = ref<HTMLDialogElement>();
const error = ref('');
const busy = ref(false);
let reading = 0;
const params = computed(() => ({ textbook_id: book, chapter_id: selectedChapter.value }));
const taskRef = computed(
  () =>
    editing.value?.task_ref ??
    tasks.value.find((task) => task.object_ref.object_id === selectedTask.value)?.object_ref,
);
const solutionKey = (method: Schema['SolutionRef']) => method.object_id + ':' + method.version;

function displayError(cause: unknown) {
  if (!lifecycle.signal.aborted)
    error.value = cause instanceof Error ? cause.message : '暂时无法读取章节关联。';
}

async function readAssociations() {
  const version = ++reading;
  associations.value = [];
  if (!selectedChapter.value) return;
  try {
    const rows = await get(endpoint, { ...opts, params: params.value, query: { limit: 100 } });
    if (version === reading) associations.value = rows.items;
  } catch (cause) {
    if (version === reading) displayError(cause);
  }
}

async function load() {
  try {
    const [contents, definitions] = await Promise.all([
      get('/api/m1/material-imports/{import_id}/contents', {
        ...opts,
        params: { import_id: material.textbook.import_id },
        query: { catalog_only: true },
      }),
      get('/api/m1/domains/{domain_id}/objects', {
        ...opts,
        params: { domain_id: domain },
        query: { kinds: ['task', 'solution'], limit: 100 },
      }),
    ]);
    sections.value = contents.chapters as unknown as Chapter[];
    selectedChapter.value = sections.value[0]?.chapter_id ?? '';
    tasks.value = definitions.items.filter((item) => item.object_ref.kind === 'task');
    methodNames.value = Object.fromEntries(
      definitions.items.flatMap((item) =>
        item.object_ref.kind === 'solution' ? [[solutionKey(item.object_ref), item.name]] : [],
      ),
    );
  } catch (cause) {
    displayError(cause);
  }
}

async function refreshMethods() {
  const item = taskRef.value;
  methods.value = [];
  if (!item || item.kind !== 'task') return;
  try {
    const detail = await get('/api/m1/domains/{domain_id}/objects/{object_id}', {
      ...opts,
      params: { domain_id: domain, object_id: item.object_id },
      query: { version: item.version },
    });
    const content = detail.object.content;
    if (taskRef.value?.object_id === item.object_id && 'method_refs' in content)
      methods.value = content.method_refs ?? [];
  } catch (cause) {
    displayError(cause);
  }
}

function open(current?: Schema['ChapterAssociationView']) {
  error.value = '';
  editing.value = current;
  selectedTask.value = current?.task_ref.object_id ?? '';
  selectedMethods.value = current?.method_refs.map(solutionKey) ?? [];
  void refreshMethods();
  dialog.value?.showModal();
}

async function save(remove?: Schema['ChapterAssociationView']) {
  const current = remove ?? editing.value;
  const task = remove?.task_ref ?? taskRef.value;
  if (!task || task.kind !== 'task' || busy.value) return;
  busy.value = true;
  error.value = '';
  const requestId = crypto.randomUUID();
  const command: Schema['ChapterAssociationCommand'] = {
    request_id: requestId,
    action: remove ? 'remove' : editing.value ? 'update' : 'add',
    task_ref: task,
    association_id: current?.association_ref.id,
    expected_revision: current?.association_ref.revision,
    method_refs: remove
      ? []
      : methods.value.filter((method) => selectedMethods.value.includes(solutionKey(method))),
  };
  try {
    try {
      await post(endpoint, command, { ...opts, params: params.value });
    } catch (cause) {
      const receipt = await get('/api/m1/requests/receipt', {
        ...opts,
        query: {
          action: 'product.save_chapter_association',
          resource_kind: 'textbook',
          resource_id: book,
          request_id: requestId,
        },
      });
      if (receipt.receipt_state !== 'completed') throw cause;
    }
    dialog.value?.close();
    await readAssociations();
  } catch (cause) {
    displayError(cause);
  } finally {
    busy.value = false;
  }
}

function taskName(task: Schema['TaskRef']) {
  return (
    tasks.value.find((item) => item.object_ref.object_id === task.object_id)?.name ?? task.object_id
  );
}

watch(selectedChapter, () => void readAssociations());
onMounted(() => void load());
onBeforeUnmount(() => lifecycle.abort());
</script>

<template>
  <section class="editor-panel" aria-label="章节关联">
    <p v-if="!sections.length">采用教材解析结果后，可以为章节添加关联。</p>
    <template v-else>
      <div class="association-heading">
        <label
          >章节
          <select v-model="selectedChapter">
            <option
              v-for="chapter in sections"
              :key="chapter.chapter_id"
              :value="chapter.chapter_id"
            >
              {{ chapter.title }}
            </option>
          </select></label
        >
        <button type="button" class="primary" :disabled="busy" @click="open()">添加关联</button>
      </div>
      <table v-if="associations.length" class="admin-data-table">
        <thead>
          <tr>
            <th scope="col">任务</th>
            <th scope="col">本章采用的方法</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in associations" :key="row.association_ref.id">
            <th scope="row">{{ taskName(row.task_ref) }}</th>
            <td>
              {{
                row.method_refs
                  .map((method) => methodNames[solutionKey(method)] ?? method.object_id)
                  .join('、')
              }}
            </td>
            <td>
              <div class="admin-row-actions">
                <button type="button" class="secondary" :disabled="busy" @click="open(row)">
                  编辑
                </button>
                <button type="button" class="destructive" :disabled="busy" @click="save(row)">
                  取消关联
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else>本章还没有关联任务。</p>
    </template>
    <p v-if="error && !dialog?.open" role="alert">{{ error }}</p>
    <dialog ref="dialog" aria-label="配置章节关联">
      <form @submit.prevent="save()">
        <h3>{{ editing ? '编辑关联' : '添加关联' }}</h3>
        <label v-if="!editing"
          >任务
          <select
            v-model="selectedTask"
            aria-label="任务"
            required
            @change="
              selectedMethods = [];
              refreshMethods();
            "
          >
            <option value="">请选择任务</option>
            <option
              v-for="task in tasks"
              :key="task.object_ref.object_id"
              :value="task.object_ref.object_id"
            >
              {{ task.name }}
            </option>
          </select>
        </label>
        <fieldset :disabled="busy">
          <legend>本章采用的方法</legend>
          <p v-if="taskRef && !methods.length">此任务还没有可选方法。</p>
          <label v-for="method in methods" :key="solutionKey(method)">
            <input v-model="selectedMethods" type="checkbox" :value="solutionKey(method)" />
            {{ methodNames[solutionKey(method)] ?? method.object_id }}
          </label>
        </fieldset>
        <p v-if="error" role="alert">{{ error }}</p>
        <footer class="editor-footer">
          <button type="button" class="secondary" :disabled="busy" @click="dialog?.close()">
            取消</button
          ><button type="submit" :disabled="busy || !selectedMethods.length">保存</button>
        </footer>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.association-heading {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 16px;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
}
.association-heading label {
  min-width: min(100%, 16rem);
}
</style>
