<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { textbookData } from '../data';
import type { ClassroomReport } from '../live';
const props = defineProps<{ report?: ClassroomReport; available: boolean }>();
const emit = defineEmits<{ close: []; save: [report: ClassroomReport] }>();
const dialog = ref<HTMLDialogElement | null>(null);
const selected = ref([...(props.report?.chapters || [])]);
const unknown = ref(props.report?.unknown || false);
onMounted(() => dialog.value?.showModal());
function save() {
  emit('save', {chapters:unknown.value ? [] : [...selected.value],unknown:unknown.value,confirmedAt:new Date().toISOString()});
}
</script>

<template>
  <dialog ref="dialog" class="progress-dialog" aria-labelledby="progress-title" @close="emit('close')">
    <form @submit.prevent="save">
      <header><h3 id="progress-title">更新课堂进度</h3><button type="button" aria-label="关闭" @click="dialog?.close()">×</button></header>
      <template v-if="available">
        <p>学校现在学到哪？可以选择一章或多章。</p>
        <p v-if="report" class="confirmed-date">上次确认：{{ new Date(report.confirmedAt).toLocaleString('zh-CN') }}</p>
        <label class="unknown"><input type="checkbox" v-model="unknown"> 暂不确定</label>
        <div class="chapter-list">
          <fieldset v-for="unit in textbookData.units" :key="unit.id" :disabled="unknown">
            <legend>{{ unit.name }}</legend>
            <label v-for="chapter in unit.chapters" :key="chapter.id">
              <input type="checkbox" :value="chapter.id" v-model="selected"> {{ chapter.name }}
            </label>
          </fieldset>
        </div>
        <footer><button type="button" @click="dialog?.close()">取消</button><button class="primary" :disabled="!unknown && !selected.length">确认</button></footer>
      </template>
      <template v-else><p>当前空间还没有接入可更新的教材目录。</p><footer><button type="button" @click="dialog?.close()">关闭</button></footer></template>
    </form>
  </dialog>
</template>

<style scoped>
.progress-dialog { width: min(480px, calc(100vw - 40px)); max-height: 85vh; margin: auto; border: 1px solid #d4e4dc; border-radius: 12px; padding: 22px; color: #2c3e50; font-family: inherit; box-sizing: border-box; }
.progress-dialog::backdrop { background: #10231b66; }
header, footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3 { margin: 0; color: #1b4332; font-size: 17px; }
p { font-size: 13px; line-height: 1.6; }
.confirmed-date { font-size: 12px; color: #6b7a8a; }
button { background: white; border: 1px solid #d4e4dc; border-radius: 6px; padding: 7px 14px; cursor: pointer; font: inherit; font-size: 13px; }
header button { border: 0; font-size: 20px; }
.chapter-list { max-height: 48vh; overflow: auto; margin: 12px 0 18px; }
fieldset { border: 0; padding: 8px 0; margin: 0; }
legend { font-size: 13px; font-weight: 600; color: #2d6a4f; }
label { display: flex; align-items: center; gap: 6px; padding: 6px 4px; font-size: 13px; cursor: pointer; }
input { accent-color: #2d6a4f; }
fieldset:disabled { opacity: .45; }
footer { justify-content: flex-end; }
.primary { background: #2d6a4f; color: white; }
button:disabled { opacity: .45; cursor: default; }
</style>
