<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import Learner from './Learner.vue';
import Admin from './Admin.vue';
import { state, storageWarning, scriptedPreview } from './state';
import type { Role } from './data';
const route=useRoute();
const raw=new URLSearchParams(location.search).get('role');
const role:Role=raw==='admin'||raw==='parent'?raw:'student';
const area=computed(()=>String(route.params.page||''));
const homeTools=ref(false);
const isHome=computed(()=>role==='student'&&(!area.value||['home','status'].includes(area.value)));
function switchRole(e:Event){location.href=`structure.html?role=${(e.target as HTMLSelectElement).value}`;}
const previewLink=computed(()=>{const url=new URL(location.href);if(scriptedPreview)url.searchParams.delete('preview');else url.searchParams.set('preview','scripted');url.hash='#/chapter?chapter=fractions';return url.href;});
</script>
<template><div class="wireframe" :class="role"><div class="review-strip"><span>交互试用 <b>{{ state.sessions.some(s=>s.id===String(route.query.id)&&s.real)&&area==='lesson'?'真实模型 · 临时反馈，未更新学习状态':scriptedPreview?'预写走查 · 合成教学情境':'章节状态与历史资料为预写参考' }}</b></span><div><button v-if="isHome" class="text" @click="homeTools=!homeTools" :aria-expanded="homeTools">首页情境</button><a v-if="role==='student'" :href="previewLink">{{ scriptedPreview?'返回交互试用':'预写走查' }}</a><a href="phase4.html">旧流程工具</a><label>评审视角 <select :value="role" @change="switchRole" aria-label="评审视角"><option value="student">学生</option><option value="parent">家长</option><option value="admin">管理员</option></select></label></div></div>
 <div v-if="isHome&&homeTools" class="home-review" aria-label="首页情境设置"><label>参考资料<select v-model="state.home.reference" aria-label="首页参考资料"><option value="available">已有学习评价参考</option><option value="unassessed">有记录，尚无评价</option><option value="none">首次学习，无历史参考</option></select></label><label>时间情境<select v-model.number="state.home.timePreview" aria-label="首页时间情境"><option :value="0">实际计时未接入</option><option :value="26">示例：今日 26 分钟</option><option :value="30">示例：今日 30 分钟</option></select></label><label>目录规模<select v-model.number="state.home.catalogScale" aria-label="章节目录规模"><option :value="3">3 章参考</option><option :value="30">30 章规模走查</option><option :value="300">300 章规模走查</option></select></label><p>新增目录为合成材料，无学习评价或教学内容，不代表真实教材。仅切换预写参考，不删除本轮实际活动。这里是评审工具，不是学生功能。</p></div>
 <p v-if="storageWarning" role="alert" class="storage-warning">{{ storageWarning }}</p><Admin v-if="role==='admin'" :page="area"/><Learner v-else :parent="role==='parent'" :page="area"/></div></template>
