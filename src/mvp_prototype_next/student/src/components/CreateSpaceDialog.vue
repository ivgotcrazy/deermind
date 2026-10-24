<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { courseFlow } from '../course-flow';
import { createSpace, chapterReady } from '../../../shared/learning-flow';
const emit=defineEmits<{close:[];created:[id:string]}>();
const dialog=ref<HTMLDialogElement>(),bookId=ref(''),targetId=ref(''),error=ref('');
const courses=computed(()=>courseFlow.courses.filter(c=>c.snapshot.book.units.some(u=>u.chapters.some(ch=>chapterReady(c.snapshot,ch.id).explain))));
const books=computed(()=>[...new Map(courses.value.map(c=>[c.snapshot.book.id,c.snapshot.book])).values()]);
const targets=computed(()=>courses.value.filter(c=>c.snapshot.book.id===bookId.value));
const selected=computed(()=>targets.value.find(c=>c.id===targetId.value));
function choose(){targetId.value=targets.value.length===1?targets.value[0]!.id:'';}
function create(){try{if(!selected.value)throw Error('请选择教材和学习目标。');emit('created',createSpace(selected.value.id).id);}catch(e){error.value=(e as Error).message;}}
onMounted(()=>{if(books.value.length===1){bookId.value=books.value[0]!.id;choose();}dialog.value?.showModal();});
</script>
<template><dialog ref="dialog" class="space-dialog" aria-labelledby="create-space-title" @cancel.prevent="emit('close')"><header><h2 id="create-space-title">新建学习空间</h2><button aria-label="关闭" @click="emit('close')">×</button></header><p>选择准备好的教材和目标，每次学习时再选择章节。</p><form @submit.prevent="create"><label>教材<select aria-label="教材" v-model="bookId" @change="choose"><option value="">请选择教材</option><option v-for="b in books" :key="b.id" :value="b.id">{{b.name}}</option></select></label><label>学习目标<select aria-label="学习目标" v-model="targetId"><option value="">请选择目标</option><option v-for="c in targets" :key="c.id" :value="c.id">{{c.snapshot.target.name}}</option></select></label><p v-if="selected" class="description">{{selected.snapshot.target.description}}</p><p v-if="!books.length">管理员尚未应用可用课程，请先在后台准备内容并应用更新。</p><p v-if="error" role="alert">{{error}}</p><footer><button type="button" @click="emit('close')">取消</button><button class="primary" :disabled="!selected" type="submit">创建学习空间</button></footer></form><small>Mock 联动预览 · 本浏览器的学生 A</small></dialog></template>
<style scoped>
.space-dialog{margin:auto;max-height:90vh;overflow:auto;width:min(520px,90vw);border:1px solid #dce5df;border-radius:12px;padding:24px;color:#2c3e50}.space-dialog::backdrop{background:#1b302b66}header,footer{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{font-size:20px;margin:0}p{font-size:14px;line-height:1.7}label{display:block;font-size:14px;margin:18px 0}select{display:block;width:100%;padding:10px;margin-top:8px;border:1px solid #d4dfd9;border-radius:6px;background:white}button{font:inherit;padding:9px 16px;border:1px solid #cfddd4;border-radius:6px;background:white;cursor:pointer}.primary{background:#2d6a4f;color:white}button:disabled{opacity:.5}small{display:block;color:#7a8980;margin-top:20px}.description{background:#f4f7f5;padding:12px}
</style>
