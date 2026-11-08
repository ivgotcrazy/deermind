<script setup lang="ts">
import { computed, ref } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import { copyTeaching, newTeachingId, type NodeRouting, type TeachingBlueprint, type TeachingTransition } from '../model/teaching-mock';
const props=defineProps<{blueprint:TeachingBlueprint;nodeId:string;selectedEdge:string}>();
const emit=defineEmits<{save:[policy:NodeRouting,transitions:TeachingTransition[]]}>();
const node=computed(()=>props.blueprint.stages.find(n=>n.id===props.nodeId));
const outgoing=computed(()=>props.blueprint.transitions.filter(e=>e.from===props.nodeId));
const policy=computed<NodeRouting>(()=>(props.nodeId==='start'?props.blueprint.startRouting:node.value?.routing)||{
  when:props.nodeId==='start'?'收到并确认本次活动请求后判断。':'本节点形成结果、收到学生相关回应或子活动返回后判断。',
  otherwise:props.nodeId==='start'?'等待或澄清必要的活动请求，不自动启动活动。':'需要继续处理时，可在允许动作内留在本节点回应；需要学生输入时等待，缺少必要信息时澄清。无法继续时按节点的相应处理执行，不自动重复或宣布结束。',
});
const editing=ref(false),error=ref('');
const form=ref<NodeRouting>({when:'',otherwise:''}),rows=ref<TeachingTransition[]>([]);
function name(id:string){return id==='start'?'开始':id==='end'?'结束':props.blueprint.stages.find(n=>n.id===id)?.name||'节点不存在';}
function edit(){form.value=copyTeaching(policy.value);rows.value=copyTeaching(outgoing.value);error.value='';editing.value=true;}
function add(){rows.value.push({id:newTeachingId('edge'),from:props.nodeId,to:'',label:'',condition:'',basis:''});}
function move(index:number,offset:number){const [row]=rows.value.splice(index,1);rows.value.splice(index+offset,0,row);}
function save(){
  if(!form.value.when.trim()||!form.value.otherwise.trim()){error.value='请填写判断时机和未命中时的处理。';return;}
  if(!rows.value.length){error.value='非结束节点至少保留一条条件转移。';return;}
  const targets=new Set([...props.blueprint.stages.map(n=>n.id),'end']);
  if(rows.value.some(r=>!targets.has(r.to)||!r.label.trim()||!r.condition.trim()||!r.basis.trim())){error.value='请补齐每条转移的名称、条件、判断依据和目标节点。';return;}
  emit('save',copyTeaching(form.value),copyTeaching(rows.value));editing.value=false;
}
</script>

<template>
  <section class="node-routing" aria-label="节点条件转移">
    <div class="row-between"><h4>条件转移</h4><button class="btn" @click="edit">编辑条件转移</button></div>
    <p class="muted">按顺序检查，选择第一条满足条件且通过强制规则检查的转移；一次只走一条。未命中推荐策略不阻止继续。</p>
    <dl><dt>何时判断</dt><dd>{{policy.when}}</dd></dl>
    <div class="routing-table"><table class="data-table"><thead><tr><th>顺序</th><th>条件与依据</th><th>目标</th></tr></thead><tbody>
      <tr v-for="(edge,index) in outgoing" :key="edge.id" :class="{highlight:edge.id===selectedEdge}"><td>{{index+1}}</td><td><strong>{{edge.label}}</strong><p>{{edge.condition}}</p><small>依据：{{edge.basis}}</small></td><td>{{name(edge.to)}}</td></tr>
    </tbody></table></div>
    <p v-if="!outgoing.length" class="callout amber">尚未配置条件转移。</p>
    <dl><dt>没有条件命中时</dt><dd>{{policy.otherwise}}</dd></dl>
    <p class="muted">当前只保存 Mock 定义，不执行语义判断。学生走查使用固定脚本。</p>
  </section>
  <WorkbenchDialog v-if="editing" :title="'条件转移：'+name(nodeId)" wide @close="editing=false">
    <form @submit.prevent="save" novalidate>
      <label>何时判断<textarea v-model="form.when" rows="2"/></label>
      <p>从上到下为优先顺序。条件必须遵守活动规则；选择同一节点表示等待下一次触发后继续，不是自动重复执行。</p>
      <section v-for="(row,index) in rows" :key="row.id" class="routing-edit-row" :aria-label="'转移 '+(index+1)">
        <div class="row-between"><strong>转移 {{index+1}}</strong><div class="button-row"><button class="btn" type="button" :disabled="index===0" @click="move(index,-1)">上移</button><button class="btn" type="button" :disabled="index===rows.length-1" @click="move(index,1)">下移</button><button class="btn" type="button" @click="rows.splice(index,1)">删除</button></div></div>
        <div class="two-columns"><label>转移名称<input v-model="row.label" maxlength="30" placeholder="例如：学生同意检测"/></label><label>目标节点<select v-model="row.to"><option value="" disabled>请选择</option><option v-for="n in blueprint.stages" :key="n.id" :value="n.id">{{n.name}}{{n.id===nodeId?'（本节点）':''}}</option><option value="end">结束</option></select></label></div>
        <label>满足什么条件<textarea v-model="row.condition" rows="2"/></label><label>判断依据<textarea v-model="row.basis" rows="2"/></label>
      </section>
      <button class="btn" type="button" @click="add">添加条件转移</button>
      <label>没有条件命中时<textarea v-model="form.otherwise" rows="3"/></label>
      <p v-if="error" role="alert" class="callout danger">{{error}}</p>
      <div class="dialog-footer button-row"><button class="btn" type="button" @click="editing=false">取消</button><button class="btn primary">应用到草稿</button></div>
    </form>
  </WorkbenchDialog>
</template>

<style scoped>
.node-routing{border-top:1px solid #e1e8e3;margin-top:24px;padding-top:16px}.node-routing h4{margin:0}.node-routing p,.node-routing dl{font-size:13px;line-height:1.8}.node-routing dt{font-weight:600;margin:14px 0 6px}.node-routing dd{margin:0;white-space:pre-wrap}.routing-table{overflow:auto}.routing-table td{vertical-align:top;min-width:44px}.routing-table td:last-child{min-width:90px}.routing-table p{margin:6px 0}.routing-table small{color:#748479}.highlight{background:#e7f3eb}.routing-edit-row{border:1px solid #dce6df;border-radius:8px;padding:16px;margin:16px 0}.routing-edit-row .two-columns{margin-top:12px}
</style>
