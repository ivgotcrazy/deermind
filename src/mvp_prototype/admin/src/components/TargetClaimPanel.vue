<script setup lang="ts">
import { computed, ref, nextTick } from 'vue';
import { go } from '../workbench/navigation';
import { domainMock } from '../workbench/domain-mock';
import { mockId } from '../workbench/textbook-mock';
import { targetClaim, mappedChapters, allChapters, omittedAspects, conditionIssues, recordTargetChange, type MockTarget, type TargetClaimSelection, type LearningRequirement } from '../workbench/target-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';
const props=defineProps<{target:MockTarget;selection:TargetClaimSelection}>();
const claim=computed(()=>targetClaim(props.selection.claimId));
const chapters=computed(()=>mappedChapters(props.target,props.selection.claimId));
const usedChapters=computed(()=>chapters.value.filter(ch=>!props.selection.requirements.length||props.selection.requirements.some(r=>r.chapterIds.includes(ch.id))));
const issues=computed(()=>conditionIssues(props.target,props.selection));
const omitted=computed(()=>omittedAspects(props.selection));
const chapterName=(id:string)=>allChapters(props.target.bookId).find(c=>c.id===id)?.name||'章节不存在';
const aspectName=(id:string)=>claim.value?.aspects.find(a=>a.id===id)?.name||'方面不存在';
const methodName=(id:string)=>domainMock.methods.find(m=>m.id===id)?.name||'方法不存在';
function openClaim(){go('evaluation',{id:props.selection.claimId,returnTo:location.hash});}
function openChapter(id:string){go('textbooks',{id:props.target.bookId,chapter:id,tab:'mapping',returnTo:location.hash});}
function openMethod(id:string){go('domain',{id,domain:claim.value?.domainId,filter:'solution',returnTo:location.hash});}
const editor=ref<'requirement'|'omission'|null>(null),error=ref(''),errorNode=ref<HTMLElement>(),editingId=ref(''),deleting=ref(false),notice=ref('');
const draft=ref<LearningRequirement>({id:'',name:'',chapterIds:[],aspectIds:[],standard:''}),reason=ref('');
function edit(value?:LearningRequirement){editingId.value=value?.id||'';draft.value=value?JSON.parse(JSON.stringify(value)):{id:mockId('REQUIREMENT'),name:'',chapterIds:chapters.value.length===1?[chapters.value[0]!.id]:[],aspectIds:[],standard:''};error.value='';deleting.value=false;editor.value='requirement';}
function editOmission(){reason.value=props.selection.omissionReason;error.value='';editor.value='omission';}
async function fail(message:string){error.value=message;await nextTick();errorNode.value?.focus();errorNode.value?.scrollIntoView({block:'center'});}
function finish(change:string){recordTargetChange(props.target,change);editor.value=null;notice.value='已保存。仅调整本目标的学习要求，Claim 定义与个人 Belief 未改变。';}
function save(){
  if(editor.value==='omission'){if(!reason.value.trim())return fail('请说明本目标不要求这些方面的依据，尚未检测不是裁剪理由。');props.selection.omissionReason=reason.value.trim();return finish('修改目标方面裁剪依据');}
  if(!draft.value.name.trim()||!draft.value.standard.trim())return fail('请填写学生能理解的要求名称和具体达标标准。');
  if(!draft.value.chapterIds.length||draft.value.chapterIds.some(id=>!chapters.value.some(ch=>ch.id===id)))return fail('请选择目标范围内、映射了该任务的章节，移除已失效的章节引用。');
  if(!draft.value.aspectIds.length||draft.value.aspectIds.some(id=>!claim.value?.aspects.some(a=>a.id===id&&a.applicable&&a.criterion.trim()&&a.evidence.trim())))return fail('请选择已定义完整且适用的 Claim 方面，移除失效引用。');
  const index=props.selection.requirements.findIndex(r=>r.id===editingId.value),value=JSON.parse(JSON.stringify(draft.value));
  if(index<0)props.selection.requirements.push(value);else props.selection.requirements[index]=value;
  finish((index<0?'添加':'修改')+'学习要求：'+value.name);
}
function remove(){props.selection.requirements=props.selection.requirements.filter(r=>r.id!==editingId.value);finish('移除学习要求：'+draft.value.name);}
</script>
<template><div class="target-claim-panel">
  <template v-if="claim">
    <div class="section-heading"><div><h3>{{claim.name}}</h3><p class="muted">逐项说明学生需要做到什么；每项可引用一个或多个评价方面。</p></div><button class="text-link" @click="openClaim">查看 Claim 定义 ↗</button></div>
    <p v-if="notice" role="status" class="saved-note">{{notice}}</p>
    <section class="panel conditions-panel"><div class="section-heading"><h4>方法与帮助条件</h4><span class="badge" :class="issues.length?'amber':'green'">{{issues.length?'方法或范围待核对':'未发现引用范围冲突'}}</span></div>
      <p class="method-policy">Claim 要求：<strong>{{claim.methods.length===1?'使用指定方法':claim.methodMode==='all'?'分别覆盖全部所选方法':'所选方法任选一种'}}</strong></p><div class="method-links"><button v-for="id in claim.methods" :key="id" class="text-link" @click="openMethod(id)">{{methodName(id)}} ↗</button><span v-if="!claim.methods.length" class="muted">方法尚未定义</span></div>
      <table class="data-table method-context"><thead><tr><th>要求所属章节</th><th>教材中采用的方法</th></tr></thead><tbody><tr v-for="ch in usedChapters" :key="ch.id"><td><button class="text-link" @click="openChapter(ch.id)">{{ch.name}} ↗</button></td><td>{{ch.mappings.filter(m=>m.taskId===claim!.taskId).flatMap(m=>m.methods).map(methodName).join('、')||'未选方法'}}</td></tr></tbody></table>
      <div v-if="issues.length" class="callout amber condition-issues"><p v-for="issue in issues" :key="issue">{{issue}}</p><p>本目标尚不能确认条件相容。请核对教材映射或选用匹配的 Claim；不会自动取方法交集，也不会将“任选一种”的判断当成“指定方法已掌握”。</p></div>
      <p class="support-boundary"><b>帮助边界：</b>{{claim.support||'尚未定义'}}</p>
      <details><summary>查看 Claim 的范围、质量与方法责任</summary><dl class="field-list"><dt>任务范围</dt><dd>{{claim.scope||'尚未定义'}}</dd><dt>适用条件</dt><dd>{{claim.conditions||'尚未定义'}}</dd><dt>质量要求</dt><dd>{{claim.quality||'尚未定义'}}</dd><dt>方法责任</dt><dd>{{claim.methodNote||'尚未定义'}}</dd></dl><p class="muted">这里引用原定义。若需要改变方法、帮助或迁移条件，应在评估模型管理中明确对应 Claim；目标中不另写一份定义。</p></details>
    </section>
    <div class="section-heading"><h3>具体学习要求 <span class="muted">{{selection.requirements.length}} 项</span></h3><button class="btn primary" @click="edit()">添加学习要求</button></div>
    <section class="table-card"><table class="data-table requirement-table"><thead><tr><th>学习要求 / 章节</th><th>引用的评价方面</th><th>达标标准</th><th></th></tr></thead><tbody><tr v-for="r in selection.requirements" :key="r.id"><td><strong>{{r.name}}</strong><small>{{r.chapterIds.map(chapterName).join('、')}}</small></td><td>{{r.aspectIds.map(aspectName).join('、')}}</td><td class="multiline">{{r.standard}}</td><td><button class="btn" :aria-label="'编辑要求 '+r.name" @click="edit(r)">编辑</button></td></tr></tbody></table><p v-if="!selection.requirements.length" class="empty">尚无具体学习要求。添加名称、所属章节、引用方面和达标标准；不会按四个方面自动生成四项。</p></section>
    <div v-if="omitted.length" class="omission-note"><div class="section-heading"><strong>本目标未要求：{{omitted.map(a=>a.name).join('、')}}</strong><button class="text-link" @click="editOmission">编辑裁剪依据</button></div><p>{{selection.omissionReason||'尚未说明裁剪依据，目标配置仍待补充。'}}</p><p class="muted">这些方面仍保留在共享 Claim 中；未纳入目标不表示学习者已掌握或无需评价。</p></div>
    <p class="muted">以上是学习要求定义，不是学生的达标结果；当前原型不运行目标评价。</p>
  </template>
  <section v-else class="panel"><h3>引用的 Claim 不存在</h3><p>请返回目标调整引用，不能以空白要求视为已完成配置。</p></section>
  <WorkbenchDialog v-if="editor" :title="editor==='omission'?'目标方面裁剪依据':editingId?'编辑学习要求':'添加学习要求'" wide @close="editor=null"><form @submit.prevent="save" novalidate>
    <p v-if="error" ref="errorNode" role="alert" tabindex="-1" class="callout danger">{{error}}</p>
    <template v-if="editor==='requirement'">
      <p class="muted">{{claim?.name}} · 仅修改本目标，不修改共享 Claim。</p><label>学习要求名称<input v-model="draft.name" placeholder="用学生能理解的话说明需要做到什么"/></label>
      <fieldset><legend>所属章节</legend><label v-for="ch in chapters" :key="ch.id" class="check-label"><input v-model="draft.chapterIds" type="checkbox" :value="ch.id"/>{{ch.name}}</label><label v-for="id in draft.chapterIds.filter(id=>!chapters.some(ch=>ch.id===id))" :key="id" class="check-label"><input v-model="draft.chapterIds" type="checkbox" :value="id"/>{{chapterName(id)}}（已失效，请移除）</label><p v-if="!chapters.length" class="muted">所选范围内尚无对应任务映射，请先调整教材或目标范围。</p></fieldset>
      <fieldset><legend>引用的评价方面</legend><label v-for="a in claim?.aspects" :key="a.id" class="check-label aspect-option"><input v-model="draft.aspectIds" type="checkbox" :value="a.id" :disabled="(!a.applicable||!a.criterion.trim()||!a.evidence.trim())&&!draft.aspectIds.includes(a.id)"/><span>{{a.name}}<small>{{a.applicable?(a.criterion||'定义待补充'):'此 Claim 不适用：'+a.reason}}</small></span></label><label v-for="id in draft.aspectIds.filter(id=>!claim?.aspects.some(a=>a.id===id))" :key="id" class="check-label"><input v-model="draft.aspectIds" type="checkbox" :value="id"/>{{id}}（方面已不存在，请移除）</label></fieldset>
      <label>达标标准<textarea v-model="draft.standard" rows="4" placeholder="在所引用 Claim 的条件内，什么表现和有效判断足以满足本项要求"/></label><p class="muted">方法与帮助边界沿用上方 Claim。标准不能把原定义中的迁移、延迟或方法条件悄悄改为另一种含义。</p>
      <p v-if="deleting" class="callout amber">只移除本目标的这项要求，Claim 和学习记录不变。<button type="button" class="text-link" @click="remove">确认移除要求</button></p>
    </template>
    <template v-else><p>本目标不要求：{{omitted.map(a=>a.name).join('、')}}。</p><label>裁剪依据<textarea v-model="reason" rows="4" placeholder="说明目标范围或阶段目的，不以学生不会或尚未检测作为依据"/></label></template>
    <div class="dialog-footer editor-footer"><button v-if="editingId&&editor==='requirement'" type="button" class="text-link remove-link" @click="deleting=true">移除此要求</button><div class="button-row"><button type="button" class="btn" @click="editor=null">取消</button><button type="submit" class="btn primary">保存</button></div></div>
  </form></WorkbenchDialog>
</div></template>
<style scoped>
.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 14px}.section-heading h3{font-size:17px;margin:0}.section-heading h4{margin:0}.section-heading p{margin:4px 0 0}.conditions-panel{margin-top:18px}.method-policy{font-size:13px}.method-links{display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 16px}.method-context th:first-child{width:35%}.support-boundary{font-size:13px;color:#5d7265}.condition-issues p{margin:6px 0}.requirement-table th:first-child{width:28%}.requirement-table th:nth-child(2){width:18%}.requirement-table th:last-child{width:70px}.requirement-table strong{font-weight:500}.multiline{white-space:pre-wrap}.saved-note{font-size:13px;color:#2d6a4f}.omission-note{background:#fff8e8;border:1px solid #e9dfbf;border-radius:8px;padding:16px;font-size:13px;margin:16px 0}.omission-note .section-heading{margin-bottom:6px}.omission-note p{margin:5px 0}legend{font-size:13px;color:#405a4c;margin:18px 0 8px}.aspect-option{align-items:flex-start}.aspect-option input{margin-top:5px}.aspect-option small{display:block;color:#77897d;font-size:12px}.editor-footer{display:flex;justify-content:flex-end;align-items:center;gap:18px}.editor-footer .button-row{margin:0}.remove-link{margin-right:auto;color:#9b533d}@media(max-width:1100px){.requirement-table th:first-child{width:25%}.requirement-table th:nth-child(2){width:17%}}
</style>
