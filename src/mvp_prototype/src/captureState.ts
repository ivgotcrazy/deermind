import { reactive, watch } from 'vue';
import input from '../../mvp_foundation/examples/input-fixture.json';
export type Point = [number,number];
export type Capture = {kind:'images'|'pdf'|'ink'|'voice'; originals:string[]; transcript:string; prompt:string; answer:string; strokes:Point[][]; provenance:string};
type Draft = {kind:Capture['kind']; stage:'empty'|'source'|'recording'|'preview'; prompt:string; answer:string; transcript:string; checked:boolean; sameQuestion:boolean; strokes:Point[][]};
const initial=():Draft=>({kind:'images',stage:'empty',prompt:'',answer:'',transcript:'',checked:false,sameQuestion:false,strokes:[]});
const key='deermind-phase4-input-v1';
function restore():Draft{try{const d=JSON.parse(localStorage.getItem(key)||'null');if(d&&Array.isArray(d.strokes)&&['images','pdf','ink','voice'].includes(d.kind))return d;}catch{}return initial();}
export const capture=reactive(restore());
export const captureWarning=reactive({text:''});
watch(capture,()=>{try{localStorage.setItem(key,JSON.stringify(capture));}catch{captureWarning.text='输入草稿未能保存；当前页面仍可查看。';}},{deep:true});
export const originalPages=input.pages.map(p=>p.text);
export const voiceOriginal=input.voice_original;
export function clearCapture(){Object.assign(capture,initial());}
export function selectCapture(kind:Capture['kind']){clearCapture();capture.kind=kind;}
export function loadCapture(){capture.stage=capture.kind==='voice'?'recording':'source';}
export function previewCapture(){capture.stage='preview';capture.checked=false;capture.sameQuestion=false;capture.prompt=capture.kind==='voice'?input.voice_transcript:input.recognition;capture.answer=capture.kind==='voice'?'':input.recognized_answer;capture.transcript=capture.prompt;}
export function captureSnapshot():Capture{return {kind:capture.kind,originals:capture.kind==='voice'?[voiceOriginal]:capture.kind==='ink'?[]:[...originalPages],transcript:capture.transcript,prompt:capture.prompt,answer:capture.answer,strokes:JSON.parse(JSON.stringify(capture.strokes)),provenance:capture.kind==='ink'?'浏览器实际笔迹；未运行手写识别':'作者合成输入与预写识别／转写，无真实拍照、PDF解析或录音'};}
