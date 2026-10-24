<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { route, go } from '../workbench/navigation';
import { domainMock } from '../workbench/domain-mock';
import { mockId, recordBookChange, type MaterialChapter } from '../workbench/textbook-mock';
import { targetMock, recordTargetChange } from '../workbench/target-mock';
import { evaluationMock } from '../workbench/evaluation-mock';
import { flow, applyTargets } from '../workbench/learning-flow';
import { chapterReady } from '../../../shared/learning-flow';
import { textbookImports, newImport, importBook, fillSample, fillRealSample, finishRecognition, pageLocation, savePage, scanFixtures, mappingIssues, acceptMapping, suggestTarget, applicationIssues } from '../workbench/textbook-import';
import ChapterMappingPanel from './ChapterMappingPanel.vue';
import ImportedScanPage from './ImportedScanPage.vue';
import MaterialOrganizeWorkspace from './MaterialOrganizeWorkspace.vue';

const location=window.location;
const focusPage=ref<number>();
function useRealBook(){if(draft.value?.pages.length){const id=newImport();fillRealSample(textbookImports.find(d=>d.id===id)!);go('textbooks',{tab:'import',source:id});}else fillRealSample(draft.value!);}
const draft=computed(()=>textbookImports.find(d=>d.id===route.source));
const book=computed(()=>draft.value&&importBook(draft.value));
const chapters=computed(()=>book.value?.units.flatMap(u=>u.chapters)||[]);
const current=computed(()=>draft.value?.pages.find(p=>p.id===draft.value?.selectedPage)||draft.value?.pages[0]);
const selectedChapter=computed({get:()=>draft.value?.mappingChapterId||current.value?.chapterId||chapters.value[0]?.id||'',set:(id:string)=>{if(draft.value)draft.value.mappingChapterId=id;}});
const mappingChapter=computed(()=>chapters.value.find(c=>c.id===selectedChapter.value)||chapters.value[0]);
const readyChapters=computed(()=>chapters.value.filter(c=>c.checked));
const target=computed(()=>targetMock.targets.find(t=>t.id===draft.value?.targetId));
const applicationChanged=computed(()=>{const applied=flow.courses.find(c=>c.snapshot.book.id===book.value?.id&&c.snapshot.target.id===target.value?.id);return !!applied&&(JSON.stringify(applied.snapshot.book)!==JSON.stringify(book.value)||JSON.stringify(applied.snapshot.target)!==JSON.stringify(target.value));});
const targets=computed(()=>targetMock.targets.filter(t=>t.bookId===book.value?.id));
const stepNames=['上传扫描件','识别整理','核对修正','关联模型','目标与应用'];
const text=ref(''),chapterId=ref(''),label=ref(''),printedPage=ref(''),error=ref(''),notice=ref(''),filter=ref('all'),zoom=ref(false);
const savedText=computed(()=>draft.value&&current.value?pageLocation(draft.value,current.value):undefined);
const dirty=computed(()=>!!savedText.value&&(text.value!==savedText.value.text||chapterId.value!==current.value?.chapterId||label.value!==savedText.value.label||printedPage.value!==savedText.value.printedPage));
watch(()=>current.value?.id,()=>loadPage(),{immediate:true});
watch(()=>draft.value?.step,()=>nextTick(()=>document.querySelector('.page-container')?.scrollTo({top:0})));
function loadPage(){const loc=savedText.value;if(loc){text.value=loc.text;chapterId.value=current.value!.chapterId;label.value=loc.label;printedPage.value=loc.printedPage;}error.value='';}
function switchPage(id:string){if(dirty.value){error.value='当前页有未保存的修改，请先保存核对结果或撤销修改。';return;}draft.value!.selectedPage=id;zoom.value=false;notice.value='';}
function nextStep(step:number){if(dirty.value&&draft.value?.step===2){error.value='请先保存当前页的修改。';return;}error.value='';draft.value!.step=step;}
function filesChanged(event:Event){
  const files=Array.from((event.target as HTMLInputElement).files||[]);if(!files.length||!draft.value)return;
  if(files.some(f=>!(/\.pdf$/i.test(f.name)||/^image\//.test(f.type)))){error.value='请选择 PDF 或扫描图片。';return;}
  draft.value.files.push(...files.map(f=>({id:mockId('SOURCE'),name:f.name,kind:/\.pdf$/i.test(f.name)?'PDF':'扫描图片',size:f.size})));
  if(!draft.value.book.name)draft.value.book.name=files[0]!.name.replace(/\.[^.]+$/,'');
  error.value='';(event.target as HTMLInputElement).value='';
}
function move(index:number,delta:number){const files=draft.value!.files;[files[index],files[index+delta]]=[files[index+delta]!,files[index]!];}
function start(){
  const d=draft.value!;
  if(!d.files.length){error.value='请先选择扫描件，或使用示例扫描件。';return;}
  if(!d.book.name.trim()||!domainMock.domains.some(x=>x.id===d.book.domainId)){error.value='请填写教材名称并选择关联领域。';return;}
  error.value='';d.step=1;d.state='processing';d.progress=0;d.error='';process(d.id);
}
let timer:ReturnType<typeof setTimeout>|undefined,runningId='';
function process(id:string){
  runningId=id;
  timer=setTimeout(()=>{
    const d=textbookImports.find(d=>d.id===id);if(!d||d.state!=='processing')return;
    d.progress=Math.min(100,d.progress+25);
    if(d.failNext&&d.progress===50){d.failNext=false;d.state='failed';d.error='模拟识别中断，已选文件已保留。可以重试。';return;}
    if(d.progress===100){finishRecognition(d);return;}
    process(id);
  },500);
}
function retry(){draft.value!.state='processing';draft.value!.error='';process(draft.value!.id);}
function pause(){clearTimeout(timer);const d=textbookImports.find(d=>d.id===runningId);if(d?.state==='processing'){d.state='failed';d.error='识别整理已暂停，可继续处理。';}}
onBeforeUnmount(pause);
function confirmPage(){
  try{savePage(draft.value!,current.value!,text.value,chapterId.value,label.value,printedPage.value);loadPage();notice.value='本页已保存并核对。';error.value='';}
  catch(e){error.value=(e as Error).message;}
}
function renameChapter(ch:MaterialChapter,event:Event){ch.name=(event.target as HTMLInputElement).value;recordBookChange(book.value!,'调整识别目录');}
function useMapping(){try{acceptMapping(draft.value!,mappingChapter.value!.id);error.value='';notice.value='已采用建议，可在下方继续修改方法和来源。';}catch(e){error.value=(e as Error).message;}}
function prepareTarget(){try{suggestTarget(draft.value!);error.value='';}catch(e){error.value=(e as Error).message;}}
function apply(){
  const issues=applicationIssues(draft.value!);if(issues.length){error.value=issues.join(' ');return;}
  try{recordTargetChange(target.value!,'核对导入教材的目标要求');applyTargets(book.value!.id,target.value!.id);draft.value!.state='applied';draft.value!.appliedAt=new Date().toLocaleString('sv-SE');error.value='';nextTick(()=>document.querySelector('.import-success')?.scrollIntoView({block:'start'}));}
  catch(e){error.value=(e as Error).message;}
}
function openOwner(page:string){go(page,{domain:book.value?.domainId,filter:page==='targets'?book.value?.id:undefined,returnTo:location.hash});}
function locationLabel(id:string){if(draft.value?.sample==='bnu6a')return '书页 '+chapters.value.flatMap(c=>c.locations).find(l=>l.id===id)?.printedPage;const p=draft.value?.pages.find(p=>p.id===id);return p?'第 '+(draft.value!.pages.indexOf(p)+1)+' 页 · '+scanFixtures[p.fixture]!.kind:id;}
function locate(id:string){focusPage.value=Number(chapters.value.flatMap(c=>c.locations).find(l=>l.id===id)?.printedPage);draft.value!.selectedPage=id;draft.value!.step=2;loadPage();}
const remaining=computed(()=>draft.value?.pages.filter(p=>!p.resolved).length||0);
const hasMapping=computed(()=>!!mappingChapter.value?.mappings.length);
function snapshot(){return {book:book.value!,target:target.value!,domain:domainMock,claims:evaluationMock.claims};}
</script>
<template><div v-if="draft&&book" class="wb-page import-workspace">
  <header class="page-header"><div><button class="text-link" @click="go('textbooks')">← 返回教材列表</button><h2>导入教材</h2><p class="page-desc">{{book.name||'从扫描件准备可学习的教材内容'}}</p></div><span class="badge">Mock 交互预览</span></header>
  <p v-if="draft.sample==='bnu6a'" class="import-notice">真实教材书页 49—50、91—93；识别、图文整理及模型关联均为固定 mock，未运行 OCR。</p><p v-else class="import-notice">当前为自编扫描示例，文件不实际上传或识别。<button class="text-link" @click="useRealBook">改用真实教材书页走查 →</button></p>
  <nav class="import-steps" aria-label="教材导入步骤"><button v-for="(name,i) in stepNames" :key="name" :aria-current="draft.step===i?'step':undefined" :disabled="i!==draft.step&&(i===1||!draft.pages.length||i===0)" :class="{active:draft.step===i,done:draft.step>i}" @click="nextStep(i)"><span>{{i+1}}</span>{{name}}</button></nav>
  <p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <p v-if="notice&&draft.step!==0" class="saved-note" role="status">{{notice}}</p>

  <template v-if="draft.step===0">
    <div class="upload-grid"><section class="panel"><div class="section-heading"><h3>批量导入教材</h3><button class="btn primary" @click="useRealBook">载入真实教材书页</button></div>
      <label class="file-picker">选择 PDF 或扫描图片<input type="file" accept=".pdf,image/*" multiple @change="filesChanged"/></label>
      <p class="muted">一次选择整本 PDF 或多张扫描图片，按阅读顺序批量整理。真实书页走查载入 49—50、91—93 页；自选文件仍只演示固定 mock。</p><details v-if="!draft.sample"><summary>使用其他演示数据</summary><button class="btn" @click="fillSample(draft);error=''">使用示例扫描件</button></details>
      <table class="data-table upload-files"><thead><tr><th>文件</th><th>顺序与移除</th></tr></thead><tbody><tr v-for="(f,i) in draft.files" :key="f.id"><td>{{i+1}}. {{f.name}}<small>{{f.kind}} · {{f.size?Math.round(f.size/1024)+' KB':'真实原页已载入'}}</small></td><td class="file-actions"><button class="btn" :aria-label="'上移 '+f.name" :disabled="i===0" @click="move(i,-1)">↑</button><button class="btn" :aria-label="'下移 '+f.name" :disabled="i===draft.files.length-1" @click="move(i,1)">↓</button><button class="text-link" :aria-label="'移除 '+f.name" @click="draft.files.splice(i,1)">移除</button></td></tr></tbody></table><p v-if="!draft.files.length" class="empty">尚未选择文件。</p>
    </section><section class="panel"><h3>教材信息</h3><label>教材名称<input v-model="draft.book.name"/></label><div class="field-pair"><label>出版社 / 编写方<input v-model="draft.book.publisher"/></label><label>教材版次<input v-model="draft.book.edition"/></label></div><div class="field-pair"><label>年级 / 适用对象<input v-model="draft.book.grade"/></label><label>学科<input v-model="draft.book.subject"/></label></div><label>关联领域<select v-model="draft.book.domainId" aria-label="关联领域"><option value="">请选择</option><option v-for="d in domainMock.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>来源说明<textarea v-model="draft.book.sourceNote" rows="2"/></label><p class="muted">教材没有答案或解析也可以导入；后续生成的解答须标明来源。</p></section></div>
    <details class="mock-controls"><summary>Mock 处理场景</summary><label class="check-label"><input type="checkbox" v-model="draft.failNext"/>模拟一次识别中断</label></details>
    <footer class="import-footer"><span class="muted">草稿保存在本浏览器，可稍后继续。</span><button class="btn primary" @click="start">上传并开始整理</button></footer>
  </template>
  <section v-else-if="draft.step===1" class="panel processing-panel">
    <h3>{{draft.state==='failed'?'识别整理已暂停':'正在识别整理'}}</h3><p>{{draft.files.length}} 个来源文件 · {{draft.book.name}}</p><progress :value="draft.progress" max="100"/><p>{{draft.progress}}%</p>
    <ol class="processing-stages"><li :class="{complete:draft.progress>=25}">接收扫描件并保留页序</li><li :class="{complete:draft.progress>=50}">识别正文、公式和图形</li><li :class="{complete:draft.progress>=75}">整理章节与内容，标出疑点</li><li :class="{complete:draft.progress===100}">准备原页与整理结果的对照视图</li></ol>
    <p v-if="draft.error" class="callout amber" role="alert">{{draft.error}}</p><button v-if="draft.state==='failed'" class="btn primary" @click="retry">继续整理</button><button v-else class="btn" @click="pause">暂停整理</button>
  </section>
  <template v-else-if="draft.step===2&&draft.sample==='bnu6a'"><MaterialOrganizeWorkspace :key="draft.id" :book="book" :focus-page="focusPage" @next="selectedChapter=readyChapters[0]!.id;nextStep(3)"/></template>
  <template v-else-if="draft.step===2">
    <div class="section-heading"><div><h3>对照原页，核对目录和内容</h3><p class="muted">共 {{draft.pages.length}} 页 · {{remaining}} 页待核对 · {{readyChapters.length}} 章已核对。可先完成一章，其余稍后处理。</p></div><button class="btn" :disabled="!readyChapters.length||dirty" @click="selectedChapter=readyChapters[0]!.id;nextStep(3)">下一步：关联模型</button></div>
    <div class="review-layout"><aside class="panel import-directory" aria-label="导入内容目录"><label>显示页面<select aria-label="显示页面" v-model="filter"><option value="all">全部页面</option><option value="pending">待核对</option></select></label>
      <section v-for="unit in book.units" :key="unit.id"><input class="unit-name" :value="unit.name" :aria-label="'单元名称 '+unit.id" @change="unit.name=($event.target as HTMLInputElement).value;recordBookChange(book,'调整识别目录')"/>
        <div v-for="ch in unit.chapters" :key="ch.id"><input :value="ch.name" :aria-label="'章节名称 '+ch.id" @change="renameChapter(ch,$event)"/><button v-for="p in draft.pages.filter(p=>p.chapterId===ch.id&&(filter==='all'||!p.resolved))" :key="p.id" class="page-choice" :class="{active:current?.id===p.id}" :aria-current="current?.id===p.id?'page':undefined" @click="switchPage(p.id)">{{locationLabel(p.id)}}<small>{{p.resolved?'已核对':p.issue?'有识别疑点':'待核对'}}</small></button></div>
      </section>
    </aside><div v-if="current&&savedText" class="page-compare">
      <section class="panel original-panel"><div class="section-heading"><h3>原页</h3><button class="btn" @click="zoom=!zoom">{{zoom?'恢复大小':'放大原页'}}</button></div><p class="muted">{{draft.files.find(f=>f.id===current!.fileId)?.name}} · 文件第 {{current.filePage}} 页</p><div class="scan-scroll" :class="{zoom}"><ImportedScanPage :fixture="current.fixture"/></div></section>
      <section class="panel correction-panel"><h3>整理结果</h3><p v-if="current.issue&&!current.resolved" class="callout amber">{{current.issue}}</p><label>所属章节<select v-model="chapterId" aria-label="所属章节"><option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ch.name}}</option></select></label><div class="field-pair"><label>印刷书页码<input v-model="printedPage"/></label><label>页内位置<input v-model="label"/></label></div><label>识别整理内容<textarea v-model="text" rows="10"/></label><p v-if="current.fixture===1" class="muted">图形保留在原页，当前练习未附教材答案；不将生成解答冒充原文。</p>
        <div class="button-row"><button class="btn primary" @click="confirmPage">保存并确认本页</button><button v-if="dirty" class="btn" @click="loadPage">撤销本页修改</button></div><p class="muted">{{current.resolved?'本页已核对；再次修改后需重新保存。':'确认表示已检查本页内容，不是审批发布。'}}</p>
      </section>
    </div></div>
  </template>
  <template v-else-if="draft.step===3">
    <div class="section-heading"><div><h3>把章节关联到已有模型</h3><p class="muted">先核对建议，再采用或修改。Task 不直接关联 KC；知识由所选 Solution 递归汇总。</p></div><button class="btn primary" :disabled="!!mappingIssues(draft).length" @click="nextStep(4)">下一步：目标与应用</button></div>
    <label class="chapter-select">当前章节<select aria-label="当前章节" v-model="selectedChapter"><option v-for="ch in chapters" :key="ch.id" :value="ch.id">{{ch.name}}{{ch.checked?'':' · 待核对'}}</option></select></label>
    <section v-if="mappingChapter" class="panel"><p v-if="!mappingChapter.checked" class="callout amber">本章尚未核对完成，可以先准备其他章节。<button class="text-link" @click="locate(mappingChapter.locations[0]!.id)">去核对原页 →</button></p>
      <div v-if="!hasMapping&&mappingChapter.checked" class="mapping-suggestion"><h3>关联建议 <span class="badge">Mock</span></h3><p v-if="draft.sample==='bnu6a'">{{mappingChapter.items?.some(i=>i.blocks.some(b=>b.id==='B-CONDITIONS'))?'连续求一个量的几分之几：两层参照关系，分别对应逐层求量与先合并比例。':'统计探究内容已整理；统计 Task 与 Claim 尚待准备，不套用现有分数模型。'}}</p><p v-else>{{draft.pages.find(p=>p.chapterId===mappingChapter!.id)?.fixture===2?'三角形面积：底乘对应高，再除以二。':'数量增加：已知原量和增加比例，先求增加量再加回原量。'}}</p><p class="muted">依据本章已核对的例题与讲解；采用后仍可编辑具体 Task、Solution 和来源。</p><button class="btn primary" @click="useMapping">采用此关联建议</button></div>
      <ChapterMappingPanel :key="mappingChapter.id" :book="book" :chapter="mappingChapter" @locate="locate"/>
    </section><p v-if="mappingIssues(draft).length" class="muted">{{mappingIssues(draft).join(' ')}}</p><div class="button-row"><button class="btn" @click="nextStep(2)">返回核对内容</button><button class="text-link" @click="openOwner('domain')">缺少模型？前往领域管理补充 →</button></div>
  </template>
  <template v-else-if="draft.step===4">
    <section v-if="draft.state==='applied'&&!applicationChanged" class="panel import-success" role="status"><h3>教材已可供学生选用</h3><p>{{book.name}} · {{target?.name}} · {{draft.appliedAt}}</p><p>已准备章节可以开始学习，待准备章节保留在目录中。已有学习空间同步采用，原活动保留当时版本。</p><div class="button-row"><a class="btn primary" href="/student/" target="_blank" rel="noopener">打开学生端</a><button class="btn" @click="go('textbooks',{id:book.id,chapter:readyChapters[0]?.id,tab:'content'})">查看教材</button></div></section>
    <p v-if="applicationChanged" class="callout amber">内容有修改，尚未应用到学生端。核对后重新应用更新。</p>
    <section class="panel"><div class="section-heading"><div><h3>学习目标与达标标准</h3><p class="muted">教材内容与目标要求分别确认。生成的是可修改建议，点击应用后才供学生选用。</p></div><button v-if="!targets.length" class="btn" :disabled="!!mappingIssues(draft).length" @click="prepareTarget">生成目标建议</button></div>
      <label v-if="targets.length">选用目标<select aria-label="选用目标" v-model="draft.targetId"><option value="">请选择</option><option v-for="t in targets" :key="t.id" :value="t.id">{{t.name}}</option></select></label>
      <template v-if="target"><label>学习目标名称<input v-model="target.name"/></label><div v-for="selection in target.claims" :key="selection.claimId" class="target-section"><h4>{{evaluationMock.claims.find(c=>c.id===selection.claimId)?.name}} <span class="badge">Task Claim</span></h4><p class="muted">{{evaluationMock.claims.find(c=>c.id===selection.claimId)?.methodMode==='all'?'分别覆盖所规定的方法':'可采用所规定方法中的一种'}}；仍以章节实际采用的方法为教学范围。</p><table class="data-table import-requirements"><thead><tr><th>学习要求</th><th>达标标准</th></tr></thead><tbody><tr v-for="r in selection.requirements" :key="r.id"><td><label :for="'req-name-'+r.id" class="sr-only">学习要求 {{r.id}}</label><input :id="'req-name-'+r.id" v-model="r.name"/><small>{{r.chapterIds.map(id=>chapters.find(ch=>ch.id===id)?.name).join('、')}}</small></td><td><label :for="'req-standard-'+r.id" class="sr-only">达标标准 {{r.id}}</label><textarea :id="'req-standard-'+r.id" v-model="r.standard" rows="3"/></td></tr></tbody></table></div><button class="text-link" @click="go('targets',{id:target.id,returnTo:location.hash})">在目标管理中完整编辑 →</button></template>
      <p v-else class="empty">尚未选择学习目标。可以生成建议，或到目标管理中建立。</p><button v-if="!target" class="text-link" @click="openOwner('targets')">前往目标管理 →</button><button v-if="!targets.length" class="text-link" @click="openOwner('evaluation')">补充 Task Claim →</button>
    </section>
    <section class="panel"><h3>应用后，学生可以做什么</h3><table class="data-table availability-table"><thead><tr><th>章节</th><th v-if="draft.sample==='bnu6a'">图文阅读</th><th>{{draft.sample==='bnu6a'?'讲解依据':'讲解'}}</th><th>{{draft.sample==='bnu6a'?'检测依据':'检测'}}</th></tr></thead><tbody><tr v-for="ch in chapters" :key="ch.id"><td>{{ch.name}}</td><td v-if="draft.sample==='bnu6a'">{{ch.checked?'可阅读':'待核对'}}</td><td>{{target&&chapterReady(snapshot(),ch.id).explain?(draft.sample==='bnu6a'?'已关联':'可开展'):'待准备'}}</td><td>{{target&&chapterReady(snapshot(),ch.id).test?(draft.sample==='bnu6a'?'已关联':'可开展'):'待准备'}}</td></tr></tbody></table><p class="muted">{{draft.sample==='bnu6a'?'应用后学生可阅读已核对的真实图文材料；此样本未接通真实教学或自动出题，不复用增加四分之一的旧脚本。':'本轮已提供增加四分之一的 mock 学习对话。其他章节可继续准备，不代表已接通真实教学。'}}</p></section>
    <footer class="import-footer"><button class="btn" @click="nextStep(3)">返回模型关联</button><div><p v-if="applicationIssues(draft).length" class="muted">{{applicationIssues(draft).join(' ')}}</p><button class="btn primary" :disabled="!!applicationIssues(draft).length" @click="apply">{{draft.state==='applied'?'重新应用更新':'应用并供学生选用'}}</button></div></footer>
  </template>
</div><div v-else class="wb-page"><h2>未找到导入草稿</h2><button class="btn" @click="go('textbooks')">返回教材列表</button></div></template>
<style scoped>
.import-workspace{max-width:1600px}.import-notice{font-size:12px;color:#7d8c82;line-height:1.7;margin:0 0 18px}.import-steps{display:flex;border-bottom:1px solid #dce5df;margin:20px 0 24px}.import-steps button{display:flex;align-items:center;justify-content:center;gap:9px;flex:1;padding:14px 5px;border:0;border-bottom:3px solid transparent;background:none;color:#738279;font:inherit;cursor:pointer}.import-steps button.active{color:#255d43;border-color:#2d6a4f;font-weight:600}.import-steps button:disabled{cursor:default}.import-steps span{border:1px solid #c7d7cd;border-radius:50%;width:24px;height:24px;display:grid;place-items:center}.import-steps .active span,.import-steps .done span{background:#2d6a4f;color:#fff;border-color:#2d6a4f}.upload-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:22px}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:16px}.section-heading h3,.panel h3{margin:0 0 10px;font-size:17px}.file-picker{display:block;padding:24px;border:1px dashed #9db7a9;border-radius:8px;background:#f5faf6}.file-picker input{margin:14px 0 0}.upload-files td{overflow-wrap:anywhere}.file-actions{white-space:nowrap}.file-actions .btn{padding:5px 9px;margin-right:5px}.field-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.import-footer{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:24px 0}.mock-controls{margin:12px 0;color:#7c8c82}.mock-controls label{margin-top:10px}.processing-panel{max-width:780px;margin:30px auto}.processing-panel progress{width:100%;height:12px;accent-color:#2d6a4f}.processing-stages{line-height:2.5;color:#87928b}.processing-stages .complete{color:#2d6a4f}.review-layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:18px}.import-directory{padding:16px;align-self:start;max-height:75vh;overflow:auto}.import-directory input{font-size:12px;margin-bottom:8px}.import-directory .unit-name{font-weight:600;background:#f6f8f6}.page-choice{width:100%;padding:12px 10px;text-align:left;background:none;border:0;border-left:3px solid transparent;border-radius:4px;font:inherit;font-size:13px;cursor:pointer}.page-choice.active{border-color:#2d6a4f;background:#edf5ef}.page-choice small{display:block;color:#7a8a80;font-size:12px;margin-top:4px}.page-compare{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}.page-compare>.panel{padding:20px;min-width:0}.scan-scroll{overflow:auto;max-height:650px}.scan-scroll.zoom .scan-page{min-width:640px}.correction-panel textarea{line-height:1.9;min-height:255px;resize:vertical}.chapter-select{max-width:550px}.mapping-suggestion{border-left:3px solid #80a48e;background:#f1f7f3;padding:18px 20px;margin-bottom:24px}.target-section{margin:22px 0}.target-section h4{font-size:16px;margin:0 0 10px}.import-requirements th:first-child{width:35%}.import-requirements textarea,.import-requirements input{margin:0;font:inherit}.import-requirements td{vertical-align:top}.import-success{border-left:4px solid #2d6a4f}.saved-note{color:#2d6a4f}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:1250px){.review-layout{grid-template-columns:185px minmax(0,1fr)}.page-compare{gap:12px}.page-compare>.panel{padding:14px}.field-pair{grid-template-columns:1fr;gap:0}}
@media(max-width:1050px){.upload-grid{grid-template-columns:1fr}.review-layout{grid-template-columns:170px minmax(0,1fr)}.page-compare{grid-template-columns:1fr}.import-steps button{font-size:12px;gap:5px}.section-heading{flex-wrap:wrap}}
</style>
