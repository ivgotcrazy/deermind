<script setup lang="ts">
import { ref } from 'vue';
import { materialPageUrl } from '../model/material-content';
const props=defineProps<{page:number;pages:number[];rect:number[];editable?:boolean}>();
const emit=defineEmits<{change:[page:number,rect:number[]]}>();
const drawing=ref(false),start=ref<number[]|null>(null),selection=ref<number[]|null>(null),zoom=ref(false);
function point(event:PointerEvent){const r=(event.currentTarget as HTMLElement).getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))];}
function down(event:PointerEvent){if(!drawing.value)return;event.preventDefault();start.value=point(event);selection.value=null;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);}
function move(event:PointerEvent){if(!start.value)return;const p=point(event);selection.value=[Math.min(p[0],start.value[0]),Math.min(p[1],start.value[1]),Math.abs(p[0]-start.value[0]),Math.abs(p[1]-start.value[1])];}
function up(){if(selection.value&&selection.value[2]>.005&&selection.value[3]>.005)emit('change',props.page,selection.value);start.value=null;selection.value=null;drawing.value=false;}
function pageChange(value:number){emit('change',value,[0,0,1,1]);}
</script>
<template><section class="review-source"><div class="source-toolbar"><button class="btn" aria-label="上一原页" :disabled="pages.indexOf(page)<=0" @click="pageChange(pages[pages.indexOf(page)-1])">‹</button><label>原书页<select aria-label="原书页" :value="page" @change="pageChange(Number(($event.target as HTMLSelectElement).value))"><option v-for="p in pages" :key="p" :value="p">第 {{p}} 页</option></select></label><button class="btn" aria-label="下一原页" :disabled="pages.indexOf(page)>=pages.length-1" @click="pageChange(pages[pages.indexOf(page)+1])">›</button><button class="text-link" @click="zoom=!zoom">{{zoom?'缩小':'放大'}}</button></div>
  <div v-if="editable" class="button-row"><button class="btn" :class="{primary:drawing}" @click="drawing=!drawing">{{drawing?'在原页拖动框选':'框选出处'}}</button><span v-if="drawing" class="muted">按住鼠标，框选内容所在区域</span></div>
  <div class="source-scroll"><div class="source-image" :class="{drawing,zoom}" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="start=null;selection=null"><img :src="materialPageUrl(page)" :alt="'教材原书第'+page+'页'" draggable="false"/><div class="source-region" :style="{left:(selection||rect)[0]*100+'%',top:(selection||rect)[1]*100+'%',width:(selection||rect)[2]*100+'%',height:(selection||rect)[3]*100+'%'}"/></div></div>
</section></template>
<style scoped>.source-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.source-toolbar label{flex:1;margin:0;min-width:90px;font-size:11px}.source-toolbar select{padding:6px}.source-scroll{overflow:auto;max-height:68vh;margin-top:12px;border:1px solid #e1e8ed;background:#f6f8f7}.source-image{position:relative;line-height:0;width:100%;user-select:none}.source-image.zoom{width:190%}.source-image.drawing{cursor:crosshair;touch-action:none}.source-image img{width:100%;pointer-events:none}.source-region{position:absolute;border:2px solid #c77d25;background:#f9b75112;pointer-events:none}</style>
