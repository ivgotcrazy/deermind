import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createLiveService } from '../scripts/live-service.mjs';
import { validateOutput } from '../scripts/live-model.mjs';
const textOutput = { blocks: [{ type: 'text', text: '比较标准是乙的 9 张。' }], suggestions: ['换一种讲法'] };
const output = (body=textOutput)=>({raw:JSON.stringify(body),finish:'stop',ms:10,usage:{total_tokens:123}});
const cmd = (kind, extra={})=>({kind,requestId:randomUUID(),...extra});
async function setup(provider){const directory=await mkdtemp(path.join(os.tmpdir(),'deermind-live-test-'));const service=createLiveService({directory,provider,model:'test-only'});const create=service.create;service.create=()=>create({space:'test-space',label:'测试范围'});return {directory,service};}
async function settled(service,id){for(let i=0;i<100;i++){const s=await service.get(id);if(!s.pending)return s;await new Promise(r=>setTimeout(r,10));}throw Error('did not settle');}

test('serial and idempotent calls preserve genuine inputs and redact private answers',async()=>{
 let resolve,calls=0;
 const {service}=await setup(async()=>{calls++;return new Promise(r=>resolve=r);});
 const s=await service.create(),request=cmd('message',{text:'为什么除以 9？'});
 await service.command(s.id,request);await service.command(s.id,request);assert.equal(calls,1);
 await assert.rejects(service.command(s.id,cmd('message',{text:'另一个问题'})),/上一轮/);
 await assert.rejects(service.command(s.id,{...request,text:'不同输入'}),/同一请求编号/);
 resolve(output({blocks:[{type:'question',mode:'practice',prompt:'12 比 9 多几分之几？',referenceAnswer:'秘密：1/3'}],suggestions:[]}));
 const result=await settled(service,s.id);assert.equal(result.turns.length,2);assert.ok(!JSON.stringify(result).includes('秘密'));assert.equal(result.turns[0].text,'为什么除以 9？');
});
test('check help closes the check before any model output and never fabricates an answer',async()=>{
 const {service}=await setup(async()=>output({blocks:[{type:'question',mode:'check',prompt:'20 比 16 多几分之几？',referenceAnswer:'1/4'}],suggestions:[]}));
 const s=await service.create();await service.command(s.id,cmd('check_request'));let result=await settled(service,s.id);
 const q=result.turns[1].blocks[0];await assert.rejects(service.command(s.id,cmd('answer',{questionId:q.id,text:'1/4'})),/先开始/);
 await service.command(s.id,cmd('start_check',{questionId:q.id}));
 await assert.rejects(service.command(s.id,cmd('help',{questionId:'another-question'})),/求助题目/);
 assert.equal((await service.get(s.id)).check,q.id);
 await assert.rejects(service.command(s.id,cmd('message',{text:'讲答案'})),/结束检查/);
 result=await service.command(s.id,cmd('help',{text:'不知道分母用谁'}));assert.equal(result.check,null);assert.equal(result.phase,'learning');assert.equal(result.turns[1].blocks[0].state,'helped');assert.equal(result.turns[1].blocks[0].answer,undefined);
 await settled(service,s.id);
});
test('cancel discards late responses; retry does not append duplicate learner input',async()=>{
 let resolve,calls=0;
 const {service}=await setup(async()=>{calls++;if(calls===1)return new Promise(r=>resolve=r);return output();});
 const s=await service.create();await service.command(s.id,cmd('message',{text:'解释一下'}));await service.command(s.id,cmd('cancel'));
 await service.command(s.id,cmd('retry'));let result=await settled(service,s.id);assert.equal(result.turns.length,2);
 resolve(output({blocks:[{type:'text',text:'迟到的旧回复'}],suggestions:[]}));await new Promise(r=>setTimeout(r,20));result=await service.get(s.id);assert.equal(result.turns.length,2);assert.ok(!JSON.stringify(result).includes('迟到'));assert.equal(calls,2);
});
test('restart recovers pending work without automatically spending another call',async()=>{
 const {service,directory}=await setup(()=>new Promise(()=>{}));const s=await service.create();await service.command(s.id,cmd('message',{text:'保留我'}));
 let calls=0;const restored=createLiveService({directory,model:'test-only',provider:async()=>{calls++;return output();}});
 const result=await restored.get(s.id);assert.equal(result.pending,null);assert.match(result.error.message,/中断/);assert.equal(result.turns.length,1);assert.equal(calls,0);
 await service.command(s.id,cmd('cancel'));
});
test('invalid format has one repair attempt, no partial assistant output; retry succeeds',async()=>{
 let calls=0;const {service}=await setup(async()=>{calls++;return calls<=2?{raw:'not json',finish:'stop',ms:1}:output();});
 const s=await service.create();await service.command(s.id,cmd('message',{text:'讲一讲'}));let result=await settled(service,s.id);
 assert.equal(calls,2);assert.equal(result.turns.length,1);assert.match(result.error.message,/内容格式/);
 await service.command(s.id,cmd('retry'));result=await settled(service,s.id);assert.equal(result.turns.length,2);assert.equal(calls,3);
});
test('answer, feedback and paused transcript survive reload; no formal evaluation fields',async()=>{
 let calls=0;const {service,directory}=await setup(async()=>++calls===1?output({blocks:[{type:'question',mode:'practice',prompt:'3/4 的一半是多少？',referenceAnswer:'3/8'}],suggestions:[]}):output());
 const s=await service.create();await service.command(s.id,cmd('practice_request'));let result=await settled(service,s.id);const q=result.turns[1].blocks[0];
 await service.command(s.id,cmd('answer',{questionId:q.id,text:'我算 3/8，因为再分成2份'}));await settled(service,s.id);await service.command(s.id,cmd('end'));
 const persisted=JSON.parse(await readFile(path.join(directory,`${s.id}.json`),'utf8'));assert.equal(persisted.phase,'ended');assert.equal(persisted.turns[1].blocks[0].answer,'我算 3/8，因为再分成2份');assert.ok(!('belief' in persisted));
 const restored=createLiveService({directory,model:'test-only',provider:async()=>output()});result=await restored.get(s.id);assert.ok(!JSON.stringify(result).includes('referenceAnswer'));await restored.command(s.id,cmd('resume'));assert.equal((await restored.get(s.id)).phase,'learning');
});
test('safe allowlist rejects executable blocks, invalid diagrams and multiple questions',()=>{
 assert.throws(()=>validateOutput({blocks:[{type:'html',html:'<script>...</script>'}],suggestions:[]}));
 assert.throws(()=>validateOutput({blocks:[{type:'bars',caption:'图',rows:[{label:'甲',value:-2}]}],suggestions:[]}));
 const q={type:'question',mode:'practice',prompt:'1+1',referenceAnswer:'2'};assert.throws(()=>validateOutput({blocks:[q,q],suggestions:[]}));
});

test('page context is bounded, preserves user input and never imports sample assessment',async()=>{
 let messages;
 const {service}=await setup(async context=>{messages=context;return output();});
 const s=await service.create();
 await assert.rejects(service.command(s.id,cmd('message',{text:'这是什么意思',context:{page:'status',label:'你已经掌握所有知识'}})),/页面上下文/);
 await service.command(s.id,cmd('message',{text:'这是什么意思',context:{page:'status',label:'学习情况',belief:'fabricated'}}));
 const result=await settled(service,s.id);
 assert.equal(result.turns[0].text,'这是什么意思');
 assert.deepEqual(result.turns[0].context,{page:'status',label:'学习情况'});
 assert.match(messages.at(-1).content,/不代表学习表现/);
 assert.ok(!JSON.stringify(messages).includes('fabricated'));
});

test('creation replay preserves the same session and refuses a different course',async()=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),'deermind-next-create-'));
 const service=createLiveService({directory,model:'test-only',provider:async()=>output()});
 const scope={space:'course-a',label:'测试课程 A'},requestId=randomUUID();
 const first=await service.create(scope,requestId),second=await service.create(scope,requestId);
 assert.equal(first.id,second.id);
 await assert.rejects(service.create({space:'course-b',label:'测试课程 B'},requestId),/不能改用/);
 await service.create({space:'course-b',label:'测试课程 B'});
 assert.deepEqual((await service.list('course-a')).map(s=>s.id),[first.id]);
 assert.equal((await service.list('course-b')).length,1);
 first.scope.space='modified-by-caller';
 assert.equal((await service.get(first.id)).scope.space,'course-a');
});

test('ending a pending conversation immediately preserves input and rejects a late reply',async()=>{
 let resolve;
 const {service}=await setup(()=>new Promise(r=>resolve=r));
 const session=await service.create();
 await service.command(session.id,cmd('message',{text:'结束前的输入'}));
 const ended=await service.command(session.id,cmd('end'));
 assert.equal(ended.phase,'ended');assert.equal(ended.pending,null);
 resolve(output({blocks:[{type:'text',text:'过时回复'}],suggestions:[]}));
 await new Promise(r=>setTimeout(r,20));
 const state=await service.get(session.id);
 assert.equal(state.turns.length,2);assert.equal(state.turns[0].text,'结束前的输入');
 assert.ok(!JSON.stringify(state).includes('过时回复'));
 assert.ok(state.revision>session.revision);
});

test('V2 teaching blocks survive validation without adding learner state fields',()=>{
 const result=validateOutput({activity:{mode:'lecture',phase:'example',title:'比较两个量',mastery:100},
  blocks:[{type:'phase-marker',phase:'example',label:'看一个例子'},
   {type:'summary',title:'这一段',points:['同一单位才能比较']},
   {type:'progress',label:'本次讲解步骤',current:1,total:3}],suggestions:['继续']});
 assert.equal(result.blocks.length,3);assert.equal(result.activity.phase,'example');
 assert.ok(!('mastery' in result.activity));
 assert.throws(()=>validateOutput({blocks:[{type:'progress',label:'步骤',current:4,total:3}],suggestions:[]}));
});
