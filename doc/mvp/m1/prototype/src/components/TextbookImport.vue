<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { loadSample, finishRecognition, type ImportDraft } from '../model/imports';
import { mockId } from '../model/textbook';
import WorkbenchDialog from './WorkbenchDialog.vue';
import MaterialContents from './MaterialContents.vue';
import { domainData, domainStorageError, saveEntity, id, type Domain } from '../model/domain';
import { prepareIntegration, normalizeExtraction } from '../model/material-integration';

const props = defineProps<{ draft: ImportDraft; hash:string }>();
const emit = defineEmits<{ back: [] }>();
const error = ref('');
const domainEditor=ref<Domain|null>(null);
const domain=computed(()=>domainData.domains.find(d=>d.id===props.draft.book.domainId));
const domainLocked=computed(()=>!!props.draft.flow?.requests.length||!!props.draft.integration?.entries.some(e=>Object.keys(e.bindings).length));
const step = computed(() => props.draft.state === 'upload' ? 0 : 1);
watch(()=>props.draft.state,state=>{if(state==='review'){if(!props.draft.integration)props.draft.integration=prepareIntegration(props.draft.book);else normalizeExtraction(props.draft.book,props.draft.integration);}},{immediate:true});
function newDomain(){domainEditor.value={id:id('DOM'),name:'',scope:'',description:'',version:0};}
function saveDomain(){if(!domainEditor.value?.name.trim())return;props.draft.book.domainId=saveEntity(domainData.domains,domainEditor.value).id;domainEditor.value=null;}
function demo(mode:'empty'|'partial'|'full'){
  if(domainLocked.value)return;
  props.draft.book.domainId=saveEntity(domainData.domains,{id:id('DOM'),name:'小学数学 · '+({empty:'空领域新建',partial:'部分已有',full:'全部已有'}[mode]),scope:'两层分率关系演示',description:'独立 mock 场景，不覆盖已有领域。',version:0}).id;
  props.draft.demo=mode;sample();
}
let timer: ReturnType<typeof setTimeout> | undefined;

function sample() { loadSample(props.draft); props.draft.reviewExamples=false;props.draft.contentReview=undefined;props.draft.flow=undefined;error.value = ''; }
function reviewSample(){
  const d=props.draft;d.contentReview=undefined;
  d.book.domainId=saveEntity(domainData.domains,{id:id('DOM'),name:'小学数学 · 四例核对',scope:'跨页解法、错误演算、统计图与平面图形',description:'独立mock示例领域，不覆盖已有定义。',version:0}).id;
  sample();d.reviewExamples=true;
  d.files=[11,49,50,93].map(page=>({id:'BNU-PAGE-'+page,name:'北师大六上-书页'+page+'.png',kind:'扫描图片',size:0}));
  d.book.name='北师大六上 · 四例核对走查';d.book.sourceNote='第11、49、50、93页；范围为四个代表性样例，不是完整书页提取。';
}
function chooseFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  if (files.some(f => !(/\.pdf$/i.test(f.name) || /^image\//.test(f.type)))) {
    error.value = '请选择PDF或扫描图片。'; input.value = ''; return;
  }
  if (props.draft.sample) props.draft.files = [];
  props.draft.sample = false;
  props.draft.files.push(...files.map(f => ({ id: mockId('SOURCE'), name: f.name, kind: /\.pdf$/i.test(f.name) ? 'PDF' : '扫描图片', size: f.size })));
  if (!props.draft.book.name) props.draft.book.name = files[0].name.replace(/\.[^.]+$/, '');
  input.value = ''; error.value = '';
}
function move(index: number, delta: number) {
  const files = props.draft.files;
  [files[index], files[index + delta]] = [files[index + delta], files[index]];
}
function process() {
  timer = setTimeout(() => {
    const draft = props.draft;
    draft.progress = Math.min(100, draft.progress + 25);
    if (draft.failNext && draft.progress === 50) {
      draft.failNext = false; draft.state = 'failed'; draft.error = '模拟识别中断，已选文件已保留。可以继续。'; return;
    }
    if (draft.progress === 100) { finishRecognition(draft); return; }
    process();
  }, 500);
}
function start() {
  const draft = props.draft;
  if(!domain.value){error.value='请先选择教材所属领域；没有合适的领域时可以新建。';return;}
  if(domainStorageError.value){error.value=domainStorageError.value;return;}
  if (!draft.files.length) { error.value = '请先选择扫描件，或载入真实教材书页。'; return; }
  if (!draft.book.name.trim()) { error.value = '请填写教材名称。'; return; }
  if (!draft.sample) {
    error.value = '本轮未接入OCR，不能整理所选文件。请使用“载入真实教材书页”走查预设结果；所选文件未上传。'; return;
  }
  error.value = ''; draft.error = ''; draft.state = 'processing'; draft.progress = 0; process();
}
function resume() { if(!domain.value||domainStorageError.value)return;props.draft.state = 'processing'; props.draft.error = ''; process(); }
onBeforeUnmount(() => { clearTimeout(timer); if (props.draft.state === 'processing') props.draft.state = 'paused'; });
</script>

<template><section class="wb-page">
  <header class="page-header"><div><button class="text-link" @click="emit('back')">← 返回教材列表</button><h2>{{draft.state==='review'?draft.book.name:'导入教材'}}</h2><p class="page-desc">{{domain?domain.name:'选择领域，再上传教材'}}{{draft.state==='review'?' · 解析内容、提交入库、建立章节关联':''}}</p></div><span class="badge">Mock</span></header>
  <p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <section v-if="draft.state==='upload'||!domain" class="panel"><div class="row-between"><h3>教材所属领域</h3><button class="btn" :disabled="domainLocked||!!domainStorageError" @click="newDomain">新建领域</button></div><label>所属领域<select aria-label="所属领域" v-model="draft.book.domainId" :disabled="domainLocked"><option value="">请选择</option><option v-if="draft.book.domainId&&!domain" :value="draft.book.domainId">原领域不存在，请重新选择</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><p class="muted">提取出的知识、方法、任务和题目均在此领域中查找或新建。已有领域可以为空。</p><p v-if="domainLocked&&!domain" class="callout amber">已有模型关联的领域无法读取。请先在领域管理核查，当前不自动改绑其他领域。</p></section>
  <template v-if="step===0">
    <div class="two-columns">
      <section class="panel"><div class="row-between"><h3>批量导入教材</h3><button class="btn primary" @click="sample">载入真实教材书页</button></div>
        <label class="upload-box">选择PDF或扫描图片<input type="file" accept=".pdf,image/*" multiple @change="chooseFiles"/></label>
        <p class="muted">原型只演示文件选择。内置真实书页可以走查固定mock结果，不运行真实识别。</p><button class="btn" @click="reviewSample">载入四例核对样例</button><p class="muted">包含跨页两解法、错误演算、漏提统计图和六种图形；同时创建独立示例领域。</p>
        <table v-if="draft.files.length" class="data-table upload-files"><thead><tr><th>文件</th><th>顺序与移除</th></tr></thead><tbody><tr v-for="(file,index) in draft.files" :key="file.id"><td>{{index+1}}. {{file.name}}<small>{{file.kind}}</small></td><td><div class="button-row"><button class="btn" :aria-label="'上移 '+file.name" :disabled="index===0" @click="move(index,-1)">↑</button><button class="btn" :aria-label="'下移 '+file.name" :disabled="index===draft.files.length-1" @click="move(index,1)">↓</button><button class="text-link" :aria-label="'移除 '+file.name" @click="draft.files.splice(index,1)">移除</button></div></td></tr></tbody></table>
        <p v-else class="empty">尚未选择文件</p>
      </section>
      <section class="panel"><h3>教材信息</h3><label>教材名称<input v-model="draft.book.name"/></label><div class="edit-pair"><label>出版社／编写方<input v-model="draft.book.publisher"/></label><label>教材版次<input v-model="draft.book.edition" placeholder="未知可留待补充"/></label><label>年级／适用对象<input v-model="draft.book.grade"/></label><label>学科<input v-model="draft.book.subject"/></label></div><label>来源说明<textarea v-model="draft.book.sourceNote" rows="4"/></label><p class="muted">没有答案或解析也可准备教材；后续解答应说明来源。</p></section>
    </div>
    <details class="mock-tools"><summary>Mock处理场景</summary><label class="check-line"><input type="checkbox" v-model="draft.failNext"/>模拟一次识别中断</label><p>以下入口创建独立演示领域，并载入五页真实原件；全部已有／部分已有会预置模型，不覆盖你原有的领域。</p><div class="button-row"><button class="btn" @click="demo('empty')">空领域新建</button><button class="btn" @click="demo('partial')">部分已有对象</button><button class="btn" @click="demo('full')">全部已有对象</button></div></details>
    <footer class="row-between"><p class="muted">{{domain?'草稿保存在本浏览器，可稍后继续。':'请先选择所属领域，再开始导入。'}}</p><button class="btn primary" :disabled="!domain||!!domainStorageError" @click="start">上传并开始整理</button></footer>
  </template>
  <section v-else-if="draft.state!=='review'" class="panel processing"><h3>{{draft.state==='processing'?'正在识别整理':draft.state==='paused'?'演示已暂停':'识别整理中断'}}</h3><p>{{draft.files.length}} 个文件 · 使用预设整理结果，不运行真实OCR</p><progress :value="draft.progress" max="100" aria-label="识别整理进度"/><p>{{draft.progress}}%</p><p v-if="draft.error" class="callout amber" role="alert">{{draft.error}}</p><p v-if="draft.state==='paused'" class="callout">演示计时器随页面离开而暂停，已保存进度可继续。真实后台任务留到工程实现。</p><button v-if="draft.state!=='processing'" class="btn primary" :disabled="!domain||!!domainStorageError" @click="resume">继续整理</button></section>
  <MaterialContents v-else-if="domain" :draft="draft" :hash="hash"/>
  <WorkbenchDialog v-if="domainEditor" title="新建所属领域" @close="domainEditor=null"><label>领域名称<input v-model="domainEditor.name"/></label><label>覆盖范围<input v-model="domainEditor.scope" placeholder="例如小学数学"/></label><label>领域说明<textarea v-model="domainEditor.description"/></label><div class="dialog-footer"><button class="btn" @click="domainEditor=null">取消</button><button class="btn primary" :disabled="!domainEditor.name.trim()" @click="saveDomain">创建并选用</button></div></WorkbenchDialog>
</section></template>
<style scoped>.import-tabs{margin:0 0 18px;flex-wrap:wrap}</style>
