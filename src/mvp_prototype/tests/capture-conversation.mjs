import assert from 'node:assert/strict';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {chromium,expect} from '@playwright/test';
import {createPrototypeServer} from '../scripts/serve.mjs';
const output=fileURLToPath(new URL('../../../doc/mvp/phase-4-product-and-domain-foundation/assets/product-interaction/conversation/',import.meta.url));
await mkdir(output,{recursive:true});
let completed=false,modelCalls=0;const errors=[],checks=[],captures=[];
const server=createPrototypeServer({directory:output,config:{key:'fixture',model:'fixed'},provider:async()=>{modelCalls++;throw Error('Mock only');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,channel:'msedge'}),context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN',timezoneId:'Asia/Shanghai'}),p=await context.newPage();
p.setDefaultTimeout(10000);p.on('pageerror',e=>errors.push(e.message));
const key='deermind-space-conversations-v1',btn=name=>p.getByRole('button',{name,exact:true}),nav=async name=>p.locator('.nav-items').getByRole('button',{name}).click();
const state=()=>p.evaluate(key=>JSON.parse(localStorage.getItem(key)||'{}')['math-6b'],key);
const input=()=>p.locator('.conversation-composer textarea');
async function send(text){await input().fill(text);await input().press('Enter');}
async function shot(id,title){const pane=await p.locator('.chat-pane').boundingBox(),chat=await p.locator('.continuous-chat').boundingBox();assert.ok(Math.abs(pane.width-chat.width)<=2,'conversation must fill its V2 pane');await p.evaluate(()=>document.fonts.ready);const img=await p.screenshot({path:output+'/'+id+'.png',animations:'disabled'});captures.push({id,title,file:id+'.png',route:new URL(p.url()).pathname+new URL(p.url()).search,viewport:p.viewportSize(),sha256:createHash('sha256').update(img).digest('hex')});console.log(id+' '+title);}
async function findHistory(text){await btn('历史').click();await p.getByLabel('搜索对话历史').fill(text);}
async function checkOffer(){await send('出一道题检测一下');await btn('开始检测').click();}
try{
  await p.goto(base+'/student/?preview=pages');await expect(p.getByRole('heading',{name:'首页',exact:true})).toBeVisible();
  const original=await state();await p.locator('.bar-input').fill('为什么增加四分之一还要加原量？');await p.locator('.bottom-input-bar').getByRole('button',{name:'发送',exact:true}).click();
  await expect(p.locator('.conversation-header')).toContainText('增加量与总量');await expect(p.locator('.home-page:visible')).toBeVisible();await expect(btn('结束 ×')).toHaveCount(0);
  assert.deepEqual((await state()).messages.slice(0,original.messages.length),original.messages);await shot('H01','从首页直接交流，旧记录保留');
  const firstId=(await state()).currentId;await input().fill('还没发送的草稿');await nav('教材');assert.equal((await state()).currentId,firstId);await p.locator('.textbook-page:visible').getByLabel('查找章节',{exact:true}).fill('圆柱的表面积');await shot('H02','浏览其他章节不切换当前活动');
  await btn('讲解').click();await expect(p.locator('.conversation-header')).toContainText('圆柱的表面积');assert.equal((await state()).activities.find(a=>a.id===firstId).status,'已保留');await expect(input()).toHaveValue('还没发送的草稿');await shot('H03','明确请求后切换讲解，保留旧进度和草稿');
  const secondId=(await state()).currentId;await findHistory('图里的原长');await shot('H04','按内容查找历史');const old=(await state()).messages.find(m=>m.activityId==='DEMO-L2'&&m.role==='assistant');await p.locator(`[data-result-id="${old.id}"]`).click();assert.equal((await state()).currentId,secondId);await shot('H05','定位原消息，当前活动不变');
  await p.locator(`[data-message-id="${old.id}"]`).getByRole('button',{name:'接着聊',exact:true}).click();await expect(input()).toHaveValue('还没发送的草稿');await expect(p.locator('.composer-reference')).toContainText('从图中找出');await shot('H06','引用旧内容回到最新位置，保留草稿');
  await btn('取消引用').click();await expect(input()).toHaveValue('还没发送的草稿');assert.equal((await state()).referenceId,'');await p.locator(`[data-message-id="${old.id}"]`).getByRole('button',{name:'接着聊',exact:true}).click();await send('继续上次进度');assert.equal((await state()).currentId,'DEMO-L2');assert.equal((await state()).activities.filter(a=>a.id==='DEMO-L2').length,1);await shot('H07','跨日续学追加到末尾，不复制活动');
  checks.push('自然输入与页面按钮追加同一时间线；浏览不切换；明确切换保留进度；草稿和跨日活动身份保留');
  await findHistory('说明数量关系');const ended=(await state()).messages.find(m=>m.activityId==='DEMO-T2'&&m.role==='assistant');await p.locator(`[data-result-id="${ended.id}"]`).click();await p.locator(`[data-message-id="${ended.id}"]`).getByRole('button',{name:'接着聊',exact:true}).click();await send('这里的图怎么理解？');assert.equal((await state()).activities.find(a=>a.id==='DEMO-T2').status,'已结束');assert.notEqual((await state()).currentId,'DEMO-T2');await shot('H08','追问已结束检测，原检测不重新开放');
  await send('出一道题检测一下');await shot('H09','先说明检测安排，再由学生开始');await btn('开始检测').click();await expect(input()).toHaveAttribute('aria-label','答案和理由');const testId=(await state()).currentId;await shot('H10','检测题内嵌，底部统一作答');await findHistory('图里的原长');await send('我先看一下旧记录');assert.equal((await state()).currentId,testId);assert.equal((await state()).activities.find(a=>a.id===testId).submitted,undefined);
  await input().fill('还没提交的答案');await btn('讲解').click();await expect(p.getByRole('dialog',{name:'切换学习内容'})).toBeVisible();assert.equal((await state()).currentId,testId);await shot('H11','检测中切换内容先说明后果');await btn('继续检测').click();assert.equal((await state()).activities.find(a=>a.id===testId).status,'进行中');await expect(input()).toHaveValue('还没提交的答案');
  await btn('讲解').click();await btn('结束检测并切换').click();assert.equal((await state()).activities.find(a=>a.id===testId).status,'已结束');assert.equal((await state()).activities.find(a=>a.id===testId).submitted,undefined);await shot('H12','结束检测后切换，未提交不计错');
  await checkOffer();const helpId=(await state()).currentId;await input().fill('我算到一半的草稿');await btn('求助并结束检测').click();assert.equal((await state()).activities.find(a=>a.id===helpId).status,'已结束');assert.equal((await state()).activities.find(a=>a.id===helpId).submitted,undefined);await expect(input()).toHaveValue('我算到一半的草稿');await shot('H13','求助先结束检测，草稿不变成正式答案');
  await checkOffer();const answerId=(await state()).currentId;await p.locator('.mock-examples summary').click();await btn('填入示例作答').click();await btn('提交答案').click();assert.equal((await state()).activities.find(a=>a.id===answerId).status,'已结束');await expect(input()).toBeEnabled();await shot('H14','检测结束后仍可交流，反馈不等于持久掌握');
  checks.push('已结束检测不复活；准备与开始分开；切换可取消；求助先结束；草稿不算作答；反馈后输入仍可用');
  await findHistory('');await btn('筛选').click();await p.getByLabel('开始日期',{exact:true}).fill('2026-10-27');await p.getByLabel('结束日期',{exact:true}).fill('2026-10-27');await p.getByLabel('历史活动类型',{exact:true}).selectOption('检测');await p.getByLabel('历史章节',{exact:true}).selectOption('c4-3');await expect(p.locator('.history-result')).toHaveCount(6);await shot('H15','日期章节类型组合查找');await p.getByLabel('搜索对话历史').fill('不存在的搜索片段');await expect(p.locator('.history-results')).toContainText('没有找到');await btn('清除条件').click();await btn('回到最新').click();
  await input().fill('数学空间的草稿');const beforeSwitch=await state();await p.locator('.space-trigger').click();await p.getByRole('button',{name:/语文·六下/}).click();await p.locator('.bottom-input-bar .expand-btn').click();await expect(p.locator('.conversation-messages')).not.toContainText('增加量');await send('你好');await shot('H16','另一空间独立交流，不借用数学历史');
  await p.locator('.space-trigger').click();await p.getByRole('button',{name:/数学·六下/}).click();await expect(p.locator('.bar-input')).toHaveValue('数学空间的草稿');assert.equal((await state()).messages.length,beforeSwitch.messages.length);await p.reload();await expect(p.locator('.bar-input')).toHaveValue('数学空间的草稿');await p.locator('.bottom-input-bar .expand-btn').click();await shot('H17','刷新后恢复本空间记录与未发送草稿');
  await p.setViewportSize({width:1024,height:768});await shot('H18','平板仍保留左侧对话和右侧页面');assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await p.locator('textarea:visible').count(),1);await btn('▼ 收起').click();await expect(input()).toHaveValue('数学空间的草稿');await btn('▲ 展开').click();
  await checkOffer();const spaceTest=(await state()).currentId;await p.locator('.space-trigger').click();await p.getByRole('button',{name:/语文·六下/}).click();await expect(p.getByRole('dialog',{name:'切换学习空间'})).toBeVisible();await btn('继续检测').click();assert.equal((await state()).currentId,spaceTest);await p.locator('.space-trigger').click();await p.getByRole('button',{name:/语文·六下/}).click();await btn('结束检测并切换空间').click();assert.equal((await state()).activities.find(a=>a.id===spaceTest).status,'已结束');
  checks.push('日期章节类型搜索及空结果；按空间隔离消息和草稿；刷新恢复；平板唯一输入；切换空间先收束检测');
  assert.deepEqual(errors,[]);assert.equal(modelCalls,0);completed=true;
}catch(e){await p.screenshot({path:output+'/failure.png'});throw e;}
finally{
  const sourceHashes={};for(const file of ['student/src/App.vue','student/src/conversation.ts','student/src/components/ConversationPane.vue','student/src/components/StudentPages.vue','student/src/components/HomePage.vue','tests/capture-conversation.mjs'])sourceHashes[file]=createHash('sha256').update(await readFile(new URL('../'+file,import.meta.url))).digest('hex');
  await writeFile(output+'/capture-manifest.json',JSON.stringify({completed,sourceCommit:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),sourceHashes,studentBuildHash:createHash('sha256').update(await readFile(new URL('../student/dist/index.html',import.meta.url))).digest('hex'),checks,captures,errors,modelCalls},null,2)+'\n');await browser.close();await new Promise(r=>server.close(r));
}
