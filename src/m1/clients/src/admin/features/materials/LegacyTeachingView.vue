<script setup lang="ts">
import { computed, ref } from 'vue';
import { ElTabs, ElTabPane, ElButton, ElDrawer, ElEmpty } from 'element-plus';
import type { Edition, BookTypes } from '../../../shared/book/editions';
import KnowledgeList from './KnowledgeList.vue';
import TeachingTaskDetails from './TeachingTaskDetails.vue';

const props = defineProps<{ edition: Edition }>();
const tasks = computed(() => (Array.isArray(props.edition.teaching) ? props.edition.teaching : []));
const knowledgeItems = computed(() => {
  const names = new Set(tasks.value.flatMap((t) => t.direct_knowledge.map((k) => k.name)));
  for (const entry of props.edition.entries) {
    for (const name of entry.knowledge_names) names.add(name);
  }
  return Array.from(names, (name) => ({ key: name, name }));
});
const active = ref('knowledge');
const selectedKnowledge = ref('');
const selectedTask = ref<BookTypes['TeachingTask']>();
const open = ref(false);
const definitions = computed(() =>
  tasks.value.flatMap((task) =>
    task.direct_knowledge.filter((concept) => concept.name === selectedKnowledge.value),
  ),
);
const relatedTasks = computed(() => {
  const name = selectedKnowledge.value;
  const matching = tasks.value.filter(
    (t) =>
      t.direct_knowledge.some((k) => k.name === name) ||
      t.methods.some((m) => m.knowledge.includes(name)),
  );
  const entries = props.edition.entries.filter((entry) => entry.knowledge_names.includes(name));
  return [...new Set([...matching, ...entries].map((task) => task.name))];
});

function showKnowledge(name: string) {
  selectedTask.value = undefined;
  selectedKnowledge.value = name;
  open.value = true;
}
function showTask(task: BookTypes['TeachingTask']) {
  selectedKnowledge.value = '';
  selectedTask.value = task;
  open.value = true;
}
</script>
<template>
  <p>历史版本 · 按发布时的定义查看</p>
  <ElTabs v-model="active"
    ><ElTabPane label="知识" name="knowledge">
      <KnowledgeList v-if="knowledgeItems.length" :items="knowledgeItems" @select="showKnowledge" />
      <ElEmpty v-else description="本版暂无知识" :image-size="45" /> </ElTabPane
    ><ElTabPane label="任务" name="tasks">
      <ul>
        <li v-for="t in tasks" :key="t.name">
          <ElButton link type="primary" @click="showTask(t)">{{ t.name }}</ElButton>
        </li>
        <template v-if="!tasks.length"
          ><li v-for="entry in edition.entries" :key="entry.task_ref.object_id">
            {{ entry.name }} · {{ entry.method_names.join('、') }}
          </li></template
        >
      </ul>
    </ElTabPane></ElTabs
  >
  <ElDrawer
    v-model="open"
    :title="selectedTask?.name || selectedKnowledge"
    size="min(620px, 96vw)"
    destroy-on-close
  >
    <TeachingTaskDetails v-if="selectedTask" :task="selectedTask" />
    <template v-else>
      <dl v-for="(concept, i) in definitions" :key="i">
        <dt>含义</dt>
        <dd>{{ concept.meaning }}</dd>
        <dt>适用条件</dt>
        <dd>{{ concept.applicability }}</dd>
      </dl>
      <p v-if="!definitions.length">此版本仅记录了知识名称。</p>
      <dl v-if="relatedTasks.length">
        <dt>关联任务</dt>
        <dd v-for="name in relatedTasks" :key="name">{{ name }}</dd>
      </dl>
    </template>
  </ElDrawer>
</template>
<style scoped>
dt {
  color: var(--el-text-color-secondary);
}
dd {
  margin: 4px 0 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
