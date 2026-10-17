<script setup lang="ts">
import { computed, ref } from 'vue';
import { fixture, flows, fingerprint } from '../foundationState';
import { recordsReview } from '../recordState';
import ContentPackageReview from './ContentPackageReview.vue';
const m=flows.maintenance;
const arriving=recordsReview.issues.find(i=>i.id===recordsReview.activeIssue&&i.decision==='maintenance');
if(arriving&&!m.published&&!m.issueId){m.issueId=arriving.id;m.approvedFingerprint='';}
const linkedIssue=computed(()=>recordsReview.issues.find(i=>i.id===m.issueId));
const stale=ref(false);const selectedSpace=ref(false);const message=ref('');
const currentFingerprint=computed(()=>fingerprint(m.candidate));
function referenceExists(reference:string,type:string){return fixture.supporting_objects.some(o=>o.type===type&&`${o.id}@${o.version}`===reference);}
const structurallyValid=computed(()=>Object.values(m.candidate).every(v=>v.trim())&&referenceExists(m.candidate.solution_ref,'SolutionTemplate')&&referenceExists(m.candidate.knowledge_ref,'KnowledgeComponent'));
const checked=computed(()=>!stale.value&&m.checkedFingerprint===currentFingerprint.value&&structurallyValid.value);
const reviewFingerprint=computed(()=>currentFingerprint.value+'|'+m.reason.trim()+'|'+(m.issueId||''));
const approved=computed(()=>checked.value&&m.review==='pass'&&!!m.reason.trim()&&m.approvedFingerprint===reviewFingerprint.value);
const changed=computed(()=>['name','responsibility','conditions','solution_ref','knowledge_ref'].some(k=>m.candidate[k as keyof typeof m.candidate]!==fixture.definition[k as keyof typeof fixture.definition]));
const labels:Record<keyof typeof m.candidate,string>={name:'名称',responsibility:'问题责任',conditions:'参数与适用条件',solution_ref:'方法引用',knowledge_ref:'知识引用'};
function audit(text:string){m.audit.push(text);message.value=text;}
function check(){m.checkedFingerprint=structurallyValid.value&&!stale.value?currentFingerprint.value:'';audit(m.checkedFingerprint?'本地字段与引用检查通过；语义和教学意义仍需人工核对。':'检查未通过：核对必填内容、方法与知识引用，以及引用基础。');}
function approve(){if(!checked.value||m.review!=='pass'||!m.reason.trim()||!changed.value)return;m.approvedFingerprint=reviewFingerprint.value;audit('管理员已记录审核依据；批准当前候选，仅允许发布到合成内容目录。');}
function publish(){if(!approved.value||m.published)return;m.published=JSON.parse(JSON.stringify(m.candidate));if(linkedIssue.value){linkedIssue.value.linkedVersion='PT-DEMO-AREA@2';linkedIssue.value.history.push('关联候选已本地发布 PT-DEMO-AREA@2；真实采用影响与重处理仍未执行，事项未自动关闭。');}audit('合成目录已发布 v2；现有演示空间仍采用 v1，尚未更新。');}
function adopt(){if(!m.published||!selectedSpace.value||m.adopted)return;m.adopted=true;audit('已模拟将校内演示空间指定为采用 v2；范围和目标选择保持，校外空间不变。真实失效与重处理未执行。');}
</script>
<template>
<main class="f-flow-page f-wide">
  <span class="f-eyebrow">管理员 · 内容与维护</span><h1>每次修改，都看清依据和影响</h1>
  <ContentPackageReview />
  <p class="f-provenance">本地合成维护流程 · 不发布到真实模型，不执行真实评价重算。可修改的是领域定义，不能直接把学生设为“已掌握”。</p>
  <section v-if="linkedIssue" class="f-card"><h2>关联人工事项 {{ linkedIssue.id }}</h2><p>来源记录：{{ linkedIssue.recordId }}</p><p>{{ linkedIssue.description }}</p><p>候选发布只追加版本关联，不自动解决该事项。真实影响仍待处理。</p></section>
  <ol class="f-step-strip"><li :class="{active:!checked}">准备候选</li><li :class="{active:checked&&!approved}">检查与审核</li><li :class="{active:approved&&!m.published}">发布</li><li :class="{active:!!m.published}">指定采用</li></ol>
  <div class="f-flow-columns">
    <section class="f-card">
      <div class="f-content-heading"><div><span class="f-eyebrow">Domain / ProblemTemplate</span><h2>{{ fixture.definition.id }}</h2></div><span class="f-tag">{{ m.published?'已发布 v2':'候选 v2' }}</span></div>
      <p>候选所依据的定义：v1 · 方法 {{ fixture.definition.solution_ref }} · 知识 {{ fixture.definition.knowledge_ref }}</p>
      <details><summary>查看引用对象</summary><article v-for="obj in fixture.supporting_objects" :key="obj.id" class="f-diff"><b>{{ obj.type }} · {{ obj.id }}@{{ obj.version }}</b><p>{{ obj.name }}</p><p>{{ obj.definition }}</p></article></details>
      <p class="f-muted">维护目的：核对同一面积要求在不同图形摆放下的适用边界。初始候选与 v1 一致，须明确实际修改内容。</p>
      <label v-for="(label,key) in labels" :key="key" class="f-field">{{ label }}<textarea v-if="key==='responsibility'||key==='conditions'" v-model="m.candidate[key]" :aria-label="label" :disabled="!!m.published"/><input v-else v-model="m.candidate[key]" :aria-label="label" :disabled="!!m.published"/></label>
      <details open><summary>与 v1 的差异</summary><template v-for="(label,key) in labels" :key="key"><div v-if="m.candidate[key]!==fixture.definition[key]" class="f-diff"><b>{{ label }}</b><p><span>原：</span>{{ fixture.definition[key] }}</p><p><span>新：</span>{{ m.candidate[key] }}</p></div></template><p v-if="!changed">尚无修改，不创建一个内容相同的新版本。</p></details>
    </section>
    <section class="f-card">
      <h2>检查、审核和发布</h2>
      <p>字段与引用检查只确认必填项及本合成目录的引用存在，不证明数学语义正确。</p>
      <button class="f-secondary" :disabled="!!m.published" @click="check">检查字段与引用</button>
      <p :class="checked?'f-state-met':'f-muted'">{{ checked?'当前候选结构检查通过':'当前候选尚无有效检查结果' }}</p>
      <details class="f-demo-controls"><summary>走查引用变化</summary><label><input type="checkbox" v-model="stale" :disabled="!!m.published" @change="m.checkedFingerprint='';m.approvedFingerprint=''"/> 模拟引用基础已经变化</label><p class="f-muted">变化后需核对引用与候选，再重新检查、审核；旧批准不能继续发布。</p></details>
      <h3 class="f-spaced">人工核对代表性案例</h3>
      <ul><li>底 6、高 4 且单位一致，面积为 12；核对所写范围能否支持该例。</li><li>旋转后的三角形，底与对应高仍明确；核对表面变化是否改变问题责任。</li><li>只给斜边长度、没有对应高；不得把斜边当高套用该模板。</li></ul>
      <label class="f-field">人工审核结论<select v-model="m.review" aria-label="人工审核结论" :disabled="!!m.published"><option value="pending">尚未审核</option><option value="pass">所核对案例支持当前候选</option><option value="fail">发现问题，不通过</option><option value="unresolved">仍有疑问，保持未决</option></select></label>
      <label class="f-field">审核依据<textarea v-model="m.reason" aria-label="审核依据" :disabled="!!m.published" placeholder="记录实际核对的内容、差异、适用范围和未解决限制。"/></label>
      <div class="f-actions"><button class="f-secondary" :disabled="!checked||m.review!=='pass'||!m.reason.trim()||!changed||!!m.published" @click="approve">记录批准</button><button class="f-primary" :disabled="!approved||!!m.published" @click="publish">发布候选 v2</button></div>
      <p v-if="m.approvedFingerprint&&!approved&&!m.published" class="f-notice">候选、依据或引用条件已改变，原批准不再适用。</p>
      <p class="f-muted f-spaced">同一管理员可以完成这些步骤，操作分别记录；结论只覆盖实际检查的范围。</p>
    </section>
  </div>
  <section class="f-card"><div class="f-content-heading"><h2>发布之后，选择哪些空间采用</h2><span class="f-tag">目录 {{ m.published?'v2':'v1' }} · 校内空间 {{ m.adopted?'v2':'v1' }}</span></div>
    <p v-if="!m.published">候选尚未发布，不能指定采用。</p>
    <template v-else><label class="f-checkbox"><input type="checkbox" v-model="selectedSpace" :disabled="m.adopted"/> 校内合成演示空间 · 当前 {{ m.adopted?'v2':'v1' }}</label><p>影响：本例仅更新该空间引用的模板版本；所选章节点、目标和原始学习记录保留。新版本的真实教学效果及历史结果重处理须由工程实现验证。</p><p class="f-muted">校外内部教材空间尚未准备，不在本次采用范围内。已知失效的结果不得继续用于当前判断。</p><button class="f-primary" :disabled="!selectedSpace||m.adopted" @click="adopt">指定所选空间采用 v2</button></template>
  </section>
  <section class="f-card"><h2>操作与后续影响</h2><ol><li v-for="(entry,i) in m.audit" :key="i">{{ entry }}</li></ol><p v-if="!m.audit.length">还没有维护操作。</p><p class="f-muted">真实失效、待执行／失败／未决重处理尚未接入，本页不能把它们显示为已完成；也不重新执行历史教学。</p></section>
  <p v-if="message" role="status" class="f-notice">{{ message }}</p>
</main>
</template>
