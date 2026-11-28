<script setup lang="ts">
import { computed, ref, toRaw, watch } from 'vue';
import {
  ElButton,
  ElTabs,
  ElTabPane,
  ElInput,
  ElSelect,
  ElOption,
  ElDrawer,
  ElMessageBox,
  ElEmpty,
  ElTag,
} from 'element-plus';
import { outline, type Edition } from '../../../shared/book/editions';
import {
  dependents,
  newTask,
  newMethod,
  prerequisites,
  type Model,
  type Selection,
  type Task,
} from './modelEditing';
import TaskMethods from './TaskMethods.vue';
import LegacyTeachingView from './LegacyTeachingView.vue';
import KnowledgeList from './KnowledgeList.vue';

const props = defineProps<{
  edition: Edition;
  tree: Edition;
  chapter?: string;
  save?: (value: Model) => Promise<void>;
}>();
const emit = defineEmits<{ source: [string] }>();
const model = computed(() =>
  !Array.isArray(props.edition.teaching) ? props.edition.teaching : undefined,
);
const editable = computed(() => props.edition.status === 'draft' && Boolean(props.save));
const tab = ref<Selection['kind']>('knowledge'),
  filter = ref(''),
  taskType = ref(''),
  text = ref('');
const open = ref(false),
  editing = ref(false),
  busy = ref(false),
  error = ref(''),
  fresh = ref(false);
const selected = ref<Selection>(),
  trail = ref<Selection[]>([]),
  draft = ref<Model>();
const data = computed(() => (editing.value ? draft.value : model.value));
const knowledge = computed(() =>
  data.value?.knowledge.find(
    (k) => k.key === selected.value?.key && selected.value.kind === 'knowledge',
  ),
);
const task = computed(() =>
  data.value?.tasks.find((t) =>
    selected.value?.kind === 'tasks'
      ? t.key === selected.value.key
      : t.knowledge_key === knowledge.value?.key,
  ),
);
const nodes = computed(() => outline(props.tree.nodes));
const chapters = computed(() =>
  nodes.value.filter((n) => ['chapter', 'unit', 'section'].includes(n.node.node_kind)),
);
const chapterOf = (id: string) => chapters.value.find((n) => n.node.node_id === id)?.title ?? '';
const nodeLabel = (id: string) => nodes.value.find((n) => n.node.node_id === id)?.title ?? id;
const byNode = computed(() => new Map(props.tree.nodes.map((node) => [node.node_id, node])));
const within = (id: string, parent: string) => {
  let node = byNode.value.get(id);
  while (node) {
    if (node.node_id === parent) return true;
    const next: string | null = node.parent_id;
    node = next ? byNode.value.get(next) : undefined;
  }
  return !parent;
};
const filteredTasks = computed(
  () =>
    model.value?.tasks.filter(
      (t) =>
        (!filter.value || within(t.chapter_id, filter.value)) &&
        (!taskType.value || t.task_type === taskType.value) &&
        t.name.includes(text.value.trim()),
    ) ?? [],
);
const filteredKnowledge = computed(
  () =>
    model.value?.knowledge.filter(
      (k) =>
        k.name.includes(text.value.trim()) &&
        (!filter.value ||
          model.value?.tasks.some(
            (t) => t.knowledge_key === k.key && within(t.chapter_id, filter.value),
          )),
    ) ?? [],
);
const lookup = (key: string) => data.value?.tasks.find((t) => t.key === key);
const label = (t: Task) => (t.task_type === 'knowledge' ? '知识任务' : '综合任务');
watch(
  () => props.chapter,
  (v) => {
    filter.value = v ?? '';
  },
  { immediate: true },
);
function show(item: Selection, nested = false) {
  if (nested && selected.value) trail.value.push(selected.value);
  else trail.value = [];
  selected.value = item;
  editing.value = false;
  error.value = '';
  open.value = true;
}
function begin() {
  if (!model.value) return;
  draft.value = structuredClone(toRaw(model.value));
  fresh.value = false;
  editing.value = true;
  error.value = '';
}
function create(kind: 'knowledge' | 'composite') {
  begin();
  if (!draft.value) return;
  const chapter = filter.value || chapters.value[0]?.node.node_id || '';
  if (kind === 'knowledge') {
    const k = { key: crypto.randomUUID(), name: '', meaning: '', applicability: '' };
    draft.value.knowledge.push(k);
    draft.value.tasks.push(newTask(chapter, k));
    selected.value = { kind: 'knowledge', key: k.key };
  } else {
    const t = newTask(chapter);
    draft.value.tasks.push(t);
    selected.value = { kind: 'tasks', key: t.key };
  }
  fresh.value = true;
  open.value = true;
  trail.value = [];
}
function pairWith(key: string) {
  const a = task.value,
    b = lookup(key);
  if (!a || !b || b.task_type !== 'knowledge' || a.key === b.key) return;
  const previous = b.knowledge_key;
  b.knowledge_key = a.knowledge_key;
  a.knowledge_key = previous;
}
function back() {
  const previous = trail.value.pop();
  if (previous) {
    selected.value = previous;
    editing.value = false;
    error.value = '';
  }
}
async function persist() {
  if (!draft.value || !props.save || busy.value) return;
  if (knowledge.value && fresh.value && task.value?.name === '掌握')
    task.value.name = '掌握' + knowledge.value.name.trim();
  if (
    !task.value?.name.trim() ||
    !task.value.chapter_id ||
    (knowledge.value && !knowledge.value.name.trim())
  ) {
    error.value = '请填写名称并选择章节。';
    return;
  }
  if (
    task.value.methods.some(
      (m) => !m.name.trim() || m.dependencies.some((d) => !d.task_key || !d.reason.trim()),
    )
  ) {
    error.value = '请填写方法名称，并为每项前置任务选择任务、说明原因。';
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    await props.save(draft.value);
    editing.value = false;
    open.value = false;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function removeSelected() {
  if (!model.value || !task.value || !props.save) return;
  const current = task.value;
  const refs = dependents(model.value, current);
  if (refs.length) {
    error.value =
      '请先调整引用本任务的方法：' +
      refs.map((r) => r.owner.name + ' / ' + r.method.name).join('、');
    return;
  }
  try {
    await ElMessageBox.confirm(
      current.knowledge_key ? '将同时删除知识及其唯一知识任务。' : '将删除任务及其全部方法。',
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    );
  } catch {
    return;
  }
  busy.value = true;
  error.value = '';
  try {
    await props.save({
      knowledge: model.value.knowledge.filter((k) => k.key !== current.knowledge_key),
      tasks: model.value.tasks.filter((t) => t.key !== current.key),
    });
    open.value = false;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
function cancel() {
  if (fresh.value) open.value = false;
  editing.value = false;
  error.value = '';
}
</script>
<template>
  <LegacyTeachingView v-if="!model" :edition="edition" />
  <div v-else class="teaching-model">
    <ElTabs v-model="tab" aria-label="提炼内容"
      ><ElTabPane label="知识" name="knowledge" /><ElTabPane label="任务" name="tasks"
    /></ElTabs>
    <div class="filters">
      <ElInput
        v-model="text"
        clearable
        :placeholder="tab === 'knowledge' ? '搜索知识' : '搜索任务'"
        aria-label="搜索提炼内容"
      />
      <ElSelect v-model="filter" clearable filterable placeholder="全部章节" aria-label="筛选章节"
        ><ElOption
          v-for="c in chapters"
          :key="c.node.node_id"
          :value="c.node.node_id"
          :label="c.title"
      /></ElSelect>
      <ElSelect
        v-if="tab === 'tasks'"
        v-model="taskType"
        clearable
        placeholder="全部任务类型"
        aria-label="筛选任务类型"
        ><ElOption label="知识任务" value="knowledge" /><ElOption
          label="综合任务"
          value="composite"
      /></ElSelect>
    </div>
    <div v-if="editable" class="actions">
      <ElButton v-if="tab === 'knowledge'" type="primary" plain @click="create('knowledge')"
        >新增知识</ElButton
      >
      <template v-else
        ><ElButton @click="create('knowledge')">新增知识任务</ElButton
        ><ElButton type="primary" plain @click="create('composite')"
          >新增综合任务</ElButton
        ></template
      >
    </div>
    <template v-if="tab === 'knowledge'">
      <KnowledgeList
        v-if="filteredKnowledge.length"
        :items="filteredKnowledge"
        @select="(key) => show({ kind: 'knowledge', key })"
      />
      <ElEmpty v-else description="当前范围暂无知识" :image-size="48" /> </template
    ><template v-else>
      <ul v-if="filteredTasks.length">
        <li v-for="t in filteredTasks" :key="t.key">
          <ElButton link type="primary" @click="show({ kind: 'tasks', key: t.key })">{{
            t.name
          }}</ElButton>
          <small
            >{{ label(t) }} · {{ chapterOf(t.chapter_id) }} · {{ t.methods.length }} 种方法</small
          >
        </li>
      </ul>
      <ElEmpty v-else description="当前范围暂无任务" :image-size="48"
    /></template>
    <ElDrawer
      v-model="open"
      :close-on-click-modal="!editing"
      :close-on-press-escape="!editing"
      :show-close="!editing && !busy"
      :title="knowledge ? knowledge.name || '新增知识' : task?.name || '新增任务'"
      size="min(620px, 96vw)"
      destroy-on-close
    >
      <section v-if="data && task" class="detail">
        <ElButton v-if="trail.length && !editing" link @click="back">返回上一项</ElButton>
        <p v-if="error" role="alert" class="problem">{{ error }}</p>
        <template v-if="knowledge">
          <template v-if="editing"
            ><label>知识名称<ElInput v-model="knowledge.name" /></label
            ><label>含义<ElInput v-model="knowledge.meaning" type="textarea" /></label>
            <label>适用条件<ElInput v-model="knowledge.applicability" type="textarea" /></label>
            <template v-if="fresh"
              ><label>对应的知识任务名称<ElInput v-model="task.name" /></label
              ><label
                >所属章节<ElSelect v-model="task.chapter_id"
                  ><ElOption
                    v-for="c in chapters"
                    :key="c.node.node_id"
                    :value="c.node.node_id"
                    :label="c.title" /></ElSelect></label
            ></template>
            <template v-else
              ><label
                >对应的知识任务<ElSelect :model-value="task.key" @change="pairWith"
                  ><ElOption
                    v-for="t in data.tasks.filter((t) => t.task_type === 'knowledge')"
                    :key="t.key"
                    :label="t.name"
                    :value="t.key" /></ElSelect
              ></label>
              <p>
                选择另一知识任务时，两项知识交换对应任务。方法和前置任务仍属于各自的任务。
              </p></template
            >
          </template>
          <template v-else
            ><dl>
              <dt>含义</dt>
              <dd>{{ knowledge.meaning }}</dd>
              <dt>适用条件</dt>
              <dd>{{ knowledge.applicability }}</dd>
              <dt>对应的知识任务</dt>
              <dd>
                <ElButton
                  link
                  type="primary"
                  @click="show({ kind: 'tasks', key: task.key }, true)"
                  >{{ task.name }}</ElButton
                >
              </dd>
            </dl></template
          >
        </template>
        <template v-else>
          <ElTag>{{ label(task) }}</ElTag>
          <template v-if="editing"
            ><label>任务名称<ElInput v-model="task.name" /></label>
            <label
              >所属章节<ElSelect v-model="task.chapter_id" @change="task.source_nodes = []"
                ><ElOption
                  v-for="c in chapters"
                  :key="c.node.node_id"
                  :value="c.node.node_id"
                  :label="c.title" /></ElSelect
            ></label>
            <label
              >原文来源<ElSelect v-model="task.source_nodes" multiple filterable collapse-tags
                ><ElOption
                  v-for="n in nodes.filter((n) => within(n.node.node_id, task!.chapter_id))"
                  :key="n.node.node_id"
                  :value="n.node.node_id"
                  :label="n.title" /></ElSelect
            ></label>
            <label>任务说明<ElInput v-model="task.description" type="textarea" /></label>
            <label>预期产出<ElInput v-model="task.expected_output" type="textarea" /></label>
            <label>完成条件<ElInput v-model="task.completion_conditions" type="textarea" /></label>
            <label v-if="task.knowledge_key"
              >证据不足示例<ElInput v-model="task.insufficient_example" /></label
          ></template>
          <template v-else
            ><dl>
              <dt v-if="task.knowledge_key">对应知识</dt>
              <dd v-if="task.knowledge_key">
                <ElButton
                  link
                  type="primary"
                  @click="show({ kind: 'knowledge', key: task.knowledge_key }, true)"
                  >{{ data.knowledge.find((k) => k.key === task!.knowledge_key)?.name }}</ElButton
                >
              </dd>
              <dt>所属章节</dt>
              <dd>{{ chapterOf(task.chapter_id) }}</dd>
              <dt>任务说明</dt>
              <dd>{{ task.description }}</dd>
              <dt>预期产出</dt>
              <dd>{{ task.expected_output }}</dd>
              <dt>完成条件</dt>
              <dd>{{ task.completion_conditions }}</dd>
              <template v-if="task.knowledge_key"
                ><dt>证据不足示例</dt>
                <dd>{{ task.insufficient_example }}</dd></template
              >
              <dt>原文来源</dt>
              <dd v-for="id in task.source_nodes" :key="id">
                <ElButton
                  v-if="save"
                  link
                  type="primary"
                  @click="
                    open = false;
                    emit('source', id);
                  "
                  >{{ nodeLabel(id) }}</ElButton><a
                  v-else
                  :href="`/admin/?textbook=${edition.textbook_id}&tree=${tree.edition_id}&extraction=${edition.edition_id}&node=${id}#textbooks`"
                  >{{ nodeLabel(id) }}</a
                >
              </dd>
            </dl></template
          >
          <TaskMethods
            :task="task"
            :tasks="data.tasks"
            :editing="editing"
            @add="task.methods.push(newMethod())"
            @remove="(index) => task!.methods.splice(index, 1)"
            @open="(key) => show({ kind: 'tasks', key }, true)"
          />
        </template>
        <template v-if="!editing"
          ><h3>{{ knowledge ? '前置知识' : '全部方法涉及的前置任务' }}</h3>
          <ElButton
            v-for="key in prerequisites(task)"
            :key="key"
            link
            type="primary"
            @click="
              knowledge && lookup(key)?.knowledge_key
                ? show({ kind: 'knowledge', key: lookup(key)!.knowledge_key! }, true)
                : show({ kind: 'tasks', key }, true)
            "
            >{{
              knowledge
                ? data.knowledge.find((k) => k.key === lookup(key)?.knowledge_key)?.name
                : lookup(key)?.name
            }}</ElButton
          >
          <p v-if="!prerequisites(task).length">无</p>
          <h3>哪些方法依赖它</h3>
          <p v-if="!dependents(data, task).length">无</p>
          <div v-for="r in dependents(data, task)" :key="r.owner.key + r.method.key">
            <ElButton link type="primary" @click="show({ kind: 'tasks', key: r.owner.key }, true)"
              >{{ r.owner.name }} / {{ r.method.name }}</ElButton
            >
          </div>
        </template>
      </section>
      <template v-if="editable" #footer
        ><div class="footer">
          <template v-if="editing"
            ><ElButton :disabled="busy" @click="cancel">取消</ElButton
            ><ElButton type="primary" :loading="busy" @click="persist">保存草稿</ElButton></template
          >
          <template v-else
            ><ElButton type="danger" plain :disabled="busy" @click="removeSelected">删除</ElButton
            ><ElButton type="primary" @click="begin">编辑</ElButton></template
          >
        </div></template
      >
    </ElDrawer>
  </div>
</template>
<style scoped>
.filters,
.actions,
.footer {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 8px 0;
}
.filters > * {
  flex: 1 1 128px;
}
.footer {
  justify-content: flex-end;
}
.teaching-model ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.teaching-model li {
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.teaching-model small {
  display: block;
  color: var(--el-text-color-secondary);
  margin-top: 3px;
}
.detail label {
  display: grid;
  gap: 5px;
  margin-bottom: 14px;
}
.detail dt,
.detail p {
  color: var(--el-text-color-secondary);
}
.detail dd {
  margin: 3px 0 12px;
  white-space: pre-wrap;
}
.detail dd :deep(.el-button),
.teaching-model li :deep(.el-button) {
  max-width: 100%;
  height: auto;
  text-align: left;
  white-space: normal;
  overflow-wrap: anywhere;
}
.detail h3 {
  font-size: 16px;
  margin: 18px 0 6px;
}
.detail .problem {
  color: var(--el-color-danger);
}
</style>
