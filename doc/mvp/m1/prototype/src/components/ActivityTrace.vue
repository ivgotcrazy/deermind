<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { Activity, Turn } from '../student/quarter';
const data=ref<{activities:Activity[];turns:Turn[]}>({activities:[],turns:[]});
const selected=ref(''),error=ref('');
function refresh(){try{const value=JSON.parse(localStorage.getItem('deermind-m1-student-trial-space-v1')||'null');data.value={activities:value?.activities||[],turns:value?.turns||[]};if(!data.value.activities.some(a=>a.id===selected.value))selected.value=data.value.activities.at(-1)?.id||'';error.value='';}catch{error.value='未能读取本浏览器的演示记录。';}}
onMounted(()=>{refresh();window.addEventListener('storage',refresh);});onBeforeUnmount(()=>window.removeEventListener('storage',refresh));
const activity=computed(()=>data.value.activities.find(a=>a.id===selected.value));
const turns=computed(()=>data.value.turns.filter(t=>t.activityId===selected.value));
const tree=computed(()=>{const list:{activity:Activity;depth:number}[]=[];function add(parent?:string,depth=0){for(const a of data.value.activities.filter(a=>a.parentId===parent)){list.push({activity:a,depth});add(a.id,depth+1);}}add();return list;});
</script>
<template>
  <section class="panel"><div class="row-between"><div><h3>本浏览器的学生走查记录</h3><p class="muted">模拟学生 · 北师大版数学六年级上册 · 固定脚本，未生成 Observation、Evidence 或 Belief。</p></div><button class="btn" @click="refresh">刷新记录</button></div>
    <p v-if="error" role="alert">{{error}}</p>
    <p v-if="!tree.length">还没有活动。<a href="/student/?mode=records" target="_blank">打开学生端</a>，创建学习空间并开始一次讲解或检测，再回到这里查看。</p>
    <div v-else class="trace-layout">
      <nav aria-label="活动树"><button v-for="row in tree" :key="row.activity.id" :style="{paddingLeft:12+row.depth*18+'px'}" :class="{selected:selected===row.activity.id}" @click="selected=row.activity.id"><strong>{{row.depth?'↳ ':''}}{{row.activity.kind}} · {{row.activity.title}}</strong><small>{{row.activity.status}} · {{row.activity.id}}</small></button></nav>
      <section v-if="activity" aria-label="活动运行详情"><h3>{{activity.title}}</h3><p>运行状态：{{activity.status}} · 当前蓝图节点：{{activity.state}}</p>
        <p>父活动：{{activity.parentId||'顶层活动'}}<template v-if="activity.triggerRound"> · 触发检测轮：{{activity.triggerRound}}</template></p>
        <p v-if="activity.helped">发生求助或讲解：原计划未开始轮次已取消，后续确认使用新题新轮。</p>
        <p v-if="!turns.length" class="muted">当前活动没有新消息。</p>
        <article v-for="(turn,i) in turns" :key="i"><small v-if="turn.bookReference">引用教材 · {{turn.bookReference.chapter}} · 第 {{turn.bookReference.page}} 页</small><p><b>学生：</b>{{turn.question}}</p><p v-if="turn.reply"><b>DeerMind：</b>{{turn.reply}}</p><p v-if="turn.card">展示内容：{{turn.card}}</p>
          <div v-if="turn.check"><strong>{{turn.roundId}} · {{turn.check.status}}</strong><p>{{turn.check.status==='submitted'?'提交作答':'草稿'}}：{{turn.check.answer||'未填写'}}<br>理由：{{turn.check.reason||'未填写'}}</p><p>评价：未接入；未作答不判错。</p></div>
        </article>
      </section>
    </div>
  </section>
</template>
<style scoped>
.trace-layout{display:grid;grid-template-columns:minmax(220px,32%) 1fr;gap:24px;margin-top:20px}.trace-layout nav{border-right:1px solid #dfe8e2;padding-right:12px}.trace-layout nav button{display:block;width:100%;text-align:left;border:0;background:transparent;border-radius:6px;padding:12px;color:#28563c;margin:4px 0;font:inherit;cursor:pointer}.trace-layout nav button.selected{background:#e4f1e9}.trace-layout small{display:block;color:#758579;font-size:12px;margin-top:6px}.trace-layout article{padding:16px 0;border-top:1px solid #dfe8e2;line-height:1.8;overflow-wrap:anywhere}@media(max-width:850px){.trace-layout{grid-template-columns:1fr}.trace-layout nav{border-right:0}}
</style>
