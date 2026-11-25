<script setup lang="ts">
import { ElDialog, ElButton } from 'element-plus';
import { ref } from 'vue';
import { activities, type Choices, type Guide } from '../interaction/promptPreview';
import PromptText from '../interaction/PromptText.vue';

defineProps<{ guides: Guide[] }>();
const choices = defineModel<Choices>({ required: true });
const reading = ref<Guide>();
const opened = ref(false);
function view(guide: Guide | undefined) {
  if (!guide) return;
  reading.value = guide;
  opened.value = true;
}
</script>

<template>
  <section class="target-prompts" aria-label="活动 Prompt 配置">
    <h3>活动配置</h3>
    <p>为每类活动选择一个具体版本。当前为界面预览，选择不会写入后台。</p>
    <div v-for="activity in activities" :key="activity.id" class="binding-row">
      <label :for="'prompt-choice-' + activity.id">{{ activity.name }}</label>
      <select :id="'prompt-choice-' + activity.id" v-model="choices[activity.id]">
        <option :value="undefined">选择 Prompt 版本</option>
        <option
          v-for="guide in guides.filter(
            (row) =>
              row.activity === activity.id &&
              (row.status === 'published' || row.id === choices[activity.id]),
          )"
          :key="guide.id"
          :value="guide.id"
        >
          {{ guide.name }} · v{{ guide.version
          }}{{ guide.status === 'retired' ? '（已停用）' : '' }}
        </option>
      </select>
      <ElButton
        link
        type="primary"
        :disabled="!choices[activity.id]"
        :aria-label="'查看' + activity.name + ' Prompt'"
        @click="view(guides.find((row) => row.id === choices[activity.id]))"
        >查看正文</ElButton
      >
    </div>
    <ElDialog
      v-model="opened"
      :title="reading?.name"
      width="min(720px, 94vw)"
      top="6vh"
      append-to-body
      destroy-on-close
    >
      <template v-if="reading"
        ><p class="version">版本 v{{ reading.version }}</p>
        <div class="body"><PromptText :body="reading.body" /></div
      ></template>
      <template #footer><ElButton @click="opened = false">关闭</ElButton></template>
    </ElDialog>
  </section>
</template>

<style scoped>
.target-prompts {
  padding: 16px 0;
  margin: 4px 0;
  border-block: 1px solid var(--el-border-color-light);
}
.target-prompts > p,
.version {
  margin: 5px 0 14px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.binding-row {
  display: grid;
  grid-template-columns: 5em minmax(0, 26rem) max-content;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
.body {
  max-height: 55vh;
  overflow: auto;
}
@media (max-width: 600px) {
  .binding-row {
    grid-template-columns: 4em minmax(0, 1fr) max-content;
    gap: 6px;
  }
}
</style>
