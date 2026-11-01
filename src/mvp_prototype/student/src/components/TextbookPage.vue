<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import MaterialReader from '../../../shared/MaterialReader.vue';
import type { StudentCourse } from '../student-pages';
const props=defineProps<{course:StudentCourse;classroomIds:string[]}>();
const emit=defineEmits<{startAction:[text:string];start:[chapterIds:string[],mode:'lesson'|'test']}>();
const query=ref(''),openUnits=ref<string[]>([]),reading=ref(''),selected=ref<string[]>([]),confirmTest=ref(false);
const units=computed(()=>[...new Set(props.course.chapters.map(c=>c.unit))]);
watch(()=>props.course.id,()=>{openUnits.value=[props.course.chapters.find(c=>props.classroomIds.includes(c.id))?.unit||units.value[0]||''];selected.value=[];reading.value='';},{immediate:true});
const chapter=computed(()=>props.course.chapters.find(c=>c.id===reading.value));
const chosen=computed(()=>props.course.chapters.filter(c=>selected.value.includes(c.id)));
function toggleUnit(unit:string){openUnits.value=openUnits.value.includes(unit)?openUnits.value.filter(u=>u!==unit):[...openUnits.value,unit];}
function startTest(){emit('start',[...selected.value],'test');confirmTest.value=false;selected.value=[];}
</script>
<template><div class="student-page textbook-page">
  <header class="page-header"><div><h2>教材</h2><p class="muted">{{course.title}}</p></div></header>
  <details class="panel course-definition"><summary>当前学习目标与教材说明</summary><p>{{course.target}}</p><p class="muted">选定的教材和目标由管理员维护。你可以阅读或请求讲解；每次检测再选范围。</p><p class="tiny">{{course.note}}</p></details>
  <template v-if="chapter"><button class="back" @click="reading=''">← 返回教材目录</button><section class="panel"><h3>{{chapter.name}}</h3><MaterialReader v-if="chapter.items?.length" :items="chapter.items" :related-items="course.chapters.flatMap(c=>c.items||[])"/><template v-else><p class="tiny">示例讲义 · 用于体验阅读与讲解入口，不是出版社原页</p><p>{{chapter.description}}</p><template v-if="chapter.id==='c4-3'"><p>先明确把哪个量看作一整份。原量、增加的部分和最后的总量，需要分别表示。</p><svg viewBox="0 0 500 140" role="img" aria-label="原长80米与新增四分之一的长度示意图" style="width:100%;max-width:520px"><rect x="20" y="30" width="320" height="44" fill="#d7eade" stroke="#438268"/><rect x="340" y="30" width="80" height="44" fill="#f5dfad" stroke="#ad8a40"/><text x="120" y="58" font-size="16">原长80米</text><text x="340" y="102" font-size="14">新增原长的1/4</text><text x="120" y="130" font-size="15">现在的总长包含两段</text></svg></template><p v-else class="muted">本页用于演示目录与阅读入口；本节原书内容尚未导入。</p></template><button class="primary" @click="emit('start',[chapter.id],'lesson')">讲解这一节</button></section></template>
  <template v-else><div class="controls"><label>查找章节<input v-model="query" type="search" placeholder="章节名称或单元"/></label></div><p class="muted">选择内容阅读、讲解，或勾选本次想检测的章节。</p>
    <section v-for="unit in units.filter(u=>course.chapters.some(c=>c.unit===u&&(c.name+' '+u).includes(query)))" :key="unit" class="panel"><button class="chapter-toggle" :aria-expanded="openUnits.includes(unit)||!!query" @click="toggleUnit(unit)"><strong>{{unit}}</strong><span>{{openUnits.includes(unit)?'−':'＋'}}</span></button><template v-if="openUnits.includes(unit)||query"><article v-for="c in course.chapters.filter(c=>c.unit===unit&&(c.name+' '+unit).includes(query))" :key="c.id" class="list-row chapter-row"><div class="row"><h4>{{c.name}}</h4><span v-if="classroomIds.includes(c.id)" class="badge school">学校正在学</span></div><p class="muted">{{c.description}}</p><p v-if="c.unavailable" class="tiny">{{c.unavailable}}</p><div class="row"><div class="actions"><button @click="reading=c.id">阅读材料</button><button :disabled="!c.explain" @click="emit('start',[c.id],'lesson')">讲解</button><button :disabled="!c.test" @click="selected=[c.id];confirmTest=true">检测</button></div><label style="flex-direction:row;align-items:center"><input type="checkbox" :value="c.id" v-model="selected" :disabled="!c.test"/>加入本次检测</label></div></article></template></section>
    <p v-if="!course.chapters.length" class="empty">当前空间尚未选用已准备的教材。</p><p v-else-if="!course.chapters.some(c=>(c.name+' '+c.unit).includes(query))" class="empty">没有找到章节，可以换个名称搜索。</p>
    <div v-if="selected.length" class="panel row"><div><strong>本次检测：{{selected.length}} 节</strong><p class="muted">{{chosen.map(c=>c.name).join('、')}}</p></div><div class="actions"><button @click="selected=[]">清空</button><button class="primary" @click="confirmTest=true">查看检测范围</button></div></div>
  </template>
  <div v-if="confirmTest" class="modal-shade" @click.self="confirmTest=false"><section role="dialog" aria-modal="true" aria-label="确认本次检测范围" class="modal"><header class="row"><h3>本次想检测什么？</h3><button @click="confirmTest=false">取消</button></header><article v-for="c in chosen" :key="c.id" class="list-row"><h4>{{c.name}}</h4><p class="muted">{{c.requirements.map(r=>r.name).join('；')}}</p></article><p class="notice">先根据这些要求准备检测，开始前会说明题量与预计用时。选择只对本次活动生效。</p><button class="primary" @click="startTest">准备本次检测</button></section></div>
</div></template>
