<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { recordBookChange, mockId, type MockTextbook } from '../workbench/textbook-mock';
import { materialRoles, materialProblems, materialPageUrl, visibleMaterialBlocks, publisherBookUrl, type MaterialBlock, type MaterialItem } from '../../../shared/material-content';
import MaterialBlockView from '../../../shared/MaterialBlockView.vue';
import WorkbenchDialog from './WorkbenchDialog.vue';

const props=defineProps<{book:MockTextbook;focusPage?:number}>();
const emit=defineEmits<{next:[]}>();
const copy=<T,>(x:T):T=>JSON.parse(JSON.stringify(x));
const chapters=computed(()=>props.book.units.flatMap(u=>u.chapters));
const items=computed(()=>chapters.value.flatMap(c=>c.items||[]));
const selectionKey='deermind-material-selection-'+props.book.id;
const selected=ref(sessionStorage.getItem(selectionKey)||items.value[0]?.id||'');
const item=computed(()=>items.value.find(i=>i.id===selected.value)||items.value[0]);
const chapter=computed(()=>chapters.value.find(c=>c.items?.includes(item.value!))!);
const blocks=computed(()=>items.value.flatMap(i=>i.blocks));
const selectedBlock=ref(''),sourcePage=ref(item.value?.blocks[0]?.page||49),mode=ref<'all'|'question'>('all'),pending=ref(false),zoom=ref(false);
const error=ref(''),notice=ref('');
const activeBlock=computed(()=>item.value?.blocks.find(b=>b.id===selectedBlock.value));
const pages=computed(()=>[...new Set(item.value?.blocks.map(b=>b.page)||[])]);
const allPages=computed(()=>[...new Set(blocks.value.map(b=>b.page))].sort((a,b)=>a-b));
const issues=computed(()=>materialProblems(items.value));
const shownBlocks=computed(()=>item.value?visibleMaterialBlocks(item.value,mode.value):[]);
watch(()=>item.value?.id,id=>{sessionStorage.setItem(selectionKey,id||'');selectedBlock.value='';sourcePage.value=item.value?.blocks[0]?.page||49;mode.value='all';notice.value='';error.value='';});
watch(()=>props.focusPage,page=>{if(page){const found=items.value.find(i=>i.blocks.some(b=>b.page===page));if(found)selected.value=found.id;sourcePage.value=page;}},{immediate:true});
function pickBlock(b:MaterialBlock){selectedBlock.value=b.id;sourcePage.value=b.page;}
function followReference(id:string){const owner=items.value.find(i=>i.blocks.some(b=>b.id===id));if(!owner)return;selected.value=owner.id;queueMicrotask(()=>pickBlock(owner.blocks.find(b=>b.id===id)!));}
function changed(message:string,changedBlocks:string[]=[]){
  chapter.value.checked=false;item.value!.reviewed=false;
  for(const ch of chapters.value)for(const i of ch.items||[])if(i.blocks.some(b=>b.references.some(r=>changedBlocks.includes(r)))){i.reviewed=false;ch.checked=false;}
  chapter.value.content=(chapter.value.items||[]).map(i=>i.title).join('\n');chapter.value.reviewNote='图文内容有调整，待核对本课。';recordBookChange(props.book,message);notice.value=message+'，已保存。';error.value='';
}
function confirmChapter(){
  const problems=materialProblems(chapter.value.items||[]);if(problems.length){error.value='请先处理本课疑点：'+problems.join(' ');return;}
  if(chapter.value.items?.some(i=>!i.title.trim()||!i.blocks.length)){error.value='请补齐内容标题与内容。';return;}
  chapter.value.items?.forEach(i=>i.reviewed=true);chapter.value.checked=true;chapter.value.reviewNote='已按课题对照真实原页核对图文、跨页关系及教学用途（交互走查）。';recordBookChange(props.book,'核对课题：'+chapter.value.name);notice.value='本课内容已核对，可继续关联模型。';error.value='';
}
const editor=ref<'block'|'merge'|'structure'|''>(''),draft=ref<MaterialBlock>(),mergeId=ref(''),chosen=ref<string[]>([]),destination=ref('new'),newTitle=ref(''),title=ref('');
function editBlock(b:MaterialBlock){draft.value=copy(b);editor.value='block';error.value='';}
function saveBlock(){
  const b=draft.value!;
  if(!b.title.trim()||b.rect.some(n=>!Number.isFinite(n))||b.rect[0]<0||b.rect[1]<0||b.rect[2]<=0||b.rect[3]<=0||b.rect[0]+b.rect[2]>100||b.rect[1]+b.rect[3]>100){error.value='请填写标题及有效的原页区域，区域不能超过书页。';return;}
  if(b.kind==='table'&&b.role!=='blank'&&(!b.headers?.every(h=>h.trim())||!b.rows?.length)){error.value='请补齐表头和数据行；待填写表请保留“学生待完成”用途。';return;}
  if(b.id==='B-PIE'&&b.resolved&&!b.references.includes('B-AGE')){error.value='此 mock 疑点需要关联第91页的年龄占比表，才能标为已核对。';return;}
  const index=item.value!.blocks.findIndex(x=>x.id===b.id);item.value!.blocks[index]=copy(b);changed('保存内容：'+b.title,[b.id]);editor.value='';pickBlock(item.value!.blocks[index]!);
}
function openMerge(){mergeId.value='';editor.value='merge';error.value='';}
function merge(){
  const other=chapter.value.items!.find(i=>i.id===mergeId.value);if(!other){error.value='请选择同一课题中要并入的内容。';return;}
  item.value!.blocks.push(...other.blocks);chapter.value.items=chapter.value.items!.filter(i=>i.id!==other.id);
  if(item.value!.blocks.some(b=>b.id==='B-CONDITIONS')&&['B-METHOD-A','B-METHOD-B'].every(id=>item.value!.blocks.some(b=>b.id===id)))item.value!.issue='';
  changed('合并跨页内容：'+other.title);editor.value='';
}
function openStructure(){chosen.value=[];destination.value='new';newTitle.value='';title.value=item.value!.title;editor.value='structure';error.value='';}
function saveStructure(){
  if(!title.value.trim()){error.value='请填写内容名称。';return;}
  if(chosen.value.length){
    if(chosen.value.length===item.value!.blocks.length){error.value='请至少保留一部分内容；整项并入请使用合并。';return;}
    if(destination.value==='new'&&!newTitle.value.trim()){error.value='请填写新内容名称。';return;}
    const moved=item.value!.blocks.filter(b=>chosen.value.includes(b.id));
    const target=destination.value==='new'?{id:mockId('MAT'),title:newTitle.value,kind:item.value!.kind,reviewed:false,blocks:[]} as MaterialItem:chapter.value.items!.find(i=>i.id===destination.value);
    if(!target){error.value='请选择接收内容。';return;}
    item.value!.blocks=item.value!.blocks.filter(b=>!chosen.value.includes(b.id));target.blocks.push(...moved);target.reviewed=false;
    if(destination.value==='new')chapter.value.items!.splice(chapter.value.items!.indexOf(item.value!)+1,0,target);
    if(item.value!.blocks.some(b=>b.id==='B-CONDITIONS')&&!['B-METHOD-A','B-METHOD-B'].every(id=>item.value!.blocks.some(b=>b.id===id)))item.value!.issue='解法与题目分开，请重新合并跨页例题。';
  }
  item.value!.title=title.value;changed('调整内容结构');editor.value='';
}
function moveBlock(index:number,delta:number){const bs=item.value!.blocks;[bs[index],bs[index+delta]]=[bs[index+delta]!,bs[index]!];changed('调整阅读顺序');}
const referenceName=(id:string)=>blocks.value.find(b=>b.id===id)?.title||'未找到关联内容';
const overlay=(b:MaterialBlock)=>({left:b.rect[0]+'%',top:b.rect[1]+'%',width:b.rect[2]+'%',height:b.rect[3]+'%'});
</script>
<template><section v-if="item" class="material-organizer">
  <div class="organizer-heading"><div><h3>教材整理工作区</h3><p>{{allPages.length}} 张真实书页 · {{items.length}} 项内容 · {{issues.length}} 处待核对 · {{chapters.filter(c=>c.checked).length}} 个课题已核对</p></div><button class="btn primary" :disabled="!chapters.some(c=>c.checked)" @click="emit('next')">下一步：关联模型</button></div>
  <p class="material-scope">当前样本为书内 49—50、91—93 页。原页来自出版社电子教材；图文整理、疑点和关联均为固定 mock。<a :href="publisherBookUrl" target="_blank" rel="noopener">查看教材来源 ↗</a></p>
  <p v-if="error&&!editor" class="callout danger" role="alert">{{error}}</p><p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <div class="organizer-layout">
    <aside class="material-tree panel"><h4>目录与内容</h4><label class="pending-toggle"><input type="checkbox" v-model="pending"/>只看待处理</label>
      <section v-for="unit in book.units" :key="unit.id"><h5>{{unit.name}}</h5><div v-for="ch in unit.chapters" :key="ch.id"><strong class="chapter-name">{{ch.name}} <small>{{ch.checked?'已核对':''}}</small></strong><button v-for="entry in (ch.items||[]).filter(i=>!pending||!i.reviewed||materialProblems([i]).length)" :key="entry.id" class="material-tree-item" :class="{active:item.id===entry.id}" :aria-current="item.id===entry.id?'true':undefined" @click="selected=entry.id"><span>{{entry.title}}</span><small>{{entry.kind}} · {{[...new Set(entry.blocks.map(b=>b.page))].join('、')}} 页</small><em v-if="materialProblems([entry]).length">{{materialProblems([entry]).length}} 处疑点</em><small v-else>{{entry.reviewed?'已核对':'待核对'}}</small></button></div></section>
      <p v-if="pending&&items.every(i=>i.reviewed&&!materialProblems([i]).length)" class="muted">已无待处理内容。</p>
    </aside>
    <section class="source-panel panel"><div class="source-toolbar"><h4>原始书页</h4><button class="btn" @click="zoom=true">放大原页</button></div><div class="page-switch"><button v-for="p in allPages" :key="p" class="btn" :class="{selected:sourcePage===p,related:pages.includes(p)}" @click="sourcePage=p;selectedBlock=''">{{p}} 页</button></div><p class="source-caption">书页 {{sourcePage}} · 电子页序 {{sourcePage+3}}<span v-if="activeBlock&&activeBlock.page===sourcePage"> · {{activeBlock.title}}</span></p><div class="source-scroll"><div class="source-paper"><img :src="materialPageUrl(sourcePage)" :alt="'北师大六上原书第'+sourcePage+'页'"/><button v-for="b in item.blocks.filter(b=>b.page===sourcePage)" :key="b.id" class="source-region" :class="{selected:selectedBlock===b.id}" :style="overlay(b)" :aria-label="'定位原页区域：'+b.title" @click="pickBlock(b)"/></div></div><p class="muted">点击右侧内容可定位原页区域。高亮只标记取用位置，不改动原图。</p></section>
    <section class="organized-panel panel"><header><span class="badge">{{item.kind}}</span><h3>{{item.title}}</h3><p class="muted">{{chapter.name}} · 来源 {{pages.join('、')}} 页</p><div class="button-row"><button class="btn" @click="openMerge">合并内容</button><button class="btn" @click="openStructure">调整结构</button></div></header>
      <p v-if="item.issue" class="callout amber">{{item.issue}}</p>
      <div class="material-view-tabs" role="tablist" aria-label="内容使用预览"><button role="tab" :aria-selected="mode==='all'" @click="mode='all'">完整讲解材料</button><button role="tab" :aria-selected="mode==='question'" @click="mode='question'">仅题目与条件</button></div>
      <p v-if="mode==='question'" class="preview-note">隐藏提示、解法和教学图示。此预览只检查取用内容，不代表题目已通过检测质量审核，也不证明学生独立作答。</p>
      <p v-if="!shownBlocks.length" class="empty">本项只有讲解材料，没有可单独出示的题目。</p>
      <article v-for="b in shownBlocks" :key="b.id" class="organized-block" :class="{selected:selectedBlock===b.id}" :data-block="b.id">
        <div class="block-heading"><button class="block-title" @click="pickBlock(b)">{{b.title}}</button><span class="block-role" :class="{warning:b.role==='error'||b.role==='blank'}">{{materialRoles[b.role]}}</span></div>
        <p v-if="b.issue&&!b.resolved" class="callout amber">{{b.issue}}</p><MaterialBlockView :block="b"/>
        <div v-if="b.references.length" class="block-references">关联内容：<button v-for="id in b.references" :key="id" class="text-link" @click="followReference(id)">{{referenceName(id)}} ↗</button></div>
        <footer><button class="text-link" @click="pickBlock(b)">原页 {{b.page}} ↗</button><button class="text-link" @click="editBlock(b)">编辑</button><template v-if="mode==='all'"><button class="order-button" :aria-label="'上移 '+b.title" :disabled="item.blocks.indexOf(b)===0" @click="moveBlock(item.blocks.indexOf(b),-1)">↑</button><button class="order-button" :aria-label="'下移 '+b.title" :disabled="item.blocks.indexOf(b)===item.blocks.length-1" @click="moveBlock(item.blocks.indexOf(b),1)">↓</button></template></footer>
      </article>
      <footer class="chapter-confirm"><p>核对本课的内容完整性、来源与用途。无需逐页点确认；系统未标疑点的内容仍需阅读核对。</p><button class="btn primary" @click="confirmChapter">{{chapter.checked?'重新确认本课':'确认本课整理结果'}}</button></footer>
    </section>
  </div>
  <WorkbenchDialog v-if="zoom" title="查看真实原页" wide @close="zoom=false"><p>书页 {{sourcePage}} · 电子页序 {{sourcePage+3}}</p><img class="zoomed-source" :src="materialPageUrl(sourcePage)" :alt="'原书第'+sourcePage+'页'"/></WorkbenchDialog>
  <WorkbenchDialog v-if="editor" :title="editor==='block'?'编辑图文内容':editor==='merge'?'合并跨页内容':'调整内容结构'" wide @close="editor='';error=''">
    <p v-if="error" class="callout danger" role="alert">{{error}}</p>
    <template v-if="editor==='block'&&draft"><label>内容名称<input v-model="draft.title"/></label><div class="edit-pair"><label>教学用途<select v-model="draft.role"><option v-for="(name,id) in materialRoles" :key="id" :value="id">{{name}}</option></select></label><label>来源书页<select v-model.number="draft.page"><option v-for="p in allPages" :key="p" :value="p">{{p}}</option></select></label></div>
      <label>{{draft.kind==='image'?'辅助说明（不替代原图）':'整理文字'}}<textarea v-model="draft.text" rows="3"/></label>
      <template v-if="draft.kind==='table'"><p v-if="draft.role==='blank'" class="callout">这是学生待填写的表格，保留原页中的空白，不自动补答案。</p><template v-else><label>单位 / 口径<input v-model="draft.unit"/></label><div class="table-editor"><table><thead><tr><th v-for="(_,i) in draft.headers" :key="i"><input v-model="draft.headers![i]" :aria-label="'表头 '+(i+1)"/></th></tr></thead><tbody><tr v-for="(row,i) in draft.rows" :key="i"><td v-for="(_,j) in row" :key="j"><input v-model="row[j]" :aria-label="'第'+(i+1)+'行第'+(j+1)+'列'"/></td></tr></tbody></table></div></template></template>
      <label>关联内容<select v-model="draft.references" multiple size="4" aria-label="关联内容"><option v-for="b in blocks.filter(b=>b.id!==draft!.id)" :key="b.id" :value="b.id">{{b.title}}（{{b.page}}页）</option></select></label><small>用于图与数据表、续页内容之间的引用；可多选。</small>
      <details class="crop-editor"><summary>调整原页取用区域</summary><p>相对整页的百分比。修改后预览取用范围；原始书页保持不变。</p><div class="rect-fields"><label v-for="(name,i) in ['左侧','顶部','宽度','高度']" :key="name">{{name}} %<input v-model.number="draft.rect[i]" type="number" min="0" max="100" step="0.1"/></label></div><MaterialBlockView v-if="draft.kind==='image'||draft.role==='blank'" :block="draft"/></details>
      <label v-if="draft.issue" class="check-line"><input type="checkbox" v-model="draft.resolved"/>已对照原页处理此疑点：{{draft.issue}}</label><div class="button-row"><button class="btn primary" @click="saveBlock">保存内容</button><button class="btn" @click="editor='';error=''">取消</button></div>
    </template>
    <template v-else-if="editor==='merge'"><p>将同一课题的另一项并入“{{item.title}}”，保留全部内容、用途和来源，不合并其他练习。</p><label>要并入的内容<select v-model="mergeId"><option value="">请选择</option><option v-for="i in chapter.items?.filter(i=>i.id!==item!.id)" :key="i.id" :value="i.id">{{i.title}} · {{[...new Set(i.blocks.map(b=>b.page))].join('、')}}页</option></select></label><button class="btn primary" @click="merge">确认合并</button></template>
    <template v-else><label>内容名称<input v-model="title"/></label><p>需要拆分或调整归属时，选择要移动的部分；不选择则只修改名称。</p><label v-for="b in item.blocks" :key="b.id" class="check-line"><input v-model="chosen" type="checkbox" :value="b.id"/>{{b.title}} · {{materialRoles[b.role]}}</label><template v-if="chosen.length"><label>移入<select v-model="destination"><option value="new">拆成新内容</option><option v-for="i in chapter.items?.filter(i=>i.id!==item!.id)" :key="i.id" :value="i.id">{{i.title}}</option></select></label><label v-if="destination==='new'">新内容名称<input v-model="newTitle"/></label></template><button class="btn primary" @click="saveStructure">保存结构调整</button></template>
  </WorkbenchDialog>
</section></template>
<style scoped>
.organizer-heading{display:flex;justify-content:space-between;gap:16px;align-items:center}.organizer-heading h3{margin:0 0 8px;font-size:19px}.organizer-heading p,.material-scope,.source-caption,.preview-note,.chapter-confirm p{font-size:12px;color:#6b7f73;line-height:1.8}.material-scope{margin-bottom:18px}.material-scope a{color:#2d6a4f;margin-left:12px}.organizer-layout{display:grid;grid-template-columns:190px minmax(280px,.95fr) minmax(340px,1.05fr);gap:14px;align-items:start}.organizer-layout>.panel{padding:16px;min-width:0}.material-tree{position:sticky;top:12px;max-height:85vh;overflow:auto}.material-tree h4,.source-toolbar h4{margin:0 0 14px;font-size:15px}.material-tree h5{font-size:13px;color:#7b8d81;margin:24px 0 12px}.chapter-name{font-size:13px;display:block;margin:12px 0}.chapter-name small{color:#2d6a4f}.pending-toggle,.check-line{display:flex;align-items:center;gap:8px;font-size:13px}.pending-toggle input,.check-line input{width:auto;margin:0}.material-tree-item{display:block;width:100%;border:0;border-left:3px solid transparent;border-radius:5px;background:none;text-align:left;padding:12px 8px;font:inherit;font-size:13px;cursor:pointer}.material-tree-item.active{background:#edf5ef;border-color:#2d6a4f}.material-tree-item small,.material-tree-item em{display:block;font-size:11px;line-height:1.7;color:#829186;font-style:normal}.material-tree-item em{color:#ad7838}.source-panel{position:sticky;top:12px}.source-toolbar{display:flex;justify-content:space-between;align-items:start}.page-switch{display:flex;flex-wrap:wrap;gap:5px}.page-switch .btn{font-size:12px;padding:5px 9px}.page-switch .selected{background:#2d6a4f;color:white}.page-switch .related{border-color:#7fa48d}.source-scroll{max-height:68vh;overflow:auto;background:#eff2ef;border:1px solid #e1e8e2}.source-paper{position:relative}.source-paper>img{display:block;width:100%;height:auto}.source-region{position:absolute;border:1px solid #689a7d;background:#679b7615;cursor:pointer;padding:0}.source-region.selected{border:2px solid #c48b39;background:#e8b95c30}.source-panel>.muted{font-size:11px;line-height:1.7}.organized-panel>header h3{font-size:18px;margin:10px 0}.material-view-tabs{display:flex;margin-top:20px;border-bottom:1px solid #dce6de}.material-view-tabs button{flex:1;font:inherit;font-size:13px;border:0;border-bottom:2px solid transparent;padding:12px 4px;background:none;cursor:pointer}.material-view-tabs button[aria-selected=true]{border-color:#2d6a4f;color:#2d6a4f;font-weight:600}.organized-block{border:1px solid #e1e8e2;border-radius:6px;padding:14px;margin-top:16px;min-width:0}.organized-block.selected{border-color:#ad874d}.block-heading{display:flex;gap:8px;justify-content:space-between;align-items:start;margin-bottom:12px}.block-title{padding:0;text-align:left;border:0;background:none;font:inherit;font-size:14px;font-weight:600;cursor:pointer}.block-role{font-size:10px;white-space:nowrap;background:#edf4ef;color:#47765c;padding:3px 5px;border-radius:4px}.block-role.warning{background:#faf0db;color:#9a773c}.organized-block footer{display:flex;align-items:center;gap:12px;margin-top:12px;font-size:11px}.order-button{border:1px solid #dce5df;background:white;border-radius:3px;cursor:pointer}.order-button:disabled{opacity:.35}.block-references{font-size:12px;margin-top:10px}.block-references button{display:block;font-size:12px;text-align:left;margin-top:5px}.chapter-confirm{border-top:1px solid #dce5df;margin-top:24px;padding-top:10px}.zoomed-source{width:100%;height:auto}.edit-pair,.rect-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px}.table-editor{overflow:auto}.table-editor table{border-collapse:collapse;width:100%}.table-editor input{min-width:100px;padding:8px}.table-editor th,.table-editor td{border:1px solid #e1e8e2;padding:4px}.crop-editor{padding:16px 0;font-size:12px}.crop-editor summary{cursor:pointer}.crop-editor .material-block-view{max-width:420px;margin:auto}.saved-note{color:#2d6a4f}.check-line{margin:16px 0}.preview-note{background:#f3f6f2;padding:10px}.material-organizer .callout{font-size:12px;line-height:1.8}
@media(max-width:1350px){.organizer-layout{grid-template-columns:165px minmax(240px,.9fr) minmax(280px,1.1fr);gap:10px}.organizer-layout>.panel{padding:12px}.block-heading{flex-wrap:wrap}}
@media(max-width:1100px){.organizer-layout{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.material-tree{grid-column:1/-1;position:static;max-height:250px}.material-tree>section{display:inline-block;width:48%;vertical-align:top;padding-right:12px}.source-panel{top:8px}.organizer-heading{flex-wrap:wrap}.organized-block{padding:10px}.button-row{flex-wrap:wrap}}
</style>
