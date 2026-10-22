import { reactive, ref, toRaw } from 'vue';
import { seed } from './seed';
import { migrateDirectEditing } from './migration';
import { editableKinds, personalKinds, objectKey, type AdminState, type ModelObject, type Kind, type Check } from './model';
export const STORAGE_KEY = 'deermind-next-admin-workbench-v1';
export const storageError = ref('');
export const clone = <T>(x:T):T => JSON.parse(JSON.stringify(x));
let initial = seed();
try {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    const data = JSON.parse(saved);
    if(![1,2,3].includes(data.schema) || !Array.isArray(data.objects) || !data.invalidated || !Array.isArray(data.issues)) throw Error();
    if(data.schema<3) {
      if(!localStorage.getItem(STORAGE_KEY+'.before-direct-editing')) localStorage.setItem(STORAGE_KEY+'.before-direct-editing',saved);
      initial=migrateDirectEditing(data);
      for(const draft of initial.drafts) {
        try {
          const raw=sessionStorage.getItem('admin-candidate-draft:'+draft.sourceIssueId);
          const old=data.issues.find((i:any)=>i.id===draft.sourceIssueId);
          const pending=raw&&JSON.parse(raw);
          if(pending?.candidate&&pending.baseline===JSON.stringify(old?.candidate)) {
            draft.object={...pending.candidate,domainId:draft.object.domainId};
          }
        } catch { /* Original session draft is retained for recovery. */ }
      }
    } else {
      if(!Array.isArray(data.domains) || !Array.isArray(data.drafts) || !Array.isArray(data.changes) || !Array.isArray(data.annotations)) throw Error();
      initial=data;
    }
  }
} catch { storageError.value='本地工作记录无法读取，原记录未覆盖。请先导出浏览器中的原始记录，再检查恢复；当前只读显示初始示例。'; }
export const state = reactive<AdminState>(initial);
export const notice = ref('');
export const mode = ref<'demo'|'real'>('demo');
export function transact(fn:(s:AdminState)=>void) {
  if(storageError.value) throw Error(storageError.value);
  const saved = localStorage.getItem(STORAGE_KEY);
  if(saved && JSON.parse(saved).revision !== state.revision) throw Error('另一窗口已更新工作记录。请刷新本页后再操作，避免覆盖。');
  const next = clone(toRaw(state)); fn(next); next.revision++;
  try { localStorage.setItem(STORAGE_KEY,JSON.stringify(next)); } catch { throw Error('浏览器保存失败，本次操作未提交。请导出已有记录并检查存储空间。'); }
  Object.assign(state,next);
}
export function act(fn:()=>void) { notice.value=''; try { fn(); } catch(e) { notice.value=e instanceof Error?e.message:String(e); } }
export function latest(id:string, s:AdminState=state):ModelObject|undefined { return s.objects.filter(o=>o.id===id).sort((a,b)=>b.version-a.version)[0]; }
export function resolve(ref:string, bindings?:Record<string,number>, s:AdminState=state):ModelObject|undefined {
  const [id,version] = ref.split('@');
  const exact = version ? Number(version) : bindings?.[id!];
  return exact!==undefined ? s.objects.find(o=>o.id===id && o.version===exact) : bindings ? undefined : latest(id!,s);
}
export function catalog(s:AdminState=state) { return s.objects.filter(o=>latest(o.id,s)?.version===o.version); }
export function domain(id:string,s:AdminState=state) { return s.domains.find(d=>d.id===id); }
export function createDomain(name:string,scope:string,description:string) {
  const values={name:name.trim(),scope:scope.trim(),description:description.trim()};
  if(!values.name || !values.scope) throw Error('请填写领域名称和覆盖范围。');
  if(values.name.length>80 || values.scope.length>1000 || values.description.length>2000) throw Error('名称最多 80 字，覆盖范围最多 1000 字，说明最多 2000 字。');
  const id='DOM-'+crypto.randomUUID().toUpperCase();
  transact(s=>{
    const normalized=(v:string)=>v.normalize('NFKC').toLocaleLowerCase();
    if(s.domains.some(d=>normalized(d.name)===normalized(values.name))) throw Error('已有同名领域，请使用可区分的名称。');
    s.domains.unshift({id,...values,createdAt:new Date().toISOString()});
  });
  return id;
}
export function dependents(id:string,s:AdminState=state) { return catalog(s).filter(o=>o.relations.some(r=>r.ref.split('@')[0]===id)); }
export function scopeBindings(scope:string) { return state.spaces.find(s=>s.id===scope)?.adopted || state.activities.find(a=>a.id===scope)?.versions; }
export function objectActivity(key:string) { return state.activities.find(a=>a.objects.includes(key)); }
export function canAccess(ref:string, dataMode='demo') { return state.access.some(a=>a.ref===ref && a.mode===dataMode); }
export function recordAccess(ref:string,purpose:string,dataMode='demo') {
  if(!purpose.trim()) throw Error('请填写本次查看用途。');
  transact(s=>s.access.push({at:new Date().toISOString(),ref,purpose:purpose.trim(),mode:dataMode}));
}

export function updateDomain(id:string,name:string,scope:string,description:string,baseVersion:number) {
  const values={name:name.trim(),scope:scope.trim(),description:description.trim()};
  if(!values.name||!values.scope)throw Error('请填写领域名称和覆盖范围。');
  if(values.name.length>80||values.scope.length>1000||values.description.length>2000)throw Error('名称最多 80 字，覆盖范围最多 1000 字，说明最多 2000 字。');
  transact(s=>{
    const d=domain(id,s);if(!d||(d.version||1)!==baseVersion)throw Error('领域已变化，请重新打开编辑。');
    if(s.domains.some(o=>o.id!==id&&o.name.normalize('NFKC').toLowerCase()===values.name.normalize('NFKC').toLowerCase()))throw Error('已有同名领域。');
    if(d.name===values.name&&d.scope===values.scope&&d.description===values.description)return;
    (d.history??=[]).push({name:d.name,scope:d.scope,description:d.description,version:d.version||1,at:new Date().toISOString()});
    Object.assign(d,values,{version:(d.version||1)+1});
  });
}
export const fieldsByKind:Partial<Record<Kind,Record<string,string>>>={
  task:{完成责任:'',参数范围:'',排除范围:''},solution:{适用条件:'',方法:''},kc:{定义:'',适用范围:''},
  material:{来源:'',内容:''},chapter:{原始材料:'',核对文本:'',待核对:'无'},mapping:{映射依据:'',核对说明:'无'},
  target:{方法选择:'',达标条件:'',裁剪依据:'保留默认四个方面'},
};
export const relationKinds:Record<string,Kind[]>={'可用方法':['solution'],'适用任务':['task'],'分解为子任务':['task'],'任务理解依赖':['kc'],'方法依赖':['kc'],'先修知识':['kc'],'映射任务':['task'],'允许方法':['solution'],'采用 Claim':['claim'],'精确绑定任务版本':['task'],'教材章节':['chapter'],'所属材料':['material'],'章节映射':['mapping'],'适用章节':['chapter'],'包含章节':['chapter'],'可选目标':['target'],'证据解释规则':['evidence-rule'],'推断规则':['inference-rule']};
export const relationLabels:Partial<Record<Kind,string[]>>={task:['可用方法','任务理解依赖'],solution:['适用任务','分解为子任务','方法依赖'],kc:['先修知识'],material:['包含章节'],chapter:['所属材料','章节映射','可选目标'],mapping:['教材章节','映射任务','允许方法'],target:['适用章节','采用 Claim','允许方法'],claim:['精确绑定任务版本','证据解释规则','推断规则'],'evidence-rule':[],'inference-rule':[]};
export function blankDefinition(kind:Kind,domainId='',parent=''):ModelObject {
  if(!editableKinds.includes(kind))throw Error('该类型请在评估模型管理中导入定义包。');
  if(['task','solution','kc'].includes(kind)&&!domain(domainId))throw Error('请先进入一个有效领域。');
  const prefix:Partial<Record<Kind,string>>={task:'T',solution:'S',kc:'KC',material:'MAT',chapter:'CH',mapping:'MAP',target:'TG'};
  const relation=kind==='chapter'?'所属材料':kind==='mapping'?'教材章节':kind==='target'?'适用章节':'';
  return {id:prefix[kind]+'-'+crypto.randomUUID().slice(0,12).toUpperCase(),version:1,kind,space:['task','solution','kc'].includes(kind)?'Domain':'Learning',model:({task:'Task Model',solution:'Solution Model',kc:'Knowledge Component Model'} as Partial<Record<Kind,string>>)[kind]||'材料、目标与采用关系',name:'',summary:'',status:'draft',source:'管理员直接创建',fields:clone(fieldsByKind[kind]||{}),relations:parent&&relation?[{label:relation,ref:parent}]:[],...(domainId?{domainId}:{}),...(kind==='target'?{requiredAspects:['independent','understanding','transfer','retention']}:{}),at:new Date().toISOString()};
}
export function saveDraft(object:ModelObject,baseVersion:number,draftId?:string) {
  const id=draftId||'DRAFT-'+crypto.randomUUID();
  transact(s=>{const item=s.drafts.find(d=>d.id===id);if(item){item.object=clone(object);item.at=new Date().toISOString();}else s.drafts.unshift({id,object:clone(object),baseVersion,at:new Date().toISOString()});});
  return id;
}
export function saveDefinition(input:ModelObject,baseVersion:number,draftId?:string,fromPackage=false) {
  if(mode.value!=='demo')throw Error('真实模型目录尚未接入，不能改写真实学习记录。');
  if(!editableKinds.includes(input.kind)&&!(fromPackage&&['claim','evidence-rule','inference-rule'].includes(input.kind)))throw Error('此对象不可手工修改。');
  let result='';
  transact(s=>{
    const previous=latest(input.id,s);
    if((previous?.version||0)!==baseVersion)throw Error('该对象已有新版本，请重新打开当前版本编辑。原输入已保留。');
    if(previous&&(previous.kind!==input.kind||previous.space!==input.space||previous.domainId!==input.domainId))throw Error('对象身份、类型和领域归属不可改写。');
    const next=clone(input);next.version=baseVersion+1;
    const failures=checks(next,s).filter(c=>!c.passed);
    const bad=next.relations.filter(r=>!relationLabels[next.kind]?.includes(r.label)||!relationKinds[r.label]?.includes(resolve(r.ref,undefined,s)?.kind||next.kind));
    if(bad.length)failures.push({name:'关联类型',passed:false,detail:'请选择本对象支持的关系及对应类型对象。'});
    if(failures.length)throw Error(failures.map(c=>c.name+'：'+c.detail).join('\n'));
    const content=(o:ModelObject)=>JSON.stringify({name:o.name,summary:o.summary,fields:o.fields,relations:o.relations,aspects:o.aspects,requiredAspects:o.requiredAspects});
    if(previous&&content(previous)===content(next)){result=objectKey(previous);if(draftId)s.drafts=s.drafts.filter(d=>d.id!==draftId);return;}
    next.status='published'; // Legacy storage label: saved definition, no approval workflow.
    next.at=new Date().toISOString();next.source=fromPackage?'管理员导入定义包后保存':'管理员直接保存';
    next.referenceVersions=Object.fromEntries(catalog(s).filter(o=>!personalKinds.includes(o.kind)).map(o=>[o.id,o.version]));next.referenceVersions[next.id]=next.version;
    s.objects.push(next);s.changes.unshift({ref:objectKey(next),beforeVersion:baseVersion,at:next.at,note:fromPackage?'导入定义包并保存':previous?'修改并保存':'新增并保存'});
    if(draftId)s.drafts=s.drafts.filter(d=>d.id!==draftId);
    if(next.kind==='chapter') {
      const prep=s.preparations.find(p=>p.chapter===next.id);
      if(!prep)s.preparations.push({chapter:next.id,reviewed:false,note:''});
      else if(previous&&JSON.stringify(previous.fields)!==JSON.stringify(next.fields))prep.reviewed=false;
    }
    result=objectKey(next);
  });
  return result;
}
export function readDefinitionPackage(value:unknown):ModelObject {
  const data=value as {format?:string;object?:ModelObject};const o=data?.object;
  if(data?.format!=='deermind-definition-package-v1'||!o||!['claim','evidence-rule','inference-rule'].includes(o.kind))throw Error('需要 Claim、证据规则或推断规则定义包。');
  if(typeof o.id!=='string'||!/^[-A-Za-z0-9_]+$/.test(o.id)||typeof o.name!=='string'||typeof o.summary!=='string'||!o.fields||Array.isArray(o.fields)||!Object.values(o.fields).every(v=>typeof v==='string')||!Array.isArray(o.relations)||!o.relations.every(r=>r&&typeof r.label==='string'&&typeof r.ref==='string'))throw Error('定义包字段或引用结构不完整。');
  if(o.kind==='claim'&&(!Array.isArray(o.aspects)||!o.aspects.length||!o.aspects.every(a=>a&&typeof a.key==='string'&&typeof a.label==='string'&&typeof a.criterion==='string'&&typeof a.evidence==='string'&&typeof a.applicable==='boolean')))throw Error('Claim 必须定义评价方面及其条件。');
  const base=latest(o.id);if(base&&base.kind!==o.kind)throw Error('编号已用于另一类型的对象。');
  if(o.version!==(base?.version||0)+1)throw Error('定义包版本必须为当前版本加一，新对象从 v1 开始。');
  const next:ModelObject={id:o.id,version:o.version,kind:o.kind,space:'Evaluation',model:o.kind==='claim'?'Learner State Model':o.kind==='evidence-rule'?'Evidence Model':'Inference Model',name:o.name,summary:o.summary,fields:clone(o.fields),relations:clone(o.relations),...(o.kind==='claim'?{aspects:clone(o.aspects)}:{}),status:'draft',source:'导入定义包',at:new Date().toISOString()};
  const failures=checks(next).filter(c=>!c.passed);if(failures.length)throw Error(failures.map(c=>c.name+'：'+c.detail).join('\n'));
  return next;
}
export function annotate(subject:string,text:string,dataMode:'demo'|'real'=mode.value) {
  if(!text.trim())throw Error('请填写核对意见。');
  if(!canAccess(subject,dataMode))throw Error('请先记录查看个人资料的用途。');
  transact(s=>s.annotations.unshift({id:'NOTE-'+crypto.randomUUID(),subject,text:text.trim(),at:new Date().toISOString(),mode:dataMode}));
}
export function invalidateEvidence(ref:string,reason:string,subject:string) {
  if(!reason.trim())throw Error('请说明停止使用的依据。');
  if(mode.value!=='demo'||!canAccess(subject)||!state.activities.some(a=>a.id===subject&&a.objects.includes(ref))||resolve(ref)?.kind!=='evidence')throw Error('只能在获准查看的活动中停止使用其 Evidence。');
  transact(s=>{const affected=new Set([ref]);let changed=true;while(changed){changed=false;for(const o of s.objects)if(personalKinds.includes(o.kind)&&o.relations.some(r=>affected.has(r.ref))&&!affected.has(objectKey(o))){affected.add(objectKey(o));changed=true;}}
    for(const key of affected)s.invalidated[key]=reason.trim()+'。待重新解释或推断；原历史内容保留。';
    s.annotations.unshift({id:'NOTE-'+crypto.randomUUID(),subject,text:'停止使用 '+[...affected].join('、')+'：'+reason.trim(),at:new Date().toISOString(),mode:'demo'});
  });
}
export function checks(candidate:ModelObject,s:AdminState=state):Check[] {
  const effective = (id:string) => id===candidate.id || id===objectKey(candidate) ? candidate : resolve(id,undefined,s);
  const result:Check[]=[{name:'必要定义',passed:!!candidate.name.trim() && !!candidate.summary.trim() && Object.values(candidate.fields).every(x=>!!x.trim()),detail:'名称、说明和已有定义字段不得为空；语义是否正确仍需人工核对。'}];
  if(['task','solution','kc'].includes(candidate.kind)) result.push({name:'领域归属',passed:!!candidate.domainId&&!!domain(candidate.domainId,s),detail:'领域定义必须归属于已建立的领域；不通过教材或学习空间猜测归属。'});
  const missing=candidate.relations.filter(r=>!r.label.trim() || !effective(r.ref));
  result.push({name:'引用存在且版本可解析',passed:!missing.length,detail:missing.length?missing.map(r=>r.ref).join('、'):'所有候选引用均能定位；检查采用当前目录版本。'});
  const expected:Record<string,string[]>={'可用方法':['solution'],'适用任务':['task'],'分解为子任务':['task'],'任务理解依赖':['kc'],'方法依赖':['kc'],'先修知识':['kc'],'映射任务':['task'],'允许方法':['solution'],'采用 Claim':['claim'],'精确绑定任务版本':['task'],'教材章节':['chapter'],'所属材料':['material'],'章节映射':['mapping'],'适用章节':['chapter']};
  const wrong=candidate.relations.filter(r=>expected[r.label] && !expected[r.label]!.includes(effective(r.ref)?.kind||''));
  result.push({name:'关系类型',passed:!wrong.length,detail:wrong.length?wrong.map(r=>`${r.label} → ${r.ref}`).join('；'):'子任务指向 TaskTemplate，知识依赖指向 KC，不将 Solution 当作子任务。'});
  const visited=new Set<string>(), visiting=new Set<string>();
  const cyclic=(id:string):boolean=>{
    if(visiting.has(id)) return true; if(visited.has(id)) return false;
    const o=effective(id); if(!o) return false;
    visiting.add(id);
    const refs=o.relations.filter(r=>['可用方法','分解为子任务','先修知识'].includes(r.label));
    if(refs.some(r=>cyclic(r.ref.split('@')[0]!))) return true;
    visiting.delete(id);visited.add(id);return false;
  };
  result.push({name:'递归依赖无环',passed:!cyclic(candidate.id),detail:'检查 Task → 方法 → 子任务以及 KC 先修依赖；不把反向浏览关系当成循环。'});
  if(['mapping','target'].includes(candidate.kind)) {
    const tasks=candidate.kind==='mapping'?candidate.relations.filter(r=>r.label==='映射任务').map(r=>r.ref.split('@')[0]):candidate.relations.filter(r=>r.label==='采用 Claim').flatMap(r=>effective(r.ref)?.relations.filter(x=>x.label==='精确绑定任务版本').map(x=>x.ref.split('@')[0])||[]);
    const methods=candidate.relations.filter(r=>r.label==='允许方法');
    result.push({name:'任务与方法相容',passed:tasks.length>0 && methods.length>0 && methods.every(r=>effective(r.ref)?.relations.some(x=>x.label==='适用任务' && tasks.includes(x.ref.split('@')[0]))),detail:'所选方法必须用于已选择的任务；方法范围与 Claim 文字条件仍需核对。'});
    if(candidate.kind==='target') {
      const claims=candidate.relations.filter(r=>r.label==='采用 Claim').map(r=>effective(r.ref));
      result.push({name:'目标方面已有定义',passed:!!candidate.requiredAspects?.length && claims.length>0 && claims.every(c=>candidate.requiredAspects!.every(k=>c?.aspects?.some(a=>a.key===k && a.applicable))),detail:'目标要求只能选择所采用 Claim 中已定义、适用的方面；裁剪不能反写共享 Claim。'});
    }
  }
  if(candidate.kind==='claim'){
    const binding=candidate.relations.filter(r=>r.label==='精确绑定任务版本');
    result.push({name:'Claim 精确绑定单个任务',passed:binding.length===1 && /^[^@]+@\d+$/.test(binding[0]!.ref) && resolve(binding[0]!.ref,undefined,s)?.kind==='task',detail:'Claim 不绑定多任务集合，也不通过修改目标新建个人 Claim。'});
    const aspects=candidate.aspects||[];
    result.push({name:'评价方面可追溯',passed:aspects.length>0&&new Set(aspects.map(a=>a.key)).size===aspects.length&&aspects.every(a=>a.key&&a.criterion&&a.evidence&&(a.applicable||a.reason)),detail:'方面键不重复，定义、证据条件和裁剪依据完整；不适用不等于学生得零分。'});
  }
  return result;
}
export function readiness(chapter:string,bindings?:Record<string,number>) {
  const prep=state.preparations.find(p=>p.chapter===chapter);
  const ch=resolve(chapter,bindings);
  const maps=bindings ? ch?.relations.filter(r=>r.label==='章节映射').map(r=>resolve(r.ref,bindings)).filter(Boolean)||[] : catalog().filter(o=>o.kind==='mapping'&&o.relations.some(r=>r.label==='教材章节'&&r.ref.split('@')[0]===chapter));
  const goals=bindings ? ch?.relations.filter(r=>r.label==='可选目标').map(r=>resolve(r.ref,bindings)).filter(Boolean)||[] : catalog().filter(o=>o.kind==='target'&&o.relations.some(r=>r.label==='适用章节'&&r.ref.split('@')[0]===chapter));
  const validMapping=maps.some(o=>o&&checks(o).every(c=>c.passed));
  const validTarget=goals.some(o=>o&&checks(o).every(c=>c.passed));
  return [{label:'浏览',ready:!!prep?.reviewed,reason:prep?.reviewed?'来源与章节已核对':'等待原材料核对'},
    {label:'讲解',ready:!!prep?.reviewed && validMapping,reason:validMapping?'示例映射可解析，实际教学质量另行验证':'缺少明确的任务与方法映射'},
    {label:'练习反馈',ready:!!prep?.reviewed && validMapping,reason:'需要原题、参考解法和反馈依据；当前为示例核对结果'},
    {label:'正式评价',ready:!!prep?.reviewed && validMapping && validTarget,reason:validTarget?'示例定义齐备；尚未连接正式评价引擎':'目标或 Claim 条件尚不完整'}];
}
