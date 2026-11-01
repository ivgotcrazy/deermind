<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { route, go } from '../workbench/navigation';
import WorkbenchDialog from './WorkbenchDialog.vue';
import TeachingBlueprint from './TeachingBlueprint.vue';
import { teachingMock, teachingScenes, teachingSceneBlueprint, teachingSceneStrategies, teachingBlueprintDraft, copyTeaching, newTeachingId, recordTeachingChange, validateTeachingBlueprint, type TeachingStage, type TeachingTransition, type TeachingStrategy, type TeachingRule } from '../workbench/teaching-mock';

const tabs=[{id:'blueprint',name:'教学蓝图'},{id:'strategies',name:'教学策略'},{id:'rules',name:'通用规则'}];
const tab=computed(()=>route.tab||'blueprint');
const draft=teachingBlueprintDraft;
const dirty=computed(()=>JSON.stringify(draft.value)!==JSON.stringify(teachingMock.blueprint));
const selectedStage=ref('teach'),selectedEdge=ref('');
const stage=computed(()=>draft.value.stages.find(s=>s.id===selectedStage.value));
const edge=computed(()=>draft.value.transitions.find(e=>e.id===selectedEdge.value));
const notice=ref(''),error=ref(''),errorNode=ref<HTMLElement>();
const dialog=ref<'stage'|'edge'|'meta'|'strategy'|'rule'|'history'|'discard'|null>(null);
const removing=ref(false),isNew=ref(false),strategyGroup=ref('');
const stageForm=ref<TeachingStage>({id:'',name:'',purpose:'',inputs:'',approach:'',outputs:'',strategies:[]});
const edgeForm=ref<TeachingTransition>({id:'',from:'',to:'',label:'',condition:'',basis:''});
const insertAt=ref(''),metaForm=ref({name:'',purpose:''});
const strategyForm=ref<TeachingStrategy>({} as TeachingStrategy),ruleForm=ref<TeachingRule>({} as TeachingRule);
const query=ref(''),status=ref('all'),page=ref(1);
const filtered=computed(()=>teachingMock.strategies.filter(s=>(status.value==='all'||s.enabled===(status.value==='enabled'))&&[s.name,s.purpose,s.when].join(' ').includes(query.value.trim())));
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/8)));
const strategy=computed(()=>teachingMock.strategies.find(s=>s.id===route.id));
const outgoing=computed(()=>stage.value?draft.value.transitions.filter(e=>e.from===stage.value!.id):[]);
const strategyGroups=[
  {id:'definition',title:'基本定义与适用条件',fields:[['purpose','教学目的'],['when','适用情况'],['avoid','不适用情况'],['inputs','需要的信息']]},
  {id:'organization',title:'教学组织',fields:[['organization','如何组织教学'],['help','允许的帮助'],['observe','需要观察的表现']]},
  {id:'adjustment',title:'调整与结束',fields:[['adjust','调整方式'],['end','结束条件']]},
  {id:'basis',title:'依据与示例',fields:[['basis','依据与限制'],['examples','领域示例']]},
];
const editingGroups=computed(()=>strategyGroups.filter(g=>!strategyGroup.value||g.id===strategyGroup.value));
const dialogTitle=computed(()=>dialog.value==='stage'?(isNew.value?'添加教学阶段':'编辑阶段：'+stageForm.value.name):dialog.value==='edge'?(isNew.value?'添加连接':'编辑转移条件'):dialog.value==='strategy'?(isNew.value?'新建教学策略':'编辑'+(strategyGroups.find(g=>g.id===strategyGroup.value)?.title||'策略')):dialog.value==='rule'?(isNew.value?'新增通用规则':'编辑通用规则'):dialog.value==='meta'?'编辑蓝图信息':dialog.value==='history'?'教学模型修改记录':'放弃蓝图修改');
watch([query,status],()=>page.value=1);
watch(pages,n=>page.value=Math.min(page.value,n));
function stageName(id:string){return id==='start'?'开始':id==='end'?'结束':draft.value.stages.find(s=>s.id===id)?.name||'未指定';}
function strategyName(id:string){return teachingMock.strategies.find(s=>s.id===id)?.name||'策略不存在';}
function referencedBy(id:string){return teachingMock.blueprint.stages.filter(s=>s.strategies.includes(id)).map(s=>s.name).join('、');}
function valueOf(s:TeachingStrategy,key:string){return String(s[key as keyof TeachingStrategy]||'');}
function setStrategyField(key:string,value:string){(strategyForm.value as unknown as Record<string,unknown>)[key]=value;}
function pickStage(id:string){selectedStage.value=id;selectedEdge.value='';error.value='';}
function pickEdge(id:string){selectedEdge.value=id;selectedStage.value='';error.value='';}
function open(kind:typeof dialog.value){dialog.value=kind;error.value='';removing.value=false;}
function close(){dialog.value=null;error.value='';removing.value=false;}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'nearest'});}
function editStage(create=false){isNew.value=create;stageForm.value=create?{id:newTeachingId('stage'),name:'',purpose:'',inputs:'',approach:'',outputs:'',strategies:[]}:copyTeaching(stage.value!);insertAt.value=draft.value.transitions.find(e=>e.from===(stage.value?.id||'teach'))?.id||draft.value.transitions[0]?.id||'';open('stage');}
function editEdge(create=false){isNew.value=create;edgeForm.value=create?{id:newTeachingId('edge'),from:stage.value?.id||'entry',to:'',label:'',condition:'',basis:''}:copyTeaching(edge.value!);open('edge');}
function editMeta(){metaForm.value={name:draft.value.name,purpose:draft.value.purpose};open('meta');}
function saveStage(){
  const s=stageForm.value;
  if(!s.name.trim()||!s.purpose.trim()||!s.inputs.trim()||!s.outputs.trim())return fail('请填写阶段名称、目的、所需信息和阶段结果。');
  if(isNew.value){
    const link=draft.value.transitions.find(e=>e.id===insertAt.value);if(!link)return fail('请选择新阶段插入的位置。');
    const after=draft.value.stages.findIndex(n=>n.id===link.from);draft.value.stages.splice(after+1,0,copyTeaching(s));
    const previousTo=link.to;link.to=s.id;
    draft.value.transitions.push({id:newTeachingId('edge'),from:s.id,to:previousTo,label:'本阶段完成',condition:'本阶段结果已形成，可以继续。',basis:s.outputs});
  }else{const index=draft.value.stages.findIndex(n=>n.id===s.id);draft.value.stages[index]=copyTeaching(s);}
  pickStage(s.id);close();notice.value='阶段已加入蓝图草稿；保存蓝图后生效。';
}
function saveEdge(){
  const e=edgeForm.value;
  if(!e.from||!e.to||e.from===e.to||e.from==='end'||e.to==='start')return fail('请选择不同且有效的起点与终点。');
  if(!e.label.trim()||!e.condition.trim()||!e.basis.trim())return fail('请填写连接名称、转移条件和判断依据。');
  if(draft.value.transitions.some(x=>x.id!==e.id&&x.from===e.from&&x.to===e.to))return fail('这两个阶段已有连接，请编辑原连接的条件。');
  const index=draft.value.transitions.findIndex(x=>x.id===e.id);if(index<0)draft.value.transitions.push(copyTeaching(e));else draft.value.transitions[index]=copyTeaching(e);
  pickEdge(e.id);close();notice.value='转移条件已加入蓝图草稿。';
}
function removeSelected(){
  if(dialog.value==='stage'){const id=stageForm.value.id;draft.value.stages=draft.value.stages.filter(s=>s.id!==id);draft.value.transitions=draft.value.transitions.filter(e=>e.from!==id&&e.to!==id);selectedStage.value=draft.value.stages[0]?.id||'';}
  else{draft.value.transitions=draft.value.transitions.filter(e=>e.id!==edgeForm.value.id);selectedEdge.value='';}
  close();notice.value='已从草稿移除，请补齐路径后保存蓝图。';
}
function saveBlueprint(){
  const problem=validateTeachingBlueprint(draft.value);if(problem)return fail(problem);
  const old=teachingMock.blueprint,changes:string[]=[];
  if(old.name!==draft.value.name||old.purpose!==draft.value.purpose)changes.push('蓝图信息');
  for(const s of draft.value.stages)if(JSON.stringify(s)!==JSON.stringify(old.stages.find(x=>x.id===s.id)))changes.push('阶段「'+s.name+'」');
  for(const e of draft.value.transitions)if(JSON.stringify(e)!==JSON.stringify(old.transitions.find(x=>x.id===e.id)))changes.push('连接「'+e.label+'」');
  if(old.stages.length>draft.value.stages.length||old.transitions.length>draft.value.transitions.length)changes.push('移除阶段或连接');
  teachingMock.blueprint=copyTeaching(draft.value);recordTeachingChange('保存蓝图：'+changes.join('、'));notice.value='蓝图已保存为教学模型 v'+teachingMock.revision+'。预设情境仍基于 v1，需重新核对。';error.value='';
}
function discard(){draft.value=copyTeaching(teachingMock.blueprint);selectedStage.value=draft.value.stages[0]?.id||'';selectedEdge.value='';close();notice.value='已恢复上次保存的蓝图。';}
function openStrategy(id:string){go('interaction',{tab:'strategies',id,returnTo:location.hash});notice.value='';}
function returnFromStrategy(){if(route.returnTo.startsWith('#/interaction'))location.hash=route.returnTo;else go('interaction',{tab:'strategies'});}
function editStrategy(group='',create=false){
  isNew.value=create;strategyGroup.value=group;
  strategyForm.value=create?{id:newTeachingId('strategy'),name:'',purpose:'',when:'',avoid:'',inputs:'',organization:'',help:'',observe:'',adjust:'',end:'',basis:'',examples:'',enabled:true,version:1}:copyTeaching(strategy.value!);open('strategy');
}
function saveStrategy(){
  const s=strategyForm.value;
  if(['name','purpose','when','avoid','organization','observe','adjust','end','basis'].some(key=>!valueOf(s,key).trim()))return fail('请补齐名称、目的、适用与不适用情况、教学组织、观察、调整、结束条件和依据。');
  const existing=teachingMock.strategies.find(x=>x.id===s.id);s.version=existing?existing.version+1:1;
  if(existing)Object.assign(existing,copyTeaching(s));else teachingMock.strategies.unshift(copyTeaching(s));
  recordTeachingChange((existing?'修改':'新增')+'策略「'+s.name+'」'+(strategyGroup.value?'：'+strategyGroups.find(g=>g.id===strategyGroup.value)?.title:''));
  close();go('interaction',{tab:'strategies',id:s.id,returnTo:route.returnTo});notice.value='策略已保存；引用它的阶段使用同一份定义。预设情境需核对。';
}
function toggleStrategy(){if(!strategy.value)return;strategy.value.enabled=!strategy.value.enabled;strategy.value.version++;recordTeachingChange((strategy.value.enabled?'启用':'停用')+'策略「'+strategy.value.name+'」');notice.value=strategy.value.enabled?'策略已启用。':'策略已停用，阶段中的引用保留并标示不可用。';}
function editRule(rule?:TeachingRule){isNew.value=!rule;ruleForm.value=rule?copyTeaching(rule):{id:newTeachingId('rule'),name:'',when:'',requirement:'',basis:'',enabled:true,version:1};open('rule');}
function saveRule(){const r=ruleForm.value;if(!r.name.trim()||!r.when.trim()||!r.requirement.trim()||!r.basis.trim())return fail('请填写规则名称、适用情况、要求和依据。');const current=teachingMock.rules.find(x=>x.id===r.id);r.version=current?current.version+1:1;if(current)Object.assign(current,copyTeaching(r));else teachingMock.rules.push(copyTeaching(r));recordTeachingChange((current?'修改':'新增')+'规则「'+r.name+'」');close();notice.value='通用规则已保存。';}
function toggleRule(r:TeachingRule){r.enabled=!r.enabled;r.version++;recordTeachingChange((r.enabled?'启用':'停用')+'规则「'+r.name+'」');}

const sceneId=ref(teachingScenes.some(s=>s.id===route.scope)?route.scope:'foundation');
const scene=computed(()=>teachingScenes.find(s=>s.id===sceneId.value)!);
const trail=ref(['entry']);
const step=computed(()=>scene.value.steps.find(s=>s.id===trail.value[trail.value.length-1])!);
const sceneStrategy=computed(()=>teachingSceneStrategies.find(s=>s.id===step.value.strategy));
const visited=computed(()=>['focus',...trail.value.map(id=>scene.value.steps.find(s=>s.id===id)!.stage)]);
const scenePathText=computed(()=>trail.value.map(id=>{const item=scene.value.steps.find(s=>s.id===id)!;return teachingSceneBlueprint.stages.find(s=>s.id===item.stage)?.name+(item.strategy?'（'+teachingSceneStrategies.find(s=>s.id===item.strategy)?.name+'）':'');}).join(' → '));
const sceneEdges=computed(()=>['start-focus','focus-entry',...visited.value.slice(1).map((id,i)=>teachingSceneBlueprint.transitions.find(e=>e.from===visited.value[i]&&e.to===id)?.id||'')]);
const showSceneGraph=ref(false);
const sceneGraphSelection=ref('');
const sceneEdge=computed(()=>teachingSceneBlueprint.transitions.find(e=>e.id===sceneGraphSelection.value));
const sceneNode=computed(()=>teachingSceneBlueprint.stages.find(s=>s.id===sceneGraphSelection.value));
function enterScenes(){go('interaction',{tab:'scenes',scope:sceneId.value,round:trail.value[trail.value.length-1]});notice.value='';}
function changeScene(id:string){sceneId.value=id;trail.value=['entry'];sceneGraphSelection.value='';go('interaction',{tab:'scenes',scope:id,round:'entry'});}
function advance(id:string){trail.value.push(id);sceneGraphSelection.value='';go('interaction',{tab:'scenes',scope:sceneId.value,round:id});}
function previous(){if(trail.value.length>1){trail.value.pop();go('interaction',{tab:'scenes',scope:sceneId.value,round:trail.value[trail.value.length-1]});}}
function scenePath(target:string,path=['entry']):string[]|undefined{const item=scene.value.steps.find(s=>s.id===path[path.length-1]);if(!item)return;if(item.id===target)return path;for(const id of [item.next,...(item.choices||[]).map(c=>c.next)].filter(Boolean) as string[]){if(!path.includes(id)){const found=scenePath(target,[...path,id]);if(found)return found;}}}
watch(()=>[route.tab,route.scope,route.round],()=>{if(route.tab==='scenes'){if(teachingScenes.some(s=>s.id===route.scope))sceneId.value=route.scope;if(route.round&&route.round!==trail.value[trail.value.length-1])trail.value=scenePath(route.round)||['entry'];}},{immediate:true});
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue='';}}
onMounted(()=>window.addEventListener('beforeunload',beforeUnload));onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload));
</script>

<template><div class="wb-page teaching-workspace">
  <header class="page-header"><div><div class="muted">Interaction Space · 教学模型 v{{teachingMock.revision}}</div><h2>教学模型管理</h2><p class="page-desc">定义教学怎样开始、推进与结束，让策略和规则落在具体阶段中。</p></div><div class="header-actions"><button class="btn" @click="open('history')">修改记录</button><button v-if="tab!=='scenes'" class="btn" @click="enterScenes">情境推演</button></div></header>
  <nav v-if="tab!=='scenes'" class="tabs teaching-tabs" aria-label="教学模型分区"><button v-for="t in tabs" :key="t.id" :class="{active:tab===t.id}" :aria-current="tab===t.id?'page':undefined" @click="go('interaction',{tab:t.id});notice=''">{{t.name}}</button></nav>
  <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
  <p v-if="error&&!dialog" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
  <p v-if="dirty&&tab!=='blueprint'" class="callout amber">蓝图有未保存的修改。<button class="text-link" @click="go('interaction',{tab:'blueprint'})">返回蓝图保存或取消 →</button></p>

  <template v-if="tab==='blueprint'">
    <div class="blueprint-heading"><div><h3>{{draft.name}}</h3><p>{{draft.purpose}}</p></div><button class="text-link" @click="editMeta">编辑信息</button></div>
    <div class="blueprint-tools"><span class="muted">点击阶段查看职责，点击连线编辑转移条件。</span><div><button class="btn" @click="editStage(true)">添加阶段</button><button class="btn" @click="editEdge(true)">添加连接</button></div></div>
    <div class="blueprint-layout">
      <section class="panel graph-panel"><TeachingBlueprint :blueprint="draft" :selected-stage="selectedStage" :selected-transition="selectedEdge" @stage="pickStage" @transition="pickEdge"/></section>
      <aside class="panel inspector" aria-label="蓝图定义详情">
        <template v-if="stage"><div class="row-between"><span class="eyebrow">阶段定义</span><button class="btn" @click="editStage()">编辑阶段</button></div><h3>{{stage.name}}</h3><p class="inspector-lead">{{stage.purpose}}</p>
          <dl class="inspector-fields"><dt>需要的信息</dt><dd>{{stage.inputs}}</dd><dt>怎样开展</dt><dd>{{stage.approach||'尚未补充'}}</dd><dt>留下的结果</dt><dd>{{stage.outputs}}</dd></dl>
          <h4>可用策略</h4><div v-if="stage.strategies.length" class="strategy-links"><div v-for="id in stage.strategies" :key="id"><button class="text-link" @click="openStrategy(id)">{{strategyName(id)}} ↗</button><span v-if="!teachingMock.strategies.find(s=>s.id===id)?.enabled" class="badge amber">已停用 · 不可选择</span></div></div><p v-else class="muted">此阶段负责组织或收束，不预设教学策略。</p>
          <h4>接下来可能去哪里</h4><button v-for="e in outgoing" :key="e.id" class="outgoing-link" @click="pickEdge(e.id)"><strong>{{stageName(e.to)}} →</strong><span>{{e.condition}}</span></button><p v-if="!outgoing.length" class="callout amber">尚无出口，请添加连接。</p>
        </template>
        <template v-else-if="edge"><div class="row-between"><span class="eyebrow">转移规则</span><button class="btn" @click="editEdge()">编辑连接</button></div><h3>{{edge.label}}</h3><p class="connection-names">{{stageName(edge.from)}} → {{stageName(edge.to)}}</p><dl class="inspector-fields"><dt>什么时候转移</dt><dd>{{edge.condition}}</dd><dt>判断依据</dt><dd>{{edge.basis}}</dd></dl><p class="callout">需要语义判断的条件由规则约束下的 LLM 理解；此处仅定义与展示，不执行判断。</p></template>
        <p v-else class="empty">选择阶段或连接，查看其定义。</p>
      </aside>
    </div>
    <details><summary>以表格查看全部连接 · {{draft.transitions.length}} 条</summary><div class="table-card"><table class="data-table"><thead><tr><th>从哪里</th><th>到哪里</th><th>转移条件</th><th></th></tr></thead><tbody><tr v-for="e in draft.transitions" :key="e.id"><td>{{stageName(e.from)}}</td><td>{{stageName(e.to)}}</td><td>{{e.condition}}</td><td><button class="text-link" :aria-label="'编辑连接：'+e.label" @click="pickEdge(e.id);editEdge()">编辑</button></td></tr></tbody></table></div></details>
    <div class="blueprint-save"><span>{{dirty?'有未保存的蓝图修改':'蓝图已保存 · 可直接编辑，无审核流程'}}</span><button class="btn" :disabled="!dirty" @click="open('discard')">取消修改</button><button class="btn primary" :disabled="!dirty" @click="saveBlueprint">保存蓝图</button></div>
  </template>

  <template v-else-if="tab==='strategies'">
    <template v-if="!route.id"><div class="toolbar"><label class="search-label">搜索策略<input v-model="query" type="search" placeholder="名称、目的或适用情况"/></label><label>策略状态<select v-model="status"><option value="all">全部</option><option value="enabled">启用</option><option value="disabled">停用</option></select></label><button class="btn primary" @click="editStrategy('',true)">新建策略</button></div>
      <section class="table-card"><table class="data-table strategy-table"><thead><tr><th>教学策略</th><th>教学目的 / 适用情况</th><th>被哪些阶段使用</th><th>状态 / 版本</th></tr></thead><tbody><tr v-for="s in filtered.slice((page-1)*8,page*8)" :key="s.id"><td><button class="text-link item-name" @click="openStrategy(s.id)">{{s.name}}</button></td><td>{{s.purpose}}<small>{{s.when}}</small></td><td>{{referencedBy(s.id)||'尚未引用'}}</td><td><span class="badge" :class="s.enabled?'green':''">{{s.enabled?'启用':'停用'}}</span><small>v{{s.version}}</small></td></tr></tbody></table><p v-if="!filtered.length" class="empty">没有匹配的策略，请调整搜索或新建。</p></section>
      <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page===1" @click="page--">上一页</button><span>{{page}} / {{pages}}</span><button class="btn" :disabled="page===pages" @click="page++">下一页</button></div>
    </template>
    <template v-else-if="strategy"><button class="text-link" @click="returnFromStrategy">← 返回{{route.returnTo.includes('tab=scenes')?'情境推演':route.returnTo.includes('tab=blueprint')||route.returnTo==='#/interaction'?'教学蓝图':'策略列表'}}</button><div class="strategy-heading"><div><span class="eyebrow">通用教学策略 · v{{strategy.version}}</span><h3>{{strategy.name}}</h3></div><div><span class="badge" :class="strategy.enabled?'green':''">{{strategy.enabled?'启用':'停用'}}</span><button class="btn" @click="toggleStrategy">{{strategy.enabled?'停用策略':'启用策略'}}</button></div></div>
      <p class="callout" :class="!strategy.enabled&&referencedBy(strategy.id)?'amber':''">被以下阶段引用：{{referencedBy(strategy.id)||'尚未引用'}}。{{!strategy.enabled?'停用后不能作为可选策略；引用保留以便调整。':'修改后使用同一份策略定义，不在各阶段复制。'}}</p>
      <section v-for="g in strategyGroups" :key="g.id" class="panel strategy-section"><div class="row-between"><h3>{{g.title}}</h3><button class="btn" @click="editStrategy(g.id)">编辑{{g.title}}</button></div><dl class="field-list"><template v-for="[key,label] in g.fields" :key="key"><dt>{{label}}</dt><dd>{{valueOf(strategy,key)||'尚未补充'}}</dd></template></dl></section>
    </template><p v-else class="empty">未找到此策略。<button class="text-link" @click="go('interaction',{tab:'strategies'})">返回列表</button></p>
  </template>

  <template v-else-if="tab==='rules'">
    <div class="row-between rule-intro"><p class="muted">不同阶段共同遵循的教学要求；不在此改写学习目标或能力评价规则。</p><button class="btn primary" @click="editRule()">新增规则</button></div>
    <section class="table-card"><table class="data-table rule-table"><thead><tr><th>规则 / 适用情况</th><th>具体要求</th><th>依据</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="r in teachingMock.rules" :key="r.id"><td><strong>{{r.name}}</strong><small>{{r.when}}</small></td><td>{{r.requirement}}</td><td>{{r.basis}}</td><td><span class="badge" :class="r.enabled?'green':''">{{r.enabled?'启用':'停用'}}</span><small>v{{r.version}}</small></td><td><div class="row-actions"><button class="text-link" :aria-label="'编辑规则：'+r.name" @click="editRule(r)">编辑</button><button class="text-link" :aria-label="(r.enabled?'停用':'启用')+'规则：'+r.name" @click="toggleRule(r)">{{r.enabled?'停用':'启用'}}</button></div></td></tr></tbody></table></section>
    <details class="system-boundaries"><summary>适用的系统约束 · 只读</summary><ul><li>学生可以停止或暂停；当天总使用时间遵守已确定的 30 分钟边界。</li><li>讲解分段推进；独立检测实质求助先结束检测，未做部分保持未检测。</li><li>实际帮助保留。教学完成不等于目标达成，能力认识仍由 Evaluation 负责。</li><li>本页不能改写正式学习目标、创建 KC 能力评分或借用另一个空间的个人记录。</li></ul></details>
  </template>

  <template v-else-if="tab==='scenes'">
    <button class="text-link" @click="go('interaction',{tab:'blueprint'})">← 返回教学蓝图</button>
    <div class="scene-header"><div><h3>三种学生情境</h3><p class="muted">预设分支 · 基于教学模型 v1 · 不调用 LLM、不产生真实评价</p></div><button class="btn" @click="changeScene(sceneId)">重新推演</button></div>
    <p v-if="teachingMock.revision!==1" class="callout amber" role="status">规则已修改，示例待核对。下方仍展示 v1 的预设路径，不是当前 v{{teachingMock.revision}} 规则的运行或验证结果。</p>
    <div class="scene-choices" aria-label="选择学生情境"><button v-for="s in teachingScenes" :key="s.id" class="btn" :class="{primary:sceneId===s.id}" :aria-pressed="sceneId===s.id" @click="changeScene(s.id)">{{s.name}}</button></div>
    <section class="panel scenario-context"><strong>本次重点：理解连续两级部分量的参照关系</strong><p>气象小组 12 人，摄影人数是气象的 1/3，航模人数是摄影的 3/4。求航模人数。</p><p class="muted">三种情境均已明确本次重点。{{scene.starting}}</p></section>
    <div class="stage-strip" aria-label="当前教学阶段"><span v-for="(s,i) in teachingSceneBlueprint.stages" :key="s.id" :class="{active:step.stage===s.id,visited:visited.includes(s.id)}"><small>{{i+1}}</small>{{s.name}}</span></div>
    <div class="scene-layout">
      <section class="panel conversation"><div class="row-between"><span class="eyebrow">学生看到的交互 · 预写示例</span><span class="muted">第 {{trail.length}} 步</span></div><h3>{{step.title}}</h3><div class="speech student"><span>学生</span><p>{{step.student}}</p></div><div class="speech tutor"><span>DeerMind</span><p>{{step.tutor}}</p>
          <figure v-if="sceneId==='transfer'&&['check','help','contrast','success'].includes(step.id)" class="teaching-figure">
            <svg viewBox="0 0 400 190" role="img" aria-label="花坛分区示意图：五个等面积区域，前三个种花，种花区域的上半部种玫瑰">
              <text x="200" y="22" text-anchor="middle">花坛总面积 40 平方米</text>
              <rect x="25" y="40" width="350" height="100" fill="#f5f6f1" stroke="#779283"/>
              <rect x="25" y="40" width="210" height="100" fill="#c8e3ce"/>
              <rect x="25" y="40" width="210" height="50" fill="#efd0d6"/>
              <path d="M95 40V140 M165 40V140 M235 40V140 M305 40V140" stroke="#779283"/>
              <path d="M25 90H235" stroke="#b47788" stroke-dasharray="4 3"/>
              <text x="130" y="70" text-anchor="middle">玫瑰</text><text x="130" y="120" text-anchor="middle">其他花</text>
              <text x="305" y="96" text-anchor="middle">未种花</text>
              <path d="M25 146V154H235V146" fill="none" stroke="#568160"/>
              <text x="130" y="178" text-anchor="middle">种花区域</text>
            </svg><figcaption>五列面积相等；虚线把种花区域平分为两半。</figcaption>
          </figure>
          <figure v-if="(sceneId==='foundation'&&step.id==='teach')||(sceneId==='explanation'&&step.id==='foundation')" class="teaching-figure">
            <svg viewBox="0 0 400 135" role="img" aria-label="十二个圆点平均分为三组，每组四个，圈出其中一组">
              <g v-for="group in 3" :key="group"><rect :x="14+(group-1)*130" y="22" width="112" height="65" rx="8" :fill="group===1?'#d5e9db':'#fff'" stroke="#6d9279"/><circle v-for="dot in 4" :key="dot" :cx="34+(group-1)*130+(dot-1)*24" cy="54" r="7" fill="#38674a"/></g>
              <text x="200" y="117" text-anchor="middle">一共 12 个，平均分成 3 组</text>
            </svg><figcaption>绿色区域表示其中一组。</figcaption>
          </figure>
        </div>
        <div v-if="step.choices" class="response-branches"><h4>选择接下来的学生表现</h4><button v-for="c in step.choices" :key="c.next" class="branch-button" @click="advance(c.next)">{{c.label}} →</button></div>
        <div class="scene-controls"><button class="btn" :disabled="trail.length===1" @click="previous">上一轮</button><button v-if="step.next" class="btn primary" @click="advance(step.next)">下一轮</button><span v-else-if="!step.choices" class="badge green">本次情境已收束</span><span v-else class="muted">选择一个分支继续</span></div>
      </section>
      <aside class="panel decision"><span class="eyebrow">本轮教学决策 · 预设期望</span><h3>{{teachingSceneBlueprint.stages.find(s=>s.id===step.stage)?.name}}</h3><dl class="inspector-fields"><dt>采用策略</dt><dd><template v-if="sceneStrategy"><strong>{{sceneStrategy.name}} · v1</strong><button class="text-link" @click="openStrategy(sceneStrategy.id)">查看当前策略定义 ↗</button></template><span v-else>阶段组织，无需选择讲解策略</span></dd><dt>为什么这样选择</dt><dd>{{step.reason}}</dd><dt>接下来观察什么</dt><dd>{{step.observe}}</dd><dt>评价与帮助边界</dt><dd>{{step.evidence}}</dd></dl></aside>
    </div>
    <div class="path-summary"><span class="muted">已经走过</span><span>明确重点 → {{scenePathText}}</span></div>
    <button class="text-link graph-toggle" :aria-expanded="showSceneGraph" @click="showSceneGraph=!showSceneGraph">{{showSceneGraph?'收起':'展开'}}蓝图路径与来源规则</button>
    <div v-if="showSceneGraph" class="blueprint-layout scene-graph"><section class="panel graph-panel"><TeachingBlueprint :blueprint="teachingSceneBlueprint" :active-stage="step.stage" :visited="visited" :traced-edges="sceneEdges" :selected-stage="sceneNode?.id" :selected-transition="sceneEdge?.id" @stage="sceneGraphSelection=$event" @transition="sceneGraphSelection=$event"/></section><aside class="panel inspector"><span class="eyebrow">示例依据 · v1 定义</span><template v-if="sceneEdge"><h3>{{sceneEdge.label}}</h3><dl class="inspector-fields"><dt>转移条件</dt><dd>{{sceneEdge.condition}}</dd><dt>判断依据</dt><dd>{{sceneEdge.basis}}</dd></dl></template><template v-else-if="sceneNode"><h3>{{sceneNode.name}}</h3><p>{{sceneNode.purpose}}</p><dl class="inspector-fields"><dt>如何开展</dt><dd>{{sceneNode.approach}}</dd><dt>阶段结果</dt><dd>{{sceneNode.outputs}}</dd></dl></template><p v-else>绿色显示已经经过的阶段与连接。点击节点或连线查看其 v1 定义；这里不编辑当前模型。</p></aside></div>
  </template>

  <WorkbenchDialog v-if="dialog" :title="dialogTitle" wide @close="close"><form v-if="dialog!=='history'&&dialog!=='discard'" @submit.prevent="dialog==='stage'?saveStage():dialog==='edge'?saveEdge():dialog==='strategy'?saveStrategy():dialog==='rule'?saveRule():(Object.assign(draft,metaForm),close())" novalidate>
    <p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
    <template v-if="dialog==='meta'"><label>蓝图名称<input v-model="metaForm.name"/></label><label>蓝图用途<textarea v-model="metaForm.purpose"/></label></template>
    <template v-if="dialog==='stage'"><label>阶段名称<input v-model="stageForm.name" maxlength="60"/></label><label>阶段目的<textarea v-model="stageForm.purpose"/></label><div class="two-columns"><label>需要的信息<textarea v-model="stageForm.inputs"/></label><label>留下的结果<textarea v-model="stageForm.outputs"/></label></div><label>怎样开展<textarea v-model="stageForm.approach"/></label><fieldset class="strategy-picker"><legend>可用策略（可多选）</legend><label v-for="s in teachingMock.strategies" :key="s.id" class="check-label"><input v-model="stageForm.strategies" type="checkbox" :value="s.id" :disabled="!s.enabled&&!stageForm.strategies.includes(s.id)"/>{{s.name}}{{s.enabled?'':'（已停用）'}}</label></fieldset><label v-if="isNew">插入到哪条连接中<select v-model="insertAt"><option v-for="e in draft.transitions" :key="e.id" :value="e.id">{{stageName(e.from)}} → {{stageName(e.to)}} · {{e.label}}</option></select></label><p v-if="isNew" class="muted">保留原进入条件；新阶段完成后连接原终点，可再编辑两条连接。</p></template>
    <template v-if="dialog==='edge'"><div class="two-columns"><label>起点<select v-model="edgeForm.from" aria-label="起点"><option value="start">开始</option><option v-for="s in draft.stages" :key="s.id" :value="s.id">{{s.name}}</option></select></label><label>终点<select v-model="edgeForm.to" aria-label="终点"><option value="">请选择</option><option v-for="s in draft.stages" :key="s.id" :value="s.id">{{s.name}}</option><option value="end">结束</option></select></label></div><label>连接名称<input v-model="edgeForm.label" maxlength="30" placeholder="例如：愿意尝试"/></label><label>转移条件<textarea v-model="edgeForm.condition" rows="3"/></label><label>判断依据<textarea v-model="edgeForm.basis" rows="3"/></label><p class="muted">需要语义判断的条件用清楚的语言表达，不要求编写代码。</p></template>
    <template v-if="dialog==='strategy'"><label v-if="!strategyGroup||strategyGroup==='definition'">策略名称<input v-model="strategyForm.name" maxlength="80"/></label><fieldset v-for="g in editingGroups" :key="g.id"><legend v-if="isNew">{{g.title}}</legend><label v-for="[key,label] in g.fields" :key="key">{{label}}<textarea :value="valueOf(strategyForm,key)" rows="3" @input="setStrategyField(key,($event.target as HTMLTextAreaElement).value)"/></label></fieldset><p class="muted">通用策略不绑定某道题；具体领域用法放在示例中。</p></template>
    <template v-if="dialog==='rule'"><label>规则名称<input v-model="ruleForm.name"/></label><label>适用情况<textarea v-model="ruleForm.when"/></label><label>具体要求<textarea v-model="ruleForm.requirement" rows="4"/></label><label>依据与限制<textarea v-model="ruleForm.basis"/></label></template>
    <p v-if="removing" class="callout amber">{{dialog==='stage'?'移除阶段会一并移除关联连接。请在草稿中补齐路径，保存时不会自动猜测新的连接。':'将从蓝图草稿中移除此连接。'}}<button type="button" class="btn danger-btn" @click="removeSelected">确认移除</button><button type="button" class="btn" @click="removing=false">保留</button></p>
    <div class="dialog-footer button-row"><button v-if="!isNew&&(dialog==='stage'||dialog==='edge')" type="button" class="text-link remove-button" @click="removing=true">移除{{dialog==='stage'?'阶段':'连接'}}</button><button type="button" class="btn" @click="close">取消</button><button class="btn primary" type="submit">{{dialog==='stage'||dialog==='edge'||dialog==='meta'?'应用到草稿':'保存'}}</button></div>
  </form><template v-else-if="dialog==='history'"><p class="muted">仅本次 Mock 页面会话的修改记录，刷新恢复示例。没有真实模型发布或能力变更。</p><div v-for="h in teachingMock.history" :key="h.version" class="history-row"><strong>v{{h.version}}</strong><div>{{h.change}}<small>{{h.at}}</small></div></div></template><template v-else><p>放弃未保存的蓝图修改，恢复上次保存的版本？</p><div class="dialog-footer button-row"><button class="btn" @click="close">继续编辑</button><button class="btn primary" @click="discard">确认放弃</button></div></template></WorkbenchDialog>
</div></template>

<style scoped>
.teaching-workspace{max-width:1600px}.header-actions,.blueprint-tools>div,.strategy-heading>div:last-child{display:flex;align-items:center;gap:10px}.teaching-tabs{margin-top:0}.saved-note{padding:9px 14px;color:#2b6b48;background:#eaf5ee;border-radius:6px;margin-bottom:14px;font-size:13px}.blueprint-heading{display:flex;justify-content:space-between;gap:20px;margin-bottom:14px}.blueprint-heading h3{font-size:18px;color:#2d4b3c}.blueprint-heading p{color:#687e70;font-size:13px;margin-top:4px}.blueprint-heading>.text-link{flex-shrink:0}.blueprint-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:14px 0}.blueprint-layout{display:grid;grid-template-columns:minmax(460px,1.45fr) minmax(300px,1fr);gap:18px;align-items:start}.graph-panel{padding:0;overflow:auto}.inspector{position:sticky;top:12px;padding:20px}.inspector h3{font-size:18px;margin:12px 0}.eyebrow{color:#7b8c80;font-size:11px;letter-spacing:.4px}.inspector-lead{font-size:13px;color:#4f6b59}.inspector-fields{font-size:13px;line-height:1.85}.inspector-fields dt{color:#788b7d;margin:17px 0 4px;font-size:12px}.inspector-fields dd{white-space:pre-wrap;overflow-wrap:anywhere}.strategy-links{display:flex;flex-direction:column;gap:9px}.strategy-links>div{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.outgoing-link{display:block;width:100%;background:#f8faf9;border:1px solid #e3ebe6;border-radius:6px;padding:10px 12px;text-align:left;margin:8px 0;color:#365b44;font:inherit}.outgoing-link strong{display:block;font-size:13px}.outgoing-link span{display:block;color:#748479;font-size:12px;margin-top:3px}.connection-names{font-size:13px;color:#587461;padding:10px;background:#f1f7f3;border-radius:6px}.blueprint-save{position:sticky;bottom:0;z-index:2;display:flex;align-items:center;gap:10px;background:#fff;border:1px solid #dce6df;border-radius:8px;padding:12px 16px;box-shadow:0 -4px 18px #244b3410;margin-top:20px}.blueprint-save>span{flex:1;font-size:12px;color:#6f8175}.item-name{font-size:14px;font-weight:600}.strategy-table td:first-child{width:155px}.strategy-table td:nth-child(2){width:48%}.strategy-heading{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:18px 0}.strategy-heading h3{font-size:22px;color:#264e37}.strategy-section .field-list{margin-bottom:0}.strategy-section .row-between h3{margin:0}.strategy-section .field-list dt{width:135px}.rule-intro{margin:18px 0}.rule-table td:first-child{width:20%}.rule-table td:nth-child(3){width:22%}.rule-table th:nth-child(4),.rule-table td:nth-child(4){width:76px;white-space:nowrap}.rule-table th:last-child,.rule-table td:last-child{width:106px;white-space:nowrap}.rule-table .row-actions .text-link{white-space:nowrap}.row-actions{display:flex;gap:12px}.system-boundaries ul{padding-left:22px;font-size:13px;line-height:2}.history-row{display:flex;gap:20px;padding:15px 0;border-bottom:1px solid #e5ece7;font-size:13px}.history-row small{display:block;color:#7a8d80;margin-top:5px}.strategy-picker{display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;margin-top:14px}.strategy-picker legend,fieldset>legend{font-weight:600;color:#34553f;margin-top:12px}.remove-button{margin-right:auto;color:#a44b32}.scene-header{display:flex;justify-content:space-between;align-items:center;margin:18px 0}.scene-header h3{font-size:20px;color:#2d4b3c}.scene-choices{display:flex;gap:10px;margin:18px 0;flex-wrap:wrap}.scenario-context{padding:16px 20px}.scenario-context p{font-size:13px}.stage-strip{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0}.stage-strip>span{display:flex;align-items:center;gap:6px;background:#edf0ee;color:#7a8c80;padding:7px 10px;border:1px solid transparent;border-radius:6px;font-size:12px}.stage-strip small{font-size:11px}.stage-strip>span.visited{background:#edf5f0;color:#426c51}.stage-strip>span.active{background:#e0efe6;border-color:#438b61;color:#214c32;font-weight:600}.scene-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,1fr);gap:18px;align-items:start}.conversation h3{margin:14px 0 20px;font-size:18px}.speech{padding:14px 16px;border-radius:8px;margin:14px 0;font-size:14px;line-height:1.95}.speech>span{font-size:11px;color:#738879}.speech.student{background:#f2f5f8;margin-left:22px}.speech.tutor{background:#eef7f1;margin-right:22px}.speech p{margin:4px 0}.teaching-figure{margin:16px 0 0;padding:8px;background:#fff;border:1px solid #dbe8df;border-radius:6px}.teaching-figure svg{display:block;width:100%;max-width:420px;margin:auto}.teaching-figure text{font-size:13px;fill:#345a43}.teaching-figure figcaption{font-size:12px;color:#647c6c;text-align:center;line-height:1.6;margin-top:4px}.decision h3{margin-top:14px}.decision dd>.text-link{display:block;margin-top:5px}.response-branches{border-top:1px solid #e3ebe6;margin-top:24px}.branch-button{display:block;background:white;border:1px solid #d6e3d9;color:#345e43;border-radius:6px;padding:10px 14px;width:100%;text-align:left;font-size:13px;margin:8px 0}.branch-button:hover{background:#eff7f2}.scene-controls{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:24px}.path-summary{display:flex;align-items:flex-start;gap:16px;padding:12px 0;font-size:12px;color:#54715e;line-height:1.9}.path-summary>.muted{flex-shrink:0}.graph-toggle{margin:8px 0 16px}.scene-graph{margin-top:8px}@media(max-width:1180px){.blueprint-layout{grid-template-columns:minmax(440px,1.3fr) minmax(270px,1fr);gap:12px}.inspector{padding:15px}}@media(max-width:1250px){.blueprint-layout,.scene-layout{grid-template-columns:1fr}.inspector{position:static}.header-actions{flex-wrap:wrap}.blueprint-tools{flex-wrap:wrap}.graph-panel{max-width:740px}.scene-choices .btn{white-space:normal}}@media(max-width:700px){.page-header{flex-wrap:wrap}.strategy-picker{grid-template-columns:1fr}.blueprint-save{flex-wrap:wrap}.blueprint-save>span{flex-basis:100%}.strategy-heading{flex-wrap:wrap}.rule-table{min-width:650px}.table-card{overflow:auto}}
</style>
