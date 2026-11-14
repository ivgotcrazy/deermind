<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import { domainData, clone, blankInstance, saveEntity, instanceIssues, instanceSignature, instanceStatus, type Task, type Instance, type Kind } from '../../model/domain';
import ContentVisuals from '../ContentVisuals.vue';
import ContentVisualEditor from '../ContentVisualEditor.vue';
import type { ContentVisual } from '../../model/content-visuals';
import WorkbenchDialog from '../WorkbenchDialog.vue';
import ReviewBlockView from '../ReviewBlockView.vue';
const props=defineProps<{task:Task;initial?:Instance}>();
const emit=defineEmits<{open:[kind:Kind,id:string];saved:[id:string]}>();
const query=ref(''),source=ref(''),page=ref(1),notice=ref('');
const selected=ref<Instance|null>(null),editing=ref(false),preview=ref(false),error=ref('');
const outcome=ref('pass');
const visualEditor=ref<{value?:ContentVisual;owner:string}|null>(null);
function visualTarget(owner:string){return owner==='task'?selected.value:selected.value?.solutions.find(s=>(s.id||s.methodId)===owner);}
function saveVisual(value:ContentVisual){const target=visualTarget(visualEditor.value!.owner);if(target){const list=target.visuals??=[],i=list.findIndex(v=>v.id===value.id);if(i<0)list.push(value);else list[i]=value;}visualEditor.value=null;}
function removeVisual(owner:string,key:string){const target=visualTarget(owner);if(target)target.visuals=target.visuals?.filter(v=>v.id!==key);}

const rows=computed(()=>domainData.instances.filter(q=>q.domainId===props.task.domainId&&q.taskId===props.task.id&&(!source.value||q.source===source.value)&&(q.question+' '+q.id).includes(query.value.trim())));
const filtered=computed(()=>rows.value.slice((page.value-1)*10,page.value*10));
const methods=computed(()=>domainData.methods.filter(m=>m.domainId===props.task.domainId&&props.task.methods.includes(m.id)));
const inputs=computed(()=>props.task.parameters.filter(p=>p.role==='题目已给定'));
const unresolved=computed(()=>props.task.parameters.filter(p=>p.role!=='题目已给定'));
function open(q?:Instance,edit=false){selected.value=q?clone(q):blankInstance(props.task);editing.value=edit||!q;preview.value=false;error.value='';outcome.value='pass';}
onMounted(()=>{if(props.initial)open(props.initial,true);});
function toggleMethod(key:string,checked:boolean){if(!selected.value)return;if(checked)selected.value.solutions.push({methodId:key,working:''});else selected.value.solutions=selected.value.solutions.filter(s=>s.methodId!==key);}
function methodName(key:string){return domainData.methods.find(m=>m.id===key)?.name||'方法引用缺失';}
function save(checked:boolean){
  const q=selected.value!;
  if(!q.question.trim()){error.value='请先填写题面。';return;}
  if(checked){
    const issues=instanceIssues(q);if(issues.length){error.value='尚不能作为可用题目：'+issues.join('；');return;}
    if(outcome.value!=='pass'){
      error.value=outcome.value==='mismatch'?'模拟检查：任务归类不符，不能保存为当前任务的可用实例。':outcome.value==='unclear'?'模拟检查：题目条件不清，不能保存为可用实例。':'模拟检查：参考解答存在问题，不能保存为可用实例。';return;
    }
    q.checkedSignature=instanceSignature(q);q.checkedAt=new Date().toLocaleString('zh-CN');
  }else{q.checkedSignature='';q.checkedAt='';}
  saveEntity(domainData.instances,q);notice.value=checked?'已保存为可用题目（mock）。归类和解答检查为演示结果，不是真实模型判断。':'实例草稿已保存，尚未作为可用题目。';selected.value=null;query.value='';source.value='';page.value=1;emit('saved',q.id);
}
function addTable(){selected.value!.table={headers:['原量','增加比例'],rows:[['','']]};}
</script>
<template><div>
  <div class="object-toolbar"><div class="instance-filters"><label>搜索实例<input v-model="query" type="search" placeholder="题面或编号" @input="page=1"/></label><label>来源<select v-model="source" @change="page=1"><option value="">全部</option><option>人工编写</option><option>教材导入</option></select></label></div><button class="btn primary" @click="open()">新建题目</button></div>
  <p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <p class="muted">题目属于当前任务；学生每次的展示和作答另记。教材导入和手动编写均保留各自来源，检查结果为 mock。</p>
  <section class="panel"><table v-if="rows.length" class="data-table"><thead><tr><th>题目</th><th>给定信息</th><th>来源</th><th>准备情况</th><th>操作</th></tr></thead><tbody><tr v-for="q in filtered" :key="q.id"><td class="question-cell"><button class="text-link" @click="open(q)">{{q.question}}</button><small>{{q.id}} · v{{q.version}}</small></td><td><div v-for="(value,key) in q.bindings" :key="key">{{key}} = {{value||'未填'}}</div></td><td>{{q.source}}</td><td><span class="badge" :class="{warning:instanceStatus(q)!=='可用（mock）'}">{{instanceStatus(q)}}</span></td><td><button class="text-link" :aria-label="'编辑题目 '+q.id" @click="open(q,true)">编辑</button></td></tr></tbody></table><div v-else class="empty">{{query||source?'没有匹配的题目。':'还没有题目。先新建一道具体题目，描述任务要求的具体情境。'}}</div><div v-if="rows.length>10" class="pagination"><button class="btn" :disabled="page===1" @click="page--">上一页</button><span>{{page}} / {{Math.ceil(rows.length/10)}}</span><button class="btn" :disabled="page*10>=rows.length" @click="page++">下一页</button></div></section>
  <WorkbenchDialog v-if="selected" :title="preview?'学生看到的题目':editing?(selected.version?'编辑题目':'新建题目'):'题目详情'" wide @close="selected=null">
    <template v-if="selected.reviewContent">
      <p class="muted">教材核对工作区保存的内容快照。模型关联不等于已完成教学与检测准备。</p>
      <section v-for="part in selected.reviewContent.filter(p=>!preview||p.role==='question')" :key="part.id" class="entry-editor"><h3>{{part.name}}</h3><ReviewBlockView v-for="block in part.blocks" :key="block.id" :block="block"/></section>
      <footer class="dialog-footer"><button class="btn" @click="preview=!preview">{{preview?'返回完整内容':'预览学生题面'}}</button><a v-if="selected.reviewSource" class="btn primary" :href="'#/textbooks?tab=import&source='+encodeURIComponent(selected.reviewSource.importId)+'&item='+encodeURIComponent(selected.reviewSource.itemId)">返回教材核对处修改</a></footer>
    </template>
    <template v-else-if="preview"><section class="student-question" data-testid="student-question"><p class="multiline">{{selected.question||'尚未填写题面'}}</p><ContentVisuals :items="selected.visuals"/><table v-if="selected.table" class="data-table"><thead><tr><th v-for="(h,index) in selected.table.headers" :key="index">{{h}}</th></tr></thead><tbody><tr v-for="(row,index) in selected.table.rows" :key="index"><td v-for="(cell,j) in row" :key="j">{{cell}}</td></tr></tbody></table></section><footer class="dialog-footer"><button class="btn" @click="preview=false">返回{{editing?'编辑':'题目详情'}}</button></footer></template>
    <template v-else><p class="muted">所属任务：{{task.name}} · v{{task.version}}</p><p v-if="error" class="callout danger" role="alert">{{error}}</p>
      <template v-if="editing">
        <label>题目内容<textarea v-model="selected.question" rows="4" placeholder="完整已知条件、所求及需要学生承担的解释责任"/></label>
        <div class="row-between"><h3>题面表格</h3><button v-if="!selected.table" class="btn" @click="addTable">添加表格</button><button v-else class="text-link" @click="selected.table=null">移除表格</button></div>
        <div v-if="selected.table" class="entry-editor"><p class="muted">表头、数据和空白均属于题面，不能把待求答案补进来。</p><div class="table-scroll"><table class="data-table editable-table"><thead><tr><th v-for="(_,j) in selected.table.headers" :key="j"><input v-model="selected.table.headers[j]" :aria-label="'题面表头'+(j+1)"/></th><th>操作</th></tr></thead><tbody><tr v-for="(row,i) in selected.table.rows" :key="i"><td v-for="(_,j) in row" :key="j"><input v-model="row[j]" :aria-label="'题面表格'+(i+1)+'行'+(j+1)+'列'"/></td><td><button class="text-link" @click="selected.table.rows.splice(i,1)">移除行 {{i+1}}</button></td></tr></tbody></table></div><div class="button-row"><button class="btn" @click="selected.table.rows.push(selected.table.headers.map(()=>''))">添加行</button><button class="btn" @click="selected.table.headers.push('');selected.table.rows.forEach(row=>row.push(''))">添加列</button><button class="btn" :disabled="selected.table.headers.length<2" @click="selected.table.headers.pop();selected.table.rows.forEach(row=>row.pop())">移除末列</button></div></div>
        <h3>题面图表</h3><ContentVisuals :items="selected.visuals" editing metadata @edit="value=>visualEditor={value,owner:'task'}" @remove="key=>removeVisual('task',key)"/><button class="btn" @click="visualEditor={owner:'task'}">添加题面图表</button><p class="muted">仅放题目条件及作答对象。原型支持关系图与表格；其他必要图形只存说明时仍属于待补绘。</p>
        <h3>本题已给定的信息</h3><p class="muted">填写这道题固定给出的内容。待研究的变量和需要调查的信息不在这里预填答案。</p><div class="edit-pair"><label v-for="p in inputs" :key="p.symbol">{{p.symbol}} · {{p.name}}<input v-model="selected.bindings[p.symbol]" :aria-label="'绑定参数 '+p.symbol"/><small>{{p.condition}}</small></label></div><p v-if="!inputs.length" class="muted">任务未声明参数表；直接核对题意、条件和所需表现即可。</p>
        <template v-if="unresolved.length"><h3>留给学习者处理的内容</h3><table class="data-table" aria-label="待研究与待查信息"><thead><tr><th>对象／变量</th><th>用途</th><th>约束</th></tr></thead><tbody><tr v-for="p in unresolved" :key="p.symbol"><td>{{p.symbol}} · {{p.name}}</td><td>{{p.role}}</td><td>{{p.condition}}</td></tr></tbody></table></template>
        <label>参考答案／评分要点<textarea v-model="selected.answer" rows="3"/></label><h3>参考方法与具体解答</h3><p class="muted">只选择对本题实际适用的方法，解答不会进入学生题面预览。</p>
        <div v-for="m in methods" :key="m.id" class="entry-editor"><label class="check-line"><input type="checkbox" :checked="selected.solutions.some(s=>s.methodId===m.id)" @change="toggleMethod(m.id,($event.target as HTMLInputElement).checked)"/>{{m.name}}</label><template v-for="s in selected.solutions.filter(s=>s.methodId===m.id)" :key="s.id||s.methodId"><p v-if="s.id" class="muted">参考解法 · {{s.id}} · {{s.origin||'来源未记录'}}<br/>{{s.sourceNote}}</p><label>具体解答<textarea v-model="s.working" :aria-label="m.name+'的具体解答'" rows="3"/></label><ContentVisuals :items="s.visuals" editing metadata @edit="value=>visualEditor={value,owner:s.id||s.methodId}" @remove="key=>removeVisual(s.id||s.methodId,key)"/><button class="btn" @click="visualEditor={owner:s.id||s.methodId}">添加解法图表</button></template></div><p v-if="!methods.length" class="callout amber">任务还没有关联方法，请先在任务的“方法”页补齐。</p>
        <div v-for="s in selected.solutions.filter(s=>!methods.some(m=>m.id===s.methodId))" :key="s.id||s.methodId" class="callout amber">{{methodName(s.methodId)}}已不在任务的方法中。<button class="text-link" @click="selected.solutions=selected.solutions.filter(x=>x!==s)">移除失效引用</button></div>
        <div class="edit-pair"><label>来源类型<select v-model="selected.source"><option>人工编写</option><option>教材导入</option></select></label><label>来源说明<input v-model="selected.sourceNote" placeholder="编写说明，或教材名称及书页；不编造来源"/></label></div>
        <details class="mock-tools"><summary>模拟语义检查结果</summary><p>只演示交互，不运行 LLM，不用关键词判断题意。实际结果在工程阶段接入。</p><label>本次模拟结果<select v-model="outcome" aria-label="本次模拟结果"><option value="pass">归类及解答通过</option><option value="mismatch">任务归类不符</option><option value="unclear">题目条件不清</option><option value="answer">参考解答有问题</option></select></label></details>
        <footer class="dialog-footer"><button class="btn" @click="preview=true">预览学生题面</button><button class="btn" @click="save(false)">保存草稿</button><button class="btn primary" @click="save(true)">检查并保存为可用题</button></footer>
      </template>
      <template v-else><p class="multiline question-title">{{selected.question}}</p><ContentVisuals :items="selected.visuals" metadata/><span class="badge">{{instanceStatus(selected)}}</span><p v-if="instanceStatus(selected)==='需重新检查'" class="callout amber">题目或关联定义已变化，先前的 mock 检查不能继续沿用。</p><dl class="field-list"><dt>参数</dt><dd><div v-for="(value,key) in selected.bindings" :key="key">{{key}} = {{value}}</div></dd><dt>参考答案／评分要点</dt><dd>{{selected.answer||'尚未填写'}}</dd><dt>来源</dt><dd>{{selected.source}} · {{selected.sourceNote||'尚未填写'}}</dd><dt>检查</dt><dd>{{selected.checkedAt?'最近 mock 检查：'+selected.checkedAt:'尚未检查'}}。题意和解答未接入真实语义判断。</dd></dl><section v-for="s in selected.solutions" :key="s.id||s.methodId" class="entry-editor"><button class="text-link model-name" @click="emit('open','solution',s.methodId)">{{methodName(s.methodId)}} →</button><p v-if="s.id" class="muted">参考解法 · {{s.id}} · {{s.origin||'来源未记录'}}<br/>{{s.sourceNote}}</p><p class="multiline">{{s.working}}</p><ContentVisuals :items="s.visuals" metadata/></section><footer class="dialog-footer"><button class="btn" @click="preview=true">预览学生题面</button><button class="btn primary" @click="editing=true;error=''">编辑题目</button></footer></template>
    </template>
  </WorkbenchDialog>
<ContentVisualEditor v-if="visualEditor" :value="visualEditor.value" :owner="visualEditor.owner" task-owner="task" @save="saveVisual" @close="visualEditor=null"/>
</div></template>
