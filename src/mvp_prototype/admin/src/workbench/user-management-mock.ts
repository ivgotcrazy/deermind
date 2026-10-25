import { reactive } from 'vue';
import { learningSpaces } from './learning-space-mock';

export const userRoles={student:'学生',parent:'家长',admin:'管理员'} as const;
export type UserRole=keyof typeof userRoles;
export interface MockAccount {id:string;name:string;login:string;role:UserRole;learnerId:string;createdAt:string;credentialVersion:number;lastLogin:string}
export interface ParentRelation {id:string;parentId:string;studentId:string;active:boolean;scope:string;verifiedAt:string;reason:string;updatedAt:string}
export interface AccountOperation {id:string;at:string;actor:string;accountIds:string[];action:string;reason:string;detail:string}
export interface AccountConfirmation {accountId:string;studentId:string;type:'participation'|'notice';version:string;at:string}
const actor='ACC-ADMIN';
const visibility='该孩子的学习空间及按既定可见规则可查阅的学习资料；不授予代作答、修改资料或管理权限。';
const account=(id:string,name:string,login:string,role:UserRole,learnerId=''):MockAccount=>({id,name,login,role,learnerId,createdAt:'2026-10-22 09:00',credentialVersion:1,lastLogin:''});
export const userMock=reactive({
  accounts:[account('ACC-STUDENT-A','学生 A','student.a','student','LEARNER-A'),account('ACC-STUDENT-B','学生 B','student.b','student','LEARNER-B'),account('ACC-STUDENT-C','学生 C','student.c','student','LEARNER-C'),account('ACC-PARENT-A','家长 A','parent.a','parent'),account('ACC-PARENT-B','家长 B','parent.b','parent'),account(actor,'本地管理员','admin.local','admin')],
  relations:[['REL-AA','ACC-PARENT-A','ACC-STUDENT-A'],['REL-AB','ACC-PARENT-A','ACC-STUDENT-B'],['REL-BA','ACC-PARENT-B','ACC-STUDENT-A']].map(([id,parentId,studentId])=>({id:id!,parentId:parentId!,studentId:studentId!,active:true,scope:visibility,verifiedAt:'2026-10-22 10:00',updatedAt:'2026-10-22 10:00',reason:'合成示例：管理员已在系统外核实本人与亲子关系。'} as ParentRelation)),
  confirmations:[{accountId:'ACC-STUDENT-A',studentId:'ACC-STUDENT-A',type:'participation',version:'MOCK-NOTICE-1',at:'2026-10-22 11:00'},{accountId:'ACC-PARENT-A',studentId:'ACC-STUDENT-A',type:'notice',version:'MOCK-NOTICE-1',at:'2026-10-22 10:30'}] as AccountConfirmation[],
  operations:[] as AccountOperation[],
});
for(const a of userMock.accounts)userMock.operations.push({id:'CREATE-'+a.id,at:a.createdAt,actor:'系统初始化（示例）',accountIds:[a.id],action:a.role==='admin'?'初始化管理员':'建立示例账号',reason:'人工编写的合成账号，不是实际身份核实。',detail:`${a.name} · ${a.login}${a.learnerId?' · '+a.learnerId:''}；未创建学习空间，未运行评价。`});
for(const r of userMock.relations)userMock.operations.push({id:'LINK-'+r.id,at:r.verifiedAt,actor,accountIds:[r.parentId,r.studentId],action:'建立亲子关联',reason:r.reason,detail:r.id+'；'+r.scope});
export const findAccount=(id:string)=>userMock.accounts.find(a=>a.id===id);
export const relationsFor=(id:string)=>userMock.relations.filter(r=>r.parentId===id||r.studentId===id);
export const accountSpaces=(a:MockAccount)=>a.role==='student'?learningSpaces.filter(s=>s.studentId===a.learnerId):[];
export const relatedStudentIds=(a:MockAccount)=>a.role==='student'?[a.id]:a.role==='parent'?relationsFor(a.id).filter(r=>r.active).map(r=>r.studentId):[];
export const visibleSpaces=(a:MockAccount)=>relatedStudentIds(a).flatMap(id=>{const student=findAccount(id);return student?accountSpaces(student):[];});
const now=()=>new Date().toLocaleString('sv-SE').slice(0,16);
const id=(prefix:string)=>prefix+'-'+crypto.randomUUID().slice(0,8).toUpperCase();
function verified(value:boolean,reason:string){if(!value||!reason.trim())throw Error('请先确认已完成本次操作所需的系统外核实，并记录依据。');if(reason.trim().length>1000)throw Error('核实依据最多 1000 字。');return reason.trim();}
function record(accountIds:string[],action:string,reason:string,detail:string){userMock.operations.unshift({id:id('OP'),at:now(),actor,accountIds,action,reason,detail});}
function nameValue(name:string){const value=name.trim();if(!value||value.length>60)throw Error('请填写姓名或显示名称，最多 60 字。');return value;}
export function createAccount(role:'student'|'parent',name:string,login:string,checked:boolean,reason:string){
  if(role!=='student'&&role!=='parent')throw Error('首个管理员由部署初始化，本流程仅开立学生或家长账号。');
  const basis=verified(checked,reason),display=nameValue(name),username=login.trim();
  if(!/^[^\s]{3,40}$/.test(username))throw Error('账号名为 3–40 个字符，不能包含空白。');
  const normalized=(s:string)=>s.normalize('NFKC').toLowerCase();
  if(userMock.accounts.some(a=>normalized(a.login)===normalized(username)))throw Error('该账号名已存在，请使用不同的账号名；同名人员不自动合并。');
  const a=account(id('ACC'),display,username,role,role==='student'?id('LEARNER'):'');a.createdAt=now();userMock.accounts.push(a);
  record([a.id],'开户',basis,`建立${userRoles[role]}账号 ${a.login}${a.learnerId?'；学习者 '+a.learnerId:''}；未自动关联家长或孩子，未创建学习空间。`);return a;
}
export function renameAccount(accountId:string,name:string,reason:string){
  const a=findAccount(accountId);if(!a)throw Error('账号不存在。');const display=nameValue(name);if(!reason.trim())throw Error('请记录修改原因。');if(a.name===display)return;
  const before=a.name;a.name=display;
  // Keep the current course fixtures' display names aligned; stable learner IDs and history remain unchanged.
  if(a.role==='student')for(const s of accountSpaces(a))s.studentName=display;
  record([a.id],'修改显示名称',reason.trim(),`${before} → ${display}；账号名、角色、学习者及空间归属不变。`);
}
export function linkAccounts(parentId:string,studentId:string,checked:boolean,reason:string){
  const parent=findAccount(parentId),student=findAccount(studentId),basis=verified(checked,reason);
  if(parent?.role!=='parent'||student?.role!=='student')throw Error('必须选择一个家长账号和一个学生账号，管理员身份不能替代家长身份。');
  const existing=userMock.relations.find(r=>r.parentId===parentId&&r.studentId===studentId);
  if(existing?.active)throw Error('这两个账号已经有关联，不重复建立。');
  const at=now();let r:ParentRelation;
  if(existing){Object.assign(existing,{active:true,verifiedAt:at,updatedAt:at,reason:basis});r=existing;}
  else{r={id:id('REL'),parentId,studentId,active:true,scope:visibility,verifiedAt:at,updatedAt:at,reason:basis};userMock.relations.push(r);}
  record([parentId,studentId],existing?'恢复亲子关联':'建立亲子关联',basis,`${r.id}；${parent.name} → ${student.name}；${r.scope}不代替首次确认。`);return r;
}
export function unlinkAccounts(relationId:string,checked:boolean,reason:string){
  const r=userMock.relations.find(r=>r.id===relationId),basis=verified(checked,reason);if(!r?.active)throw Error('该关联不存在或已经解除。');
  r.active=false;r.updatedAt=now();r.reason=basis;
  record([r.parentId,r.studentId],'解除亲子关联',basis,`${r.id}；停止该段关系带来的查看权限；其他关联、原账号、学习空间及历史记录保持。`);
}
export function recoverAccount(accountId:string,checked:boolean,reason:string){
  const a=findAccount(accountId),basis=verified(checked,reason);if(!a)throw Error('账号不存在。');
  const before=a.credentialVersion;a.credentialVersion++;
  record([a.id],'找回原账号',basis,`凭据记录 v${before} → v${a.credentialVersion}；沿用 ${a.id}${a.learnerId?' / '+a.learnerId:''}。未实际生成密码、重置登录或断开设备会话。`);
}
