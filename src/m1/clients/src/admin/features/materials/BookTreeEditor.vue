<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  ElTree,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElMessageBox,
  ElRadioGroup,
  ElRadioButton,
} from 'element-plus';
import { outline, type Edition, type Node } from '../../../shared/book/editions';
const props = defineProps<{
  edition: Edition;
  selected: string;
  busy: boolean;
  save: (nodes: Node[]) => Promise<void>;
}>();
const emit = defineEmits<{ select: [string] }>();
type Row = { id: string; label: string; children: Row[] };
const rows = computed(() => {
  const data = outline(props.edition.nodes),
    byId = new Map<string, Row>(
      data.map(({ node, title }) => [
        node.node_id,
        { id: node.node_id, label: title, children: [] },
      ]),
    );
  const roots: Row[] = [];
  for (const { node } of data) {
    (node.parent_id ? byId.get(node.parent_id)!.children : roots).push(byId.get(node.node_id)!);
  }
  return roots;
});
const expanded = computed(() => {
  const parents = new Map(props.edition.nodes.map((node) => [node.node_id, node.parent_id]));
  const path = new Set(rows.value.map((root) => root.id));
  let id: string | null | undefined = props.selected;
  while (id && !path.has(id)) {
    path.add(id);
    id = parents.get(id);
  }
  return [...path];
});
const kinds = {
  book: '全书',
  unit: '单元',
  chapter: '章',
  section: '节',
  group: '栏目',
  example: '例题',
  exercise: '练习',
  subquestion: '小问',
  solution: '解法',
  heading: '标题',
  paragraph: '段落',
  caption: '图注',
  formula: '公式',
  table: '表格',
  chart: '统计图',
  diagram: '示意图',
  image: '插图',
};
const open = ref(false),
  mode = ref<'edit' | 'add'>('edit'),
  place = ref<'child' | 'sibling'>('child');
const draft = ref<Node>(),
  base = ref<Node>(),
  text = ref(''),
  structure = ref(''),
  error = ref(''),
  saving = ref(false);
const editable = computed(() => props.edition.status === 'draft');
watch(
  () => props.edition.edition_id,
  () => {
    open.value = false;
  },
);
function start(type: 'edit' | 'add') {
  const node = props.edition.nodes.find((n) => n.node_id === props.selected);
  if (!node) return;
  mode.value = type;
  base.value = node;
  place.value = 'child';
  error.value = '';
  draft.value =
    type === 'edit'
      ? JSON.parse(JSON.stringify(node))
      : {
          node_id: crypto.randomUUID(),
          parent_id: node.node_id,
          node_kind: 'paragraph',
          sibling_order: 1,
          content: null,
          covered_page_ids: [...node.covered_page_ids],
        };
  text.value = String(draft.value?.content?.text ?? '');
  structure.value = draft.value?.content?.structure
    ? JSON.stringify(draft.value.content.structure, null, 2)
    : '';
  open.value = true;
}
async function submit() {
  if (!draft.value || !base.value || saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    const value = { ...draft.value },
      nodes = props.edition.nodes.map((n) => ({ ...n }));
    const content = { ...value.content };
    if (text.value.trim()) content.text = text.value;
    else delete content.text;
    if (structure.value.trim()) {
      const parsed = JSON.parse(structure.value);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object')
        throw Error('结构化内容须为对象。');
      content.structure = parsed;
    } else delete content.structure;
    value.content = Object.keys(content).length ? content : null;
    if (mode.value === 'edit') nodes[nodes.findIndex((n) => n.node_id === value.node_id)] = value;
    else {
      value.parent_id = place.value === 'child' ? base.value.node_id : base.value.parent_id;
      value.sibling_order =
        place.value === 'child'
          ? Math.max(
              0,
              ...nodes.filter((n) => n.parent_id === value.parent_id).map((n) => n.sibling_order),
            ) + 1
          : base.value.sibling_order + 1;
      for (const n of nodes)
        if (n.parent_id === value.parent_id && n.sibling_order >= value.sibling_order)
          n.sibling_order++;
      nodes.push(value);
    }
    await props.save(nodes);
    open.value = false;
    emit('select', value.node_id);
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    saving.value = false;
  }
}
async function remove() {
  const node = props.edition.nodes.find((n) => n.node_id === props.selected);
  if (!node?.parent_id) return;
  const ids = new Set([node.node_id]);
  for (const row of outline(props.edition.nodes))
    if (row.node.parent_id && ids.has(row.node.parent_id)) ids.add(row.node.node_id);
  try {
    await ElMessageBox.confirm(
      '将删除所选节点及其 ' + (ids.size - 1) + ' 个子节点。',
      '删除内容节点',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  try {
    await props.save(props.edition.nodes.filter((n) => !ids.has(n.node_id)));
    emit('select', node.parent_id);
  } catch (e) {
    error.value = (e as Error).message;
  }
}
</script>
<template>
  <ElTree
    aria-label="教材内容树"
    :data="rows"
    node-key="id"
    :current-node-key="selected"
    highlight-current
    :default-expanded-keys="expanded"
    :expand-on-click-node="false"
    @node-click="(row: Row) => emit('select', row.id)"
  >
    <template #default="{ data }">
      <span class="node-label" :title="data.label">{{ data.label }}</span>
      <span v-if="editable && data.id === selected" class="node-actions">
        <ElButton link type="primary" :disabled="busy" @click.stop="start('edit')">编辑</ElButton>
        <ElButton link type="primary" :disabled="busy" @click.stop="start('add')">添加</ElButton>
        <ElButton
          link
          type="danger"
          :disabled="busy || selected === rows[0]?.id"
          @click.stop="remove"
          >删除</ElButton
        >
      </span>
    </template>
  </ElTree>
  <p v-if="error && !open" role="alert">{{ error }}</p>
  <ElDialog
    v-model="open"
    :title="mode === 'add' ? '添加内容节点' : '编辑内容节点'"
    width="min(560px,92vw)"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <ElForm v-if="draft" label-position="top">
      <ElFormItem v-if="mode === 'add'" label="添加位置"
        ><ElRadioGroup v-model="place"
          ><ElRadioButton value="child">子节点</ElRadioButton
          ><ElRadioButton value="sibling" :disabled="!base?.parent_id"
            >同级节点</ElRadioButton
          ></ElRadioGroup
        ></ElFormItem
      >
      <ElFormItem label="类型"
        ><ElSelect v-model="draft.node_kind" :disabled="!draft.parent_id"
          ><ElOption
            v-for="(label, key) in kinds"
            :key="key"
            :label="label"
            :value="key"
            :disabled="key === 'book'" /></ElSelect
      ></ElFormItem>
      <ElFormItem label="正文"><ElInput v-model="text" type="textarea" :rows="4" /></ElFormItem>
      <ElFormItem
        v-if="structure || ['table', 'chart', 'formula', 'diagram'].includes(draft.node_kind)"
        label="结构化内容（JSON）"
        ><ElInput v-model="structure" type="textarea" :rows="3"
      /></ElFormItem>
      <ElFormItem label="来源页"
        ><ElSelect v-model="draft.covered_page_ids" multiple
          ><ElOption
            v-for="(p, i) in edition.pages"
            :key="p.page_id"
            :value="p.page_id"
            :label="p.printed ? '书页 ' + p.printed : '原页 ' + (i + 1)" /></ElSelect></ElFormItem
    ></ElForm>
    <p v-if="error" role="alert">{{ error }}</p>
    <template #footer
      ><ElButton @click="open = false">取消</ElButton
      ><ElButton type="primary" :loading="saving" @click="submit">保存节点</ElButton></template
    ></ElDialog
  >
</template>
<style scoped>
.node-actions {
  display: flex;
  gap: 6px;
  flex: 0 0 auto;
  margin-left: auto;
  padding-left: 6px;
}
.node-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.el-tree :deep(.el-tree-node__content) {
  min-height: 34px;
}
.el-tree {
  max-height: 60vh;
  overflow: auto;
}
.el-tree :deep(.el-tree-node__label) {
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
