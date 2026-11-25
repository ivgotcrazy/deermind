<script setup lang="ts">
import { ref } from 'vue';
import type { KnowledgeRef, MemberRef, MemberRow, Prerequisite, SolutionRef, TaskRef } from './api';

const { kind, catalog, ownerId } = defineProps<{
  kind: 'task' | 'solution';
  catalog: MemberRow[];
  ownerId: string | null;
}>();
const methods = defineModel<SolutionRef[]>('methods', { required: true });
const knowledge = defineModel<KnowledgeRef[]>('knowledge', { required: true });
const prerequisites = defineModel<Prerequisite[]>('prerequisites', { required: true });
const choice = ref<MemberRef | null>(null);
const prerequisiteChoice = ref<TaskRef | null>(null);

function caption(reference: MemberRef) {
  const row = catalog.find((item) => item.object_ref.object_id === reference.object_id);
  return `${row?.name ?? reference.object_id} · v${reference.version}`;
}

function addChoice() {
  const selected = choice.value;
  if (
    selected?.kind === 'solution' &&
    !methods.value.some((ref) => ref.object_id === selected.object_id)
  ) {
    methods.value.push(selected);
  }
  if (
    selected?.kind === 'kc' &&
    !knowledge.value.some((ref) => ref.object_id === selected.object_id)
  ) {
    knowledge.value.push(selected);
  }
  choice.value = null;
}

function removeMethod(index: number) {
  const [removed] = methods.value.splice(index, 1);
  for (const link of prerequisites.value) {
    link.method_refs = (link.method_refs ?? []).filter(
      (ref) => ref.object_id !== removed?.object_id,
    );
  }
}

function addPrerequisite() {
  const selected = prerequisiteChoice.value;
  if (
    selected &&
    !prerequisites.value.some((link) => link.task_ref.object_id === selected.object_id)
  ) {
    prerequisites.value.push({
      task_ref: selected,
      reason: '',
      applies_to: 'all',
      method_refs: [],
    });
  }
  prerequisiteChoice.value = null;
}

function toggleMethod(link: Prerequisite, method: SolutionRef, checked: boolean) {
  const present = link.method_refs ?? [];
  link.method_refs = checked
    ? [...present, method]
    : present.filter((ref) => ref.object_id !== method.object_id);
}
</script>

<template>
  <fieldset>
    <legend>{{ kind === 'task' ? '任务方法' : '直接知识成分' }}</legend>
    <ul v-if="(kind === 'task' ? methods : knowledge).length">
      <li
        v-for="(reference, index) in kind === 'task' ? methods : knowledge"
        :key="reference.object_id"
      >
        {{ caption(reference) }}
        <button
          type="button"
          @click="kind === 'task' ? removeMethod(index) : knowledge.splice(index, 1)"
        >
          取消关联
        </button>
      </li>
    </ul>
    <label>
      {{ kind === 'task' ? '选择方法' : '选择知识成分' }}
      <select v-model="choice">
        <option :value="null">请选择</option>
        <template v-for="row in catalog" :key="row.object_ref.object_id">
          <option
            v-if="row.object_ref.kind === (kind === 'task' ? 'solution' : 'kc')"
            :value="row.object_ref"
          >
            {{ row.name }} · v{{ row.object_ref.version }}
          </option>
        </template>
      </select>
    </label>
    <button type="button" :disabled="!choice" @click="addChoice">
      {{ kind === 'task' ? '关联方法' : '关联知识成分' }}
    </button>
  </fieldset>

  <fieldset v-if="kind === 'task'">
    <legend>先导任务</legend>
    <label>
      选择先导任务
      <select v-model="prerequisiteChoice">
        <option :value="null">请选择</option>
        <template v-for="row in catalog" :key="row.object_ref.object_id">
          <option
            v-if="row.object_ref.kind === 'task' && row.object_ref.object_id !== ownerId"
            :value="row.object_ref"
          >
            {{ row.name }} · v{{ row.object_ref.version }}
          </option>
        </template>
      </select>
    </label>
    <button type="button" :disabled="!prerequisiteChoice" @click="addPrerequisite">添加先导</button>
    <fieldset v-for="(link, index) in prerequisites" :key="link.task_ref.object_id">
      <legend>{{ caption(link.task_ref) }}</legend>
      <label>先导理由 <textarea v-model="link.reason" required rows="2" /></label>
      <label>
        适用范围
        <select v-model="link.applies_to" @change="link.method_refs = []">
          <option value="all">全部方法</option>
          <option value="specified">指定方法</option>
        </select>
      </label>
      <template v-if="link.applies_to === 'specified'">
        <label v-for="method in methods" :key="method.object_id" class="choice">
          <input
            type="checkbox"
            :checked="link.method_refs?.some((ref) => ref.object_id === method.object_id)"
            @change="toggleMethod(link, method, ($event.target as HTMLInputElement).checked)"
          />
          {{ caption(method) }}
        </label>
      </template>
      <button type="button" @click="prerequisites.splice(index, 1)">取消先导</button>
    </fieldset>
  </fieldset>
</template>

<style scoped>
fieldset {
  margin-block: 0.5rem;
  border: 1px solid var(--el-border-color);
}
label {
  display: grid;
  gap: 0.3rem;
  margin-block: 0.4rem;
}
.choice {
  display: flex;
  align-items: center;
}
ul {
  margin-block: 0.5rem;
  padding-inline-start: 1.4rem;
}
li {
  margin-block: 0.25rem;
}
</style>
