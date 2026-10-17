import { computed, reactive, watch } from 'vue';
import catalog from '../../mvp_foundation/examples/course-setup-fixture.json';

export type Course = {id:string; name:string; version:number; units:string[]};
type Exam = {id:string;status:'idle'|'ready'|'running'|'paused'|'ended'; units:string[]; questions:string[]; answers:string[]; draft:string; endReason:''|'completed'|'manual'|'help'; helpId:string; courseId:string; version:number; suggestionBasis:string};
type Journey = {
 adoptions:{courseId:string;from:number;to:number;scope:string[];basis:string;at:string}[];
 version:1; courses:Course[]; selectedCourse:string; selectedUnits:string[]; exam:Exam; examHistory:Exam[];
 suggestion:{validity:'valid'|'stale'|'repair'; response:''|'later'|'declined'|'accepted'; revision:number};
 material:{stage:'empty'|'processing'|'review'|'published'; taskId:string; ocr:string[]; reviewed:boolean[]; standard:string; referenceReviewed:boolean; mappingReviewed:boolean; reason:string; approved:string; audit:string[]};
 accounts:{profiles:{id:string; name:string; role:'student'|'parent'; credentialRevision:number}[]; links:{parent:string; child:string; active:boolean}[]; parentConfirmed:boolean; childConfirmed:boolean; audit:string[]};
};
const emptyExam=():Exam=>({id:crypto.randomUUID(),status:'idle',units:[],questions:[],answers:[],draft:'',endReason:'',helpId:'',courseId:'',version:1,suggestionBasis:''});
function initial():Journey{return {version:1,adoptions:[],courses:[],selectedCourse:'',selectedUnits:['u-calc'],exam:emptyExam(),examHistory:[],suggestion:{validity:'valid',response:'',revision:1},material:{stage:'empty',taskId:'',ocr:[],reviewed:[false,false],standard:catalog.target_standard,referenceReviewed:false,mappingReviewed:false,reason:'',approved:'',audit:[]},accounts:{profiles:[{id:'CHILD-DEMO-1',name:'演示学生',role:'student',credentialRevision:1},{id:'PARENT-DEMO-1',name:'演示家长一',role:'parent',credentialRevision:1},{id:'PARENT-DEMO-2',name:'演示家长二',role:'parent',credentialRevision:1}],links:[{parent:'PARENT-DEMO-1',child:'CHILD-DEMO-1',active:true},{parent:'PARENT-DEMO-2',child:'CHILD-DEMO-1',active:true}],parentConfirmed:true,childConfirmed:true,audit:[]}};}
const key='deermind-phase4-course-setup-v1';
function restore():Journey{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d?.version===1&&Array.isArray(d.courses)&&d.exam&&d.material&&d.accounts?.links){const restored={...d,adoptions:d.adoptions||[],exam:{...d.exam,id:d.exam.id||crypto.randomUUID()},examHistory:(d.examHistory||[]).map((e:Exam)=>({...e,id:e.id||crypto.randomUUID()}))};localStorage.setItem(key,JSON.stringify(restored));return restored;}}catch{}return initial();}
export const journey=reactive(restore());
export const journeyWarning=reactive({text:''});
watch(journey,()=>{try{localStorage.setItem(key,JSON.stringify(journey));}catch{journeyWarning.text='本轮演示无法保存，刷新可能丢失进度。';}},{deep:true});
export const examBusy=computed(()=>['running','paused'].includes(journey.exam.status));
export const parentLinked=computed(()=>journey.accounts.links.some(l=>l.parent==='PARENT-DEMO-1'&&l.child==='CHILD-DEMO-1'&&l.active));
export const demoConfirmed=computed(()=>journey.accounts.parentConfirmed&&journey.accounts.childConfirmed&&journey.accounts.links.some(l=>l.child==='CHILD-DEMO-1'&&l.active));
export const currentCourse=computed(()=>journey.courses.find(c=>c.id===journey.selectedCourse));
export const currentMaterialVersion=computed(()=>journey.material.stage==='published'?2:1);
export function resetJourney(){const fresh=initial();Object.assign(journey,fresh);}
export function prepareExam(units:string[],suggested=false){
 if(examBusy.value||!currentCourse.value)return false;
 archiveExam();
 const chosen=catalog.units.filter(u=>units.includes(u.id)&&currentCourse.value!.units.includes(u.id));
 const questions=[...new Set(chosen.flatMap(u=>u.question_ids))];
 journey.exam={...emptyExam(),status:'ready',units:chosen.map(u=>u.id),questions,courseId:currentCourse.value.id,version:currentCourse.value.version,suggestionBasis:suggested?String(journey.suggestion.revision):''};return true;
}
export function endExam(reason:Exam['endReason']){if(!examBusy.value)return;journey.exam.endReason=reason;if(reason==='help')journey.exam.helpId=journey.exam.questions[journey.exam.answers.length]||'';journey.exam.status='ended';journey.exam.draft='';}
function archiveExam(){if(journey.exam.status==='ended')journey.examHistory.push(JSON.parse(JSON.stringify(journey.exam)));}
export function newPlan(){if(!examBusy.value){archiveExam();journey.exam=emptyExam();}}
export { catalog };
