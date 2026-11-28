<script setup lang="ts">
import { ElButton, ElInput, ElSelect, ElOption } from 'element-plus';
import { type Task } from './modelEditing';
const props = defineProps<{ task: Task; tasks: Task[]; editing: boolean }>();
const emit = defineEmits<{ open: [string]; add: []; remove: [number] }>();
function choices(index: number, current: string) {
  const used = props.task.methods[index]?.dependencies.map((d) => d.task_key) ?? [];
  return props.tasks.filter(
    (t) =>
      t.key !== props.task.key &&
      (t.key === current || !used.includes(t.key)) &&
      (props.task.task_type === 'composite' || t.task_type === 'knowledge'),
  );
}
</script>
<template>
  <section class="methods">
    <header>
      <h3>方法</h3>
      <ElButton v-if="editing" @click="emit('add')">添加方法</ElButton>
    </header>
    <p v-if="!task.methods.length">尚无方法</p>
    <article v-for="(method, i) in task.methods" :key="method.key">
      <template v-if="editing">
        <header>
          <label>方法名称<ElInput v-model="method.name" /></label
          ><ElButton link type="danger" @click="emit('remove', i)">移除方法</ElButton>
        </header>
        <label>步骤<ElInput v-model="method.steps" type="textarea" /></label>
        <label>依据<ElInput v-model="method.rationale" /></label
        ><label>适用条件<ElInput v-model="method.applicability" /></label> </template
      ><template v-else
        ><h4>{{ method.name }}</h4>
        <dl>
          <dt>步骤</dt>
          <dd>{{ method.steps }}</dd>
          <dt>依据</dt>
          <dd>{{ method.rationale }}</dd>
          <dt>适用条件</dt>
          <dd>{{ method.applicability }}</dd>
        </dl></template
      >
      <header>
        <strong>前置任务</strong
        ><ElButton
          v-if="editing"
          link
          type="primary"
          :disabled="!choices(i, '').length"
          @click="method.dependencies.push({ task_key: '', reason: '' })"
          >添加前置任务</ElButton
        >
      </header>
      <p v-if="!method.dependencies.length">无前置任务</p>
      <div v-for="(dep, j) in method.dependencies" :key="j" class="dependency">
        <template v-if="editing"
          ><label
            >选择任务<ElSelect v-model="dep.task_key" filterable aria-label="选择前置任务">
              <ElOption
                v-for="t in choices(i, dep.task_key)"
                :key="t.key"
                :value="t.key"
                :label="t.name" /></ElSelect
          ></label>
          <label>依赖原因<ElInput v-model="dep.reason" /></label
          ><ElButton link type="danger" @click="method.dependencies.splice(j, 1)"
            >移除依赖</ElButton
          ></template
        >
        <template v-else
          ><ElButton link type="primary" @click="emit('open', dep.task_key)">{{
            tasks.find((t) => t.key === dep.task_key)?.name
          }}</ElButton
          ><span>{{ dep.reason }}</span></template
        >
      </div>
    </article>
  </section>
</template>
<style scoped>
.methods header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.methods h3,
.methods h4 {
  margin: 8px 0;
}
.methods article {
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 14px;
  margin: 10px 0;
}
.methods label {
  display: grid;
  gap: 4px;
  margin: 8px 0;
  flex: 1;
}
.dependency {
  border-left: 2px solid var(--el-border-color);
  padding-left: 12px;
  margin: 8px 0;
}
.dependency span {
  margin-left: 8px;
}
.methods dt,
.methods p {
  color: var(--el-text-color-secondary);
}
.methods dd {
  margin: 2px 0 8px;
  white-space: pre-wrap;
}
</style>
