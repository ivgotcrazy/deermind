<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
defineProps<{ title: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
const previous = document.activeElement as HTMLElement | null;
onMounted(() => dialog.value?.showModal());
onBeforeUnmount(() => {
  dialog.value?.close();
  previous?.focus();
});
</script>
<template>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="modal"
      @cancel.prevent="emit('close')"
      @click="$event.target === dialog && emit('close')"
    >
      <div class="modal-heading">
        <h2>{{ title }}</h2>
        <button class="icon-button" aria-label="关闭对话框" @click="emit('close')">×</button>
      </div>
      <slot /></dialog
  ></Teleport>
</template>
