<script setup lang="ts">
import type { ContentVisual } from '../model/content-visuals';
defineProps<{items?:ContentVisual[];editing?:boolean;metadata?:boolean}>();
const emit=defineEmits<{edit:[value:ContentVisual];remove:[id:string]}>();
</script>
<template><div class="content-visuals"><figure v-for="v in items||[]" :key="v.id" class="content-visual" :aria-label="v.title">
  <figcaption class="row-between"><strong>{{v.title}}</strong><span v-if="editing" class="button-row"><button type="button" class="text-link" :aria-label="'编辑图表 '+v.title" @click="emit('edit',v)">编辑</button><button type="button" class="text-link" :aria-label="'移除图表 '+v.title" @click="emit('remove',v.id)">移除</button></span></figcaption>
  <p class="multiline">{{v.description}}</p>
  <div v-if="v.kind==='relation'" class="relation-figure"><template v-for="(node,i) in v.nodes" :key="i"><span v-if="i" class="relation-arrow">{{v.links?.[i-1]}} →</span><div>{{node}}</div></template></div>
  <div v-if="v.kind==='table'&&v.table" class="table-scroll"><table class="data-table" :aria-label="v.title+'数据'"><thead><tr><th v-for="(h,i) in v.table.headers" :key="i">{{h}}</th></tr></thead><tbody><tr v-for="(row,i) in v.table.rows" :key="i"><td v-for="(cell,j) in row" :key="j">{{cell}}</td></tr></tbody></table></div>
  <p v-if="metadata" class="muted">{{v.origin}} · {{v.sourceNote}}</p>
</figure></div></template>
<style scoped>.content-visual{margin:16px 0;padding:16px;border:1px solid #dce7e1;border-radius:8px;background:#fafcfb;overflow-wrap:anywhere}.content-visual figcaption{gap:12px;flex-wrap:wrap}.relation-figure{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:center;padding:12px 0}.relation-figure>div{border:1px solid #bad1c2;border-radius:6px;padding:16px;background:#f0f7f2;white-space:pre-wrap}.relation-arrow{color:#2d6a4f}.content-visual .muted{margin-bottom:0}</style>
