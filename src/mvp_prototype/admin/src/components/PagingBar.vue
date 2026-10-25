<script setup lang="ts">
import { route,setQuery } from '../workbench/navigation';
defineProps<{total:number;page?:number}>();
</script>
<template><div class="pagination"><button class="btn" :disabled="(page??route.p)<=1" @click="setQuery({p:(page??route.p)-1})">上一页</button><span>{{total}} 项 · 第 {{page??route.p}} / {{Math.max(1,Math.ceil(total/10))}} 页</span><button class="btn" :disabled="(page??route.p)*10>=total" @click="setQuery({p:(page??route.p)+1})">下一页</button></div></template>
