import { reactive, watch } from 'vue';
import { flows, fixture } from './foundationState';
import { catalog, journey } from './journeyState';
import lesson from '../../mvp_foundation/examples/chapter-lesson.json';
import { checkInputs, type InputCheck } from './checkInputState';
import type { Capture } from './captureState';
export type LearningRecord={id:string;spaceId:string;space:string;source:'external'|'lesson'|'test';prompt:string;answer:string;help:string;status:'pending'|'unanswered'|'correct'|'incorrect';provenance:string;version:string;checks?:InputCheck[];input?:Capture;hidden?:boolean;synthetic:boolean};
export type LessonRecords={practiceSubmitted:boolean;practiceText:string;runs:{answers:string[];ended:string;helpQuestion?:number}[]};
type Note={kind:'transcription'|'retry';text:string;reason:string;at:string};
type Issue={id:string;recordId:string;purpose:string;category:'input'|'domain'|'evaluation'|'interaction'|'technical'|'unresolved';description:string;decision:'pending'|'maintenance'|'nochange'|'unresolved';linkedVersion:string;history:string[]};
type Review={notes:Record<string,Note[]>;issues:Issue[];activeIssue:string;access:{recordId:string;purpose:string;at:string}[]};
const key='deermind-phase4-record-review-v1';
function initial():Review{return {notes:{},issues:[],activeIssue:'',access:[]};}
function restore():Review{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d?.notes&&Array.isArray(d.issues)&&Array.isArray(d.access))return d;}catch{}return initial();}
export const recordsReview=reactive(restore());
export const reviewWarning=reactive({text:''});
watch(recordsReview,()=>{try{localStorage.setItem(key,JSON.stringify(recordsReview));}catch{reviewWarning.text='记录或复核说明未能保存，刷新可能丢失。';}},{deep:true});
export function resetRecords(){Object.assign(recordsReview,initial());}
export function liveRecords(s:LessonRecords):LearningRecord[]{
 const out:LearningRecord[]=flows.requests.map(r=>({id:`help-${r.id}`,spaceId:r.spaceId||'demo',space:r.spaceName||'章节／求助演示空间',source:'external',prompt:r.prompt,answer:r.answer,help:r.helpShown==='explain'?'页面已展示预写完整讲解':r.helpShown==='hint'?'页面已展示预写提示':'尚无帮助展示记录；不能据请求推定',status:r.answer?'pending':'unanswered',provenance:'当前浏览器实际提交；没有真实语义判断',version:'题面 v1',input:r.input,hidden:r.hidden,synthetic:false}));
 if(s.practiceSubmitted)out.push({id:'lesson-practice',spaceId:'demo',space:'章节／求助演示空间',source:'lesson',prompt:lesson.practice.prompt,answer:s.practiceText,help:'讲解内练习，保留已接触讲解的背景',status:'pending',provenance:'实际练习提交，未运行正式评价',version:'DEMO-LESSON-AREA-001@1',synthetic:false});
 s.runs.forEach((run,i)=>run.answers.forEach((answer,j)=>out.push({id:`lesson-check-${i}-${j}`,checks:checkInputs.log[`lesson-check-${i}-${j}`]||[],spaceId:'demo',space:'章节／求助演示空间',source:'test',prompt:lesson.check.questions[j]!,answer,help:`章节后的检测；结束原因 ${run.ended}，不能抹去先前讲解背景`,status:'pending',provenance:'已结束检测的实际提交，未判定',version:'DEMO-LESSON-AREA-001@1',synthetic:false})));
 const exams=[...journey.examHistory,...(journey.exam.status==='ended'?[journey.exam]:[])];
 exams.forEach(e=>e.answers.forEach((answer,j)=>out.push({id:`range-${e.id}-${j}`,checks:checkInputs.log[`range-${e.id}-${j}`]||[],spaceId:e.courseId,space:journey.courses.find(c=>c.id===e.courseId)?.name||e.courseId,source:'test',prompt:catalog.questions.find(q=>q.id===e.questions[j])?.prompt||'题面引用缺失',answer,help:`范围检测；结束原因 ${e.endReason}，独立性未判定`,status:'pending',provenance:'当前浏览器实际提交；原始版本保持',version:`教材与目标 v${e.version}`,synthetic:false})));
 return out;
}
export function referenceRecords():LearningRecord[]{return fixture.attempts.filter(a=>a.ended).map(a=>({id:`reference-${a.id}`,spaceId:'reference',space:'预写状态展示空间',source:a.source==='外部录入'?'external':a.source==='范围检测'?'test':'lesson',prompt:a.prompt,answer:a.answer,help:a.context,status:a.judgment as LearningRecord['status'],provenance:'预写评价参考，不是本轮模型判断',version:'DEMO-PRODUCT-FLOW-001@1',synthetic:true}));}
export function addNote(id:string,kind:Note['kind'],text:string,reason:string){if(!text.trim()||!reason.trim())return; (recordsReview.notes[id]??=[]).push({kind,text:text.trim(),reason:reason.trim(),at:new Date().toISOString()});}
