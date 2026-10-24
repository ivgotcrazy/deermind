<script setup lang="ts">
import { computed } from 'vue';
import { state, resolve } from '../workbench/store';
import { kinds, personalKinds, objectKey, type Kind, type ModelObject } from '../workbench/model';
import { route, go, setQuery, openObject } from '../workbench/navigation';
import { observedObjects, relatedActivities, recordSpaces, observationStatus } from '../workbench/observation';
import PagingBar from './PagingBar.vue';
const location=window.location;

// Restore the original ObjectBrowser hierarchy: space -> scope -> overview -> records.
const spaces=[
  {id:'Domain',name:'Domain Space',icon:'📐',description:'领域定义及其采用情况',global:true},
  {id:'Learning',name:'Learning Space',icon:'📚',description:'学生的课程范围、目标与采用版本',global:false},
  {id:'Evaluation',name:'Evaluation Space',icon:'📊',description:'证据、能力判断与目标评价',global:false},
  {id:'Interaction',name:'Interaction Space',icon:'💬',description:'观察、决策与实际帮助',global:false},
  {id:'Reasoning',name:'AI Reasoning',icon:'🧠',description:'候选、校验与提交的运行追溯',global:false},
  {id:'Evolution',name:'Evolution Space',icon:'🌱',description:'对象修改与历史演化记录',global:true},
];
const space=computed(()=>spaces.find(s=>s.id===route.tab)||spaces[0]!);
const scope=computed(()=>space.value.global?'':route.scope);
const chosen=computed(()=>state.spaces.find(s=>s.id===scope.value));
const invalidScope=computed(()=>!!scope.value&&!chosen.value);
const contexts=computed(()=>state.spaces.filter(s=>!scope.value||s.id===scope.value));
const students=computed(()=>[...new Map(state.spaces.map(s=>[s.studentId,s.studentName])).entries()]);
const activities=computed(()=>state.activities.filter(a=>!scope.value||a.ls===scope.value));
const objects=computed(()=>observedObjects(state,space.value.id,scope.value));
const records=computed(()=>objects.value.filter(o=>personalKinds.includes(o.kind)));
const types:Record<string,string[]>={Domain:['task','solution','kc'],Learning:['learning-space','material','chapter','mapping','target'],Evaluation:['evidence','belief','assessment','claim','evidence-rule','inference-rule'],Interaction:['observation','policy','action'],Reasoning:['candidate','validation','commit'],Evolution:['change','legacy-issue']};
const labels:Record<string,string>={...kinds,'learning-space':'学习空间',candidate:'Candidate 候选',validation:'Validation 校验',commit:'Commit 提交',change:'对象修改记录','legacy-issue':'历史演化事项'};
const type=computed(()=>types[space.value.id]!.includes(route.filter)?route.filter:types[space.value.id]![0]!);
const query=computed(()=>route.q.trim().toLowerCase());
function matches(...values:string[]){return !query.value||values.join(' ').toLowerCase().includes(query.value);}
const objectRows=computed(()=>objects.value.filter(o=>o.kind===type.value&&matches(o.id,o.name,o.model)));
const contextRows=computed(()=>contexts.value.filter(s=>matches(s.id,s.name,s.studentName)));
const activityRows=computed(()=>activities.value.filter(a=>matches(a.id,a.name,a.ls)));
const changes=computed(()=>state.changes.filter(c=>matches(c.ref,c.note)));
const issues=computed(()=>state.issues.filter(i=>i.dataMode==='demo'&&matches(i.id,i.title)));
const total=computed(()=>space.value.id==='Reasoning'?activityRows.value.length:type.value==='learning-space'?contextRows.value.length:type.value==='change'?changes.value.length:type.value==='legacy-issue'?issues.value.length:objectRows.value.length);
const page=computed(()=>Math.min(route.p,Math.max(1,Math.ceil(total.value/10))));
function slice<T>(rows:T[]){return rows.slice((page.value-1)*10,page.value*10);}
function count(kind:string){return objects.value.filter(o=>o.kind===kind).length;}
function typeCount(kind:string):number|undefined{return space.value.id==='Reasoning'?undefined:kind==='learning-space'?contexts.value.length:kind==='change'?state.changes.length:kind==='legacy-issue'?state.issues.filter(i=>i.dataMode==='demo').length:count(kind);}
const missingBindings=computed(()=>contexts.value.reduce((sum,s)=>sum+Object.entries(s.adopted).filter(([id,v])=>!resolve(`${id}@${v}`)).length,0));
const incompleteActivities=computed(()=>activities.value.filter(a=>a.objects.some(key=>!resolve(key))));
const metrics=computed(()=>{
  const metric=(label:string,value:number|string,note:string)=>({label,value,note});
  if(space.value.id==='Domain')return [metric('任务模板',count('task'),'按当前已保存身份去重'),metric('方法模板',count('solution'),'不把方法视作个人能力'),metric('知识成分',count('kc'),'不计算个人 KC 掌握率'),metric('采用这些定义的空间',state.spaces.filter(s=>Object.keys(s.adopted).some(id=>objects.value.some(o=>o.id===id))).length,'采用旧版本也计入；每空间一次')];
  if(space.value.id==='Learning')return [metric('学习空间',contexts.value.length,'按空间身份去重'),metric('学生',new Set(contexts.value.map(s=>s.studentId)).size,'只统计本范围学生'),metric('活动记录',activities.value.length,'已有活动，不代表已完成学习'),metric('采用引用缺失',missingBindings.value,'按空间与对象版本计数')];
  if(space.value.id==='Evaluation')return [metric('Evidence 记录',count('evidence'),'按对象与版本去重'),metric('Belief 版本记录',count('belief'),'含历史；不是已掌握人数'),metric('目标评价记录',count('assessment'),'不等于已达标人数'),metric('已退出当前使用',records.value.filter(o=>state.invalidated[objectKey(o)]).length,'保留记录供追溯')];
  if(space.value.id==='Interaction')return [metric('Observation 记录',count('observation'),'已记录对象版本，非候选生成量'),metric('决策记录',count('policy'),'不代表动作已执行'),metric('实际行动记录',count('action'),'具体展示结果在详情核对'),metric('关联活动',new Set(records.value.flatMap(o=>relatedActivities(state,o,scope.value).map(a=>a.id))).size,'按活动身份去重')];
  if(space.value.id==='Reasoning')return ['候选生成量','校验通过率','提交结果','调用耗时'].map(label=>metric(label,'—','原始运行日志未接入'));
  return [metric('对象修改记录',state.changes.length,'直接保存的修改记录'),metric('历史演化事项',state.issues.filter(i=>i.dataMode==='demo').length,'只读保留，不恢复审核流程')];
});
const distributions=computed(()=>{
  if(space.value.id==='Reasoning'||space.value.id==='Evolution')return [];
  if(space.value.id==='Learning')return [{title:'空间活动记录覆盖',items:[{label:'有活动记录',count:contexts.value.filter(s=>activities.value.some(a=>a.ls===s.id)).length},{label:'暂无活动记录',count:contexts.value.filter(s=>!activities.value.some(a=>a.ls===s.id)).length}]}];
  const personalSpace=['Evaluation','Interaction'].includes(space.value.id);
  const groups=[{title:personalSpace?'个人记录类型':'已保存定义类型',items:types[space.value.id]!.filter(k=>!personalSpace||personalKinds.includes(k as Kind)).map(k=>({label:labels[k]!,count:count(k)}))}];
  if(['Evaluation','Interaction'].includes(space.value.id))groups.push({title:'个人记录的使用标记',items:[{label:'未标记退出',count:records.value.filter(o=>!state.invalidated[objectKey(o)]).length},{label:'已退出当前使用',count:records.value.filter(o=>!!state.invalidated[objectKey(o)]).length}]});
  return groups;
});
function objectScope(o:ModelObject){const sources=relatedActivities(state,o,scope.value);return sources.length===1?sources[0]!.id:scope.value;}
function open(o:ModelObject){openObject(objectKey(o),objectScope(o));}
function sourceLabel(o:ModelObject){if(!personalKinds.includes(o.kind))return scope.value?'本空间采用的定义版本':'共享定义';const ids=recordSpaces(state,o);return ids.length?ids.map(id=>`${state.spaces.find(s=>s.id===id)?.studentName||'未知学生'} · ${id}`).join('；'):'未关联学习空间';}
function trace(id:string){go('activity',{id,scope:id,returnTo:location.hash});}
function openContext(id:string){go('observed-space',{id,returnTo:location.hash});}
function showIssue(id:string){go('observed-issue',{id,returnTo:location.hash});}
</script>

<template><div class="space-browser">
  <div class="space-content">
    <p class="scope-note">旧版历史观测 · <button class="text-link" @click="go('objects',{tab:space.id})">返回当前空间观测 →</button></p>
    <header class="space-header"><div><h2>{{space.name}}</h2><p>{{space.description}}</p></div><span v-if="space.global" class="badge">全局共享范围</span><label v-else class="scope-selector">观测范围<select aria-label="观测范围" :value="scope" @change="setQuery({scope:($event.target as HTMLSelectElement).value,q:'',p:1})"><option value="">全部 Learning Space（记录聚合）</option><option v-if="invalidScope" :value="scope">{{scope}} · 范围不存在</option><optgroup v-for="[id,name] in students" :key="id" :label="name"><option v-for="s in state.spaces.filter(s=>s.studentId===id)" :key="s.id" :value="s.id">{{s.name}} · {{s.id}}</option></optgroup></select></label></header>
    <p v-if="invalidScope" class="callout danger" role="alert">所选学习空间不存在，未改为查询全部学生。请重新选择观测范围。</p>
    <div v-if="chosen" class="ls-info-bar"><strong>{{chosen.studentName}}</strong><span>{{chosen.name}}</span><span>{{chosen.id}}</span><button class="text-link" @click="openContext(chosen.id)">查看范围与采用版本 →</button></div>
    <p v-if="!space.global && missingBindings" class="callout amber">本范围有 {{missingBindings}} 个采用引用无法解析，定义统计仅包含可解析部分。请在学习空间详情核对版本。</p>
    <div v-if="!space.global && incompleteActivities.length" class="callout amber" role="status"><p>{{incompleteActivities.length}} 条活动存在结果引用缺失。下方对象统计只包含可解析记录，不能据此断言没有产生结果。</p><button class="text-link" @click="go('trace-list',{filter:scope,returnTo:location.hash})">查看本范围活动 →</button></div>
    <p class="scope-note">{{space.global?'全局已保存示例数据':'当前范围内的全部已记录示例数据'}}；数量不表示学习质量或模型准确率。</p>
    <section class="metric-row" data-testid="observation-metrics" aria-label="范围统计"><div v-for="m in metrics" :key="m.label" class="metric-card"><span>{{m.label}}</span><strong>{{m.value}}</strong><small>{{m.note}}</small></div></section>
    <div class="dist-row"><section v-for="d in distributions" :key="d.title" class="dist-card"><h3>{{d.title}}</h3><div v-for="item in d.items" :key="item.label" class="dist-bar-item"><span>{{item.label}}</span><div class="dist-track"><div class="dist-fill" :style="{width:`${item.count/Math.max(1,...d.items.map(i=>i.count))*100}%`}"></div></div><strong>{{item.count}}</strong></div></section></div>
    <div class="object-tabs" aria-label="观测记录类型"><button v-for="kind in types[space.id]" :key="kind" :class="{active:type===kind}" @click="setQuery({filter:kind,q:'',p:1})">{{labels[kind]}}<span v-if="typeCount(kind)!==undefined" class="tab-count">{{typeCount(kind)}}</span></button></div>
    <template v-if="space.id==='Reasoning'"><section class="panel"><h3>{{labels[type]}}日志尚未接入</h3><p>当前数据仅保存活动事实与部分结果对象，没有逐次候选、校验和提交日志。无法计算通过率或耗时，也不能把已保存的 Observation 数量当成候选生成量。</p><p>下面可追溯已有活动及其引用的对象；活动详情中的演示瀑布图不属于性能测量。</p></section><h3 class="records-heading">可追溯的活动</h3></template>
    <p v-if="space.id==='Evolution'" class="callout">这里只查看已发生的修改与保留的历史事项。新增和修改在各自管理页面完成，MVP 不提供审核发布工作流。</p>
    <div class="toolbar"><label class="search-label">筛选记录<input aria-label="筛选观测记录" :value="route.q" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})" placeholder="名称或编号"/></label><span class="muted">搜索只筛选下方列表，上方统计保持当前观测范围。</span></div>
    <section class="table-card observation-table"><table class="data-table" v-if="space.id==='Reasoning'"><thead><tr><th>活动</th><th>学习空间</th><th>记录时间</th><th>追溯</th></tr></thead><tbody><tr v-for="a in slice(activityRows)" :key="a.id"><td>{{a.name}}<small>{{a.id}}</small></td><td>{{a.ls}}</td><td>{{a.at}}</td><td><button class="text-link" @click="trace(a.id)">查看活动记录</button></td></tr></tbody></table>
      <table v-else-if="type==='learning-space'" class="data-table"><thead><tr><th>学习空间</th><th>学生</th><th>已采用的教材与目标</th><th>活动记录</th></tr></thead><tbody><tr v-for="s in slice(contextRows)" :key="s.id"><td><button class="text-link" @click="openContext(s.id)">{{s.name}}</button><small>{{s.id}}</small></td><td>{{s.studentName}}</td><td>{{resolve(`${s.material}@${s.adopted[s.material]}`)?.name||'教材引用缺失'}}<small>{{resolve(`${s.target}@${s.adopted[s.target]}`)?.name||'目标引用缺失'}}</small></td><td>{{activities.filter(a=>a.ls===s.id).length}} 条</td></tr></tbody></table>
      <table v-else-if="type==='change'" class="data-table"><thead><tr><th>对象版本</th><th>修改说明</th><th>保存时间</th><th>追溯</th></tr></thead><tbody><tr v-for="c in slice(changes)" :key="c.ref"><td>{{c.ref}}</td><td>{{c.note}}</td><td>{{c.at}}</td><td><button class="text-link" @click="openObject(c.ref,'')">查看版本记录</button></td></tr></tbody></table>
      <table v-else-if="type==='legacy-issue'" class="data-table"><thead><tr><th>历史事项</th><th>原始结论</th><th>来源</th><th>追溯</th></tr></thead><tbody><tr v-for="i in slice(issues)" :key="i.id"><td>{{i.title}}<small>{{i.id}}</small></td><td>{{i.conclusion||'未形成结论'}}</td><td>{{i.origin}}</td><td><button class="text-link" @click="showIssue(i.id)">查看历史记录</button></td></tr></tbody></table>
      <table v-else class="data-table"><thead><tr><th>对象记录</th><th>{{space.global?'模型与采用':'归属与来源'}}</th><th>记录状态</th><th>记录时间</th><th>追溯</th></tr></thead><tbody><tr v-for="o in slice(objectRows)" :key="objectKey(o)"><td><button class="text-link" @click="open(o)">{{o.name}}</button><small>{{objectKey(o)}}</small></td><td>{{sourceLabel(o)}}<small>{{o.model}}</small><small v-if="space.global">{{state.spaces.filter(s=>s.adopted[o.id]!==undefined).length}} 个空间采用此对象</small></td><td><span class="badge" :class="{amber:state.invalidated[objectKey(o)]}">{{observationStatus(state,o)}}</span></td><td>{{o.at}}</td><td><button class="text-link" @click="open(o)">查看记录</button><small v-if="personalKinds.includes(o.kind)">{{relatedActivities(state,o,scope).length}} 条来源活动</small></td></tr></tbody></table>
      <p v-if="!total" class="empty">{{invalidScope?'当前范围无可查询记录。':'当前范围没有此类已记录数据。'}}<template v-if="space.id==='Evaluation'">没有记录不表示未掌握，也不能自动判定为运行失败；需要结合具体活动核对。</template></p>
    </section><PagingBar :total="total" :page="page"/>
    <details class="count-rules"><summary>统计口径与数据边界</summary><p>示例数据来自当前浏览器的已保存状态。共享定义按身份取最新已保存版本；选定 Learning Space 后只取它实际采用的定义版本。个人记录按对象与版本去重并保留历史，不平均四个能力方面、不计算 KC 掌握率。“未标记退出”不等于语义判断已验证正确。</p><p>列表、类型数量和图表使用同一空间范围；搜索只影响列表。运行日志未接入显示“—”，可查询集合为空才显示 0。当前累计范围不代表完整生产历史，定义记录时间也不代表个人能力的更新时间。</p><p v-if="missingBindings && !space.global">本范围有 {{missingBindings}} 个采用引用无法解析，相关定义统计可能不完整。可在学习空间详情检查准确引用。</p></details>
  </div>
</div></template>

<style scoped>
.space-browser{display:flex;min-height:100%;line-height:1.6}.space-content{flex:1;min-width:0;padding:24px}.space-header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:14px}.space-header h2{font-size:22px;color:#203b30}.space-header p{font-size:13px;color:#6b7d72;margin-top:5px}.scope-selector{margin:0;min-width:260px;max-width:380px}.ls-info-bar{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 16px;background:#e8f5ee;border:1px solid #b8dfc8;border-radius:8px;font-size:12px;margin:16px 0}.scope-note{font-size:12px;color:#74847b;margin:14px 0}.metric-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.metric-card{padding:14px 16px;font-size:12px}.metric-card strong{font-size:26px}.dist-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.dist-card{background:white;border:1px solid #e1e8ed;border-radius:10px;padding:16px}.dist-card h3{font-size:13px;margin-bottom:12px;color:#294b37}.dist-bar-item{display:flex;align-items:center;gap:10px;font-size:12px;margin:9px 0}.dist-bar-item>span{width:110px;flex-shrink:0;color:#6a7e70}.dist-bar-item>strong{width:28px;text-align:right;color:#31543f}.dist-track{flex:1;height:12px;background:#eff4f0;border-radius:3px}.dist-fill{height:100%;background:#52a67c;border-radius:3px}.object-tabs{display:flex;flex-wrap:wrap;border-bottom:2px solid #e1e8ed;margin:22px 0 16px;gap:3px}.object-tabs button{display:flex;gap:8px;align-items:center;padding:8px 12px;background:none;border:0;border-bottom:2px solid transparent;margin-bottom:-2px;color:#647b6b;font-size:12px}.object-tabs button.active{color:#1b4332;border-bottom-color:#2d6a4f;font-weight:600}.tab-count{background:#edf3ef;padding:0 6px;border-radius:8px}.observation-table{overflow-x:auto}.observation-table table{min-width:670px}.records-heading{font-size:15px;color:#31543f}.count-rules{margin-bottom:20px;color:#6f8175;font-size:12px}.count-rules p{margin:12px 0}@media(max-width:1200px){.space-content{padding:18px}.metric-row{grid-template-columns:repeat(2,minmax(0,1fr))}.space-header{flex-wrap:wrap}.scope-selector{max-width:100%;min-width:240px}}@media(max-width:950px){.dist-row{grid-template-columns:1fr}}
</style>
