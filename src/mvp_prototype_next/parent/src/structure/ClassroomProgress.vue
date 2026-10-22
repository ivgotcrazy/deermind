<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { classroomMaterial, classroomProgress, classroomReports, confirmClassroomProgress } from './state';
import type { ClassroomChapter } from './state';
import { chapterPath } from './statusCatalog';
import type { StatusChapter } from './statusCatalog';
import './classroom-progress.css';

const props=defineProps<{learner:string;space:string;catalog:StatusChapter[];readonly?:boolean;prominent?:boolean}>();
const route=useRoute();
const material=computed(()=>classroomMaterial(props.space));
const current=computed(()=>classroomProgress(props.learner,props.space));
const history=computed(()=>[...classroomReports(props.learner,props.space)].reverse());
const label=computed(()=>!current.value?'尚未填写':current.value.status==='unknown'?'暂不确定':current.value.chapters.map(c=>c.name).join('、'));
const homeLabel=computed(()=>!current.value?'学校现在学到哪里？':current.value.status==='unknown'?'暂不确定':current.value.chapters.slice(0,2).map(c=>c.name).join('、')+(current.value.chapters.length>2?`等 ${current.value.chapters.length} 章`:''));
const dialog=ref<HTMLDialogElement>();
const trigger=ref<HTMLButtonElement>();
const mode=ref<'reported'|'unknown'>('reported');
const selected=ref<ClassroomChapter[]>([]);
const note=ref('');
const search=ref('');
const page=ref(1);
const historyLimit=ref(5);
const catalogResults=computed(()=>{
 const terms=search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
 return props.catalog.filter(c=>terms.every(term=>`${c.name} ${chapterPath(c)}`.toLocaleLowerCase().includes(term)));
});
const pages=computed(()=>Math.max(1,Math.ceil(catalogResults.value.length/8)));
const rows=computed(()=>catalogResults.value.slice((page.value-1)*8,page.value*8));
const validSelection=computed(()=>selected.value.length>0&&selected.value.every(c=>props.catalog.some(row=>row.id===c.id)));
const savedNotice=ref('');
const formatTime=(time:string)=>new Date(time).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
const formatDate=(time:string)=>new Date(time).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'numeric',day:'numeric'});
watch(search,()=>{page.value=1;});
watch(()=>[props.learner,props.space,route.fullPath],()=>{dialog.value?.close();savedNotice.value='';});
watch(()=>props.catalog,()=>{page.value=1;});
async function open(){
 mode.value=current.value?.status||'reported';selected.value=(current.value?.chapters||[]).map(c=>({...c}));note.value=current.value?.note||'';
 search.value='';page.value=1;historyLimit.value=5;savedNotice.value='';
 await nextTick();dialog.value?.showModal();
}
function close(){dialog.value?.close();}
function restoreFocus(){trigger.value?.focus({preventScroll:true});}
function toggle(chapter:StatusChapter,checked:boolean){
 selected.value=checked?[...selected.value,{id:chapter.id,name:chapter.name,path:chapterPath(chapter)}]:selected.value.filter(c=>c.id!==chapter.id);
}
function save(){
 if(props.readonly||mode.value==='reported'&&!validSelection.value)return;
 if(confirmClassroomProgress(props.learner,props.space,mode.value,selected.value,note.value)){
  savedNotice.value='课堂进度已更新，掌握情况未改变。';close();
 }
}
</script>
<template>
 <section v-if="material" class="classroom-context" :class="{'classroom-prominent':prominent}" aria-label="课堂进度">
  <div v-if="prominent" class="classroom-home-content"><p class="classroom-home-label">{{ current?.status==='reported'?'学校正在学':'学校课堂进度' }}</p><h2 :title="label">{{ homeLabel }}</h2><p v-if="current" class="classroom-home-date">上次确认 <time :datetime="current.confirmedAt">{{ formatDate(current.confirmedAt) }}</time></p></div>
  <div v-else class="classroom-context-line"><span class="classroom-label">课堂进度</span><span class="classroom-value" :title="label">{{ label }}</span></div>
  <button ref="trigger" :class="prominent?'classroom-update':'text'" :aria-label="readonly?'查看课堂进度':current?'更新课堂进度':'设置课堂进度'" @click="open">{{ readonly?'查看':prominent?(current?'更新进度':'设置进度'):(current?'更新':'设置') }}</button>
  <span class="classroom-sr" aria-live="polite" aria-atomic="true">{{ savedNotice }}</span>
 </section>
 <Teleport to="body">
  <dialog ref="dialog" class="classroom-dialog" aria-labelledby="classroom-title" aria-describedby="classroom-description" @close="restoreFocus">
   <form @submit.prevent="save">
    <header><div><h2 id="classroom-title">{{ readonly?'课堂进度':'更新课堂进度' }}</h2><p>{{ material?.name }}</p></div><button type="button" aria-label="关闭课堂进度" @click="close">×</button></header>
    <div class="classroom-dialog-body">
     <p id="classroom-description">记录学校教到哪里，不表示是否已经掌握。</p>
     <p v-if="current" class="classroom-confirmed">学生确认于 {{ formatTime(current.confirmedAt) }}（北京时间）</p>
     <template v-if="readonly">
      <p>{{ label }}</p><ul v-if="current?.status==='reported'" class="classroom-readonly-list"><li v-for="c in current.chapters" :key="c.id">{{ c.path }} · {{ c.name }}</li></ul><p v-if="current?.note">{{ current.note }}</p>
      <p class="classroom-help">由孩子在学生端更新；这里仅查看，不修改学习记录或评价。</p>
     </template>
     <template v-else>
      <fieldset class="classroom-mode"><legend>当前课堂情况</legend><label><input v-model="mode" type="radio" value="reported"/>知道正在学的章节</label><label><input v-model="mode" type="radio" value="unknown"/>暂不确定</label></fieldset>
      <section v-if="mode==='reported'" class="classroom-picker" aria-label="选择学校正在学的章节">
       <p class="classroom-help">选择正在学的章节，可多选。其他章节不会自动标为已学。</p>
       <label v-if="catalog.length>8" class="classroom-search">查找课堂章节<input v-model="search" type="search" placeholder="章节名称、分册或单元" aria-label="查找课堂章节"/></label>
       <div class="classroom-options">
        <label v-for="c in rows" :key="c.id" class="classroom-option"><input type="checkbox" :checked="selected.some(row=>row.id===c.id)" :aria-label="`${chapterPath(c)} · ${c.name}`" @change="toggle(c,($event.target as HTMLInputElement).checked)"/><span><strong>{{ c.name }}</strong><small>{{ chapterPath(c) }}</small></span></label>
        <p v-if="!rows.length">没有找到这个章节，可换一个名称或目录位置查找；找不到时可以先记录“暂不确定”。</p>
       </div>
       <div v-if="pages>1" class="classroom-pagination"><span>第 {{ page }} / {{ pages }} 页</span><button type="button" :disabled="page===1" @click="page--">上一页</button><button type="button" :disabled="page===pages" @click="page++">下一页</button></div>
       <div v-if="selected.length" class="classroom-selection"><span>已选 {{ selected.length }} 章</span><button v-for="c in selected" :key="c.id" type="button" :title="c.path" :aria-label="`取消选择 ${c.path} · ${c.name}`" @click="selected=selected.filter(row=>row.id!==c.id)">{{ c.name }} <span aria-hidden="true">×</span></button></div>
       <p v-if="selected.length&&!validSelection" class="classroom-help">有已选章节不在当前目录中，请重新选择，或先改为“暂不确定”。原记录仍保留。</p>
      </section>
      <p v-else class="classroom-help">保存后不再标注正在学的章节，之前的确认仍保留；你仍可正常求助。</p>
      <label class="classroom-note">小节或补充说明（选填）<textarea v-model="note" maxlength="160" rows="2" placeholder="例如：分数的应用（二），老师今天刚开始讲。"/></label>
     </template>
     <details v-if="history.length" class="classroom-history"><summary>查看更新记录（{{ history.length }} 次）</summary><ol><li v-for="item in history.slice(0,historyLimit)" :key="item.id"><time>{{ formatTime(item.confirmedAt) }}</time><strong>{{ item.status==='unknown'?'暂不确定':item.chapters.map(c=>c.name).join('、') }}</strong><span v-for="c in item.chapters" :key="c.id">{{ c.path }}</span><p v-if="item.note">{{ item.note }}</p><small>学生确认</small></li></ol><button v-if="historyLimit<history.length" type="button" @click="historyLimit+=5">查看更多更新</button></details>
    </div>
    <footer><button type="button" @click="close">{{ readonly?'关闭':'取消' }}</button><button v-if="!readonly" class="primary" type="submit" :disabled="mode==='reported'&&!validSelection">保存课堂进度</button></footer>
   </form>
  </dialog>
 </Teleport>
</template>
