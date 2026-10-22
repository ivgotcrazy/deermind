<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { state, orderedSessions } from '../../structure/state';
import { liveRequest } from '../../structure/live';
import type { LiveSession } from '../../structure/live';
const search=ref(''),space=ref('all'),page=ref(1),selected=ref(''),purpose=ref(''),error=ref(''),busy=ref(false);
const data=ref<LiveSession>();
const sessions=computed(()=>orderedSessions(state.sessions.filter(s=>s.real&&(space.value==='all'||s.space===space.value)&&`${s.id} ${s.learner}`.includes(search.value))));
const pages=computed(()=>Math.max(1,Math.ceil(sessions.value.length/15)));
const rows=computed(()=>sessions.value.slice((page.value-1)*15,page.value*15));
watch([search,space],()=>{page.value=1;selected.value='';data.value=undefined;});
watch(selected,()=>{data.value=undefined;error.value='';});
async function open(){
 if(!purpose.value.trim()||!selected.value||busy.value)return;
 const id=selected.value;
 busy.value=true;error.value='';
 try{const result=await liveRequest<LiveSession>(`sessions/${id}`);if(selected.value!==id)return;data.value=result;state.access[`integrated:${id}:${Date.now()}`]=purpose.value.trim();}
 catch(e){error.value=(e as Error).message;}finally{busy.value=false;}
}
</script>
<template><section class="actual-page">
 <header><h1>实际会话</h1><p>当前浏览器中已登记的真实模型会话。服务端保存对话；此处不会补造 Observation、Policy、Evidence 或 Belief。</p></header>
 <div class="filters"><label>查找会话<input v-model="search" aria-label="查找实际会话" placeholder="会话或学生编号"/></label><label>学习空间<select v-model="space"><option value="all">全部</option><option value="school">校内数学</option><option value="external">校外数学</option></select></label></div>
 <div class="table-wrap"><table><thead><tr><th>会话</th><th>学习空间</th><th>状态</th><th>消息数</th><th>操作</th></tr></thead><tbody><tr v-for="s in rows" :key="s.id"><td>{{ s.id }}</td><td>{{ s.space }}</td><td>{{ s.status }}</td><td>{{ s.realTurns||0 }}</td><td><button @click="selected=s.id">选择会话</button></td></tr></tbody></table></div>
 <p v-if="!sessions.length">尚无已登记的真实会话。</p><div class="pager"><span>{{ sessions.length }} 条 · {{ page }}/{{ pages }} 页</span><button :disabled="page===1" @click="page--">上一页</button><button :disabled="page>=pages" @click="page++">下一页</button></div>
 <section v-if="selected" class="detail"><h2>{{ selected }}</h2><label>本次查阅用途<textarea v-model="purpose" aria-label="实际会话查阅用途" placeholder="说明核对事项，不写入模型上下文"/></label><button :disabled="!purpose.trim()||busy" @click="open">{{ busy?'读取中…':'按用途打开实际会话' }}</button><p v-if="error" role="alert">{{ error }}</p>
  <template v-if="data"><p>模型：{{ data.model }} · {{ data.phase }} · 更新于 {{ data.updatedAt }}</p><p>正式评价：尚未执行。临时模型反馈不等于正式学习状态。</p><article v-for="turn in data.turns" :key="turn.id"><b>{{ turn.role==='user'?'学生':'DeerMind' }}</b><p v-if="turn.text">{{ turn.displayText||turn.text }}</p><template v-for="(block,i) in turn.blocks" :key="i"><p v-if="block.type==='text'||block.type==='formula'">{{ block.text }}</p><p v-else-if="block.type==='question'">[{{ block.mode }} / {{ block.state }}] {{ block.prompt }}</p><p v-else-if="block.type==='bars'">{{ block.caption }}：{{ block.rows.map(r=>r.label+' '+r.value).join('，') }}</p></template><small>{{ turn.at }}<template v-if="turn.metrics"> · {{ turn.metrics.ms }} ms</template></small></article></template>
 </section>
</section></template>
<style scoped>
.actual-page{padding:24px;max-width:1300px;margin:auto}.actual-page h1{margin-bottom:12px}.actual-page p{line-height:1.8;margin:12px 0;color:#64786b}.filters{display:flex;gap:20px;margin:20px 0}.filters label,.detail>label{display:flex;flex-direction:column;gap:8px}.actual-page input,.actual-page select,.actual-page textarea{padding:10px;border:1px solid #d2ddd5;border-radius:6px;font:inherit}.actual-page button{padding:8px 12px;border:1px solid #cbdad0;border-radius:6px;background:white;color:#2d6a4f;cursor:pointer}.actual-page button:disabled{opacity:.5;cursor:not-allowed}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;padding:14px;border-bottom:1px solid #e4ebe7}.table-wrap{overflow:auto}.pager{display:flex;gap:12px;align-items:center;margin:18px 0}.detail{background:white;border:1px solid #e1e8ed;border-radius:8px;padding:24px}.detail textarea{margin-bottom:12px}.detail h2{margin-bottom:16px}.detail article{padding:20px 0;border-top:1px solid #e1e8ed}.detail article p{white-space:pre-wrap;overflow-wrap:anywhere}
</style>
