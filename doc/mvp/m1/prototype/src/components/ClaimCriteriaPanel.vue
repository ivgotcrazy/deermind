<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import AspectRulesPanel from './AspectRulesPanel.vue';
import { clone } from '../model/domain';
import {
  completeCriterion, directMethods, evaluationData, executionCriteria,
  methodName, methodCriteria, newCriterion, saveDefinition, type Claim, type Criterion, type MethodExecution,
} from '../model/evaluation';

const props=defineProps<{claim:Claim;requestedMethod:string;blocked:boolean}>();
const emit=defineEmits<{saved:[message:string];selectMethod:[methodId:string]}>();
const methods=computed(()=>directMethods(props.claim));
const selectedId=computed(()=>{
  if(!props.requestedMethod)return methods.value[0]||'';
  return methods.value.includes(props.requestedMethod)?props.requestedMethod:'';
});
const selected=computed(()=>selectedId.value?methodCriteria(props.claim,selectedId.value):undefined);
const checks=computed(()=>executionCriteria(props.claim,selectedId.value));
const tabId=(key:string)=>'method-tab-'+props.claim.id+'-'+key;
const panelId=computed(()=>'method-panel-'+props.claim.id);
function navigateTab(event:KeyboardEvent,key:string){
  const ids=methods.value, index=ids.indexOf(key);
  let next:string;
  switch(event.key){
    case 'ArrowRight': next=ids[(index+1)%ids.length];break;
    case 'ArrowLeft': next=ids[(index+ids.length-1)%ids.length];break;
    case 'Home': next=ids[0];break;
    case 'End': next=ids[ids.length-1];break;
    default:return;
  }
  event.preventDefault();
  document.getElementById(tabId(next))?.focus();
  emit('selectMethod',next);
}
const mode=ref<''|'criterion'|'remove'|'binding'>('');
const item=ref<Criterion>(newCriterion()), binding=ref<MethodExecution>();
const returnToRule=ref(false), error=ref('');
watch(selectedId,()=>{
  mode.value='';
  binding.value=undefined;
  returnToRule.value=false;
});
const usage=(id:string)=>props.claim.executions.filter(r=>r.criteria.includes(id));
function editCriterion(existing?:Criterion,fromRule=false){
  item.value=existing?clone(existing):newCriterion();
  returnToRule.value=fromRule;
  error.value='';
  mode.value='criterion';
}
function editBinding(methodId:string){
  binding.value=clone(props.claim.executions.find(e=>e.methodId===methodId)??{methodId,criteria:[]});
  error.value='';
  mode.value='binding';
}
function close(){
  mode.value=mode.value==='criterion'&&returnToRule.value?'binding':'';
  returnToRule.value=false;
  error.value='';
}
function commit(next:Claim,change:string){
  if(props.blocked)return false;
  const result=saveDefinition(evaluationData.claims,next,change);
  if(result)emit('saved',change+'，已保存。');
  return !!result;
}
function saveCriterion(){
  const entry=clone(item.value);
  if(!entry.name.trim()||!entry.met.trim()){error.value='请填写名称和满足判据的表现。';return;}
  if(props.claim.criteria.some(c=>c.id!==entry.id&&c.name.trim()===entry.name.trim())){error.value='本 Claim 已有同名判据。';return;}
  const next=clone(props.claim);
  const index=next.criteria.findIndex(c=>c.id===entry.id);
  if(index<0)next.criteria.push(entry);else next.criteria[index]=entry;
  if(!commit(next,(index<0?'创建':'修改')+'判据「'+entry.name+'」'))return;
  if(returnToRule.value&&binding.value&&!binding.value.criteria.includes(entry.id))binding.value.criteria.push(entry.id);
  close();
}
function saveBinding(){
  if(!binding.value||binding.value.methodId!==selectedId.value)return;
  const selected=clone(binding.value);
  if(selected.criteria.some(id=>!props.claim.criteria.some(c=>c.id===id))){
    error.value='部分所选执行判据已不存在，请重新选择。';return;
  }
  const next=clone(props.claim);
  next.executions=next.executions.filter(e=>e.methodId!==selected.methodId);
  if(selected.criteria.length)next.executions.push(selected);
  if(commit(next,'修改「'+methodName(selected.methodId)+'」的本方法执行判据'))close();
}
function removeCriterion(){
  if(usage(item.value.id).length){error.value='请先解除这条判据的引用。';return;}
  const next=clone(props.claim);
  next.criteria=next.criteria.filter(c=>c.id!==item.value.id);
  if(commit(next,'删除判据「'+item.value.name+'」'))close();
}
</script>

<template>
  <section class="method-detail" aria-label="当前方法详情" :data-method="selectedId">
    <div v-if="methods.length" class="panel method-selector">
      <div class="method-bar"><span>当前方法</span>
        <a v-if="selected" class="text-link" :href="'#/domain?domain='+claim.domainId+'&kind=solution&id='+selectedId">查看方法定义 ↗</a>
      </div>
      <div class="method-tabs" role="tablist" aria-label="当前方法">
        <button v-for="key in methods" :key="key" type="button" role="tab" :id="tabId(key)"
          :aria-selected="key===selectedId" :aria-controls="panelId" :tabindex="key===(selectedId||methods[0])?0:-1"
          @click="emit('selectMethod',key)" @keydown="navigateTab($event,key)">{{methodName(key)}}</button>
      </div>
    </div>
    <div :id="panelId" class="method-content" role="tabpanel" :aria-labelledby="selectedId?tabId(selectedId):undefined" tabindex="0">
    <template v-if="selected">
      <section class="panel table-scroll" aria-label="本方法执行判据">
        <div class="row-between"><h3>本方法执行判据</h3><button class="btn" :disabled="blocked" :aria-label="methodName(selectedId)+' · 关联执行判据'" @click="editBinding(selectedId)">关联判据</button></div>
        <table v-if="checks.length" class="data-table current-checks">
          <thead><tr><th>判据</th><th>满足的表现</th><th>操作</th></tr></thead>
          <tbody><tr v-for="c in checks" :key="c.id" :data-criterion="c.id">
            <td><strong>{{c.name}}</strong><small>{{c.id}}{{completeCriterion(c)?'':' · 待补充'}}</small></td><td>{{c.met||'待填写'}}</td>
            <td><button class="btn" :disabled="blocked" :aria-label="'编辑本方法判据 '+c.name" @click="editCriterion(c)">编辑</button></td>
          </tr></tbody>
        </table>
        <p v-else class="muted">本方法的执行判据待关联。</p>

      </section>
      <AspectRulesPanel :key="selectedId" :claim="claim" :method-id="selectedId" :blocked="blocked" @saved="emit('saved',$event)"/>
    </template>
    <p v-else class="callout">{{methods.length?'链接中的方法不属于当前 Task，请从上方选择。':'请先在领域管理为这个 Task 关联方法。'}}</p>
    </div>
  </section>
  <details class="panel table-scroll criterion-library"><summary>本 Task 的可复用判据（{{claim.criteria.length}}）</summary>
    <div class="library-actions"><button class="btn primary" :disabled="blocked" @click="editCriterion()">新建判据</button></div>
    <table v-if="claim.criteria.length" class="data-table criterion-list">
      <thead><tr><th>判据</th><th>满足的表现</th><th>本方法引用</th><th>操作</th></tr></thead>
      <tbody><tr v-for="c in claim.criteria" :key="c.id" :data-criterion="c.id">
        <td><strong>{{c.name}}</strong><small>{{c.id}}{{completeCriterion(c)?'':' · 待补充'}}</small></td>
        <td>{{c.met||'待填写'}}</td>
        <td><details v-if="usage(c.id).length"><summary>{{usage(c.id).length}} 种方法</summary>
          <div v-for="r in usage(c.id)" :key="r.methodId">{{methodName(r.methodId)}}</div>
        </details><span v-else>尚未关联</span></td>
        <td><div class="button-row"><button class="btn" :aria-label="'编辑判据 '+c.name" :disabled="blocked" @click="editCriterion(c)">编辑</button>
          <button class="btn" :aria-label="'删除判据 '+c.name" :disabled="blocked||!!usage(c.id).length" :title="usage(c.id).length?'先解除现有引用':'删除判据'" @click="item=clone(c);error='';mode='remove'">删除</button></div></td>
      </tr></tbody>
    </table>
    <p v-else class="empty">先创建用于检查求解过程和结果的判据，再关联到本方法方法。</p>
  </details>

  <details v-if="claim.previous" class="panel"><summary>旧版配置参考</summary>
    <p class="muted">保留原文供核对。按用途选用到方法执行判据或四方面评价规则。</p>
    <ul><li v-for="c in claim.previous.criteria" :key="c.id"><strong>{{c.name}}</strong> · {{c.met}}
      <small>{{c.input}}　{{c.basis}}　{{c.counter}}　{{c.insufficient}}　{{c.examples}}</small>
      <button class="text-link" :disabled="blocked" @click="editCriterion({...c,id:newCriterion().id})">按此新建执行判据</button>
    </li></ul>
    <details><summary>原来的引用</summary><p v-for="r in claim.previous.rules" :key="r.methodId+r.aspectId">{{methodName(r.methodId)}} · {{claim.aspects.find(a=>a.id===r.aspectId)?.name}} · {{r.criteria.map(id=>claim.previous!.criteria.find(c=>c.id===id)?.name||id).join('、')}} · {{r.condition}}</p></details>
  </details>

  <WorkbenchDialog v-if="mode==='criterion'" :title="claim.criteria.some(c=>c.id===item.id)?'编辑判据':'新建判据'" wide @close="close">
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
    <p v-if="usage(item.id).length>1" class="callout">该判据由 {{usage(item.id).map(e=>methodName(e.methodId)).join('、')}} 共用。保存后这些引用会一起更新。</p>
    <label>判据名称<input v-model="item.name"/></label>
    <div class="edit-pair"><label>必要输入<textarea v-model="item.input" rows="2" placeholder="需要观察哪些作答、说明或操作记录"/></label>
      <label>判定依据<textarea v-model="item.basis" rows="2" placeholder="参考任务的完成要求、方法关系或实例答案"/></label></div>
    <label>满足的表现<textarea v-model="item.met" rows="2"/></label>
    <div class="edit-pair"><label>不满足的表现<textarea v-model="item.counter" rows="2"/></label><label>信息不足的情况<textarea v-model="item.insufficient" rows="2"/></label></div>
    <label>正反样例（选填）<textarea v-model="item.examples" rows="2"/></label>
    <footer class="dialog-footer"><button class="btn" @click="close">取消</button><button class="btn primary" :disabled="blocked" @click="saveCriterion">保存判据</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="mode==='binding'&&binding" title="关联本方法执行判据" wide @close="close">
    <strong>{{methodName(binding.methodId)}}</strong>
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
    <div class="row-between"><p>选择本方法需要核对的过程和结果。</p><button class="btn" @click="editCriterion(undefined,true)">新建判据</button></div>
    <div class="picker-list"><label v-for="c in claim.criteria" :key="c.id" class="check-line"><input v-model="binding.criteria" type="checkbox" :value="c.id" :aria-label="'选用 '+c.name"/><span>{{c.name}}<small>{{c.met}}</small></span></label></div>
    <p v-if="!claim.criteria.length" class="muted">本 Task 还没有执行判据。</p>
    <footer class="dialog-footer"><button class="btn" @click="close">取消</button><button class="btn primary" :disabled="blocked" @click="saveBinding">保存关联</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="mode==='remove'" title="删除判据" @close="close"><p>删除本 Claim 中的「{{item.name}}」？</p>
    <p v-if="error" role="alert" class="callout danger">{{error}}</p><footer class="dialog-footer"><button class="btn" @click="close">取消</button><button class="btn danger-btn" :disabled="blocked" @click="removeCriterion">确认删除</button></footer>
  </WorkbenchDialog>
</template>

<style scoped>
.method-detail{overflow:hidden;border:1px solid #d7e3db;border-radius:10px;background:white;margin-bottom:18px}
.method-detail>.panel,.method-content>.panel{margin:0;border:0;border-radius:0}
.method-content>.panel{border-top:1px solid #e0e9e3}
.method-selector{background:#f6faf7;padding:14px 20px 0}
.method-bar{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#40594a;font-weight:600}
.method-tabs{display:flex;overflow-x:auto;gap:6px;margin-top:8px;padding:2px 2px 0}
.method-tabs button{flex:0 0 auto;max-width:100%;padding:9px 14px;border:0;border-bottom:3px solid transparent;background:transparent;color:#435c4c;text-align:left;overflow-wrap:anywhere}
.method-tabs button:hover{background:#eaf2ec}
.method-tabs button[aria-selected="true"]{color:#245d43;background:#e4f0e7;border-color:#2d6a4f;font-weight:600}
.method-tabs button:focus-visible{outline-offset:-3px}
.row-between h3{margin:0}.current-checks,.criterion-list{margin-top:14px}.current-checks td,.criterion-list td{vertical-align:top}.tree-toggle{margin-top:12px}.criterion-library summary{cursor:pointer}.library-actions{display:flex;justify-content:flex-end}.picker-list small{display:block;color:#697c70}
</style>
