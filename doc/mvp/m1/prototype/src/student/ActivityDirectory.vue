<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Activity } from './quarter';
const props=defineProps<{activities:Activity[];activeId?:string;reviewingId?:string;expanded:string[]}>();
const emit=defineEmits<{close:[];toggle:[id:string];locate:[id:string]}>();
const limit=ref(20);
const roots=computed(()=>props.activities.filter(a=>!a.parentId).slice().reverse().sort((a,b)=>(Date.parse(b.startedAt||'')||0)-(Date.parse(a.startedAt||'')||0)));
const currentRoot=computed(()=>{
  let item=props.activities.find(a=>a.id===props.activeId);const visited=new Set<string>();
  while(item?.parentId&&!visited.has(item.id)){visited.add(item.id);item=props.activities.find(a=>a.id===item!.parentId);}
  return item?.id;
});
const shownRoots=computed(()=>roots.value.filter((a,i)=>i<limit.value||a.id===currentRoot.value));
const rows=computed(()=>{
  const result:{activity:Activity;depth:number;hasChildren:boolean;day?:string}[]=[];
  function add(activity:Activity,depth:number,day?:string){
    if(result.some(row=>row.activity.id===activity.id))return;
    const children=props.activities.filter(a=>a.parentId===activity.id).sort((a,b)=>(Date.parse(a.startedAt||'')||0)-(Date.parse(b.startedAt||'')||0));
    result.push({activity,depth,hasChildren:children.length>0,day});
    if(props.expanded.includes(activity.id))for(const child of children)add(child,depth+1);
  }
  let previous='';
  for(const root of shownRoots.value){const day=dateLabel(root);add(root,0,day!==previous?day:undefined);previous=day;}
  return result;
});
function dateLabel(a:Activity){
  if(!a.startedAt)return '较早活动 · 时间未记录';
  const date=new Date(a.startedAt),today=new Date(),yesterday=new Date();yesterday.setDate(today.getDate()-1);
  return date.toDateString()===today.toDateString()?'今天':date.toDateString()===yesterday.toDateString()?'昨天':date.toLocaleDateString('zh-CN');
}
function timeLabel(a:Activity){
  if(!a.startedAt)return '时间未记录';
  const date=new Date(a.startedAt),parent=props.activities.find(p=>p.id===a.parentId);
  const day=parent?.startedAt&&new Date(parent.startedAt).toDateString()!==date.toDateString()?date.toLocaleDateString('zh-CN')+' ':'';
  return day+date.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false});
}
</script>
<template>
  <aside class="activity-directory" aria-label="活动目录" @keydown.esc.stop="emit('close')">
    <header><h2>活动</h2><button aria-label="收起活动目录" @click="emit('close')">收起</button></header>
    <div class="directory-scroll">
      <p v-if="!activities.length" class="muted directory-empty">开始交流后，活动会自动出现在这里。</p>
      <ul v-else class="directory-list">
        <li v-for="row in rows" :key="row.activity.id">
          <div v-if="row.day" class="directory-day">{{row.day}}</div>
          <div class="directory-row" :class="{current:activeId===row.activity.id,reviewed:reviewingId===row.activity.id}" :style="{paddingLeft:Math.min(row.depth,4)*12+'px'}">
            <button v-if="row.hasChildren" class="directory-toggle" :aria-expanded="expanded.includes(row.activity.id)" :aria-label="(expanded.includes(row.activity.id)?'收起':'展开')+'子活动：'+row.activity.title" @click="emit('toggle',row.activity.id)">{{expanded.includes(row.activity.id)?'▾':'▸'}}</button>
            <span v-else class="directory-spacer" aria-hidden="true"></span>
            <button class="directory-name" :data-activity="row.activity.id" :aria-label="'定位活动：'+row.activity.kind+' · '+row.activity.title" :aria-current="activeId===row.activity.id?'true':undefined" @click="emit('locate',row.activity.id)">
              <small><time :datetime="row.activity.startedAt" :title="row.activity.startedAt?new Date(row.activity.startedAt).toLocaleString('zh-CN'):undefined">{{timeLabel(row.activity)}}</time><span>{{row.activity.kind}}</span><b v-if="activeId===row.activity.id">当前</b></small>
              <span class="directory-title" :title="row.activity.title">{{row.activity.title}}</span>
            </button>
          </div>
        </li>
      </ul>
      <button v-if="shownRoots.length<roots.length" class="directory-more" @click="limit+=20">加载更早活动</button>
    </div>
  </aside>
</template>
