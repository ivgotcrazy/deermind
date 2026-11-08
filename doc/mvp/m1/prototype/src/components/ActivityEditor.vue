<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import QuarterWalkthrough from './QuarterWalkthrough.vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import TeachingBlueprint from './TeachingBlueprint.vue';
import NodeRoutingPanel from './NodeRoutingPanel.vue';
import TeachingReferences from './TeachingReferences.vue';
import { teachingStorageError as explanationError, teachingMock as explanationModel, teachingScenes, teachingSceneBlueprint, teachingSceneStrategies, teachingBlueprintDraft as explanationDraft, copyTeaching, newTeachingId, recordTeachingChange as recordExplanationChange, validateTeachingBlueprint, type TeachingStage, type NodeRouting, type TeachingTransition, type TeachingStrategy, type TeachingRule } from '../model/teaching-mock';
import { activityNames, getActivityWorkspace, type ActivityKind } from '../model/activity-mock';

const props=defineProps<{hash:string;kind:ActivityKind}>();
const activityName=activityNames[props.kind];
const workspace=props.kind==='explanation'?{model:explanationModel,draft:explanationDraft,error:explanationError,record:recordExplanationChange,migrationNotice:''}:getActivityWorkspace(props.kind);
const teachingMock=workspace.model,teachingStorageError=workspace.error,recordTeachingChange=workspace.record;
function params(){return new URLSearchParams(props.hash.split('?')[1]);}
const route={get tab(){return params().get('tab')||'blueprint';},get kind(){return params().get('kind')||'explanation';},get scope(){return params().get('scope')||'';},get round(){return params().get('round')||'';},get id(){return params().get('id')||'';},get returnTo(){return params().get('returnTo')||'';}};
function go(page:string,query:Record<string,string>){location.hash='/'+page+'?'+new URLSearchParams({...query,kind:props.kind});}
const tabs=[{id:'blueprint',name:activityName+'蓝图'},{id:'strategies',name:'活动推荐策略'},{id:'rules',name:'活动规则'}];
const tab=computed(()=>route.tab||'blueprint');
const draft=workspace.draft;
const dirty=computed(()=>JSON.stringify(draft.value)!==JSON.stringify(teachingMock.blueprint));
const selectedStage=ref(props.kind==='explanation'?'teach':draft.value.stages[0]?.id||'start'),selectedEdge=ref('');
const stage=computed(()=>draft.value.stages.find(s=>s.id===selectedStage.value));
const scopeEditing=ref<'rules'|'strategies'|null>(null),scopeIds=ref<string[]>([]);
const scopeOptions=computed(()=>scopeEditing.value==='rules'?teachingMock.rules:teachingMock.strategies);
const nodeRuleOptions=computed(()=>teachingMock.rules.filter(r=>!teachingMock.activityRules.includes(r.id)));
const nodeStrategyOptions=computed(()=>teachingMock.strategies.filter(s=>!teachingMock.activityStrategies.includes(s.id)));
function ruleRefs(ids:string[]=[]){return ids.map(id=>teachingMock.rules.find(r=>r.id===id)).filter((r):r is TeachingRule=>!!r);}
function strategyRefs(ids:string[]=[]){return ids.map(id=>teachingMock.strategies.find(s=>s.id===id)).filter((s):s is TeachingStrategy=>!!s);}
function localRules(n:TeachingStage){return (n.rules||[]).filter(id=>!teachingMock.activityRules.includes(id));}
function localStrategies(n:TeachingStage){return n.strategies.filter(id=>!teachingMock.activityStrategies.includes(id));}
async function showRule(id:string){go('interaction',{tab:'rules',id});await nextTick();requestAnimationFrame(()=>document.querySelector('.rule-table tr.highlight')?.scrollIntoView({block:'center'}));}
function configureScope(kind:'rules'|'strategies'){scopeEditing.value=kind;scopeIds.value=[...(kind==='rules'?teachingMock.activityRules:teachingMock.activityStrategies)];}
function saveScope(){
  if(scopeEditing.value==='rules')teachingMock.activityRules=[...scopeIds.value];else teachingMock.activityStrategies=[...scopeIds.value];
  recordTeachingChange('修改'+activityName+'活动级'+(scopeEditing.value==='rules'?'规则':'推荐策略')+'引用');
  scopeEditing.value=null;notice.value='活动级配置已保存，所有节点继承；不会修改其他活动。';
}
function ruleUsage(id:string){return [teachingMock.activityRules.includes(id)?'活动级 · 所有节点':'',...draft.value.stages.filter(n=>localRules(n).includes(id)).map(n=>'节点级 · '+n.name)].filter(Boolean).join('、')||'未引用';}

const notice=ref(workspace.migrationNotice),error=ref(''),errorNode=ref<HTMLElement>();
const dialog=ref<'stage'|'meta'|'strategy'|'rule'|'discard'|null>(null);
const removing=ref(false),isNew=ref(false),strategyGroup=ref('');
const stageForm=ref<TeachingStage>({id:'',name:'',purpose:'',inputs:'',approach:'',outputs:'',strategies:[]});

const insertAt=ref(''),metaForm=ref({name:'',purpose:''});
const strategyForm=ref<TeachingStrategy>({} as TeachingStrategy),ruleForm=ref<TeachingRule>({} as TeachingRule);
const query=ref(''),status=ref('all'),page=ref(1);
const filtered=computed(()=>teachingMock.strategies.filter(s=>(status.value==='all'||s.enabled===(status.value==='enabled'))&&[s.name,s.purpose,s.when].join(' ').includes(query.value.trim())));
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/8)));
const strategy=computed(()=>teachingMock.strategies.find(s=>s.id===route.id));

const strategyGroups=[
  {id:'definition',title:'基本定义与适用条件',fields:[['purpose','策略目的'],['when','适用情况'],['avoid','不适用情况'],['inputs','需要的信息']]},
  {id:'organization',title:'组织方式',fields:[['organization','如何开展'],['help','允许的帮助'],['observe','需要观察的表现']]},
  {id:'adjustment',title:'调整与结束',fields:[['adjust','调整方式'],['end','结束条件']]},
  {id:'basis',title:'依据与示例',fields:[['basis','依据与限制'],['examples','领域示例']]},
];
const editingGroups=computed(()=>strategyGroups.filter(g=>!strategyGroup.value||g.id===strategyGroup.value));
const dialogTitle=computed(()=>dialog.value==='stage'?(isNew.value?'添加活动节点':'编辑节点：'+stageForm.value.name):dialog.value==='strategy'?(isNew.value?'新建推荐策略':'编辑'+(strategyGroups.find(g=>g.id===strategyGroup.value)?.title||'策略')):dialog.value==='rule'?(isNew.value?'新增活动规则':'编辑活动规则'):dialog.value==='meta'?'编辑蓝图信息':'放弃蓝图修改');
watch([query,status],()=>page.value=1);
watch(pages,n=>page.value=Math.min(page.value,n));
function stageName(id:string){return id==='start'?'开始':id==='end'?'结束':draft.value.stages.find(s=>s.id===id)?.name||'未指定';}
function strategyName(id:string){return teachingMock.strategies.find(s=>s.id===id)?.name||'策略不存在';}
function referencedBy(id:string){return [teachingMock.activityStrategies.includes(id)?'活动级 · 所有节点':'',...draft.value.stages.filter(s=>localStrategies(s).includes(id)).map(s=>'节点级 · '+s.name)].filter(Boolean).join('、');}
function valueOf(s:TeachingStrategy,key:string){return String(s[key as keyof TeachingStrategy]||'');}
function setStrategyField(key:string,value:string){(strategyForm.value as unknown as Record<string,unknown>)[key]=value;}
function pickStage(id:string){selectedStage.value=id;selectedEdge.value='';error.value='';}
function pickEdge(id:string){selectedEdge.value=id;selectedStage.value=draft.value.transitions.find(e=>e.id===id)?.from||'';error.value='';}
function saveRouting(policy:NodeRouting,transitions:TeachingTransition[]){
  const id=selectedStage.value;
  if(id==='end')return;
  if(id==='start')draft.value.startRouting=policy;else if(stage.value)stage.value.routing=policy;
  draft.value.transitions=[...draft.value.transitions.filter(e=>e.from!==id),...transitions];
  if(!transitions.some(e=>e.id===selectedEdge.value))selectedEdge.value='';
  notice.value='节点条件转移已加入草稿，保存蓝图后生效。';
}
function open(kind:typeof dialog.value){dialog.value=kind;error.value='';removing.value=false;}
function close(){dialog.value=null;error.value='';removing.value=false;}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'nearest'});}
function editStage(create=false){isNew.value=create;stageForm.value=create?{id:newTeachingId('stage'),name:'',purpose:'',inputs:'',approach:'',outputs:'',strategies:[],rules:[],actions:'',blocked:''}:copyTeaching(stage.value!);insertAt.value=draft.value.transitions.find(e=>e.from===(stage.value?.id||'teach'))?.id||draft.value.transitions[0]?.id||'';open('stage');}
function editMeta(){metaForm.value={name:draft.value.name,purpose:draft.value.purpose};open('meta');}
function saveStage(){
  const s=stageForm.value;
  if(!s.name.trim()||!s.purpose.trim()||!s.inputs.trim()||!s.outputs.trim())return fail('请填写节点名称、目的、所需信息和节点结果。');
  if(!s.actions?.trim()||!s.blocked?.trim())return fail('请填写允许动作和无法继续时的处理。');
  if(isNew.value){
    const link=draft.value.transitions.find(e=>e.id===insertAt.value);if(!link)return fail('请选择新节点插入的位置。');
    const after=draft.value.stages.findIndex(n=>n.id===link.from);draft.value.stages.splice(after+1,0,copyTeaching(s));
    const previousTo=link.to;link.to=s.id;
    draft.value.transitions.push({id:newTeachingId('edge'),from:s.id,to:previousTo,label:'本节点完成',condition:'本节点结果已形成，可以继续。',basis:s.outputs});
  }else{const index=draft.value.stages.findIndex(n=>n.id===s.id);draft.value.stages[index]=copyTeaching(s);}
  pickStage(s.id);close();notice.value='节点已加入蓝图草稿；保存蓝图后生效。';
}
function removeSelected(){
  if(dialog.value!=='stage'||['start','end'].includes(stageForm.value.id))return;
  const id=stageForm.value.id;draft.value.stages=draft.value.stages.filter(s=>s.id!==id);draft.value.transitions=draft.value.transitions.filter(e=>e.from!==id&&e.to!==id);selectedStage.value=draft.value.stages[0]?.id||'start';
  close();notice.value='已从草稿移除，请补齐路径后保存蓝图。';
}
function saveBlueprint(){
  const problem=validateTeachingBlueprint(draft.value,teachingMock);if(problem)return fail(problem);
  const old=teachingMock.blueprint,changes:string[]=[];
  if(JSON.stringify(old.startRouting)!==JSON.stringify(draft.value.startRouting))changes.push('开始节点条件转移');
  if(JSON.stringify(old.transitions.map(e=>e.id))!==JSON.stringify(draft.value.transitions.map(e=>e.id)))changes.push('条件转移顺序');
  if(old.name!==draft.value.name||old.purpose!==draft.value.purpose)changes.push('蓝图信息');
  for(const s of draft.value.stages)if(JSON.stringify(s)!==JSON.stringify(old.stages.find(x=>x.id===s.id)))changes.push('节点「'+s.name+'」');
  for(const e of draft.value.transitions)if(JSON.stringify(e)!==JSON.stringify(old.transitions.find(x=>x.id===e.id)))changes.push('连接「'+e.label+'」');
  if(old.stages.length>draft.value.stages.length||old.transitions.length>draft.value.transitions.length)changes.push('移除节点或连接');
  teachingMock.blueprint=copyTeaching(draft.value);recordTeachingChange('保存蓝图：'+changes.join('、'));notice.value='蓝图已保存为活动配置 v'+teachingMock.revision+'。';error.value='';
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
  if(['name','purpose','when','avoid','organization','observe','adjust','end','basis'].some(key=>!valueOf(s,key).trim()))return fail('请补齐名称、目的、适用与不适用情况、组织方式、观察、调整、结束条件和依据。');
  const existing=teachingMock.strategies.find(x=>x.id===s.id);s.version=existing?existing.version+1:1;
  if(existing)Object.assign(existing,copyTeaching(s));else teachingMock.strategies.unshift(copyTeaching(s));
  recordTeachingChange((existing?'修改':'新增')+'策略「'+s.name+'」'+(strategyGroup.value?'：'+strategyGroups.find(g=>g.id===strategyGroup.value)?.title:''));
  close();go('interaction',{tab:'strategies',id:s.id,returnTo:route.returnTo});notice.value='策略已保存；引用它的节点使用同一份定义。';
}
function toggleStrategy(){if(!strategy.value)return;strategy.value.enabled=!strategy.value.enabled;strategy.value.version++;recordTeachingChange((strategy.value.enabled?'启用':'停用')+'策略「'+strategy.value.name+'」');notice.value=strategy.value.enabled?'策略已启用。':'策略已停用，节点保留引用，不再推荐。';}
function editRule(rule?:TeachingRule){isNew.value=!rule;ruleForm.value=rule?copyTeaching(rule):{id:newTeachingId('rule'),name:'',when:'',requirement:'',basis:'',enabled:true,version:1};open('rule');}
function saveRule(){const r=ruleForm.value;if(!r.name.trim()||!r.when.trim()||!r.requirement.trim()||!r.basis.trim())return fail('请填写规则名称、适用情况、要求和依据。');const current=teachingMock.rules.find(x=>x.id===r.id);r.version=current?current.version+1:1;if(current)Object.assign(current,copyTeaching(r));else teachingMock.rules.push(copyTeaching(r));recordTeachingChange((current?'修改':'新增')+'规则「'+r.name+'」');close();notice.value='活动规则已保存。';}
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
function changeScene(id:string){sceneId.value=id;trail.value=['entry'];sceneGraphSelection.value='';go('interaction',{tab:'scenes',scope:id,round:'entry'});}
function advance(id:string){trail.value.push(id);sceneGraphSelection.value='';go('interaction',{tab:'scenes',scope:sceneId.value,round:id});}
function previous(){if(trail.value.length>1){trail.value.pop();go('interaction',{tab:'scenes',scope:sceneId.value,round:trail.value[trail.value.length-1]});}}
function scenePath(target:string,path=['entry']):string[]|undefined{const item=scene.value.steps.find(s=>s.id===path[path.length-1]);if(!item)return;if(item.id===target)return path;for(const id of [item.next,...(item.choices||[]).map(c=>c.next)].filter(Boolean) as string[]){if(!path.includes(id)){const found=scenePath(target,[...path,id]);if(found)return found;}}}
watch(()=>[route.tab,route.scope,route.round],()=>{if(route.tab==='scenes'){if(teachingScenes.some(s=>s.id===route.scope))sceneId.value=route.scope;if(route.round&&route.round!==trail.value[trail.value.length-1])trail.value=scenePath(route.round)||['entry'];}},{immediate:true});
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue='';}}
onMounted(()=>window.addEventListener('beforeunload',beforeUnload));onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload));
</script>

<template><div class="teaching-workspace" :data-activity-kind="kind">
  <nav v-if="tab!=='scenes'" class="teaching-tabs button-row" :aria-label="activityName+'活动分区'"><button v-for="t in tabs" :key="t.id" :class="{active:tab===t.id}" :aria-current="tab===t.id?'page':undefined" class="btn" @click="go('interaction',{tab:t.id});notice=''">{{t.name}}</button></nav>
  <p v-if="teachingStorageError" role="alert" class="callout danger">{{teachingStorageError}}</p>
  <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
  <p v-if="error&&!dialog" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
  <p v-if="dirty&&tab!=='blueprint'" class="callout amber">蓝图有未保存的修改。<button class="text-link" @click="go('interaction',{tab:'blueprint'})">返回蓝图保存或取消 →</button></p>

  <template v-if="tab==='blueprint'">
    <div class="blueprint-heading"><div><h3>{{draft.name}}</h3><p>{{draft.purpose}}</p></div><button class="text-link" @click="editMeta">编辑信息</button></div>
    <div class="blueprint-tools"><span class="muted">点击节点配置执行内容和条件转移；点击箭头定位对应条件。</span><div><button class="btn" @click="editStage(true)">添加节点</button></div></div>
    <div class="blueprint-layout">
      <section class="panel graph-panel"><TeachingBlueprint node-routing :blueprint="draft" :selected-stage="selectedStage" :selected-transition="selectedEdge" @stage="pickStage" @transition="pickEdge"/></section>
      <aside class="panel inspector" aria-label="蓝图定义详情">
        <template v-if="stage"><div class="row-between"><span class="eyebrow">节点定义</span><button class="btn" @click="editStage()">编辑节点</button></div><h3>{{stage.name}}</h3><p class="inspector-lead">{{stage.purpose}}</p>
          <dl class="inspector-fields"><dt>需要的信息</dt><dd>{{stage.inputs}}</dd><dt>怎样开展</dt><dd>{{stage.approach||'尚未补充'}}</dd><dt>留下的结果</dt><dd>{{stage.outputs}}</dd><dt>允许动作</dt><dd>{{stage.actions}}</dd><dt>无法继续时的处理</dt><dd>{{stage.blocked}}</dd></dl>
          <p class="scope-note">活动规则与本节点规则共同生效，本节点不能放宽活动规则。推荐策略按适用条件选择，不强制采用。</p>
          <TeachingReferences title="本节点规则" :rules="ruleRefs(localRules(stage))" @rule="showRule"/>
          <TeachingReferences title="本节点推荐策略" :strategies="strategyRefs(localStrategies(stage))" @strategy="openStrategy"/>
          <p class="muted">通过“编辑节点”调整本节点引用。继承项需在活动级管理；子活动使用自身配置，系统约束始终生效。</p>
        </template>
        <template v-else-if="selectedStage==='start'||selectedStage==='end'"><span class="eyebrow">预置节点 · 不可删除</span><h3>{{stageName(selectedStage)}}</h3><p>{{selectedStage==='start'?'本活动的唯一入口。只配置出向条件转移，没有入向连接。':'结束当前活动，没有出向连接。若为子活动，则把结果交回父活动；不表示整个聊天结束或目标达标。'}}</p><p class="scope-note">预置节点同样继承活动配置；推荐策略只在适用时采用，不增加节点动作。</p></template>
        <p v-else class="empty">选择节点，查看执行内容和条件转移。</p>
        <NodeRoutingPanel v-if="stage||selectedStage==='start'" :key="selectedStage" :blueprint="draft" :node-id="selectedStage" :selected-edge="selectedEdge" @save="saveRouting"/>
      </aside>
    </div>
    <div class="blueprint-save"><span>{{dirty?'有未保存的蓝图修改':'蓝图已保存'}}</span><button class="btn" :disabled="!dirty" @click="open('discard')">取消修改</button><button class="btn primary" :disabled="!dirty" @click="saveBlueprint">保存蓝图</button></div>
  </template>

  <template v-else-if="tab==='strategies'">
    <template v-if="!route.id">
      <section class="panel scope-panel" aria-label="活动级策略配置"><div class="row-between"><h3>活动推荐策略</h3><button class="btn" @click="configureScope('strategies')">选择活动推荐策略</button></div><p>供所有节点按适用条件考虑，不要求全部采用；没有合适推荐时可使用其他合规教法。不会自动传给子活动。</p><TeachingReferences title="当前活动推荐" :strategies="strategyRefs(teachingMock.activityStrategies)" @strategy="openStrategy"/></section>
      <h3>策略定义</h3><p class="muted">活动与节点引用同一份定义；新建定义后，选择引用位置才会加入推荐。</p>
      <section class="panel strategy-filters" aria-label="推荐策略筛选">
        <label>搜索策略<input v-model="query" type="search" placeholder="名称、目的或适用情况"/></label>
        <label>策略状态<select v-model="status"><option value="all">全部</option><option value="enabled">启用</option><option value="disabled">停用</option></select></label>
        <button class="btn primary" @click="editStrategy('',true)">新建策略</button>
      </section>
      <section class="table-card teaching-list"><table class="data-table strategy-table"><thead><tr><th>推荐策略</th><th>策略目的 / 适用情况</th><th>推荐范围</th><th>状态 / 版本</th></tr></thead><tbody><tr v-for="s in filtered.slice((page-1)*8,page*8)" :key="s.id"><td><button class="text-link item-name" @click="openStrategy(s.id)">{{s.name}}</button></td><td>{{s.purpose}}<small>{{s.when}}</small></td><td>{{referencedBy(s.id)||'尚未引用'}}</td><td><span class="badge" :class="s.enabled?'green':''">{{s.enabled?'启用':'停用'}}</span><small>v{{s.version}}</small></td></tr></tbody></table><div v-if="!filtered.length" class="empty"><p>没有符合条件的策略。</p><button v-if="query || status!=='all'" class="text-link" @click="query='';status='all'">清除筛选</button></div></section>
      <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page===1" @click="page--">上一页</button><span>{{page}} / {{pages}}</span><button class="btn" :disabled="page===pages" @click="page++">下一页</button></div>
    </template>
    <template v-else-if="strategy"><button class="text-link" @click="returnFromStrategy">← 返回{{route.returnTo.includes('tab=scenes')?'情境推演':route.returnTo.includes('tab=blueprint')||route.returnTo==='#/interaction'?'活动蓝图':'策略列表'}}</button><div class="strategy-heading"><div><span class="eyebrow">推荐策略 · v{{strategy.version}}</span><h3>{{strategy.name}}</h3></div><div><span class="badge" :class="strategy.enabled?'green':''">{{strategy.enabled?'启用':'停用'}}</span><button class="btn" @click="toggleStrategy">{{strategy.enabled?'停用策略':'启用策略'}}</button></div></div>
      <p class="callout" :class="!strategy.enabled&&referencedBy(strategy.id)?'amber':''">引用范围：{{referencedBy(strategy.id)||'尚未引用'}}。{{!strategy.enabled?'停用后不能作为可选策略；引用保留以便调整。':'修改后使用同一份策略定义，不在各节点复制。'}}</p>
      <section v-for="g in strategyGroups" :key="g.id" class="panel strategy-section"><div class="row-between"><h3>{{g.title}}</h3><button class="btn" @click="editStrategy(g.id)">编辑{{g.title}}</button></div><dl class="field-list"><template v-for="[key,label] in g.fields" :key="key"><dt>{{label}}</dt><dd>{{valueOf(strategy,key)||'尚未补充'}}</dd></template></dl></section>
    </template><p v-else class="empty">未找到此策略。<button class="text-link" @click="go('interaction',{tab:'strategies'})">返回列表</button></p>
  </template>

  <template v-else-if="tab==='rules'">
    <section class="panel scope-panel" aria-label="活动级规则配置"><div class="row-between"><h3>活动规则</h3><button class="btn" @click="configureScope('rules')">选择活动规则</button></div><p>已启用的活动规则由所有节点共同遵守。本节点规则只能补充，不能覆盖；冲突时停止相关动作，不由 LLM 自行豁免。</p><TeachingReferences title="当前活动规则" :rules="ruleRefs(teachingMock.activityRules)" @rule="showRule"/></section>
    <h3>规则定义</h3>
    <div class="row-between rule-intro"><p class="muted">规则定义供活动或节点引用，新建不会自动生效；不在此改写学习目标或能力评价规则。</p><button class="btn primary" @click="editRule()">新增规则</button></div>
    <section class="table-card teaching-list"><table class="data-table rule-table"><thead><tr><th>规则 / 适用情况</th><th>具体要求</th><th>依据</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="r in teachingMock.rules" :key="r.id" :class="{highlight:route.id===r.id}"><td><strong>{{r.name}}</strong><small>{{r.when}}</small><small class="scope-label">{{ruleUsage(r.id)}}</small></td><td>{{r.requirement}}</td><td>{{r.basis}}</td><td><span class="badge" :class="r.enabled?'green':''">{{r.enabled?'启用':'停用'}}</span><small>v{{r.version}}</small></td><td><div class="row-actions"><button class="text-link" :aria-label="'编辑规则：'+r.name" @click="editRule(r)">编辑</button><button class="text-link" :aria-label="(r.enabled?'停用':'启用')+'规则：'+r.name" @click="toggleRule(r)">{{r.enabled?'停用':'启用'}}</button></div></td></tr></tbody></table></section>
    <details class="system-boundaries"><summary>适用的系统约束 · 只读</summary><ul><li>学生可以停止或暂停；当天使用满 30 分钟只提醒，由家长决定何时结束。</li><li>子活动使用自身配置，父活动保留返回位置；检测轮内实质求助先结束检测轮，再提供帮助。</li><li>实际帮助保留。活动结束不等于目标达成，能力认识仍由 Evaluation 负责。</li><li>本页不能改写正式学习目标、创建 KC 能力评分或借用另一个空间的个人记录。</li></ul></details>
  </template>

  <QuarterWalkthrough v-else-if="kind==='explanation'&&tab==='quarter'"/>
  <template v-else-if="kind==='explanation'&&tab==='scenes'">
    <button class="text-link" @click="go('interaction',{tab:'blueprint'})">← 返回教学蓝图</button>
    <div class="scene-header"><div><h3>三种学生情境</h3><p class="muted">预设分支 · 基于活动配置 v1 · 不调用 LLM、不产生真实评价</p></div><button class="btn" @click="changeScene(sceneId)">重新推演</button></div>
    <p v-if="teachingMock.revision!==1" class="callout amber" role="status">规则已修改，示例待核对。下方仍展示 v1 的预设路径，不是当前 v{{teachingMock.revision}} 规则的运行或验证结果。</p>
    <div class="scene-choices" aria-label="选择学生情境"><button v-for="s in teachingScenes" :key="s.id" class="btn" :class="{primary:sceneId===s.id}" :aria-pressed="sceneId===s.id" @click="changeScene(s.id)">{{s.name}}</button></div>
    <section class="panel scenario-context"><strong>本次重点：理解连续两级部分量的参照关系</strong><p>气象小组 12 人，摄影人数是气象的 1/3，航模人数是摄影的 3/4。求航模人数。</p><p class="muted">三种情境均已明确本次重点。{{scene.starting}}</p></section>
    <div class="stage-strip" aria-label="当前活动节点"><span v-for="(s,i) in teachingSceneBlueprint.stages" :key="s.id" :class="{active:step.stage===s.id,visited:visited.includes(s.id)}"><small>{{i+1}}</small>{{s.name}}</span></div>
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
      <aside class="panel decision"><span class="eyebrow">本轮教学决策 · 预设期望</span><h3>{{teachingSceneBlueprint.stages.find(s=>s.id===step.stage)?.name}}</h3><dl class="inspector-fields"><dt>采用策略</dt><dd><template v-if="sceneStrategy"><strong>{{sceneStrategy.name}} · v1</strong><button class="text-link" @click="openStrategy(sceneStrategy.id)">查看当前策略定义 ↗</button></template><span v-else>节点组织，无需选择讲解策略</span></dd><dt>为什么这样选择</dt><dd>{{step.reason}}</dd><dt>接下来观察什么</dt><dd>{{step.observe}}</dd><dt>评价与帮助边界</dt><dd>{{step.evidence}}</dd></dl></aside>
    </div>
    <div class="path-summary"><span class="muted">已经走过</span><span>明确重点 → {{scenePathText}}</span></div>
    <button class="text-link graph-toggle" :aria-expanded="showSceneGraph" @click="showSceneGraph=!showSceneGraph">{{showSceneGraph?'收起':'展开'}}蓝图路径与来源规则</button>
    <div v-if="showSceneGraph" class="blueprint-layout scene-graph"><section class="panel graph-panel"><TeachingBlueprint :blueprint="teachingSceneBlueprint" :active-stage="step.stage" :visited="visited" :traced-edges="sceneEdges" :selected-stage="sceneNode?.id" :selected-transition="sceneEdge?.id" @stage="sceneGraphSelection=$event" @transition="sceneGraphSelection=$event"/></section><aside class="panel inspector"><span class="eyebrow">示例依据 · v1 定义</span><template v-if="sceneEdge"><h3>{{sceneEdge.label}}</h3><dl class="inspector-fields"><dt>转移条件</dt><dd>{{sceneEdge.condition}}</dd><dt>判断依据</dt><dd>{{sceneEdge.basis}}</dd></dl></template><template v-else-if="sceneNode"><h3>{{sceneNode.name}}</h3><p>{{sceneNode.purpose}}</p><dl class="inspector-fields"><dt>如何开展</dt><dd>{{sceneNode.approach}}</dd><dt>节点结果</dt><dd>{{sceneNode.outputs}}</dd></dl></template><p v-else>绿色显示已经经过的节点与连接。点击节点或连线查看其 v1 定义；这里不编辑当前模型。</p></aside></div>
  </template>

  <WorkbenchDialog v-if="scopeEditing" :title="scopeEditing==='rules'?'选择活动规则':'选择活动推荐策略'" @close="scopeEditing=null"><form @submit.prevent="saveScope"><p>对当前活动生效；未选用的定义仍可由具体节点引用。停用项保留引用，但不生效。</p><label v-for="item in scopeOptions" :key="item.id" class="check-label"><input v-model="scopeIds" type="checkbox" :value="item.id" :disabled="!item.enabled&&!scopeIds.includes(item.id)"/>{{item.name}}{{item.enabled?'':'（已停用）'}}</label><div class="dialog-footer button-row"><button class="btn" type="button" @click="scopeEditing=null">取消</button><button class="btn primary">保存活动配置</button></div></form></WorkbenchDialog>
  <WorkbenchDialog v-if="dialog" :title="dialogTitle" wide @close="close"><form v-if="dialog!=='discard'" @submit.prevent="dialog==='stage'?saveStage():dialog==='strategy'?saveStrategy():dialog==='rule'?saveRule():(Object.assign(draft,metaForm),close())" novalidate>
    <p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
    <template v-if="dialog==='meta'"><label>蓝图名称<input v-model="metaForm.name"/></label><label>蓝图用途<textarea v-model="metaForm.purpose"/></label></template>
    <template v-if="dialog==='stage'"><label>节点名称<input v-model="stageForm.name" maxlength="60"/></label><label>节点目的<textarea v-model="stageForm.purpose"/></label><div class="two-columns"><label>需要的信息<textarea v-model="stageForm.inputs"/></label><label>留下的结果<textarea v-model="stageForm.outputs"/></label></div><label>怎样开展<textarea v-model="stageForm.approach"/></label><label>允许动作<textarea v-model="stageForm.actions" rows="3" placeholder="允许留在本节点做什么，哪些工作应交给子活动"/></label><label>无法继续时的处理<textarea v-model="stageForm.blocked" rows="3" placeholder="信息不足、内容无法核实、规则冲突或学生停止时怎样处理"/></label>
      <p class="scope-note">继承项在活动级管理，此处只能选用本节点的补充规则和推荐策略。</p>
      <fieldset class="strategy-picker"><legend>本节点规则（可多选）</legend><label v-for="r in nodeRuleOptions" :key="r.id" class="check-label"><input v-model="stageForm.rules" type="checkbox" :value="r.id" :disabled="!r.enabled&&!stageForm.rules?.includes(r.id)"/>{{r.name}}{{r.enabled?'':'（已停用）'}}</label></fieldset>
      <fieldset class="strategy-picker"><legend>本节点推荐策略（可多选）</legend><label v-for="s in nodeStrategyOptions" :key="s.id" class="check-label"><input v-model="stageForm.strategies" type="checkbox" :value="s.id" :disabled="!s.enabled&&!stageForm.strategies.includes(s.id)"/>{{s.name}}{{s.enabled?'':'（已停用）'}}</label></fieldset>
      <label v-if="isNew">插入到哪条连接中<select v-model="insertAt"><option v-for="e in draft.transitions" :key="e.id" :value="e.id">{{stageName(e.from)}} → {{stageName(e.to)}} · {{e.label}}</option></select></label><p v-if="isNew" class="muted">保留原进入条件；新节点完成后连接原终点，可再编辑两条连接。</p></template>
    <template v-if="dialog==='strategy'"><label v-if="!strategyGroup||strategyGroup==='definition'">策略名称<input v-model="strategyForm.name" maxlength="80"/></label><fieldset v-for="g in editingGroups" :key="g.id"><legend v-if="isNew">{{g.title}}</legend><label v-for="[key,label] in g.fields" :key="key">{{label}}<textarea :value="valueOf(strategyForm,key)" rows="3" @input="setStrategyField(key,($event.target as HTMLTextAreaElement).value)"/></label></fieldset><p class="muted">通用策略不绑定某道题；具体领域用法放在示例中。</p></template>
    <template v-if="dialog==='rule'"><label>规则名称<input v-model="ruleForm.name"/></label><label>适用情况<textarea v-model="ruleForm.when"/></label><label>具体要求<textarea v-model="ruleForm.requirement" rows="4"/></label><label>依据与限制<textarea v-model="ruleForm.basis"/></label></template>
    <p v-if="removing" class="callout amber">移除节点会一并移除关联连接。请补齐路径后保存。<button type="button" class="btn danger-btn" @click="removeSelected">确认移除</button><button type="button" class="btn" @click="removing=false">保留</button></p>
    <div class="dialog-footer button-row"><button v-if="!isNew&&dialog==='stage'" type="button" class="text-link remove-button" @click="removing=true">移除节点</button><button type="button" class="btn" @click="close">取消</button><button class="btn primary" type="submit">{{dialog==='stage'||dialog==='meta'?'应用到草稿':'保存'}}</button></div>
  </form><template v-else><p>放弃未保存的蓝图修改，恢复上次保存的版本？</p><div class="dialog-footer button-row"><button class="btn" @click="close">继续编辑</button><button class="btn primary" @click="discard">确认放弃</button></div></template></WorkbenchDialog>
</div></template>

<style scoped>
.teaching-tabs .btn.active:hover{background:#2d6a4f;color:#fff}
.scope-panel{margin:16px 0}.scope-panel p,.scope-note{font-size:13px;line-height:1.8;color:#607567}.scope-note{background:#f0f6f2;padding:12px;border-radius:6px}.scope-label{color:#2d6a4f!important}.highlight{background:#eef7f1}
.teaching-workspace{max-width:1600px}.header-actions,.blueprint-tools>div,.strategy-heading>div:last-child{display:flex;align-items:center;gap:10px}.teaching-tabs{margin-top:0}.teaching-tabs .active{background:#2d6a4f;color:white}.saved-note{padding:9px 14px;color:#2b6b48;background:#eaf5ee;border-radius:6px;margin-bottom:14px;font-size:13px}.blueprint-heading{display:flex;justify-content:space-between;gap:20px;margin-bottom:14px}.blueprint-heading h3{font-size:18px;color:#2d4b3c}.blueprint-heading p{color:#687e70;font-size:13px;margin-top:4px}.blueprint-heading>.text-link{flex-shrink:0}.blueprint-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:14px 0}.blueprint-layout{display:grid;grid-template-columns:minmax(460px,1.45fr) minmax(300px,1fr);gap:18px;align-items:start}.graph-panel{padding:0;overflow:auto}.inspector{position:sticky;top:12px;padding:20px}.inspector h3{font-size:18px;margin:12px 0}.eyebrow{color:#7b8c80;font-size:11px;letter-spacing:.4px}.inspector-lead{font-size:13px;color:#4f6b59}.inspector-fields{font-size:13px;line-height:1.85}.inspector-fields dt{color:#788b7d;margin:17px 0 4px;font-size:12px}.inspector-fields dd{white-space:pre-wrap;overflow-wrap:anywhere}.strategy-links{display:flex;flex-direction:column;gap:9px}.strategy-links>div{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.outgoing-link{display:block;width:100%;background:#f8faf9;border:1px solid #e3ebe6;border-radius:6px;padding:10px 12px;text-align:left;margin:8px 0;color:#365b44;font:inherit}.outgoing-link strong{display:block;font-size:13px}.outgoing-link span{display:block;color:#748479;font-size:12px;margin-top:3px}.connection-names{font-size:13px;color:#587461;padding:10px;background:#f1f7f3;border-radius:6px}.blueprint-save{position:sticky;bottom:0;z-index:2;display:flex;align-items:center;gap:10px;background:#fff;border:1px solid #dce6df;border-radius:8px;padding:12px 16px;box-shadow:0 -4px 18px #244b3410;margin-top:20px}.blueprint-save>span{flex:1;font-size:12px;color:#6f8175}.item-name{font-size:14px;font-weight:600}.strategy-table td:first-child{width:155px}.strategy-table td:nth-child(2){width:48%}.strategy-heading{display:flex;justify-content:space-between;gap:16px;align-items:center;margin:18px 0}.strategy-heading h3{font-size:22px;color:#264e37}.strategy-section .field-list{margin-bottom:0}.strategy-section .row-between h3{margin:0}.strategy-section .field-list dt{width:135px}.rule-intro{margin:18px 0}.rule-table td:first-child{width:20%}.rule-table td:nth-child(3){width:22%}.rule-table th:nth-child(4),.rule-table td:nth-child(4){width:76px;white-space:nowrap}.rule-table th:last-child,.rule-table td:last-child{width:106px;white-space:nowrap}.rule-table .row-actions .text-link{white-space:nowrap}.row-actions{display:flex;gap:12px}.system-boundaries ul{padding-left:22px;font-size:13px;line-height:2}.strategy-picker{display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;margin-top:14px}.strategy-picker legend,fieldset>legend{font-weight:600;color:#34553f;margin-top:12px}.remove-button{margin-right:auto;color:#a44b32}.scene-header{display:flex;justify-content:space-between;align-items:center;margin:18px 0}.scene-header h3{font-size:20px;color:#2d4b3c}.scene-choices{display:flex;gap:10px;margin:18px 0;flex-wrap:wrap}.scenario-context{padding:16px 20px}.scenario-context p{font-size:13px}.stage-strip{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0}.stage-strip>span{display:flex;align-items:center;gap:6px;background:#edf0ee;color:#7a8c80;padding:7px 10px;border:1px solid transparent;border-radius:6px;font-size:12px}.stage-strip small{font-size:11px}.stage-strip>span.visited{background:#edf5f0;color:#426c51}.stage-strip>span.active{background:#e0efe6;border-color:#438b61;color:#214c32;font-weight:600}.scene-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,1fr);gap:18px;align-items:start}.conversation h3{margin:14px 0 20px;font-size:18px}.speech{padding:14px 16px;border-radius:8px;margin:14px 0;font-size:14px;line-height:1.95}.speech>span{font-size:11px;color:#738879}.speech.student{background:#f2f5f8;margin-left:22px}.speech.tutor{background:#eef7f1;margin-right:22px}.speech p{margin:4px 0}.teaching-figure{margin:16px 0 0;padding:8px;background:#fff;border:1px solid #dbe8df;border-radius:6px}.teaching-figure svg{display:block;width:100%;max-width:420px;margin:auto}.teaching-figure text{font-size:13px;fill:#345a43}.teaching-figure figcaption{font-size:12px;color:#647c6c;text-align:center;line-height:1.6;margin-top:4px}.decision h3{margin-top:14px}.decision dd>.text-link{display:block;margin-top:5px}.response-branches{border-top:1px solid #e3ebe6;margin-top:24px}.branch-button{display:block;background:white;border:1px solid #d6e3d9;color:#345e43;border-radius:6px;padding:10px 14px;width:100%;text-align:left;font-size:13px;margin:8px 0}.branch-button:hover{background:#eff7f2}.scene-controls{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:24px}.path-summary{display:flex;align-items:flex-start;gap:16px;padding:12px 0;font-size:12px;color:#54715e;line-height:1.9}.path-summary>.muted{flex-shrink:0}.graph-toggle{margin:8px 0 16px}.scene-graph{margin-top:8px}@media(max-width:1180px){.blueprint-layout{grid-template-columns:minmax(440px,1.3fr) minmax(270px,1fr);gap:12px}.inspector{padding:15px}}@media(max-width:1250px){.blueprint-layout,.scene-layout{grid-template-columns:1fr}.inspector{position:static}.header-actions{flex-wrap:wrap}.blueprint-tools{flex-wrap:wrap}.graph-panel{max-width:740px}.scene-choices .btn{white-space:normal}}@media(max-width:700px){.page-header{flex-wrap:wrap}.strategy-picker{grid-template-columns:1fr}.blueprint-save{flex-wrap:wrap}.blueprint-save>span{flex-basis:100%}.strategy-heading{flex-wrap:wrap}.rule-table{min-width:650px}.table-card{overflow:auto}}

.strategy-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 18px;
  margin: 16px 0;
}
.strategy-filters label { min-width: 0; margin: 0; }
.strategy-filters label:first-child { flex: 1 1 220px; max-width: 400px; }
.strategy-filters label:nth-child(2) { flex: 0 1 160px; }
.strategy-filters .btn { margin-inline-start: auto; }
.teaching-list {
  overflow-x: auto;
  background: white;
  border: 1px solid #e1e8ed;
  border-radius: 10px;
}
.teaching-list th, .teaching-list td { padding: 12px 16px; }
.teaching-list tbody tr:last-child td { border-bottom: 0; }
.teaching-list tbody tr:hover { background: #f7faf8; }
.strategy-table { min-width: 600px; }
@media (max-width: 760px) {
  .strategy-filters label:first-child { flex-basis: 100%; max-width: none; }
}
</style>


