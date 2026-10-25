<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { route, go, setQuery, back } from '../workbench/navigation';
import { domainMock } from '../workbench/domain-mock';
import { evaluationMock, blankClaim, saveClaim, effectNames, inferenceFields, type EvaluationClaim, type ClaimAspect, type ClaimRule } from '../workbench/evaluation-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';

const location=window.location;
const copy=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
const tabs=[{id:'definition',name:'基本定义'},{id:'aspects',name:'评价方面'},{id:'evidence',name:'证据解释'},{id:'inference',name:'状态推断'}];
const tab=computed(()=>tabs.some(t=>t.id===route.tab)?route.tab:'definition');
const claim=computed(()=>evaluationMock.claims.find(c=>c.id===route.id));
const taskOf=(c:EvaluationClaim)=>domainMock.tasks.find(t=>t.id===c.taskId&&t.domainId===c.domainId);
const task=computed(()=>claim.value?taskOf(claim.value):undefined);
const domainName=(id:string)=>domainMock.domains.find(d=>d.id===id)?.name||'领域不存在';
const methodName=(id:string)=>domainMock.methods.find(m=>m.id===id)?.name||'方法不存在';
const aspectName=(id:string)=>claim.value?.aspects.find(a=>a.id===id)?.name||'方面未定义';
const aspectApplicable=(id:string)=>claim.value?.aspects.find(a=>a.id===id)?.applicable;
const completeAspect=(a:ClaimAspect)=>a.applicable?!!(a.criterion.trim()&&a.evidence.trim()&&(!a.custom||a.reason.trim())):!!a.reason.trim();
const rows=computed(()=>evaluationMock.claims.filter(c=>(!route.domain||c.domainId===route.domain)&&[c.id,c.name,c.description,taskOf(c)?.name||''].join(' ').toLowerCase().includes(route.q.trim().toLowerCase())));
const pages=computed(()=>Math.max(1,Math.ceil(rows.value.length/10)));
const page=computed(()=>Math.min(route.p,pages.value));
const ruleFilter=ref('');
const rules=computed(()=>claim.value?.rules.filter(r=>!ruleFilter.value||r.aspectId===ruleFilter.value)||[]);
const methods=computed(()=>claim.value?.methods.map(id=>domainMock.methods.find(m=>m.id===id)).filter(m=>!!m)||[]);
const missingMethods=computed(()=>claim.value?.methods.filter(id=>!task.value?.methods.includes(id))||[]);
const notice=ref('');
type EditorKind='new'|'basic'|'methods'|'aspect'|'rule'|'inference';
const editor=ref<EditorKind|null>(null),draft=ref<EvaluationClaim>(blankClaim());
const aspectDraft=ref<ClaimAspect>({id:'',name:'',applicable:true,criterion:'',evidence:'',reason:''});
const ruleDraft=ref<ClaimRule>({id:'',aspectId:'',observation:'',effect:'support',condition:'',meaning:''});
const error=ref(''),errorNode=ref<HTMLElement>(),deleting=ref(false);
const editingTask=computed(()=>domainMock.tasks.find(t=>t.id===draft.value.taskId&&t.domainId===draft.value.domainId));
const taskChoices=computed(()=>domainMock.tasks.filter(t=>t.domainId===draft.value.domainId));
const methodChoices=computed(()=>domainMock.methods.filter(m=>m.domainId===draft.value.domainId&&editingTask.value?.methods.includes(m.id)));
const title=computed(()=>editor.value==='new'?'新建 Claim':editor.value==='basic'?'编辑基本定义':editor.value==='methods'?'编辑方法与支持边界':editor.value==='aspect'?(claim.value?.aspects.some(a=>a.id===aspectDraft.value.id)?'编辑评价方面':'添加评价方面'):editor.value==='rule'?(claim.value?.rules.some(r=>r.id===ruleDraft.value.id)?'编辑证据规则':'添加证据规则'):'编辑状态推断规则');
watch(()=>route.id,()=>{editor.value=null;notice.value='';ruleFilter.value='';});
function openClaim(id:string){go('evaluation',{id,tab:'definition',returnTo:location.hash});}
function openTask(){if(task.value)go('domain',{domain:task.value.domainId,filter:'task',id:task.value.id,returnTo:location.hash});}
function openMethod(id:string){if(claim.value)go('domain',{domain:claim.value.domainId,filter:'solution',id,returnTo:location.hash});}
function edit(kind:EditorKind){draft.value=claim.value?copy(claim.value):blankClaim();error.value='';deleting.value=false;editor.value=kind;}
function create(){edit('new');draft.value=blankClaim();draft.value.domainId=route.domain||(domainMock.domains.length===1?domainMock.domains[0]!.id:'');}
function selectTask(){draft.value.methods=[];if(!draft.value.name&&editingTask.value)draft.value.name=editingTask.value.name+'的能力评价';}
function editAspect(value?:ClaimAspect){edit('aspect');aspectDraft.value=value?copy(value):{id:'aspect-'+crypto.randomUUID().slice(0,8),name:'',applicable:true,criterion:'',evidence:'',reason:'',custom:true};}
function editRule(value?:ClaimRule){edit('rule');ruleDraft.value=value?copy(value):{id:'ER-'+crypto.randomUUID().slice(0,8).toUpperCase(),aspectId:ruleFilter.value&&aspectApplicable(ruleFilter.value)?ruleFilter.value:claim.value?.aspects.find(a=>a.applicable)?.id||'',observation:'',effect:'support',condition:'',meaning:''};}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}
function finish(change:string){
  const isNew=editor.value==='new';saveClaim(draft.value,change);editor.value=null;
  if(isNew)go('evaluation',{id:draft.value.id,tab:'definition',returnTo:location.hash});
  nextTick(()=>{notice.value=isNew?'Claim 已创建，可以继续补充评价方面与规则。':'已保存'+change.replace(/^修改/,'')+'。';});
}
function save(){
  error.value='';
  if(editor.value==='new'||editor.value==='basic'){
    if(!draft.value.name.trim())return fail('请填写 Claim 名称。');
    if(!editingTask.value)return fail('请选择领域中的一个任务模板。');
    draft.value.name=draft.value.name.trim();return finish(editor.value==='new'?'创建 Claim':'修改基本定义');
  }
  if(editor.value==='methods'){
    if(draft.value.methods.some(id=>!methodChoices.value.some(m=>m.id===id)))return fail('有方法已不属于该任务，请移除后再保存。');
    return finish('修改方法与支持边界');
  }
  if(editor.value==='aspect'){
    const a=aspectDraft.value;
    if(!a.name.trim())return fail('请填写评价方面的名称。');
    if(draft.value.aspects.some(x=>x.id!==a.id&&x.name.trim()===a.name.trim()))return fail('已有同名评价方面，请使用不同名称。');
    if(a.applicable&&(!a.criterion.trim()||!a.evidence.trim()))return fail('请填写判断标准和证据要求。');
    if((!a.applicable||a.custom)&&!a.reason.trim())return fail(a.applicable?'请说明增加这一评价方面的依据。':'请说明该方面不适用于此 Claim 的依据；尚未检测不是裁剪理由。');
    if(a.applicable&&!a.custom)a.reason='';
    const index=draft.value.aspects.findIndex(x=>x.id===a.id);
    if(index<0)draft.value.aspects.push(copy(a));else draft.value.aspects[index]=copy(a);
    return finish('修改评价方面：'+a.name);
  }
  if(editor.value==='rule'){
    const r=ruleDraft.value;
    if(!draft.value.aspects.some(a=>a.id===r.aspectId&&a.applicable))return fail('请选择一个适用的评价方面。');
    if(!r.observation.trim()||!r.condition.trim()||!r.meaning.trim())return fail('请填写观察类型、适用条件和证据解释。');
    const index=draft.value.rules.findIndex(x=>x.id===r.id);
    if(index<0)draft.value.rules.push(copy(r));else draft.value.rules[index]=copy(r);
    return finish('修改证据规则');
  }
  if(editor.value==='inference'){
    if(Object.values(draft.value.inference).some(v=>!v.trim()))return fail('请补充完整的状态推断规则。');
    finish('修改状态推断规则');
  }
}
function removeRule(){draft.value.rules=draft.value.rules.filter(r=>r.id!==ruleDraft.value.id);finish('删除证据规则');}
function tabKey(event:KeyboardEvent,index:number){const next=event.key==='ArrowRight'?(index+1)%tabs.length:event.key==='ArrowLeft'?(index+tabs.length-1)%tabs.length:-1;if(next<0)return;event.preventDefault();setQuery({tab:tabs[next]!.id});document.getElementById('claim-tab-'+tabs[next]!.id)?.focus();}
</script>

<template><div class="wb-page evaluation-workspace">
  <template v-if="!route.id">
    <header class="page-header"><div><button v-if="route.returnTo.startsWith('#/targets?')" class="text-link" @click="back('targets')">← 返回学习目标</button><button v-if="route.returnTo.startsWith('#/observed-')" class="text-link" @click="back('objects')">← 返回观测来源</button><h2>评估模型管理</h2><p class="page-desc">围绕任务定义能力要求，维护评价方面、证据解释和状态推断。</p></div><button class="btn primary" @click="create">新建 Claim</button></header>
    <div class="toolbar claim-toolbar"><label class="search-label">搜索 Claim 或任务<input :value="route.q" type="search" placeholder="名称、任务或编号" @input="setQuery({q:($event.target as HTMLInputElement).value,p:1})"/></label><label>领域<select :value="route.domain" @change="setQuery({domain:($event.target as HTMLSelectElement).value,p:1})"><option value="">全部领域</option><option v-for="d in domainMock.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><span class="muted">{{rows.length}} 项 Claim</span></div>
    <section class="table-card"><table class="data-table claim-list"><thead><tr><th>Claim</th><th>关联任务</th><th>评价方面</th><th>最近修改</th><th></th></tr></thead><tbody><tr v-for="c in rows.slice((page-1)*10,page*10)" :key="c.id"><td><button class="text-link item-name" @click="openClaim(c.id)">{{c.name}}</button><small>{{c.description||'尚未填写说明'}}</small><small class="mono">{{c.id}}</small></td><td>{{taskOf(c)?.name||'任务不存在'}}<small>{{domainName(c.domainId)}}</small></td><td><div class="aspect-tags"><span v-for="a in c.aspects" :key="a.id" class="aspect-tag" :class="{inactive:!a.applicable}" :title="a.applicable?a.criterion:'不适用：'+a.reason">{{a.name}}{{a.applicable?'':' · 不适用'}}</span></div><small v-if="c.aspects.some(a=>!completeAspect(a))">{{c.aspects.filter(a=>!completeAspect(a)).length}} 个方面待补充</small></td><td>v{{c.version}}<small>{{c.updatedAt}}</small></td><td><button class="text-link" :aria-label="'查看'+c.name" @click="openClaim(c.id)">查看 →</button></td></tr></tbody></table><div v-if="!rows.length" class="empty">{{route.q?'没有匹配的 Claim，请调整搜索。':'此领域还没有 Claim，可先选择任务并新建。'}}</div></section>
    <div v-if="pages>1" class="pagination"><button class="btn" :disabled="page<=1" @click="setQuery({p:page-1})">上一页</button><span>{{page}} / {{pages}}</span><button class="btn" :disabled="page>=pages" @click="setQuery({p:page+1})">下一页</button></div>
  </template>
  <template v-else-if="claim">
    <button class="text-link return-link" @click="back('evaluation')">← {{route.returnTo.startsWith('#/students')?'返回学生状态':route.returnTo.startsWith('#/objects')?'返回空间观测':route.returnTo.startsWith('#/activity?')?'返回交互审查':route.returnTo.startsWith('#/textbooks?')?'返回教材章节':route.returnTo.startsWith('#/targets?')?'返回学习目标':route.returnTo.startsWith('#/learning-spaces?')?'返回学习空间':'返回 Claim 列表'}}</button>
    <header class="page-header claim-header"><div><div class="muted">{{domainName(claim.domainId)}} · Task Claim · v{{claim.version}}</div><h2>{{claim.name}}</h2><p class="page-desc">{{claim.description||'尚未填写说明'}}</p><div class="task-binding"><span>关联任务</span><button v-if="task" class="text-link" @click="openTask">{{task.name}} ↗</button><span v-else class="badge amber">任务不存在</span></div></div></header>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <div class="claim-tabs" role="tablist" aria-label="Claim 详情"><button v-for="(t,i) in tabs" :id="'claim-tab-'+t.id" :key="t.id" role="tab" :aria-selected="tab===t.id" :aria-controls="'claim-panel-'+t.id" :tabindex="tab===t.id?0:-1" :class="{active:tab===t.id}" @click="setQuery({tab:t.id})" @keydown="tabKey($event,i)">{{t.name}}</button></div>
    <div :id="'claim-panel-'+tab" role="tabpanel" :aria-labelledby="'claim-tab-'+tab">
      <template v-if="tab==='definition'">
        <section class="panel"><div class="section-heading"><h3>评价范围与要求</h3><button class="btn" @click="edit('basic')">编辑基本定义</button></div><dl class="field-list"><dt>任务范围</dt><dd>{{claim.scope||'待补充'}}</dd><dt>学习者承担的工作</dt><dd>{{claim.responsibility||'待补充'}}</dd><dt>适用条件</dt><dd>{{claim.conditions||'待补充'}}</dd><dt>质量要求</dt><dd>{{claim.quality||'待补充'}}</dd></dl></section>
        <section class="panel"><div class="section-heading"><h3>方法与支持边界</h3><button class="btn" @click="edit('methods')">编辑方法与支持边界</button></div><p v-if="missingMethods.length" class="callout amber">关联任务的方法已变化，请重新核对本 Claim 选用的方法。</p><p class="method-policy">{{claim.methodMode==='any'?'所选方法任选一种':'要求覆盖全部所选方法'}}</p><table v-if="methods.length" class="data-table"><thead><tr><th>方法</th><th>适用条件</th></tr></thead><tbody><tr v-for="m in methods" :key="m.id"><td><button class="text-link" @click="openMethod(m.id)">{{m.name}} ↗</button></td><td>{{m.conditions}}</td></tr></tbody></table><p v-else class="muted">尚未选择评价所允许的方法，可从当前 Task 关联的方法中选择。</p><dl class="field-list"><dt>方法评价要求</dt><dd>{{claim.methodNote||'待补充'}}</dd><dt>允许与不允许的帮助</dt><dd>{{claim.support||'待补充'}}</dd></dl></section>
      </template>
      <template v-else-if="tab==='aspects'">
        <div class="section-heading"><p class="muted">各方面分别定义标准和证据。裁剪或扩展需说明依据；未检测不等于不适用。</p><button class="btn" @click="editAspect()">添加评价方面</button></div>
        <section class="table-card"><table class="data-table aspect-table"><thead><tr><th>评价方面</th><th>判断标准</th><th>证据要求</th><th></th></tr></thead><tbody><tr v-for="a in claim.aspects" :key="a.id"><td><strong>{{a.name}}</strong><small>{{a.applicable?(completeAspect(a)?'适用':'待补充'):'不适用'}}</small><small v-if="a.custom">扩展方面</small></td><td><p class="multiline">{{a.criterion||'待定义'}}</p><p v-if="a.reason" class="reason"><b>{{a.applicable?'扩展依据':'裁剪依据'}}：</b>{{a.reason}}</p></td><td class="multiline">{{a.evidence||'待定义'}}</td><td><button class="btn" :aria-label="'编辑'+a.name" @click="editAspect(a)">编辑</button></td></tr></tbody></table></section>
      </template>
      <template v-else-if="tab==='evidence'">
        <div class="section-heading"><p class="muted">说明什么表现，在什么条件下，对哪个评价方面形成支持、反证或不具诊断性的记录。</p><button class="btn" :disabled="!claim.aspects.some(a=>a.applicable)" @click="editRule()">添加证据规则</button></div>
        <div class="toolbar rule-toolbar"><label>评价方面<select v-model="ruleFilter"><option value="">全部方面</option><option v-for="a in claim.aspects" :key="a.id" :value="a.id">{{a.name}}{{a.applicable?'':'（不适用）'}}</option></select></label><span class="muted">{{rules.length}} 条规则</span></div>
        <section class="table-card"><table class="data-table rule-table"><thead><tr><th>评价方面 / 观察</th><th>适用条件</th><th>证据意义</th><th></th></tr></thead><tbody><tr v-for="r in rules" :key="r.id"><td><strong>{{aspectName(r.aspectId)}}</strong><small>{{r.observation}}</small><small v-if="!aspectApplicable(r.aspectId)" class="inactive-rule">此方面不适用，规则保留但不参与解释</small></td><td class="multiline">{{r.condition}}</td><td><span class="badge" :class="r.effect==='support'?'green':r.effect==='counter'?'amber':''">{{effectNames[r.effect]}}</span><p>{{r.meaning}}</p></td><td><button class="btn" :aria-label="'编辑规则'+r.id" @click="editRule(r)">编辑</button></td></tr></tbody></table><div v-if="!rules.length" class="empty">{{ruleFilter?'该方面尚无证据规则。':'尚未定义证据规则。'}}</div></section>
      </template>
      <template v-else>
        <section class="panel"><div class="section-heading"><div><h3>从证据形成 Belief</h3><p class="muted">输入：该 Claim 的适用证据、既有认识、实际帮助、时间及共同来源。</p></div><button class="btn" @click="edit('inference')">编辑推断规则</button></div><dl class="field-list"><template v-for="(label,key) in inferenceFields" :key="key"><dt>{{label}}</dt><dd>{{claim.inference[key]||'待补充'}}</dd></template></dl><p class="muted">此处维护评价定义，不显示或修改任何学生的能力状态；mock 不执行推断。</p></section>
      </template>
    </div>
    <details class="history"><summary>修改记录 · {{claim.history.length}} 条</summary><p class="muted">本次预览中的保存记录，刷新后恢复示例；未应用到学习空间或真实评价。</p><div v-for="h in claim.history" :key="h.version" class="list-row"><span>v{{h.version}} · {{h.change}}</span><span>{{h.at}}</span></div></details>
  </template>
  <section v-else class="panel"><h2>未找到这个 Claim</h2><p>请从列表重新选择。刷新会恢复初始 mock 数据。</p><button class="btn" @click="go('evaluation')">返回 Claim 列表</button></section>

  <WorkbenchDialog v-if="editor" :title="title" wide @close="editor=null"><form @submit.prevent="save" novalidate>
    <p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger form-error">{{error}}</p>
    <template v-if="editor==='new'||editor==='basic'">
      <div v-if="editor==='new'" class="field-pair"><label>领域<select v-model="draft.domainId" @change="draft.taskId='';draft.methods=[]"><option value="">请选择领域</option><option v-for="d in domainMock.domains" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>关联 Task<select v-model="draft.taskId" @change="selectTask"><option value="">请选择任务模板</option><option v-for="t in taskChoices" :key="t.id" :value="t.id">{{t.name}}</option></select></label></div>
      <p v-else class="muted">关联任务：{{editingTask?.name||'任务不存在'}}。本次编辑不改变所评价的任务。</p>
      <p v-if="editor==='new'&&!taskChoices.length" class="callout">当前领域尚无任务模板，请先在领域管理中创建。</p>
      <label>Claim 名称<input v-model="draft.name" maxlength="160" placeholder="例如：增加后的数量求解"/></label><label>说明<textarea v-model="draft.description" rows="2" placeholder="这项评价关注什么"/></label>
      <div class="field-pair"><label>任务范围<textarea v-model="draft.scope" placeholder="在任务模板中的哪些范围内评价"/></label><label>学习者承担的工作<textarea v-model="draft.responsibility" placeholder="需要由学生自己完成哪些工作"/></label></div>
      <div class="field-pair"><label>适用条件<textarea v-model="draft.conditions"/></label><label>质量要求<textarea v-model="draft.quality"/></label></div>
      <p v-if="editor==='new'" class="muted">创建后可继续设置方法、四个默认评价方面和规则；未填写内容会标为待补充。</p>
    </template>
    <template v-else-if="editor==='methods'">
      <p class="muted">仅选择此 Task 直接关联的方法；子方法和 KC 仍在领域定义中查看。</p><div class="method-picker"><label v-for="m in methodChoices" :key="m.id" class="check-label"><input v-model="draft.methods" type="checkbox" :value="m.id"/>{{m.name}}</label><label v-for="id in draft.methods.filter(id=>!methodChoices.some(m=>m.id===id))" :key="id" class="check-label"><input v-model="draft.methods" type="checkbox" :value="id"/>{{methodName(id)}}（已不属于此任务，请取消选择）</label><p v-if="!methodChoices.length" class="muted">此任务尚未关联方法，可先保存其他内容。</p></div>
      <label>方法覆盖要求<select v-model="draft.methodMode"><option value="any">任选一种所选方法</option><option value="all">需要覆盖全部所选方法</option></select></label><p class="muted">{{draft.methodMode==='any'?'一种方法成功，不代表其他方法也已掌握。':'覆盖全部方法需要各方法的相应表现，不能由一次作答替代。'}}</p>
      <label>方法评价要求<textarea v-model="draft.methodNote" rows="3"/></label><label>允许与不允许的帮助<textarea v-model="draft.support" rows="3"/></label>
    </template>
    <template v-else-if="editor==='aspect'">
      <label>方面名称<input v-model="aspectDraft.name" maxlength="80" :readonly="!aspectDraft.custom"/></label><label class="check-label"><input v-model="aspectDraft.applicable" type="checkbox"/>纳入此 Claim 的评价</label><p class="muted">没有证据或尚未检测，不是把这个方面设为“不适用”的理由。</p>
      <label>判断标准<textarea v-model="aspectDraft.criterion" rows="3" placeholder="满足什么条件，才支持这一方面"/></label><label>证据要求<textarea v-model="aspectDraft.evidence" rows="3" placeholder="需要看到哪些表现，保留什么帮助或变化记录"/></label>
      <label v-if="!aspectDraft.applicable||aspectDraft.custom">{{aspectDraft.applicable?'扩展依据':'裁剪依据'}}<textarea v-model="aspectDraft.reason" rows="2"/></label>
    </template>
    <template v-else-if="editor==='rule'">
      <div class="field-pair"><label>评价方面<select v-model="ruleDraft.aspectId"><option value="">请选择</option><option v-for="a in draft.aspects" :key="a.id" :value="a.id" :disabled="!a.applicable">{{a.name}}{{a.applicable?'':'（不适用）'}}</option></select></label><label>证据意义<select v-model="ruleDraft.effect"><option v-for="(name,key) in effectNames" :key="key" :value="key">{{name}}</option></select></label></div>
      <label>观察类型<input v-model="ruleDraft.observation" placeholder="例如：求助后的作答、解释或辨析"/></label><label>适用条件<textarea v-model="ruleDraft.condition" rows="3" placeholder="何种范围、实际帮助和表现下适用"/></label><label>证据解释<textarea v-model="ruleDraft.meaning" rows="3" placeholder="支持或反对什么，以及不能据此推断什么"/></label>
      <p v-if="deleting" class="callout amber">确认删除这条规则？只影响本次 mock 中的 Claim。<button type="button" class="text-link" @click="removeRule">确认删除</button><button type="button" class="text-link cancel-delete" @click="deleting=false">保留规则</button></p>
    </template>
    <template v-else><p class="muted">配置本 Claim 的证据综合方式，不直接填写学生的掌握结果。</p><label v-for="(label,key) in inferenceFields" :key="key">{{label}}<textarea v-model="draft.inference[key]" rows="3"/></label></template>
    <div class="dialog-footer editor-footer"><button v-if="editor==='rule'&&claim?.rules.some(r=>r.id===ruleDraft.id)" type="button" class="text-link delete-rule" @click="deleting=true">删除规则</button><div class="button-row"><button type="button" class="btn" @click="editor=null">取消</button><button class="btn primary" type="submit">{{editor==='new'?'创建 Claim':'保存'}}</button></div></div>
  </form></WorkbenchDialog>
</div></template>

<style scoped>
.evaluation-workspace{max-width:1440px}.claim-toolbar{align-items:end;margin-bottom:22px}.claim-toolbar>span{margin-left:auto;padding-bottom:9px}.claim-list th:first-child{width:25%}.claim-list th:nth-child(2){width:26%}.claim-list th:nth-child(3){width:25%}.claim-list th:last-child{width:74px}.item-name{font-size:15px;font-weight:600}.aspect-tags{display:flex;gap:6px;flex-wrap:wrap}.aspect-tag{font-size:11px;padding:2px 7px;border:1px solid #dfe9e2;border-radius:4px;background:#f0f6f2;color:#456c55;white-space:nowrap}.aspect-tag.inactive{background:#f4f5f6;color:#88948c;border-color:#e7eae8}.return-link{margin-bottom:16px}.claim-header{margin-bottom:12px}.claim-header h2{margin:6px 0;font-size:24px}.task-binding{display:flex;gap:12px;align-items:baseline;margin-top:12px;font-size:13px}.task-binding>span{color:#788b7e;flex-shrink:0}.claim-tabs{display:flex;gap:28px;border-bottom:1px solid #dbe5df;margin:22px 0}.claim-tabs button{padding:10px 2px 13px;border:0;border-bottom:3px solid transparent;background:none;color:#6b7e72;font-size:14px}.claim-tabs button.active{color:#286246;font-weight:600;border-bottom-color:#2d6a4f}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:22px;margin-bottom:14px}.section-heading h3,.section-heading p{margin:0}.section-heading>.btn{flex-shrink:0}.section-heading div>p{margin-top:6px}.field-list{margin-bottom:0;grid-template-columns:155px minmax(0,1fr)}.method-policy{font-size:13px;font-weight:600;color:#456552;margin-bottom:12px!important}.multiline{white-space:pre-line}.aspect-table th:first-child{width:17%}.aspect-table th:nth-child(2){width:39%}.aspect-table th:last-child,.rule-table th:last-child{width:76px}.data-table p{margin:0}.data-table td{line-height:1.85}.data-table .reason{margin-top:12px;font-size:12px;color:#7c705b}.rule-table th:first-child{width:21%}.rule-table th:nth-child(2){width:37%}.rule-table .badge{margin-bottom:8px}.rule-toolbar{margin-top:0}.rule-toolbar>span{padding-bottom:10px}.inactive-rule{color:#937b49!important}.history{margin-top:28px}.saved-note{font-size:13px;color:#2d6a4f;margin:10px 0}.field-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}.method-picker{padding:10px 16px;border:1px solid #e1e8e3;border-radius:6px}.method-picker label{margin:8px 0}.form-error{scroll-margin:18px}.editor-footer{display:flex;justify-content:flex-end;gap:16px;align-items:center}.editor-footer .button-row{margin:0}.delete-rule{margin-right:auto;color:#9b533d}.cancel-delete{margin-left:16px}.claim-toolbar select{min-width:150px}@media(max-width:1050px){.claim-list th:first-child{width:25%}.claim-list th:nth-child(2){width:25%}.claim-list th:nth-child(3){width:24%}.aspect-tag{white-space:normal}.field-list{grid-template-columns:125px minmax(0,1fr)}}@media(max-width:750px){.field-pair{grid-template-columns:1fr;gap:0}.claim-tabs{gap:16px}.section-heading{gap:12px}.claim-list{min-width:640px}.table-card{overflow:auto}}
</style>
