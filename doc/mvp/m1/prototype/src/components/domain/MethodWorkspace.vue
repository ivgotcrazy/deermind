<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainData, blankMethod, blankStep, readMethod, saveEntity, collectKnowledge, nextLabel, stepKinds, type Kind, type Step, type Method } from '../../model/domain';
const props=defineProps<{domainId:string;objectId:string;initial?:Method}>();
const emit=defineEmits<{saved:[id:string];open:[kind:Kind,id:string];back:[]}>();
const empty=blankMethod(props.domainId);
const method=computed(()=>readMethod(domainData.methods.find(m=>m.id===props.objectId&&m.domainId===props.domainId)||props.initial||empty));
const editing=ref(props.objectId==='new'),draft=ref(readMethod(method.value)),error=ref('');
const tasks=computed(()=>domainData.tasks.filter(t=>t.domainId===props.domainId));
const linked=computed(()=>tasks.value.filter(t=>t.methods.includes(method.value.id)));
const parents=computed(()=>domainData.methods.filter(m=>m.domainId===props.domainId&&m.steps.some(s=>s.divided&&s.solutionId===method.value.id)));
const selectedTasks=ref(linked.value.map(t=>t.id));
const knowledge=computed(()=>domainData.knowledge.filter(k=>k.domainId===props.domainId));
const collected=computed(()=>collectKnowledge([method.value.id],props.domainId));
const examples=computed(()=>domainData.instances.filter(q=>q.domainId===props.domainId&&q.solutions.some(s=>s.methodId===method.value.id)));
const taskQuery=ref(''),kcQuery=ref('');
const taskChoices=computed(()=>tasks.value.filter(t=>t.name.includes(taskQuery.value)));
const kcChoices=computed(()=>knowledge.value.filter(k=>k.name.includes(kcQuery.value)));
const destinations=computed(()=>[
  {value:'$next',label:'下一步（末步后核对完成条件）'},{value:'$success',label:'核对成功条件并结束'},{value:'$stop',label:'未解决，停止当前方法'},
  ...draft.value.steps.map((s,i)=>({value:s.key!,label:'步骤 '+(i+1)+' · '+(s.title||'未命名')})),
]);
function edit(){draft.value=readMethod(method.value);selectedTasks.value=linked.value.map(t=>t.id);editing.value=true;error.value='';}
function cancel(){editing.value=false;if(props.objectId==='new')emit('back');}
function save(){
  if(!draft.value.name.trim()){error.value='请填写方法名称。';return;}
  draft.value.steps.forEach(s=>{if(s.kind!=='process')s.divided=false;if(!s.divided){s.taskId='';s.solutionId='';}});
  const next=saveEntity(domainData.methods,draft.value);
  for(const t of tasks.value){const wanted=selectedTasks.value.includes(t.id),has=t.methods.includes(next.id);if(wanted!==has)saveEntity(domainData.tasks,{...t,methods:wanted?[...t.methods,next.id]:t.methods.filter(x=>x!==next.id)});}
  editing.value=false;emit('saved',next.id);
}
function pathNames(path:string[]){return path.map(key=>domainData.methods.find(m=>m.id===key)?.name||key).join(' → ');}
function childMethods(taskId:string){const t=tasks.value.find(x=>x.id===taskId);return domainData.methods.filter(m=>m.domainId===props.domainId&&m.id!==method.value.id&&t?.methods.includes(m.id));}
function changeKind(s:Step){if(s.kind!=='process')s.divided=false;}
function goStep(key:string){document.getElementById(key.startsWith('$')?'method-ending':'flow-'+key)?.scrollIntoView({behavior:'smooth',block:'start'});}
function destination(key:string,index:number){return key==='$next'?(method.value.steps[index+1]?'步骤 '+(index+2)+' · '+method.value.steps[index+1].title:'核对成功条件并结束'):nextLabel(method.value,key);}
function follow(key:string,index:number){goStep(key==='$next'?(method.value.steps[index+1]?.key||'$success'):key);}
</script>
<template><div>
  <header class="page-header"><div><span class="object-type">SolutionTemplate <span v-if="method.version">· {{method.id}} · v{{method.version}}</span></span><h2>{{method.name||'新建方法模板'}}</h2><p class="page-desc">描述如何完成任务；教学引导方式不在这里配置。</p></div><div class="button-row"><button class="btn" @click="emit('back')">返回方法列表</button><button v-if="!editing" class="btn primary" @click="edit">编辑方法</button></div></header>
  <p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <template v-if="editing"><form @submit.prevent="save">
    <section class="panel"><h3>方法定义</h3><label>方法名称<input v-model="draft.name" required/></label><label>方法思路<textarea v-model="draft.description" rows="2"/></label><label>适用条件<textarea v-model="draft.conditions" rows="2"/></label><div class="edit-pair"><label>输入<textarea v-model="draft.inputs" rows="3"/></label><label>输出<textarea v-model="draft.output" rows="3"/></label></div></section>
    <section class="panel"><h3>适用任务</h3><p class="muted">选中的任务会将此方法列入方法表。</p><label class="search-label">查找任务<input v-model="taskQuery" type="search"/></label><div class="picker-list"><label v-for="t in taskChoices" :key="t.id" class="check-line"><input v-model="selectedTasks" type="checkbox" :value="t.id"/>{{t.name}}</label></div><p v-if="!tasks.length" class="muted">还没有任务，可以先保存方法，再创建任务并关联。</p></section>
    <section class="panel"><div class="row-between"><h3>求解步骤</h3><button type="button" class="btn" @click="draft.steps.push(blankStep())">添加步骤</button></div>
      <p class="muted">顺序处理可以调用子任务；条件选择只走符合事实的分支；分类讨论处理全部情况；复查根据结果继续或停止。</p>
      <div v-for="(step,index) in draft.steps" :key="step.key" class="entry-editor">
        <div class="row-between"><strong>步骤 {{index+1}}</strong><div class="button-row"><button type="button" class="btn" :disabled="index===0" :aria-label="'上移步骤'+(index+1)" @click="[draft.steps[index-1],draft.steps[index]]=[draft.steps[index],draft.steps[index-1]]">↑</button><button type="button" class="text-link" @click="draft.steps.splice(index,1)">移除步骤 {{index+1}}</button></div></div>
        <div class="edit-pair"><label>步骤名称<input v-model="step.title" :aria-label="'步骤'+(index+1)+'名称'"/></label><label>处理方式<select v-model="step.kind" :aria-label="'步骤'+(index+1)+'类型'" @change="changeKind(step)"><option v-for="(name,key) in stepKinds" :key="key" :value="key">{{name}}</option></select></label></div>
        <div class="edit-pair"><label>使用的输入<textarea v-model="step.inputs" :aria-label="'步骤'+(index+1)+'输入'" rows="2" placeholder="来自题目、前序步骤或本次检查的什么信息"/></label><label>产出结果<textarea v-model="step.output" :aria-label="'步骤'+(index+1)+'输出'" rows="2" placeholder="结果名称、含义及后续用途"/></label></div>
        <label>处理说明<textarea v-model="step.detail" :aria-label="'步骤'+(index+1)+'处理'" rows="3"/></label>
        <template v-if="step.kind==='process'">
          <label class="check-line"><input v-model="step.divided" type="checkbox" :aria-label="'步骤'+(index+1)+'分解为子任务'"/>这个步骤需要分解为子任务</label>
          <div v-if="step.divided" class="submethod"><div class="edit-pair"><label>子任务<select v-model="step.taskId" :aria-label="'步骤'+(index+1)+'子任务'" @change="step.solutionId=''"><option value="">请选择</option><option v-for="t in tasks" :key="t.id" :value="t.id">{{t.name}}</option></select></label><label>选用子方法<select v-model="step.solutionId" :aria-label="'步骤'+(index+1)+'子方法'"><option value="">请选择</option><option v-for="m in childMethods(step.taskId)" :key="m.id" :value="m.id">{{m.name}}</option></select></label></div><p class="muted">上方输入、输出分别说明传入子方法的参数，以及返回结果的用途。</p><p v-if="!childMethods(step.taskId).length" class="muted">先为子任务关联方法；尚未选定时可以保存，但当前方法不完整。</p></div>
        </template>
        <template v-else>
          <p class="flow-mode">{{step.kind==='cases'?'全部情况逐项处理，汇总后再继续。':'按当前事实选择符合条件的一行；返回前面的步骤表示复查。'}}</p>
          <div v-for="(route,ri) in step.routes" :key="ri" class="route-editor">
            <div class="row-between"><strong>{{step.kind==='cases'?'情况':'分支'}} {{ri+1}}</strong><button type="button" class="text-link" :aria-label="'移除步骤'+(index+1)+'分支'+(ri+1)" @click="step.routes!.splice(ri,1)">移除</button></div>
            <label>条件<textarea v-model="route.condition" :aria-label="'步骤'+(index+1)+'分支'+(ri+1)+'条件'" rows="2"/></label>
            <div class="edit-pair"><label>如何处理<textarea v-model="route.action" :aria-label="'步骤'+(index+1)+'分支'+(ri+1)+'处理'" rows="2"/></label><label>得到什么<textarea v-model="route.result" :aria-label="'步骤'+(index+1)+'分支'+(ri+1)+'结果'" rows="2"/></label></div>
            <label v-if="step.kind!=='cases'">之后去哪<select v-model="route.next" :aria-label="'步骤'+(index+1)+'分支'+(ri+1)+'去向'"><option v-if="!destinations.some(d=>d.value===route.next)" :value="route.next">去向缺失，请重新选择</option><option v-for="d in destinations" :key="d.value" :value="d.value">{{d.label}}</option></select></label>
          </div>
          <button type="button" class="btn" :aria-label="'步骤'+(index+1)+'添加分支'" @click="step.routes!.push({condition:'',action:'',result:'',next:'$next'})">{{step.kind==='cases'?'添加情况':'添加分支'}}</button>
          <label>{{step.kind==='cases'?'覆盖与汇总':'无法判断时怎么办'}}<textarea v-model="step.coverage" :aria-label="'步骤'+(index+1)+'分支说明'" rows="2" :placeholder="step.kind==='cases'?'说明完整分类、临界值及结果汇总':'条件冲突或信息不足时如何处理'"/></label>
        </template>
        <label v-if="step.kind==='process'||step.kind==='cases'">{{step.kind==='cases'?'全部情况汇总后':'完成后'}}<select v-model="step.next" :aria-label="'步骤'+(index+1)+'去向'"><option v-if="!destinations.some(d=>d.value===step.next)" :value="step.next">去向缺失，请重新选择</option><option v-for="d in destinations" :key="d.value" :value="d.value">{{d.label}}</option></select></label>
      </div><p v-if="!draft.steps.length" class="empty">添加一步，说明方法如何处理输入并得到结果。</p>
    </section>
    <section class="panel"><h3>结束条件</h3><p class="muted">成功条件对应任务的完成要求；未解决时也需要明确停止。</p><label>成功完成<textarea v-model="draft.ending!.success" rows="3"/></label><label>无法继续时停止<textarea v-model="draft.ending!.stop" rows="3"/></label></section>
    <section class="panel"><h3>直接依赖的知识</h3><p class="muted">仅选择当前方法直接使用的 KC，子方法的知识会自动汇总。</p><label class="search-label">查找知识<input v-model="kcQuery" type="search"/></label><div class="picker-list"><label v-for="k in kcChoices" :key="k.id" class="check-line"><input v-model="draft.kc" type="checkbox" :value="k.id"/>{{k.name}}</label></div><p v-if="!knowledge.length" class="muted">还没有知识成分，可先保存，之后补齐。</p></section>
    <footer class="editor-footer"><span class="muted">保存草稿；缺失关系和流程信息会在详情中提示。</span><button type="button" class="btn" @click="cancel">取消</button><button class="btn primary">保存方法</button></footer>
  </form></template>
  <template v-else>
    <div v-if="collected.issues.length" class="callout amber" role="status"><strong>方法尚未完整</strong><ul><li v-for="issue in collected.issues" :key="issue">{{issue}}</li></ul></div>
    <section class="panel"><h3>方法定义</h3><dl class="field-list"><dt>思路</dt><dd>{{method.description||'尚未填写'}}</dd><dt>适用条件</dt><dd>{{method.conditions||'尚未填写'}}</dd><dt>输入</dt><dd>{{method.inputs||'尚未填写'}}</dd><dt>输出</dt><dd>{{method.output||'尚未填写'}}</dd></dl></section>
    <section class="panel"><h3>适用任务</h3><div class="relation-list"><button v-for="t in linked" :key="t.id" class="text-link" @click="emit('open','task',t.id)">{{t.name}} →</button></div><p v-if="!linked.length" class="muted">尚未关联任务。</p><div v-if="parents.length" class="parent-methods"><p class="muted">被以下方法作为子方法调用：</p><div class="relation-list"><button v-for="p in parents" :key="p.id" class="text-link" @click="emit('open','solution',p.id)">{{p.name}} →</button></div></div></section>
    <section class="panel"><h3>求解过程</h3><p class="muted">从步骤 1 开始，按条件决定后续去向。以下为方法定义，不是执行记录。</p>
      <nav class="flow-index" aria-label="求解步骤索引"><button v-for="(s,i) in method.steps" :key="s.key" class="btn" @click="goStep(s.key!)">{{i+1}} · {{s.title||'未命名'}}</button><button class="btn" @click="goStep('$success')">结束条件</button></nav>
      <article v-for="(step,index) in method.steps" :id="'flow-'+step.key" :key="step.key" class="flow-step" :aria-label="'步骤'+(index+1)+'详情'">
        <div class="row-between"><h4>{{index+1}}．{{step.title||'未命名步骤'}}</h4><span class="badge">{{step.divided?'调用子任务':stepKinds[step.kind||'process']}}</span></div>
        <dl class="field-list"><dt>{{step.divided?'传入子方法':'使用的输入'}}</dt><dd>{{step.inputs||'尚未补充'}}</dd><dt>{{step.divided?'返回结果':'产出结果'}}</dt><dd>{{step.output||'尚未补充'}}</dd></dl><p class="multiline">{{step.detail}}</p>
        <div v-if="step.divided" class="submethod"><span>子任务：</span><button v-if="step.taskId" class="text-link" @click="emit('open','task',step.taskId)">{{tasks.find(t=>t.id===step.taskId)?.name||'引用缺失'}}</button><span v-else>尚未选择</span><br/><span>选用方法：</span><button v-if="step.solutionId" class="text-link" @click="emit('open','solution',step.solutionId)">{{domainData.methods.find(m=>m.id===step.solutionId)?.name||'引用缺失'}}</button><span v-else>尚未选择</span></div>
        <template v-if="step.kind!=='process'"><p class="flow-mode">{{step.kind==='cases'?'全部情况都要处理，再汇总结果':'根据检查结果选择分支'}}</p><div class="table-scroll"><table class="data-table flow-routes" :aria-label="'步骤'+(index+1)+'分支'"><thead><tr><th>条件</th><th>处理</th><th>结果</th><th v-if="step.kind!=='cases'">之后去哪</th></tr></thead><tbody><tr v-for="(r,ri) in step.routes" :key="ri"><td>{{r.condition||'待补充'}}</td><td>{{r.action||'待补充'}}</td><td>{{r.result||'待补充'}}</td><td v-if="step.kind!=='cases'"><button class="text-link" @click="follow(r.next,index)">{{destination(r.next,index)}} →</button></td></tr></tbody></table></div><p class="multiline"><strong>{{step.kind==='cases'?'覆盖与汇总：':'无法判断时：'}}</strong>{{step.coverage||'尚未补充'}}</p></template>
        <p v-if="step.kind==='process'||step.kind==='cases'" class="flow-next">{{step.kind==='cases'?'汇总后':'完成后'}}：<button class="text-link" @click="follow(step.next!,index)">{{destination(step.next!,index)}} →</button></p>
      </article><p v-if="!method.steps.length" class="muted">尚无步骤。</p>
    </section>
    <section id="method-ending" class="panel"><h3>结束条件</h3><dl class="field-list"><dt>成功完成</dt><dd>{{method.ending?.success||'尚未补充'}}</dd><dt>无法继续时停止</dt><dd>{{method.ending?.stop||'尚未补充'}}</dd></dl></section>
    <section v-if="examples.length" class="panel"><h3>具体实例</h3><p class="muted">以下是预写的 mock 解答，用于对照方法定义；没有执行计算、调用 LLM 或连接集群。</p><details v-for="q in examples" :key="q.id"><summary>展开实例走查 · {{q.id}}</summary><p class="multiline">{{q.question}}</p><p class="multiline">{{q.solutions.find(s=>s.methodId===method.id)?.working}}</p><button class="text-link" @click="emit('open','task',q.taskId)">查看所属任务 →</button></details></section>
    <section class="panel"><h3>知识依据</h3><p class="muted">汇总当前方法及选定子方法可能使用的知识；不代表一次求解实际使用了全部知识。</p><table v-if="collected.rows.length" class="data-table"><thead><tr><th>知识成分</th><th>引用路径</th></tr></thead><tbody><tr v-for="row in collected.rows" :key="row.knowledge.id"><td><button class="text-link model-name" @click="emit('open','kc',row.knowledge.id)">{{row.knowledge.name}}</button></td><td><div v-for="(path,index) in row.paths" :key="index">{{path.length===1?'直接依赖':'经子方法：'+pathNames(path.slice(1))}}</div></td></tr></tbody></table><p v-else class="muted">尚未提供可汇总的知识依据。</p></section>
  </template>
</div></template>
