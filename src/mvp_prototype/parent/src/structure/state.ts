import { reactive, watch, ref } from 'vue';
import type { RecordItem } from './data';
import { chapterOf } from './data';
export type LessonEvent={id:string;kind:'segment'|'quick'|'support'|'groups'|'return'|'practice'|'practice-answer'|'message'|'check-start'|'check-end'|'ended'|'help';value?:string;index?:number};
export type Conversation={version:1;events:LessonEvent[];scenario:'none'|'quick'|'support';prepared:boolean;practiceDraft:string;practiceAnswer?:string};
export type Session={id:string;learner:string;space:string;chapter:string;segment:number;shown?:number[];postHelpShown?:boolean;status:'learning'|'check'|'ended';answer:string;submitted:boolean;endedReason:string;date:string;updatedAt?:number;conversation?:Conversation;real?:boolean;realTurns?:number;realSuccessor?:string};
export const scriptedPreview=new URLSearchParams(location.search).get('preview')==='scripted';
export type Issue={id:string;learner:string;space:string;chapter:string;recordId:string;reason:string;status:'待复核'|'已记录意见';note:string;date:string};
export type Attachment={name:string;data:string};
export type Message={id:string;text:string;at:string;attachment?:Attachment};
export type ClassroomChapter={id:string;name:string;path:string};
export type ClassroomProgress={id:string;learner:string;space:string;material:string;materialVersion:string;status:'reported'|'unknown';chapters:ClassroomChapter[];note:string;source:'student-confirmed';confirmedAt:string};
type HomePreferences={reference:'available'|'unassessed'|'none';timePreview:0|26|30;catalogScale:3|30|300;deferred:Record<string,boolean>};
type Store={version:1;classroomProgress:ClassroomProgress[];studentSpace:string;parentChild:string;parentSpace:string;sessions:Session[];issues:Issue[];drafts:Record<string,string>;attachments:Record<string,Attachment>;messages:Record<string,Message[]>;access:Record<string,string>;home:HomePreferences};
const initial=():Store=>({version:1,classroomProgress:[],studentSpace:'school',parentChild:'S0001',parentSpace:'school',sessions:[],issues:[],drafts:{},attachments:{},messages:{},access:{},home:{reference:'available',timePreview:0,catalogScale:3,deferred:{}}});
// Keep retained parent data separate from both the old origin and the new V2 student store.
const key='deermind-next-parent-v1';
export const storageWarning=ref('');
function restore():Store {try{const raw=localStorage.getItem(key);if(!raw)return initial();const s=JSON.parse(raw);if(s.version!==1||!Array.isArray(s.sessions)||!Array.isArray(s.issues)||!s.messages||!s.drafts||!s.access)throw Error();const defaults=initial();return {...defaults,...s,classroomProgress:Array.isArray(s.classroomProgress)?s.classroomProgress:[],home:{...defaults.home,...s.home}};}catch{storageWarning.value='上次走查数据无法读取，当前使用新的合成资料。';return initial();}}
export const state=reactive<Store>(restore());
watch(state,()=>{try{localStorage.setItem(key,JSON.stringify(state));}catch{storageWarning.value='浏览器未能保存，本页可继续，刷新可能丢失本次操作。';}},{deep:true});
export const uid=(prefix:string)=>`${prefix}-${crypto.randomUUID().slice(0,8)}`;
export function touchSession(s:Session){s.updatedAt=Date.now();}
export function orderedSessions(sessions:Session[]){return [...sessions].sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));}
export function startLesson(chapter:string){const s:Session={id:uid('LIVE'),learner:'S0001',space:state.studentSpace,chapter,segment:0,shown:[0],postHelpShown:false,status:'learning',answer:'',submitted:false,endedReason:'',date:new Date().toISOString().slice(0,10),updatedAt:Date.now()};state.sessions.unshift(s);return s;}
export function sessionRecord(s:Session):RecordItem{
 if(s.real)return {id:s.id,learner:s.learner,space:s.space,chapter:s.chapter,title:'真实模型对话',date:s.date,source:'讲解练习',outcome:'未作正式评价',answer:'',help:`本次真实交流共 ${s.realTurns||0} 条记录；请在原活动查看完整题目、作答和模型反馈，不计入预写章节状态。`,kind:'活动'};
 const practice=s.conversation?.practiceAnswer===undefined?undefined:{problem:'甲有 12 张卡片，乙有 9 张。乙比甲少几分之几？请说明比较标准。',answer:s.conversation.practiceAnswer};
 const teachingCount=s.conversation?s.conversation.events.filter(e=>['segment','quick','support','groups','return'].includes(e.kind)).length:s.shown?.length||s.segment+1;
 return {id:s.id,learner:s.learner,space:s.space,chapter:s.chapter,title:'本次讲解与检查',problem:s.status==='check'||s.endedReason.includes('检查')?chapterOf(s.chapter)?.question:undefined,date:s.date,source:'讲解练习',outcome:s.submitted||practice?'尚未判定':'未作答',answer:s.submitted?s.answer:'',help:`已展开 ${teachingCount} 段预写教学${s.conversation?.scenario&&s.conversation.scenario!=='none'?'，其中含明确标注的示例学生表达，不属于真实作答':''}${s.postHelpShown?'，检查结束后另查看了预写帮助':''}；没有执行模型评价`,kind:'活动',practice};
}
export function submitMessage(scope:string){const text=state.drafts[scope]?.trim()||'';const attachment=state.attachments[scope];if(!text&&!attachment)return;const message={id:uid('MSG'),text,at:new Date().toLocaleString('zh-CN'),...(attachment?{attachment}:{})};(state.messages[scope]??=[]).push(message);const session=state.sessions.find(s=>scope===`student:${s.learner}:${s.space}:${s.id}`);if(session?.conversation){session.conversation.events.push({id:uid('TURN'),kind:'message',value:message.id});touchSession(session);}state.drafts[scope]='';delete state.attachments[scope];}
export function requestReview(record:RecordItem,reason:string){const issue:Issue={id:uid('REV'),learner:record.learner,space:record.space,chapter:record.chapter,recordId:record.id,reason,status:'待复核',note:'',date:new Date().toISOString().slice(0,10)};state.issues.unshift(issue);return issue;}

// These are reports of external teaching context, never assessments or learner performances.
export function classroomMaterial(space:string){return space==='school'?{id:'BNU6A-PROTOTYPE',version:'reference-v1',name:'北师大版 · 六年级上册'}:undefined;}
export function classroomReports(learner:string,space:string){const material=classroomMaterial(space);return material?state.classroomProgress.filter(p=>p.learner===learner&&p.space===space&&p.material===material.id&&p.materialVersion===material.version):[];}
export function classroomProgress(learner:string,space:string){return classroomReports(learner,space).at(-1);}
export function classroomIsCurrent(learner:string,space:string,chapter:string){const current=classroomProgress(learner,space);return current?.status==='reported'&&current.chapters.some(c=>c.id===chapter);}
export function confirmClassroomProgress(learner:string,space:string,status:'reported'|'unknown',chapters:ClassroomChapter[],note:string){
 const material=classroomMaterial(space);
 if(learner!=='S0001'||!material||status==='reported'&&!chapters.length)return false;
 state.classroomProgress.push({id:uid('CLASS'),learner,space,material:material.id,materialVersion:material.version,status,chapters:status==='reported'?[...new Map(chapters.map(c=>[c.id,{...c}])).values()]:[],note:note.trim().slice(0,160),source:'student-confirmed',confirmedAt:new Date().toISOString()});
 return true;
}
