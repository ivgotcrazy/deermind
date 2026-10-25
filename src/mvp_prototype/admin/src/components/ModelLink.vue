<script setup lang="ts">
import { computed } from 'vue';
import { resolve, scopeBindings } from '../workbench/store';
import { route as routeSource } from '../workbench/navigation';
const route=routeSource;
import { preview } from '../workbench/ui';
const props=defineProps<{to:string;scope?:string;label?:string}>();
const context=computed(()=>props.scope??route.scope);
const obj=computed(()=>resolve(props.to,context.value?scopeBindings(context.value):undefined));
</script>
<template><button class="text-link model-link" @click="preview={ref:to,scope:context}" :title="obj ? `${obj.id} · v${obj.version}` : '引用缺失，查看原因'">{{label || obj?.name || to}} <small>{{obj ? `v${obj.version}` : '引用缺失'}}</small></button></template>
