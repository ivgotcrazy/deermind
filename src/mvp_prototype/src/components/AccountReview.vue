<script setup lang="ts">
import { computed, ref } from 'vue';
import { journey } from '../journeyState';
import { activeParent, currentParentLinked as parentLinked } from '../parentState';
defineProps<{role:'student'|'parent'|'admin'}>();
const a=computed(()=>journey.accounts);
const verified=ref(false), reason=ref(''), name=ref(''), newRole=ref<'student'|'parent'>('parent'), selected=ref('CHILD-DEMO-1'), parent=ref('PARENT-DEMO-1'), child=ref('CHILD-DEMO-1'), notice=ref('');
const allowed=computed(()=>verified.value&&reason.value.trim().length>0);
const selectedLink=computed(()=>a.value.links.find(l=>l.parent===parent.value&&l.child===child.value));
function record(action:string){a.value.audit.push(`${action}；管理员记录系统外核实依据：${reason.value.trim()}`);notice.value=action;verified.value=false;reason.value='';}
function create(){if(!allowed.value||!name.value.trim())return;const id='DEMO-'+crypto.randomUUID().slice(0,8);a.value.profiles.push({id,name:name.value.trim(),role:newRole.value,credentialRevision:1});record(`建立合成${newRole.value==='student'?'学生':'家长'}档案 ${id}，未自动建立亲子关系`);name.value='';}
function link(){if(!allowed.value)return;if(selectedLink.value)selectedLink.value.active=true;else a.value.links.push({parent:parent.value,child:child.value,active:true});record(`关联 ${parent.value} 与 ${child.value}`);}
function unlink(){if(!allowed.value||!selectedLink.value?.active)return;if(!window.confirm(`解除 ${parent.value} 与 ${child.value} 的查看关联？其他关联不变。`))return;selectedLink.value.active=false;record(`解除 ${parent.value} 与 ${child.value} 的关联`);}
function recover(){if(!allowed.value)return;const p=a.value.profiles.find(p=>p.id===selected.value);if(!p)return;p.credentialRevision++;record(`为原档案 ${p.id} 记录找回，凭据记录版本 ${p.credentialRevision}；原学习记录保留`);}
</script>
<template>
<main class="f-flow-page">
  <span class="f-eyebrow">{{ {student:'学生',parent:'家长',admin:'管理员'}[role] }} · 账号与关系</span><h1>{{ role==='admin'?'让身份、关联和找回有据可查':'开始使用前，了解彼此的边界' }}</h1>
  <details class="f-provenance"><summary>身份与首次确认演示 · 没有真实账号或授权</summary><p>角色切换仅用于走查，不是登录。没有采集密码、证件或真实同意。本页固定说明版本 DEMO-NOTICE-1，只涉及本地合成材料；真实数据用途、外部模型服务及授权条件仍须核实后才能启用。</p></details>
  <template v-if="role==='admin'">
    <section class="f-card"><h2>账号档案</h2><ul><li v-for="p in a.profiles" :key="p.id">{{ p.name }} · {{ p.role==='student'?'学生':'家长' }} · {{ p.id }} · 凭据记录 v{{ p.credentialRevision }}</li></ul><p>学生与家长使用独立账号。找回沿用原档案，不另建学习者；本轮不生成真实登录凭据。</p></section>
    <section class="f-card"><h2>先记录这次操作的核实依据</h2><label class="f-check-line"><input type="checkbox" v-model="verified"/> 已在系统外核实本人及本次操作所需关系</label><label class="f-field">核实依据<textarea v-model="reason" aria-label="身份核实依据" placeholder="仅填演示说明，不录入真实个人资料。"/></label><p class="f-muted">每次操作后清空本次确认，下一次操作需重新明确依据。</p></section>
    <section class="f-card"><h2>创建独立档案</h2><label class="f-field">演示姓名<input v-model="name" aria-label="演示账号名称"/></label><label class="f-field">角色<select v-model="newRole" aria-label="新增账号角色"><option value="student">学生</option><option value="parent">家长</option></select></label><button class="f-secondary" :disabled="!allowed||!name.trim()" @click="create">创建合成账号档案</button></section>
    <section class="f-card"><h2>逐条维护亲子关联</h2><ul><li v-for="l in a.links" :key="l.parent+l.child">{{ l.parent }} → {{ l.child }}：{{ l.active?'有效':'已解除' }}</li></ul><label class="f-field">家长<select v-model="parent" aria-label="关联家长"><option v-for="p in a.profiles.filter(p=>p.role==='parent')" :key="p.id" :value="p.id">{{ p.name }} · {{ p.id }}</option></select></label><label class="f-field">学生<select v-model="child" aria-label="关联学生"><option v-for="p in a.profiles.filter(p=>p.role==='student')" :key="p.id" :value="p.id">{{ p.name }} · {{ p.id }}</option></select></label><div class="f-actions"><button :disabled="!allowed||selectedLink?.active" @click="link">建立所选关联</button><button :disabled="!allowed||!selectedLink?.active" @click="unlink">解除所选关联</button></div><p>家长端默认使用家长一；走查工具可切换合成家长。解除所选关系后，该家长不能从旧链接查看学生资料，其他关系独立保留。</p></section>
    <section class="f-card"><h2>找回原账号</h2><label class="f-field">原档案<select v-model="selected" aria-label="找回原账号"><option v-for="p in a.profiles" :key="p.id" :value="p.id">{{ p.name }} · {{ p.id }}</option></select></label><button :disabled="!allowed" @click="recover">记录原账号找回</button><p>本轮只检查“核实后操作、身份不换、学习记录不丢”的产品行为，不执行密码重置。</p></section>
    <details v-if="a.audit.length" class="f-card"><summary>查看身份与关系操作记录</summary><ol><li v-for="(entry,i) in a.audit" :key="i">{{ entry }}</li></ol></details>
  </template>
  <template v-else>
    <section class="f-card"><h2>{{ role==='parent'?'你可以了解孩子的学习情况':'这是你的学习空间' }}</h2><p v-if="role==='parent'">学习资料由孩子在学生端录入和修改，你可以查看并咨询，不能在家长端直接更改她的题目和作答。你的私人咨询不出现在学生端。</p><p v-else>你可以选教材、提问、练习和检测。家长可以了解相关学习情况；你不用替家长确认数据用途，也不会看到家长的私人咨询。</p><p>当前演示关联：{{ activeParent?.name }}：{{ parentLinked?'与演示学生关联有效':'与演示学生的关联已解除' }}。</p></section>
    <section class="f-card"><h2>首次说明与确认</h2><p>本例仅用合成内容演示流程。正式使用前需分别向家长说明数据用途、可见范围、保留方式和实际外部服务，向孩子说明使用方式并确认愿意参加。</p><p>演示确认状态：家长{{ a.parentConfirmed?'已确认':'未确认' }}；孩子{{ a.childConfirmed?'已确认':'未确认' }}。</p><button v-if="role==='parent'" class="f-primary" :disabled="a.parentConfirmed||!parentLinked" @click="a.parentConfirmed=true">完成家长端演示确认</button><button v-else class="f-primary" :disabled="a.childConfirmed" @click="a.childConfirmed=true">我愿意参加这次演示</button><p class="f-muted">已完成且说明范围未变时不重复确认。此原型没有实际服务变更与重新授权流程。</p></section>
    <details class="f-demo-controls"><summary>走查首次使用前的状态</summary><button @click="a.parentConfirmed=false;a.childConfirmed=false">重置双方演示确认</button><p>此按钮是评审工具，不是产品的授权撤回入口。</p></details>
  </template>
  <p v-if="notice" role="status" class="f-notice">{{ notice }}</p>
</main>
</template>
