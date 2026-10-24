<script setup lang="ts">
import { materialPageUrl, type MaterialBlock } from './material-content';
defineProps<{block:MaterialBlock}>();
const box=(b:MaterialBlock)=>[b.rect[0]*10.87,b.rect[1]*15.36,b.rect[2]*10.87,b.rect[3]*15.36].join(' ');
</script>
<template><div class="material-block-view">
  <svg v-if="block.kind==='image'||block.role==='blank'" :viewBox="box(block)" :style="{maxWidth:(540*block.rect[2]*10.87/(block.rect[3]*15.36))+'px'}" role="img" :aria-label="block.title"><image :href="materialPageUrl(block.page)" width="1087" height="1536"/></svg>
  <div v-else-if="block.kind==='table'" class="material-table-wrap"><p v-if="block.unit" class="table-unit">{{block.unit}}</p><table><thead><tr><th v-for="(h,i) in block.headers" :key="i">{{h}}</th></tr></thead><tbody><tr v-for="(row,i) in block.rows" :key="i"><td v-for="(cell,j) in row" :key="j">{{cell}}</td></tr></tbody></table></div>
  <p v-else :class="{formula:block.kind==='formula'}">{{block.text}}</p>
  <p v-if="block.kind==='image'&&block.text" class="image-description">{{block.text}}</p>
</div></template>
<style scoped>
.material-block-view{min-width:0}.material-block-view svg{display:block;width:100%;height:auto;overflow:hidden;background:#fff}.material-block-view p{white-space:pre-wrap;line-height:1.85;margin:6px 0;font-size:14px}.material-block-view .formula{font-size:17px;padding:12px;background:#f5f8f5}.material-block-view .image-description,.table-unit{color:#687d70;font-size:12px}.material-table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #d4dfd8;padding:9px 7px;text-align:left;min-width:60px}th{background:#edf4ef;font-weight:500}
</style>
