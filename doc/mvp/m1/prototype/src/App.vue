<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { imports, storageError, newImport, deleteImport } from './model/imports';
import TextbookImport from './components/TextbookImport.vue';
import WorkbenchDialog from './components/WorkbenchDialog.vue';
import DomainWorkspace from './components/domain/DomainWorkspace.vue';
import './components/domain/domain.css';
import { domainData } from './model/domain';
import type { ImportDraft } from './model/imports';

const hash = ref(location.hash);
const updateHash = () => { hash.value = location.hash; };
window.addEventListener('hashchange', updateHash);
onBeforeUnmount(() => window.removeEventListener('hashchange', updateHash));
const source = computed(() => new URLSearchParams(hash.value.split('?')[1] || '').get('source'));
const isDomain = computed(() => hash.value.split('?')[0] === '#/domain');
const draft = computed(() => imports.find(d => d.id === source.value));
const deleting = ref('');
const toDelete = computed(() => imports.find(d => d.id === deleting.value));
const query = ref(''),domainFilter=ref('');
const matches=(d:ImportDraft)=>(d.book.name||'未命名教材').includes(query.value.trim())&&(!domainFilter.value||d.book.domainId===domainFilter.value);
const visibleImports = computed(() => imports.filter(matches));
const domainName=(d:ImportDraft)=>domainData.domains.find(x=>x.id===d.book.domainId)?.name||'尚未选择领域';
function currentStep(d:ImportDraft){return d.state==='review'?(d.flow?Object.keys(d.flow.links).length+' 章已关联 / '+d.flow.requests.filter(r=>r.status==='pending').length+' 组待入库':'等待核对解析内容'):stateNames[d.state];}
const stateNames = { upload: '选择扫描件', processing: '正在解析', paused: '演示已暂停', failed: '处理失败', review: '解析内容' };
function go(id = '') { location.hash = id ? '/textbooks?tab=import&source=' + encodeURIComponent(id) : '/textbooks'; }
function goDomain() { location.hash = '/domain'; }
function create() { go(newImport()); }
function remove() { deleteImport(deleting.value); deleting.value = ''; }
</script>

<template><div class="app">
  <aside class="sidebar"><div class="sidebar-brand"><span>🦌</span><strong>DeerMind</strong><span class="brand-tag">M1</span></div><nav aria-label="后台导航"><span class="nav-group-label">内容与模型</span><button class="nav-item" :class="{active:isDomain}" :aria-current="isDomain?'page':undefined" @click="goDomain">◈　领域管理</button><button class="nav-item" :class="{active:!isDomain}" :aria-current="!isDomain?'page':undefined" @click="go()">📚　教材管理</button></nav><footer class="sidebar-footer">管理员 · 交互原型</footer></aside>
  <main class="main-content"><div class="workbench-context"><strong>M1 独立原型</strong><span>Mock 数据保存在本浏览器 · 未连接真实模型服务</span></div><div v-if="storageError&&!isDomain" class="callout danger" role="alert">{{storageError}}</div>
    <div class="page-container"><DomainWorkspace v-if="isDomain" :hash="hash"/><TextbookImport v-else-if="draft" :key="draft.id" :draft="draft" :hash="hash" @back="go()"/>
      <section v-else class="wb-page"><header class="page-header"><div><h2>教材管理</h2><p class="page-desc">解析教材内容，提交领域入库，再建立章节与任务、方法的关联。</p></div><button class="btn primary" :disabled="!!storageError" @click="create">导入教材</button></header>
        <p v-if="source" class="callout" role="status">该导入在当前浏览器中不存在。请选择已有草稿或新建导入。</p>
        <div v-if="imports.length" class="edit-pair"><label class="search-label">查找教材<input v-model="query" type="search" placeholder="输入教材名称"/></label><label>按领域查找<select v-model="domainFilter" aria-label="按领域查找"><option value="">全部领域</option><option v-for="d in domainData.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label></div>
        <section class="panel"><h3>教材</h3>
          <div v-if="!imports.length" class="empty"><h4>先导入第一份教材</h4><p>进入后可载入内置真实书页，体验解析、领域入库和章节关联。</p><button class="btn" :disabled="!!storageError" @click="create">开始导入</button></div>
          <p v-else-if="!visibleImports.length" class="empty">没有匹配的教材。</p>
          <table v-else class="data-table"><thead><tr><th>教材</th><th>所属领域</th><th>文件</th><th>整理情况</th><th>操作</th></tr></thead><tbody><tr v-for="entry in visibleImports" :key="entry.id" :data-import-id="entry.id"><td><span>{{entry.book.name || '未命名教材'}}</span></td><td>{{domainName(entry)}}</td><td>{{entry.files.length}}</td><td>{{currentStep(entry)}}</td><td><div class="button-row"><button class="btn" :aria-label="'打开教材 '+(entry.book.name || '未命名教材')" @click="go(entry.id)">{{entry.state==='review'?'打开教材':'继续导入'}}</button><button v-if="!entry.integration?.applications.length&&!Object.keys(entry.flow?.links||{}).length" class="btn danger-btn" :aria-label="'删除导入 '+(entry.book.name || '未命名教材')" @click="deleting=entry.id">删除</button></div></td></tr></tbody></table>
        </section><p class="muted">数据为 mock；解析与重新解析演示固定结果，未调用 LLM。章节关联不代表学习目标与教学已配置完成。</p>
      </section>
    </div>
  </main>
  <WorkbenchDialog v-if="toDelete" title="删除未完成的导入" @close="deleting=''">
    <p>确定删除“{{toDelete.book.name || '未命名教材'}}”的这次导入？</p><p class="muted">删除本次草稿及其整理结果，无法恢复。已经保存到领域的公共定义和题目保留，不会删除其他导入。</p><div class="dialog-footer"><button class="btn" @click="deleting=''">取消</button><button class="btn danger-btn" @click="remove">确认删除</button></div>
  </WorkbenchDialog>
</div></template>
