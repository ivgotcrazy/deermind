<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{ modelValue: string[] }>();
const emit = defineEmits<{ 'update:modelValue': [string[]] }>();
const svg = ref<SVGSVGElement>();
const line = ref('');
let active: number | null = null;
function point(e: PointerEvent) {
  const box = svg.value!.getBoundingClientRect();
  return `${(((e.clientX - box.left) / box.width) * 800).toFixed(1)},${(((e.clientY - box.top) / box.height) * 200).toFixed(1)}`;
}
function start(e: PointerEvent) {
  if (active !== null) return;
  active = e.pointerId;
  svg.value!.setPointerCapture(e.pointerId);
  line.value = `M${point(e)}`;
}
function move(e: PointerEvent) {
  if (active === e.pointerId) line.value += ` L${point(e)}`;
}
function finish(e: PointerEvent) {
  if (active !== e.pointerId) return;
  if (line.value) emit('update:modelValue', [...props.modelValue, line.value]);
  line.value = '';
  active = null;
}
</script>
<template>
  <div class="writing-pad">
    <div class="pad-label">
      草稿区 · 可以用笔或鼠标书写<button class="text-button" @click="emit('update:modelValue', [])">
        清空草稿
      </button>
    </div>
    <svg
      ref="svg"
      viewBox="0 0 800 200"
      preserveAspectRatio="none"
      aria-label="手写草稿区"
      @pointerdown.prevent="start"
      @pointermove.prevent="move"
      @pointerup="finish"
      @pointercancel="finish"
      @lostpointercapture="finish"
    >
      <path v-for="(path, i) in modelValue" :key="i" :d="path" />
      <path :d="line" />
    </svg>
  </div>
</template>
