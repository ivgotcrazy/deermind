<script setup lang="ts">
import { ref, onMounted } from 'vue';
defineProps<{title:string;wide?:boolean}>();const emit=defineEmits<{close:[]}>();const dialog=ref<HTMLDialogElement>();
onMounted(()=>dialog.value?.showModal());
</script>
<template><dialog ref="dialog" class="wb-dialog" :class="{wide}" @cancel.prevent="emit('close')" aria-labelledby="dialog-title"><header><h3 id="dialog-title">{{title}}</h3><button class="btn" aria-label="关闭对话框" @click="emit('close')">关闭</button></header><div class="dialog-content"><slot/></div></dialog></template>
