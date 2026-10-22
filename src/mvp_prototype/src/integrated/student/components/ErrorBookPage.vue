<script setup lang="ts">
import { computed, watch } from 'vue';
import { historicalRecords, chapterOf, chapters } from '../../../structure/data';
import { state } from '../../../structure/state';
import { useView, inputScope } from '../workspace';
const props = defineProps<{space:string}>();
const emit = defineEmits<{startAction:[text:string,chapter:string]}>();
const view = useView(`errorbook:${props.space}`,{source:'all',chapter:'all',expanded:'',p:1,tab:'questions'});
const errors = computed(()=>state.home.reference==='none'?[]:historicalRecords('S0001',props.space).filter(r=>r.outcome==='错误'));
const filtered = computed(()=>errors.value.filter(r=>(view.source==='all'||r.source===view.source)&&(view.chapter==='all'||r.chapter===view.chapter)));
const pages = computed(()=>Math.max(1,Math.ceil(filtered.value.length/10)));
const rows = computed(()=>filtered.value.slice((view.p-1)*10,view.p*10));
const inputs = computed(()=>Object.entries(state.messages).filter(([key])=>key===inputScope(props.space)||key.startsWith(`student:S0001:${props.space}:`)).flatMap(([,messages])=>messages));
watch(()=>[view.source,view.chapter],()=>view.p=1);
watch(pages,()=>view.p=Math.min(view.p,pages.value));
</script>
<template><div class="error-book-page">
 <div class="page-header"><div><h2>错题本</h2><span class="header-sub">集中查看题目、来源和处理记录</span></div><div class="header-stats"><div class="hs-card"><span class="hs-value">{{ errors.length }}</span><span class="hs-label">示例错题</span></div><div class="hs-card"><span class="hs-value">{{ inputs.length }}</span><span class="hs-label">待处理输入</span></div></div></div>
 <div class="book-tabs"><button :class="{active:view.tab==='questions'}" @click="view.tab='questions'">错题记录</button><button :class="{active:view.tab==='inputs'}" @click="view.tab='inputs'">待处理输入</button></div>
 <template v-if="view.tab==='questions'">
 <p class="data-caption">以下为预写错题参考；真实对话与上传图片尚未经过正式判定，不自动算作错题。</p>
 <div class="filter-bar"><div class="filter-select-group"><label class="fs-label" for="error-chapter">章节</label><select id="error-chapter" class="fs-select" v-model="view.chapter"><option value="all">全部</option><option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ ch.name }}</option></select></div><div class="filter-select-group"><label class="fs-label" for="error-source">来源</label><select id="error-source" class="fs-select" v-model="view.source"><option value="all">全部</option><option>外部录入</option><option>检测</option><option>讲解练习</option></select></div><span class="filter-result">共 {{ filtered.length }} 道</span></div>
 <div class="error-list"><div v-for="err in rows" :key="err.id" class="error-card"><button class="ec-header" :aria-expanded="view.expanded===err.id" @click="view.expanded=view.expanded===err.id?'':err.id"><span class="ec-tags"><span class="ec-source">{{ err.source }}</span><span class="ec-type">预写错题</span></span><span class="ec-date">{{ err.date||'日期未知' }}</span><span class="ec-expand">{{ view.expanded===err.id?'▲':'▼' }}</span></button><div class="ec-body"><div class="ec-topic">{{ chapterOf(err.chapter)?.name }}</div><div class="ec-text">{{ err.problem||err.title }}</div></div><div class="ec-footer"><span class="ec-retry">保留原始作答与帮助条件</span><button class="ec-detect-btn" :disabled="err.chapter!=='fractions'" @click="emit('startAction',`请讲解这道题：${err.problem||chapterOf(err.chapter)?.question}。这是题库参考题，不表示我已作答。`,err.chapter)">{{ err.chapter==='fractions'?'请帮我讲讲 →':'教学内容准备中' }}</button></div><div v-if="view.expanded===err.id" class="ec-history"><div class="ech-title">原记录</div><p>作答：{{ err.answer||'未记录' }}</p><p>帮助：{{ err.help }}</p><p class="data-caption">来源编号：{{ err.id }}</p></div></div></div>
 <div class="pagination"><span>第 {{ view.p }}/{{ pages }} 页</span><button :disabled="view.p<=1" @click="view.p--">上一页</button><button :disabled="view.p>=pages" @click="view.p++">下一页</button></div><p v-if="!rows.length" class="empty">没有符合条件的错题。</p>
 </template>
 <template v-else><p class="data-caption">图片与说明仅在本地保存，尚未识别或判错。</p><article v-for="input in inputs" :key="input.id" class="error-card input-card"><span>{{ input.at }}</span><p>{{ input.text }}</p><img v-if="input.attachment" :src="input.attachment.data" :alt="input.attachment.name"/></article><p v-if="!inputs.length" class="empty">暂无待处理输入。可通过底部 ＋ 上传题目图片。</p></template>
</div></template>

<style scoped>
.error-book-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-sub { font-size: 12px; color: #8a99a8; }
.header-stats { display: flex; gap: 12px; }
.hs-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 8px;
  padding: 8px 14px; text-align: center; min-width: 60px;
}
.hs-value { display: block; font-size: 16px; font-weight: 700; }
.hs-label { font-size: 10px; color: #8a99a8; }

.filter-bar {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 16px; padding: 10px 14px;
  background: white; border: 1px solid #e1e8ed; border-radius: 8px;
}
.filter-select-group { display: flex; align-items: center; gap: 6px; }
.fs-label { font-size: 12px; color: #5a6b7a; font-weight: 500; }
.fs-select {
  padding: 5px 10px; border: 1px solid #d0d7de; background: white;
  border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit;
  color: #2c3e50; min-width: 90px;
}
.fs-select:focus { outline: none; border-color: #2d6a4f; }
.filter-result { margin-left: auto; font-size: 12px; color: #8a99a8; }

.error-list { display: flex; flex-direction: column; gap: 10px; }
.error-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden;
}
.ec-header {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  background: #f7f9fa; border-bottom: 1px solid #f0f4f7; cursor: pointer;
}
.ec-tags { display: flex; gap: 6px; flex: 1; }
.ec-source, .ec-type, .ec-status {
  font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
}
.ec-type { background: #f0f4f7; color: #5a6b7a; }
.ec-date { font-size: 11px; color: #8a99a8; }
.ec-expand { font-size: 10px; color: #8a99a8; }

.ec-body { padding: 12px 14px; }
.ec-topic { font-size: 14px; font-weight: 600; color: #2c3e50; margin-bottom: 6px; }
.ec-text { font-size: 13px; color: #3a4a5a; margin-bottom: 8px; line-height: 1.5; }
.ec-knowledge { font-size: 11px; color: #8a99a8; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.ec-kc-tag { background: #f0f4f7; color: #5a6b7a; padding: 1px 6px; border-radius: 3px; font-size: 10px; }

.ec-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; border-top: 1px solid #f0f4f7; background: #fafbfc;
}
.ec-retry { font-size: 11px; color: #8a99a8; }
.ec-detect-btn {
  background: #2d6a4f; color: white; border: none; padding: 6px 14px;
  border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
}
.ec-detect-btn:hover { background: #1b4332; }

.ec-history { padding: 12px 14px; border-top: 1px solid #f0f4f7; background: #fafbfc; }
.ech-title { font-size: 12px; font-weight: 600; color: #5a6b7a; margin-bottom: 8px; }
.ech-timeline { display: flex; flex-direction: column; gap: 6px; }
.ech-item { display: flex; gap: 10px; font-size: 12px; }
.ech-date { color: #8a99a8; width: 50px; flex-shrink: 0; }
.ech-action { color: #2c3e50; font-weight: 500; width: 80px; flex-shrink: 0; }
.ech-result { color: #5a6b7a; flex: 1; }

.empty { text-align: center; padding: 40px; color: #8a99a8; font-size: 14px; }

.error-book-page{container-type:inline-size}.ec-header{width:100%;border:0;text-align:left;font-family:inherit}.ec-source{background:#eef5f0;color:#2d6a4f}.ec-tags{flex-wrap:wrap}.ec-history p{font-size:12px;line-height:1.8}.data-caption{font-size:11px;color:#809084;line-height:1.7;margin:10px 0}.book-tabs{display:flex;gap:10px;margin-bottom:12px}.book-tabs button{border:0;background:#edf3ef;padding:7px 12px;border-radius:6px;cursor:pointer;color:#5d7064}.book-tabs .active{background:#2d6a4f;color:white}.pagination{display:flex;gap:10px;align-items:center;justify-content:flex-end;font-size:12px;margin-top:16px}.pagination button{padding:5px 8px;background:white;border:1px solid #d7e3db;border-radius:5px}.input-card{padding:16px;font-size:13px;line-height:1.8}.input-card img{display:block;max-width:100%;max-height:320px}.ec-retry{font-size:11px}
@container(max-width:520px){.page-header{flex-wrap:wrap;gap:12px}.ec-footer{flex-wrap:wrap;gap:10px}.ec-date{font-size:10px}.ec-tags{gap:5px}.header-stats{gap:16px}}

</style>
