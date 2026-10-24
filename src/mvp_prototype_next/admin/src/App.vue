<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { route as routeSource,go,openObject } from './workbench/navigation';
const route=routeSource;
import { mode,notice,storageError,state as stateSource,resolve,objectActivity } from './workbench/store';
const state=stateSource;
import { personalKinds,objectKey } from './workbench/model';
import { preview, editor, editDraft, ownerLocation } from './workbench/ui';
import ModelCatalog from './components/ModelCatalog.vue';
import SpaceObservation from './components/SpaceObservation.vue';
import RuntimeObservation from './components/RuntimeObservation.vue';
import RuntimeOverview from './components/RuntimeOverview.vue';
import UserManagement from './components/UserManagement.vue';
import ObservationDetail from './components/ObservationDetail.vue';
import DomainWorkspace from './components/DomainWorkspace.vue';
import EvaluationWorkspace from './components/EvaluationWorkspace.vue';
import TextbookWorkspace from './components/TextbookWorkspace.vue';
import TargetWorkspace from './components/TargetWorkspace.vue';
import CourseWorkspace from './components/CourseWorkspace.vue';
import LearningSpaceWorkspace from './components/LearningSpaceWorkspace.vue';
import LearnerWorkspace from './components/LearnerWorkspace.vue';
import StudentStateWorkspace from './components/StudentStateWorkspace.vue';
import TraceList from './components/TraceList.vue';
import TraceDetail from './components/TraceDetail.vue';
import ActivityReviewList from './components/ActivityReviewList.vue';
import FlowActivityReview from './components/FlowActivityReview.vue';
import ActivityReviewDetail from './components/ActivityReviewDetail.vue';
import DefinitionEditor from './components/DefinitionEditor.vue';
import WorkbenchOverview from './components/WorkbenchOverview.vue';
import WorkbenchDialog from './components/WorkbenchDialog.vue';
import ModelObjectContent from './components/ModelObjectContent.vue';
import AccessGate from './components/AccessGate.vue';
import { observationSections } from './workbench/runtime-observation';
import './workbench/workbench.css';
interface NavChild {id:string;label:string;page:string;tab?:string}
interface NavItem {id:string;label:string;icon:string;children?:NavChild[]}
const observationLabels={Domain:'领域空间',Learning:'学习空间',Evaluation:'评估空间',Interaction:'交互空间',Reasoning:'智能推理',Evolution:'模型变更'};
const navGroups:{label:string;items:NavItem[]}[]=[
  {label:'观测',items:[{id:'dashboard',label:'运行总览',icon:'📊'},{id:'trace-list',label:'交互审查',icon:'🔍'},{id:'objects',label:'空间观测',icon:'🧩',children:observationSections.map(s=>({id:s.id,label:observationLabels[s.id],page:'objects',tab:s.id}))},{id:'students',label:'学生状态',icon:'👤'}]},
  {label:'管理',items:[{id:'models',label:'模型管理',icon:'🏛️',children:[{id:'domain',label:'领域空间',page:'domain'},{id:'evaluation',label:'评估空间',page:'evaluation'}]},{id:'courses',label:'课程管理',icon:'📚',children:[{id:'textbooks',label:'教材管理',page:'textbooks'},{id:'targets',label:'学习目标',page:'targets'},{id:'learning-spaces',label:'学习空间',page:'learning-spaces'}]},{id:'users',label:'用户管理',icon:'👥'},{id:'config',label:'系统配置',icon:'⚙️'}]},
];
const active=computed(()=>route.page.startsWith('observed-')?'objects':route.page==='task-editor'?'domain':route.page==='object'?(resolve(route.id)?ownerLocation(resolve(route.id)!).page:'objects'):route.page==='activity'?'trace-list':route.page);
const expanded=ref<Record<string,boolean>>({});
const observationOrigin=computed(()=>{
  let origin=route.returnTo;
  while(origin.startsWith('#/')){const [page,query]=origin.slice(2).split('?'),values=new URLSearchParams(query);if(page==='objects')return values;origin=values.get('returnTo')||'';}
  return new URLSearchParams();
});
const observedTab=computed(()=>route.page==='objects'?(route.tab||'Domain'):observationOrigin.value.get('tab')||(route.page==='observed-space'?'Learning':route.page==='observed-issue'?'Evolution':resolve(route.id)?.space||'Domain'));
function childActive(child:NavChild){return active.value===child.page&&(!child.tab||child.tab===observedTab.value);}
function itemActive(item:NavItem){return item.id==='objects'?active.value==='objects':item.children?item.children.some(childActive):active.value===item.id;}
watch(()=>[route.page,route.id,route.tab],()=>{for(const group of navGroups)for(const item of group.items)if(item.children&&itemActive(item))expanded.value[item.id]=true;},{immediate:true});
function openChild(child:NavChild){
  if(child.page!=='objects'){go(child.page);return;}
  const context=route.page==='objects'?{...route}:route.page.startsWith('observed-')?{...Object.fromEntries(observationOrigin.value),source:'legacy',scope:observationOrigin.value.get('scope')||state.spaces.find(s=>s.id===route.scope)?.id||''}:{};
  go('objects',{...context,tab:child.tab,filter:'',review:'',result:'',q:'',id:'',p:1});
}
try{mode.value=localStorage.getItem('deermind-admin-data-mode')==='real'?'real':'demo';}catch{}
watch(()=>route.id,id=>{if(id.startsWith('NEXT-'))mode.value='real';},{immediate:true});
watch(mode,v=>{editor.value=null;try{localStorage.setItem('deermind-admin-data-mode',v);}catch{}preview.value=null;});
watch(()=>[route.page,route.id],()=>{preview.value=null;notice.value='';if(route.page==='task-editor')go('domain',{domain:'DOM-MATH',filter:'task',id:route.id||'fraction'},true);},{immediate:true});
function changeMode(value:string){mode.value=value==='real'?'real':'demo';go(active.value,active.value==='objects'?{tab:observedTab.value}:{});}
const legacyReview=computed(()=>route.source==='legacy'||route.filter.startsWith('LS-'));
const currentReview=computed(()=>mode.value==='demo'&&((route.page==='trace-list'&&!legacyReview.value)||(route.page==='activity'&&route.id.startsWith('SPACE-ACT-'))));
const legacyObservation=computed(()=>route.source==='legacy'||route.scope.startsWith('LS-'));
const legacyStudent=computed(()=>route.source==='legacy'||route.id.startsWith('ST-'));
const transientMock=computed(()=>(route.page==='dashboard'&&mode.value==='demo')||currentReview.value||(route.page==='students'&&!legacyStudent.value)||(route.page==='objects'&&!legacyObservation.value)||['users','domain','evaluation','textbooks','targets'].includes(route.page)||(route.page==='learning-spaces'&&!state.spaces.some(s=>s.id===route.id)));
const demoOnly=computed(()=>mode.value==='real'&&(['objects','object','domain','task-editor','evaluation','textbooks','targets','learning-spaces','users'].includes(route.page)||route.page.startsWith('observed-')));
const previewObj=computed(()=>preview.value?resolve(preview.value.ref):undefined);
const personalPreview=computed(()=>previewObj.value&&personalKinds.includes(previewObj.value.kind));
const previewAccess=computed(()=>previewObj.value?objectActivity(objectKey(previewObj.value))?.id||objectKey(previewObj.value):'');
watch(()=>route.page+':'+route.id,async()=>{
  if(route.page!=='maintenance')return;
  const old=state.issues.find(i=>i.id===route.id);
  const draft=state.drafts.find(d=>d.sourceIssueId===route.id);
  const object=draft?.object || (old?.published?resolve(old.published):old?.candidate);
  if(object){const target=ownerLocation(object);go(target.page,target.values,true);await nextTick();if(draft)editDraft(draft.id);}
  else if(old && state.activities.some(a=>a.id===old.origin))go('activity',{id:old.origin,tab:'handling'},true);
  else if(old?.dataMode==='real'&&old.origin.startsWith('NEXT-'))go('activity',{id:old.origin},true);
  else go('domain',{},true);
},{immediate:true});
function exportWork(){const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='deermind-admin-local-work.json';a.click();URL.revokeObjectURL(url);}
</script>
<template><div class="app"><aside class="sidebar"><div class="sidebar-brand"><span class="brand-icon">🦌</span><span class="brand-name">DeerMind</span><span class="brand-tag">Admin</span></div><nav class="sidebar-nav" aria-label="后台导航"><div v-for="group in navGroups" :key="group.label" class="nav-group"><span class="nav-group-label">{{group.label}}</span><div v-for="item in group.items" :key="item.id" class="nav-entry">
  <button class="nav-item" :aria-label="item.label" :class="{active:!item.children&&itemActive(item),'has-active':item.children&&itemActive(item)}" :aria-current="!item.children&&itemActive(item)?'page':undefined" :aria-expanded="item.children?!!expanded[item.id]:undefined" :aria-controls="item.children?'nav-'+item.id:undefined" @click="item.children?expanded[item.id]=!expanded[item.id]:go(item.id)"><span class="nav-icon">{{item.icon}}</span><span class="nav-label">{{item.label}}</span><span v-if="item.children" class="nav-chevron" aria-hidden="true">{{expanded[item.id]?'⌄':'›'}}</span></button>
  <div v-if="item.children" v-show="expanded[item.id]" :id="'nav-'+item.id" class="nav-children" role="group" :aria-label="item.label"><button v-for="child in item.children" :key="child.id" class="nav-item nav-child" :class="{active:childActive(child)}" :aria-current="childActive(child)?'page':undefined" @click="openChild(child)">{{child.label}}</button></div>
</div></div></nav><div class="sidebar-footer"><div class="user-info"><span class="user-avatar">A</span><div class="user-detail"><span class="user-name">管理员</span><span class="user-role">Local Prototype</span></div></div></div></aside>
<main class="main-content"><div class="workbench-context"><label>数据来源<select aria-label="数据来源" :value="mode" @change="changeMode(($event.target as HTMLSelectElement).value)"><option value="demo">示例走查</option><option value="real">真实会话</option></select></label><span>{{mode==='demo'?(transientMock?'Mock 交互预览 · 已应用课程、题目和本轮学习记录保存在本浏览器':'模型与学生数据为合成示例；修改保存在本浏览器'):'只读本机真实会话；未运行正式评价'}}</span><button v-if="!transientMock" class="text-link" @click="exportWork">导出工作记录</button></div><div v-if="storageError" class="global-error" role="alert">{{storageError}}</div><div v-if="notice" class="global-error" role="alert">{{notice}}<button class="text-link" @click="notice=''">收起</button></div>
<div class="page-container" :key="route.page+':'+mode"><div v-if="demoOnly" class="wb-page"><h2>尚未接入真实模型数据</h2><p class="callout">当前真实能力只包括会话保存与查阅。本页面的模型目录、能力判断和定义编辑请在“示例走查”中审阅；不会将示例数据混入真实记录。</p><button class="btn primary" @click="changeMode('demo')">切换到示例走查</button></div>
<DomainWorkspace v-else-if="route.page==='domain'"/>
<EvaluationWorkspace v-else-if="route.page==='evaluation'"/>
<TextbookWorkspace v-else-if="route.page==='textbooks'"/>
<TargetWorkspace v-else-if="route.page==='targets'"/>
<RuntimeObservation v-else-if="route.page==='objects'&&!legacyObservation"/>
<SpaceObservation v-else-if="route.page==='objects'"/>
<ObservationDetail v-else-if="route.page.startsWith('observed-')"/>
<ModelCatalog v-else-if="route.page==='object'"/>
<CourseWorkspace v-else-if="route.page==='learning-spaces'&&state.spaces.some(s=>s.id===route.id)"/>
<LearningSpaceWorkspace v-else-if="route.page==='learning-spaces'"/>
<ActivityReviewList v-else-if="route.page==='trace-list'&&currentReview"/>
<TraceList v-else-if="route.page==='trace-list'"/>
<FlowActivityReview v-else-if="route.page==='activity'&&route.id.startsWith('FLOW-ACT-')"/>
<ActivityReviewDetail v-else-if="route.page==='activity'&&currentReview"/>
<TraceDetail v-else-if="route.page==='activity'"/>
<StudentStateWorkspace v-else-if="route.page==='students'&&!legacyStudent"/>
<template v-else-if="route.page==='students'"><p class="callout">旧版个人记录 · 与当前课程示例分开保留，不按同名合并。<button class="text-link" @click="go('students')">打开当前学生状态 →</button></p><LearnerWorkspace/></template>

<RuntimeOverview v-else-if="route.page==='dashboard'&&mode==='demo'"/>
<UserManagement v-else-if="route.page==='users'"/>
<WorkbenchOverview v-else-if="['dashboard','users','config'].includes(route.page)"/>
<div v-else class="wb-page"><h2>页面不存在</h2><button class="btn" @click="go('dashboard')">返回运行总览</button></div></div>
</main><WorkbenchDialog v-if="preview" title="关联对象速览" wide @close="preview=null"><AccessGate v-if="personalPreview" :subject="previewAccess"><ModelObjectContent :reference="preview.ref" :scope="preview.scope" :observing="route.page==='objects'||route.page.startsWith('observed-')"/></AccessGate><ModelObjectContent v-else :reference="preview.ref" :scope="preview.scope" :observing="route.page==='objects'||route.page.startsWith('observed-')"/><div class="dialog-footer"><button class="btn primary" @click="openObject(preview.ref,preview.scope)">打开完整详情</button></div></WorkbenchDialog><DefinitionEditor v-if="editor && mode==='demo'" :key="editor.object.id+':'+editor.draftId"/></div></template>
<style scoped>
.nav-item.has-active{color:#fff;font-weight:600}.nav-chevron{margin-left:auto;font-size:18px;line-height:18px}.nav-children{margin:2px 0 8px 21px;padding-left:10px;border-left:1px solid rgba(232,240,236,.16)}.nav-item.nav-child{font-size:12px;padding:9px 8px;line-height:18px}.nav-item:focus-visible{outline:2px solid #95d5b2;outline-offset:-2px}
.app{display:flex;height:100vh;overflow:hidden}.sidebar{width:200px;flex-shrink:0;background:linear-gradient(180deg,#1a3a2e 0%,#163026 100%);display:flex;flex-direction:column;color:#e8f0ec}.sidebar-brand{display:flex;align-items:center;gap:8px;padding:18px 16px;border-bottom:1px solid rgba(255,255,255,.1)}.brand-icon{font-size:22px}.brand-name{font-size:16px;font-weight:600}.brand-tag{font-size:10px;background:rgba(255,255,255,.15);padding:2px 6px;border-radius:4px;margin-left:auto}.sidebar-nav{flex:1;padding:12px 8px;overflow-y:auto}.nav-group{margin-bottom:16px}.nav-group-label{display:block;font-size:10px;color:rgba(232,240,236,.6);padding:0 12px;margin-bottom:6px;font-weight:600;letter-spacing:.5px}.nav-item{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;background:none;border:none;color:rgba(232,240,236,.8);font-size:13px;cursor:pointer;border-radius:8px;font-family:inherit;text-align:left;margin-bottom:2px}.nav-item:hover{background:rgba(255,255,255,.08);color:#e8f0ec}.nav-item.active{background:rgba(64,145,108,.25);color:#fff;font-weight:500}.nav-icon{font-size:16px;width:20px;text-align:center}.sidebar-footer{padding:12px;border-top:1px solid rgba(255,255,255,.1)}.user-info{display:flex;align-items:center;gap:10px}.user-avatar{width:32px;height:32px;border-radius:50%;background:#40916c;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600}.user-detail{display:flex;flex-direction:column}.user-name{font-size:13px;font-weight:500}.user-role{font-size:10px;color:rgba(232,240,236,.6)}.main-content{flex:1;min-width:0;display:flex;flex-direction:column;overflow:hidden;background:#f5f7fa}.page-container{flex:1;overflow:auto;min-height:0}.workbench-context{min-height:54px;display:flex;align-items:center;gap:16px;padding:10px 24px;background:#fff;border-bottom:1px solid #e1e8ed;font-size:12px}.workbench-context label{display:flex;align-items:center;gap:8px;margin:0;flex-shrink:0}.workbench-context>span{color:#66796d;flex:1}.workbench-context select{padding:5px 8px;width:auto}.global-error{padding:12px 24px;background:#fdf0ed;color:#873e29;display:flex;justify-content:space-between;gap:16px}@media(max-width:1000px){.sidebar{width:175px}.workbench-context{flex-wrap:wrap;gap:8px}.workbench-context>span{min-width:240px}}
</style>
