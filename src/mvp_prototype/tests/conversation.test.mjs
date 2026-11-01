import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {webcrypto} from 'node:crypto';
import vm from 'node:vm';
const require=createRequire(import.meta.url),ts=require('../student/node_modules/typescript'),api={};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../student/src/conversation.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports:api,Date,Intl,Set,crypto:webcrypto});
const course={id:'math',title:'数学',chapters:[{id:'c4-3',name:'比例的应用'}],activities:[],questions:[]};
const request={kind:'讲解',title:'增加量与总量',chapters:['c4-3'],text:'请讲解'};
test('switching and resuming append history and keep a single activity identity',()=>{
  const c=api.seedConversation(course);api.requestActivity(c,request);const a=c.currentId,before=JSON.stringify(c.messages);c.draft='未发送';
  api.requestActivity(c,{...request,title:'另一内容'});assert.equal(c.activities.find(x=>x.id===a).status,'已保留');assert.equal(JSON.stringify(c.messages.slice(0,3)),before);assert.equal(c.draft,'未发送');
  api.requestActivity(c,{...request,resumeId:a});assert.equal(c.currentId,a);assert.equal(c.activities.length,2);
  assert.equal(api.courseWithConversation(course,c).activities[0].id,a);
});
test('preparation can be cancelled without ending current teaching; switching an active check needs confirmation',()=>{
  const c=api.seedConversation(course);api.requestActivity(c,request);const a=c.currentId;
  api.requestActivity(c,{...request,kind:'检测'});assert.equal(c.currentId,a);c.offer=undefined;assert.equal(api.currentActivity(c).status,'进行中');
  api.requestActivity(c,{...request,kind:'检测'});api.beginCheck(c);const t=c.currentId;assert.notEqual(a,t);
  api.requestActivity(c,request);assert.equal(c.currentId,t);assert.ok(c.pending);api.confirmSwitch(c);assert.equal(c.activities.find(x=>x.id===t).status,'已结束');assert.equal(c.activities.find(x=>x.id===t).submitted,undefined);
});
test('help ends a check before explanation and does not submit the draft',()=>{
  const c=api.seedConversation(course);api.requestActivity(c,{...request,kind:'检测'});api.beginCheck(c);const t=c.currentId;c.draft='草稿';api.helpDuringCheck(c);
  assert.equal(c.activities.find(x=>x.id===t).submitted,undefined);assert.equal(c.draft,'草稿');assert.equal(api.currentActivity(c).kind,'答疑');
  const boundary=c.messages.findIndex(m=>m.text.includes('请求讲解，先结束检测'));
  const explanation=c.messages.findIndex(m=>m.text.includes('这题原有120本'));assert.ok(boundary<explanation);
});
test('quoting an ended check never reopens it; unknown answers are pending and not a mastery update',()=>{
  const c=api.seedConversation(course);api.requestActivity(c,{...request,kind:'检测'});api.beginCheck(c);const t=c.currentId;api.submitCheck(c,'120');
  c.referenceId=c.messages.find(m=>m.activityId===t&&m.role==='assistant').id;api.sendConversation(c,'继续上次进度',course);
  assert.equal(c.activities.find(x=>x.id===t).status,'已结束');assert.notEqual(c.currentId,t);
  const view=api.courseWithConversation(course,c);assert.equal(view.questions[0].attempts[0].result,'待判定');assert.equal(view.questions[0].attempts[0].help,'帮助情况未确认');assert.equal(view.chapters,course.chapters);
});
test('separate spaces do not share messages or drafts; finishing does not prevent later speech',()=>{
  const c=api.seedConversation(course),other=api.seedConversation({...course,id:'other'});api.requestActivity(c,request);api.finishActivity(c);api.sendConversation(c,'你好',course);c.draft='数学草稿';
  assert.equal(other.messages.length,0);assert.equal(other.draft,'');assert.ok(c.messages.at(-1).text.includes('我在'));assert.equal(c.currentId,'');
});
